# scripts/apply_v121_fixes.py
from pathlib import Path

print("[*] Applying v1.2.1 critical fixes...")

# 1. Fix video_player.hpp
vp_hpp_path = Path("downloader/include/ui/video_player.hpp")
vp_hpp = vp_hpp_path.read_text(encoding="utf-8")
vp_hpp = vp_hpp.replace(
    "bool isPlaying() const { return m_isOpen; }",
    "bool isPlaying() const { return m_isOpen && m_hasDecodedFirstFrame; }"
)
vp_hpp_path.write_text(vp_hpp, encoding="utf-8")
print("[+] Patched video_player.hpp (isPlaying check)")

# 2. Fix video_player.cpp
vp_cpp_path = Path("downloader/src/ui/video_player.cpp")
vp_cpp = vp_cpp_path.read_text(encoding="utf-8")

# Fix avioSeekPacket to mask flags and use fseeko/ftello
old_seek = """static int64_t avioSeekPacket(void* opaque, int64_t offset, int whence) {
    FILE* f = static_cast<FILE*>(opaque);
    if (!f) return -1;

    if (whence == AVSEEK_SIZE) {
        // Return file size without changing position
        long current = ftell(f);
        if (fseek(f, 0, SEEK_END) != 0) return -1;
        long size = ftell(f);
        fseek(f, current, SEEK_SET);
        return static_cast<int64_t>(size);
    }

    int fseek_whence = SEEK_SET;
    if (whence == SEEK_CUR) fseek_whence = SEEK_CUR;
    else if (whence == SEEK_END) fseek_whence = SEEK_END;
    else if (whence == SEEK_SET) fseek_whence = SEEK_SET;

    if (fseek(f, static_cast<long>(offset), fseek_whence) != 0) {
        return -1;
    }
    return static_cast<int64_t>(ftell(f));
}"""

new_seek = """static int64_t avioSeekPacket(void* opaque, int64_t offset, int whence) {
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
}"""

vp_cpp = vp_cpp.replace(old_seek, new_seek)

# Fix open() to close and return false if first frame cannot be decoded (prevents black screen)
old_first_frame = """    // Immediately decode the first frame so the texture is immediately ready for display
    int attempts = 0;
    while (attempts < 60 && !m_hasDecodedFirstFrame) {
        attempts++;
        int ret = av_read_frame(m_formatCtx, m_packet);
        if (ret < 0) break;

        if (m_packet->stream_index == m_videoStream) {
            if (avcodec_send_packet(m_codecCtx, m_packet) == 0) {
                if (avcodec_receive_frame(m_codecCtx, m_frame) == 0) {
                    sws_scale(m_swsCtx, static_cast<const uint8_t* const*>(m_frame->data),
                              m_frame->linesize, 0, m_height,
                              m_frameRGB->data, m_frameRGB->linesize);

                    SDL_UpdateTexture(m_texture, nullptr, m_frameRGB->data[0], m_frameRGB->linesize[0]);
                    m_hasDecodedFirstFrame = true;
                }
            }
        }
        av_packet_unref(m_packet);
    }

    return true;"""

new_first_frame = """    // Immediately decode the first frame so the texture is immediately ready for display
    int attempts = 0;
    while (attempts < 80 && !m_hasDecodedFirstFrame) {
        attempts++;
        int ret = av_read_frame(m_formatCtx, m_packet);
        if (ret < 0) break;

        if (m_packet->stream_index == m_videoStream) {
            if (avcodec_send_packet(m_codecCtx, m_packet) == 0) {
                while (avcodec_receive_frame(m_codecCtx, m_frame) == 0) {
                    sws_scale(m_swsCtx, static_cast<const uint8_t* const*>(m_frame->data),
                              m_frame->linesize, 0, m_height,
                              m_frameRGB->data, m_frameRGB->linesize);

                    SDL_UpdateTexture(m_texture, nullptr, m_frameRGB->data[0], m_frameRGB->linesize[0]);
                    m_hasDecodedFirstFrame = true;
                    break;
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

    return true;"""

vp_cpp = vp_cpp.replace(old_first_frame, new_first_frame)

# Fix update() loop
old_update = """    int attempts = 0;
    while (attempts < 60) {
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
    }"""

new_update = """    bool frameDecoded = false;
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
                    sws_scale(m_swsCtx, static_cast<const uint8_t* const*>(m_frame->data),
                              m_frame->linesize, 0, m_height,
                              m_frameRGB->data, m_frameRGB->linesize);

                    SDL_UpdateTexture(m_texture, nullptr, m_frameRGB->data[0], m_frameRGB->linesize[0]);
                    frameDecoded = true;
                    m_hasDecodedFirstFrame = true;
                    break;
                }
            }
        }
        av_packet_unref(m_packet);
    }"""

vp_cpp = vp_cpp.replace(old_update, new_update)
vp_cpp_path.write_text(vp_cpp, encoding="utf-8")
print("[+] Patched video_player.cpp (decode validation & seamless loop)")

# 3. Fix switch_platform.cpp (CURLOPT_COOKIEFILE and stall timeouts)
sw_cpp_path = Path("downloader/src/platform/switch_platform.cpp")
sw_cpp = sw_cpp_path.read_text(encoding="utf-8")

old_curl_opts = """        curl_easy_setopt(curl, CURLOPT_BUFFERSIZE, 256 * 1024L); // 256 KB curl receive buffer
        curl_easy_setopt(curl, CURLOPT_TCP_NODELAY, 1L);         // Disable Nagle algorithm
        curl_easy_setopt(curl, CURLOPT_TCP_KEEPALIVE, 1L);"""

new_curl_opts = """        curl_easy_setopt(curl, CURLOPT_BUFFERSIZE, 256 * 1024L); // 256 KB curl receive buffer
        curl_easy_setopt(curl, CURLOPT_TCP_NODELAY, 1L);         // Disable Nagle algorithm
        curl_easy_setopt(curl, CURLOPT_TCP_KEEPALIVE, 1L);
        curl_easy_setopt(curl, CURLOPT_COOKIEFILE, "");          // Enable cookie engine for Google Drive redirects
        curl_easy_setopt(curl, CURLOPT_LOW_SPEED_LIMIT, 1024L);  // 1 KB/s minimum
        curl_easy_setopt(curl, CURLOPT_LOW_SPEED_TIME, 10L);     // 10s stall timeout"""

sw_cpp = sw_cpp.replace(old_curl_opts, new_curl_opts)
sw_cpp_path.write_text(sw_cpp, encoding="utf-8")
print("[+] Patched switch_platform.cpp (CURL Google Drive cookies & stall protection)")

# 4. Bump version in config.hpp
cfg_path = Path("downloader/include/core/config.hpp")
cfg = cfg_path.read_text(encoding="utf-8")
cfg = cfg.replace('APP_VERSION = "1.2.0"', 'APP_VERSION = "1.2.1"')
cfg_path.write_text(cfg, encoding="utf-8")
print("[+] Bumped config.hpp to v1.2.1")

# 5. Bump version in version.json
ver_path = Path("version.json")
ver_path.write_text("""{
  "latestVersion": "1.2.1",
  "minRequiredVersion": "1.0.0",
  "downloadUrl": "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-Backgrounds.nro",
  "releaseNotes": "Fix Plus (+) recordings browser trigger, robust video buffer with Drive cookie support, all 6 NFS Most Wanted variants"
}
""", encoding="utf-8")
print("[+] Bumped version.json to v1.2.1")
