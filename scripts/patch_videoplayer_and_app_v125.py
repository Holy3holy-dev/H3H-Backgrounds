import re
from pathlib import Path

# 1. Patch video_player.hpp
vp_hpp = Path('downloader/include/ui/video_player.hpp')
text_hpp = vp_hpp.read_text(encoding='utf-8')
if 'm_targetWidth' not in text_hpp:
    text_hpp = text_hpp.replace(
        'int m_width{0};\n    int m_height{0};',
        'int m_width{0};\n    int m_height{0};\n    int m_targetWidth{1280};\n    int m_targetHeight{720};'
    )
    if 'm_targetWidth' not in text_hpp:
        # Try CRLF
        text_hpp = text_hpp.replace(
            'int m_width{0};\r\n    int m_height{0};',
            'int m_width{0};\r\n    int m_height{0};\r\n    int m_targetWidth{1280};\r\n    int m_targetHeight{720};'
        )
    vp_hpp.write_text(text_hpp, encoding='utf-8')
    print('[+] Patched video_player.hpp')
else:
    print('[*] video_player.hpp already contains m_targetWidth')

# 2. Patch video_player.cpp
vp_cpp = Path('downloader/src/ui/video_player.cpp')
text_cpp = vp_cpp.read_text(encoding='utf-8')

# Remove m_rgbBuffer and m_frameRGB from close()
text_cpp = re.sub(
    r'if\s*\(m_rgbBuffer\)\s*\{[^}]*\}\s*if\s*\(m_frameRGB\)\s*\{[^}]*\}',
    '',
    text_cpp
)

# Standardize line endings temporarily for reliable matching
is_crlf = '\r\n' in text_cpp
if is_crlf:
    text_cpp = text_cpp.replace('\r\n', '\n')

old_open_target = '''    // Multithreaded decoding for smooth 30-60 fps on Cortex-A57
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
    }'''

new_open_replacement = '''    // Multithreaded decoding for smooth 30-60 fps on Cortex-A57
    m_codecCtx->thread_count = 3;
    m_codecCtx->thread_type = FF_THREAD_SLICE | FF_THREAD_FRAME;

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

    // Always downscale to native Switch handheld/docked target 1280x720 to conserve VRAM & CPU
    m_targetWidth = (m_width > 1280 || m_height > 720) ? 1280 : m_width;
    m_targetHeight = (m_width > 1280 || m_height > 720) ? 720 : m_height;

    AVRational rate = m_formatCtx->streams[m_videoStream]->r_frame_rate;
    if (rate.den > 0 && rate.num > 0) {
        m_fps = static_cast<double>(rate.num) / static_cast<double>(rate.den);
    } else {
        m_fps = 30.0;
    }
    m_frameIntervalMs = static_cast<int64_t>(1000.0 / (m_fps > 0 ? m_fps : 30.0));

    m_frame = av_frame_alloc();
    m_packet = av_packet_alloc();
    if (!m_frame || !m_packet) {
        close();
        return false;
    }

    m_swsCtx = sws_getContext(m_width, m_height, m_codecCtx->pix_fmt,
                              m_targetWidth, m_targetHeight, AV_PIX_FMT_RGBA,
                              SWS_FAST_BILINEAR, nullptr, nullptr, nullptr);
    if (!m_swsCtx) {
        close();
        return false;
    }

    m_texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA32,
                                  SDL_TEXTUREACCESS_STREAMING, m_targetWidth, m_targetHeight);
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
    int totalPackets = 0;
    int videoPackets = 0;
    while (totalPackets < 350 && videoPackets < 100 && !m_hasDecodedFirstFrame) {
        totalPackets++;
        int ret = av_read_frame(m_formatCtx, m_packet);
        if (ret < 0) break;

        if (m_packet->stream_index == m_videoStream) {
            videoPackets++;
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
    }'''

assert old_open_target in text_cpp, "old_open_target not found in video_player.cpp"
text_cpp = text_cpp.replace(old_open_target, new_open_replacement)

old_update = '''void VideoPlayer::update() {
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
}'''

new_update = '''void VideoPlayer::update() {
    if (!m_isOpen || !m_formatCtx || !m_codecCtx) return;

    uint32_t now = SDL_GetTicks();
    if (now - m_lastFrameTime < static_cast<uint32_t>(m_frameIntervalMs)) {
        return;
    }
    m_lastFrameTime = now;

    // Check if a frame is already decoded in codec buffers
    bool frameDecoded = false;
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

    if (frameDecoded) return;

    int totalPackets = 0;
    while (totalPackets < 200 && !frameDecoded) {
        totalPackets++;
        int ret = av_read_frame(m_formatCtx, m_packet);
        if (ret < 0) {
            // EOF reached: seek back to beginning for seamless loop
            av_seek_frame(m_formatCtx, m_videoStream, 0, AVSEEK_FLAG_BACKWARD);
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
}'''

assert old_update in text_cpp, "old_update not found in video_player.cpp"
text_cpp = text_cpp.replace(old_update, new_update)

if is_crlf:
    text_cpp = text_cpp.replace('\n', '\r\n')

vp_cpp.write_text(text_cpp, encoding='utf-8')
print('[+] Patched video_player.cpp')

# 3. Patch app.cpp
app_cpp = Path('downloader/src/ui/app.cpp')
text_app = app_cpp.read_text(encoding='utf-8')
is_crlf_app = '\r\n' in text_app
if is_crlf_app:
    text_app = text_app.replace('\r\n', '\n')

# Patch thumbFile deletion in app.cpp
old_cache_fail = '''        if (cachedSz > 50000) {
            if (!m_videoPlayer.open(vidFile, m_renderer)) {
                // Corrupted cache -> purge so it can redownload cleanly
                std::filesystem::remove(vidFile, ec);
                std::filesystem::remove(thumbFile, ec);
            }
        }'''

new_cache_fail = '''        if (cachedSz > 50000) {
            if (!m_videoPlayer.open(vidFile, m_renderer)) {
                // Video failed to open: purge only the bad video; keep thumbnail intact!
                std::filesystem::remove(vidFile, ec);
            }
        }'''

assert old_cache_fail in text_app, "old_cache_fail not found in app.cpp"
text_app = text_app.replace(old_cache_fail, new_cache_fail)

# Patch empty canvas in renderPreview to display informative status
old_canvas = '''    } else {
        // Fallback canvas with subtle Cyber-Glass animated glow
        drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x08, 0x0C, 0x14, 0xFF});
        drawNeonGradientOutline(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, 3);
    }'''

new_canvas = '''    } else {
        // Fallback canvas with subtle Cyber-Glass animated glow
        drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x08, 0x0C, 0x14, 0xFF});
        drawNeonGradientOutline(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, 3);

        // Informative center status card so screen is NEVER an empty black box
        int badgeW = 460;
        int badgeH = 80;
        int badgeX = (Theme::SCREEN_WIDTH - badgeW) / 2;
        int badgeY = (Theme::SCREEN_HEIGHT - badgeH) / 2;
        drawRect(badgeX, badgeY, badgeW, badgeH, {0x0F, 0x17, 0x2A, 0xEE});
        drawRectOutline(badgeX, badgeY, badgeW, badgeH, Theme::COLOR_CYAN, 1);

        if (m_previewLoading || m_videoDownloading) {
            int dotCount = (SDL_GetTicks() / 350) % 4;
            std::string dots = std::string(dotCount, '.');
            drawText("Загрузка видеофона" + dots, badgeX + 30, badgeY + 28, Theme::COLOR_TEXT, 16);
        } else {
            drawText("Видеофон недоступен", badgeX + 30, badgeY + 20, Theme::COLOR_TEXT, 16);
            drawText("Нажмите B для возврата или выберите другой вариант", badgeX + 30, badgeY + 48, Theme::COLOR_TEXT_MUTED, 12);
        }
    }'''

assert old_canvas in text_app, "old_canvas not found in app.cpp"
text_app = text_app.replace(old_canvas, new_canvas)

if is_crlf_app:
    text_app = text_app.replace('\n', '\r\n')

app_cpp.write_text(text_app, encoding='utf-8')
print('[+] Patched app.cpp')
print('[+] All C++ UI patches applied successfully!')
