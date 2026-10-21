#include "ui/video_player.hpp"
#include <iostream>

#ifdef HAS_SDL2

namespace h3h {
namespace ui {

namespace {

// Custom AVIO read packet callback wrapping standard C fread
static int avioReadPacket(void* opaque, uint8_t* buf, int buf_size) {
    FILE* f = static_cast<FILE*>(opaque);
    if (!f) return AVERROR_EOF;
    size_t r = fread(buf, 1, static_cast<size_t>(buf_size), f);
    if (r == 0) {
        if (feof(f)) return AVERROR_EOF;
        return AVERROR(EIO);
    }
    return static_cast<int>(r);
}

// Custom AVIO seek packet callback wrapping standard C fseek/ftell
static int64_t avioSeekPacket(void* opaque, int64_t offset, int whence) {
    FILE* f = static_cast<FILE*>(opaque);
    if (!f) return -1;

    // Mask out FFmpeg flags like AVSEEK_FORCE (0x20000)
    int cleanWhence = whence & ~0x20000;

    if (cleanWhence == AVSEEK_SIZE) {
        long current = ftell(f);
        if (fseek(f, 0, SEEK_END) != 0) return -1;
        long size = ftell(f);
        fseek(f, current, SEEK_SET);
        return static_cast<int64_t>(size);
    }

    int fseek_whence = SEEK_SET;
    if (cleanWhence == SEEK_CUR) fseek_whence = SEEK_CUR;
    else if (cleanWhence == SEEK_END) fseek_whence = SEEK_END;
    else if (cleanWhence == SEEK_SET) fseek_whence = SEEK_SET;

    if (fseek(f, static_cast<long>(offset), fseek_whence) != 0) {
        return -1;
    }
    return static_cast<int64_t>(ftell(f));
}

} // anonymous namespace

VideoPlayer::VideoPlayer() {}

VideoPlayer::~VideoPlayer() {
    close();
}

void VideoPlayer::close() {
    if (m_texture) {
        SDL_DestroyTexture(m_texture);
        m_texture = nullptr;
    }
    if (m_rgbBuffer) {
        av_free(m_rgbBuffer);
        m_rgbBuffer = nullptr;
    }
    if (m_frameRGB) {
        av_frame_free(&m_frameRGB);
        m_frameRGB = nullptr;
    }
    if (m_frame) {
        av_frame_free(&m_frame);
        m_frame = nullptr;
    }
    if (m_packet) {
        av_packet_free(&m_packet);
        m_packet = nullptr;
    }
    if (m_swsCtx) {
        sws_freeContext(m_swsCtx);
        m_swsCtx = nullptr;
    }
    if (m_codecCtx) {
        avcodec_free_context(&m_codecCtx);
        m_codecCtx = nullptr;
    }
    if (m_formatCtx) {
        avformat_close_input(&m_formatCtx);
        m_formatCtx = nullptr;
    }
    if (m_avioCtx) {
        // avio_context_free frees both m_avioCtx and the buffer allocated with av_malloc
        avio_context_free(&m_avioCtx);
        m_avioCtx = nullptr;
        m_avioBuffer = nullptr;
    } else if (m_avioBuffer) {
        av_freep(&m_avioBuffer);
        m_avioBuffer = nullptr;
    }
    if (m_fileHandle) {
        fclose(m_fileHandle);
        m_fileHandle = nullptr;
    }

    m_videoStream = -1;
    m_isOpen = false;
    m_hasDecodedFirstFrame = false;
    m_filepath.clear();
}

bool VideoPlayer::open(const std::string& filepath, SDL_Renderer* renderer) {
    close();

    if (!renderer || filepath.empty()) return false;

    // Open file using standard C fopen - works cleanly across devkitPro libnx devoptab (sdmc:/...)
    m_fileHandle = fopen(filepath.c_str(), "rb");
    if (!m_fileHandle) {
        std::cerr << "[VideoPlayer] Failed to fopen: " << filepath << std::endl;
        return false;
    }

    constexpr size_t AVIO_BUFFER_SIZE = 64 * 1024;
    m_avioBuffer = static_cast<uint8_t*>(av_malloc(AVIO_BUFFER_SIZE));
    if (!m_avioBuffer) {
        close();
        return false;
    }

    m_avioCtx = avio_alloc_context(
        m_avioBuffer,
        AVIO_BUFFER_SIZE,
        0, // read-only
        m_fileHandle,
        &avioReadPacket,
        nullptr,
        &avioSeekPacket
    );
    if (!m_avioCtx) {
        close();
        return false;
    }

    m_formatCtx = avformat_alloc_context();
    if (!m_formatCtx) {
        close();
        return false;
    }

    m_formatCtx->pb = m_avioCtx;
    m_formatCtx->flags |= AVFMT_FLAG_CUSTOM_IO;

    // Use a generic mp4 extension hint so FFmpeg does not attempt protocol resolution on "sdmc:/"
    if (avformat_open_input(&m_formatCtx, "", nullptr, nullptr) != 0) {
        std::cerr << "[VideoPlayer] avformat_open_input failed with custom AVIO for: " << filepath << std::endl;
        close();
        return false;
    }

    if (avformat_find_stream_info(m_formatCtx, nullptr) < 0) {
        std::cerr << "[VideoPlayer] avformat_find_stream_info failed for: " << filepath << std::endl;
        close();
        return false;
    }

    m_videoStream = -1;
    for (unsigned int i = 0; i < m_formatCtx->nb_streams; ++i) {
        if (m_formatCtx->streams[i]->codecpar->codec_type == AVMEDIA_TYPE_VIDEO) {
            m_videoStream = static_cast<int>(i);
            break;
        }
    }

    if (m_videoStream == -1) {
        close();
        return false;
    }

    AVCodecParameters* codecPar = m_formatCtx->streams[m_videoStream]->codecpar;
    const AVCodec* codec = avcodec_find_decoder(codecPar->codec_id);
    if (!codec) {
        close();
        return false;
    }

    m_codecCtx = avcodec_alloc_context3(codec);
    if (!m_codecCtx) {
        close();
        return false;
    }

    if (avcodec_parameters_to_context(m_codecCtx, codecPar) < 0) {
        close();
        return false;
    }

    // Multithreaded decoding for smooth 30-60 fps on Cortex-A57
    m_codecCtx->thread_count = 2;
    m_codecCtx->thread_type = FF_THREAD_FRAME | FF_THREAD_SLICE;

    if (avcodec_open2(m_codecCtx, codec, nullptr) < 0) {
        close();
        return false;
    }

    m_width = m_codecCtx->width;
    m_height = m_codecCtx->height;
    if (m_width <= 0 || m_height <= 0) {
        close();
        return false;
    }

    AVRational rate = m_formatCtx->streams[m_videoStream]->r_frame_rate;
    if (rate.den > 0 && rate.num > 0) {
        m_fps = static_cast<double>(rate.num) / static_cast<double>(rate.den);
    } else {
        m_fps = 30.0;
    }
    m_frameIntervalMs = static_cast<int64_t>(1000.0 / (m_fps > 0 ? m_fps : 30.0));

    m_frame = av_frame_alloc();
    m_frameRGB = av_frame_alloc();
    m_packet = av_packet_alloc();
    if (!m_frame || !m_frameRGB || !m_packet) {
        close();
        return false;
    }

    int numBytes = av_image_get_buffer_size(AV_PIX_FMT_RGBA, m_width, m_height, 1);
    m_rgbBuffer = static_cast<uint8_t*>(av_malloc(numBytes * sizeof(uint8_t)));
    if (!m_rgbBuffer) {
        close();
        return false;
    }

    av_image_fill_arrays(m_frameRGB->data, m_frameRGB->linesize, m_rgbBuffer,
                         AV_PIX_FMT_RGBA, m_width, m_height, 1);

    m_swsCtx = sws_getContext(m_width, m_height, m_codecCtx->pix_fmt,
                              m_width, m_height, AV_PIX_FMT_RGBA,
                              SWS_BILINEAR, nullptr, nullptr, nullptr);
    if (!m_swsCtx) {
        close();
        return false;
    }

    m_texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA32,
                                  SDL_TEXTUREACCESS_STREAMING, m_width, m_height);
    if (!m_texture) {
        close();
        return false;
    }
    // Disable alpha blending so video frames render at 100% full opacity, eliminating black transparent textures
    SDL_SetTextureBlendMode(m_texture, SDL_BLENDMODE_NONE);

    m_filepath = filepath;
    m_isOpen = true;
    m_hasDecodedFirstFrame = false;
    m_lastFrameTime = SDL_GetTicks();

    // Immediately decode the first frame so the texture is immediately ready for display
    int attempts = 0;
    while (attempts < 80 && !m_hasDecodedFirstFrame) {
        attempts++;
        int ret = av_read_frame(m_formatCtx, m_packet);
        if (ret < 0) break;

        if (m_packet->stream_index == m_videoStream) {
            if (avcodec_send_packet(m_codecCtx, m_packet) == 0) {
                while (avcodec_receive_frame(m_codecCtx, m_frame) == 0) {
                    void* pixels = nullptr;
                    int pitch = 0;
                    if (SDL_LockTexture(m_texture, nullptr, &pixels, &pitch) == 0) {
                        uint8_t* dstData[4] = { static_cast<uint8_t*>(pixels), nullptr, nullptr, nullptr };
                        int dstLinesize[4] = { pitch, 0, 0, 0 };
                        sws_scale(m_swsCtx, static_cast<const uint8_t* const*>(m_frame->data),
                                  m_frame->linesize, 0, m_height,
                                  dstData, dstLinesize);
                        SDL_UnlockTexture(m_texture);
                        m_hasDecodedFirstFrame = true;
                        break;
                    }
                }
            }
        }
        av_packet_unref(m_packet);
    }

    if (!m_hasDecodedFirstFrame) {
        // Could not decode video frame - close cleanly to avoid black texture render
        close();
        return false;
    }

    return true;
}

void VideoPlayer::update() {
    if (!m_isOpen || !m_formatCtx || !m_codecCtx) return;

    uint32_t now = SDL_GetTicks();
    if (now - m_lastFrameTime < static_cast<uint32_t>(m_frameIntervalMs)) {
        return;
    }
    m_lastFrameTime = now;

    bool frameDecoded = false;
    int attempts = 0;
    while (attempts < 80 && !frameDecoded) {
        attempts++;
        int ret = av_read_frame(m_formatCtx, m_packet);
        if (ret < 0) {
            // EOF reached: seek back to beginning for seamless loop
            av_seek_frame(m_formatCtx, -1, 0, AVSEEK_FLAG_BACKWARD);
            avcodec_flush_buffers(m_codecCtx);
            continue;
        }

        if (m_packet->stream_index == m_videoStream) {
            if (avcodec_send_packet(m_codecCtx, m_packet) == 0) {
                while (avcodec_receive_frame(m_codecCtx, m_frame) == 0) {
                    void* pixels = nullptr;
                    int pitch = 0;
                    if (SDL_LockTexture(m_texture, nullptr, &pixels, &pitch) == 0) {
                        uint8_t* dstData[4] = { static_cast<uint8_t*>(pixels), nullptr, nullptr, nullptr };
                        int dstLinesize[4] = { pitch, 0, 0, 0 };
                        sws_scale(m_swsCtx, static_cast<const uint8_t* const*>(m_frame->data),
                                  m_frame->linesize, 0, m_height,
                                  dstData, dstLinesize);
                        SDL_UnlockTexture(m_texture);
                        frameDecoded = true;
                        m_hasDecodedFirstFrame = true;
                        break;
                    }
                }
            }
        }
        av_packet_unref(m_packet);
    }
}

void VideoPlayer::render(SDL_Renderer* renderer, const SDL_Rect* dstRect) {
    if (m_isOpen && m_texture && renderer) {
        SDL_Rect fullScreen = {0, 0, 1280, 720};
        const SDL_Rect* r = dstRect ? dstRect : &fullScreen;
        SDL_RenderCopy(renderer, m_texture, nullptr, r);
    }
}

} // namespace ui
} // namespace h3h

#endif
