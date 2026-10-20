#include "ui/video_player.hpp"
#include <iostream>

#ifdef HAS_SDL2

namespace h3h {
namespace ui {

VideoPlayer::VideoPlayer() {}

VideoPlayer::~VideoPlayer() {
    close();
}

void VideoPlayer::close() {
    if (!m_isOpen) return;

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

    m_videoStream = -1;
    m_isOpen = false;
    m_filepath.clear();
}

bool VideoPlayer::open(const std::string& filepath, SDL_Renderer* renderer) {
    close();

    if (!renderer || filepath.empty()) return false;

    m_formatCtx = avformat_alloc_context();
    if (!m_formatCtx) return false;

    if (avformat_open_input(&m_formatCtx, filepath.c_str(), nullptr, nullptr) != 0) {
        close();
        return false;
    }

    if (avformat_find_stream_info(m_formatCtx, nullptr) < 0) {
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

    m_filepath = filepath;
    m_isOpen = true;
    m_lastFrameTime = SDL_GetTicks();
    return true;
}

void VideoPlayer::update() {
    if (!m_isOpen || !m_formatCtx || !m_codecCtx) return;

    uint32_t now = SDL_GetTicks();
    if (now - m_lastFrameTime < static_cast<uint32_t>(m_frameIntervalMs)) {
        return;
    }
    m_lastFrameTime = now;

    int attempts = 0;
    while (attempts < 10) {
        attempts++;
        int ret = av_read_frame(m_formatCtx, m_packet);
        if (ret < 0) {
            // EOF reached: seek back to beginning for seamless loop
            av_seek_frame(m_formatCtx, m_videoStream, 0, AVSEEK_FLAG_BACKWARD);
            avcodec_flush_buffers(m_codecCtx);
            continue;
        }

        if (m_packet->stream_index == m_videoStream) {
            if (avcodec_send_packet(m_codecCtx, m_packet) == 0) {
                if (avcodec_receive_frame(m_codecCtx, m_frame) == 0) {
                    sws_scale(m_swsCtx, static_cast<const uint8_t* const*>(m_frame->data),
                              m_frame->linesize, 0, m_height,
                              m_frameRGB->data, m_frameRGB->linesize);

                    SDL_UpdateTexture(m_texture, nullptr, m_frameRGB->data[0], m_frameRGB->linesize[0]);
                    av_packet_unref(m_packet);
                    break;
                }
            }
        }
        av_packet_unref(m_packet);
    }
}

void VideoPlayer::render(SDL_Renderer* renderer, const SDL_Rect* dstRect) {
    if (m_isOpen && m_texture && renderer) {
        SDL_RenderCopy(renderer, m_texture, nullptr, dstRect);
    }
}

} // namespace ui
} // namespace h3h

#endif
