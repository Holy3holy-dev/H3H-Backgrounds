import re
from pathlib import Path

# 1. Update config.hpp to 1.2.4
cfg_path = Path("downloader/include/core/config.hpp")
cfg_text = cfg_path.read_text(encoding="utf-8")
cfg_text = cfg_text.replace('APP_VERSION = "1.2.3";', 'APP_VERSION = "1.2.4";')
cfg_path.write_text(cfg_text, encoding="utf-8")
print("[+] config.hpp updated to 1.2.4")

# 2. Update version.json to 1.2.4
ver_path = Path("version.json")
ver_text = ver_path.read_text(encoding="utf-8")
ver_text = re.sub(r'"latestVersion":\s*"[^"]+"', '"latestVersion": "1.2.4"', ver_text)
ver_text = re.sub(r'"releaseNotes":\s*"[^"]+"', '"releaseNotes": "v1.2.4: Fix black screen on static preview and video via explicit SDL_Rect fullscreen coordinates, SDL_LockTexture direct GPU decode, and fopen/SDL_RWFromFP devoptab loading"', ver_text)
ver_path.write_text(ver_text, encoding="utf-8")
print("[+] version.json updated to 1.2.4")

# 3. Patch video_player.cpp
vp_path = Path("downloader/src/ui/video_player.cpp")
vp_text = vp_path.read_text(encoding="utf-8")

# Fix avformat_open_input to pass "" instead of "video.mp4"
vp_text = vp_text.replace(
    'if (avformat_open_input(&m_formatCtx, "video.mp4", nullptr, nullptr) != 0)',
    'if (avformat_open_input(&m_formatCtx, "", nullptr, nullptr) != 0)'
)

# Replace SDL_UpdateTexture with SDL_LockTexture / SDL_UnlockTexture in first frame decode
old_first_frame = """                    sws_scale(m_swsCtx, static_cast<const uint8_t* const*>(m_frame->data),
                              m_frame->linesize, 0, m_height,
                              m_frameRGB->data, m_frameRGB->linesize);

                    SDL_UpdateTexture(m_texture, nullptr, m_frameRGB->data[0], m_frameRGB->linesize[0]);
                    m_hasDecodedFirstFrame = true;
                    break;"""

new_first_frame = """                    void* pixels = nullptr;
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
                    }"""

if old_first_frame in vp_text:
    vp_text = vp_text.replace(old_first_frame, new_first_frame)
    print("[+] Replaced first frame SDL_UpdateTexture with SDL_LockTexture")
else:
    old_ff_crlf = old_first_frame.replace("\n", "\r\n")
    new_ff_crlf = new_first_frame.replace("\n", "\r\n")
    if old_ff_crlf in vp_text:
        vp_text = vp_text.replace(old_ff_crlf, new_ff_crlf)
        print("[+] Replaced first frame SDL_UpdateTexture with SDL_LockTexture (CRLF)")
    else:
        print("[-] Warning: old_first_frame not found")

# Replace SDL_UpdateTexture with SDL_LockTexture / SDL_UnlockTexture in update()
old_update_frame = """                    sws_scale(m_swsCtx, static_cast<const uint8_t* const*>(m_frame->data),
                              m_frame->linesize, 0, m_height,
                              m_frameRGB->data, m_frameRGB->linesize);

                    SDL_UpdateTexture(m_texture, nullptr, m_frameRGB->data[0], m_frameRGB->linesize[0]);
                    frameDecoded = true;
                    m_hasDecodedFirstFrame = true;
                    break;"""

new_update_frame = """                    void* pixels = nullptr;
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
                    }"""

if old_update_frame in vp_text:
    vp_text = vp_text.replace(old_update_frame, new_update_frame)
    print("[+] Replaced update() SDL_UpdateTexture with SDL_LockTexture")
else:
    old_uf_crlf = old_update_frame.replace("\n", "\r\n")
    new_uf_crlf = new_update_frame.replace("\n", "\r\n")
    if old_uf_crlf in vp_text:
        vp_text = vp_text.replace(old_uf_crlf, new_uf_crlf)
        print("[+] Replaced update() SDL_UpdateTexture with SDL_LockTexture (CRLF)")
    else:
        print("[-] Warning: old_update_frame not found")

# Update VideoPlayer::render to always use explicit fullscreen rectangle if dstRect is null
old_vp_render = """void VideoPlayer::render(SDL_Renderer* renderer, const SDL_Rect* dstRect) {
    if (m_isOpen && m_texture && renderer) {
        SDL_RenderCopy(renderer, m_texture, nullptr, dstRect);
    }
}"""

new_vp_render = """void VideoPlayer::render(SDL_Renderer* renderer, const SDL_Rect* dstRect) {
    if (m_isOpen && m_texture && renderer) {
        SDL_Rect fullScreen = {0, 0, 1280, 720};
        const SDL_Rect* r = dstRect ? dstRect : &fullScreen;
        SDL_RenderCopy(renderer, m_texture, nullptr, r);
    }
}"""

if old_vp_render in vp_text:
    vp_text = vp_text.replace(old_vp_render, new_vp_render)
    print("[+] VideoPlayer::render patched with explicit rectangle")
else:
    old_vr_crlf = old_vp_render.replace("\n", "\r\n")
    new_vr_crlf = new_vp_render.replace("\n", "\r\n")
    if old_vr_crlf in vp_text:
        vp_text = vp_text.replace(old_vr_crlf, new_vr_crlf)
        print("[+] VideoPlayer::render patched with explicit rectangle (CRLF)")

vp_path.write_text(vp_text, encoding="utf-8")
print("[+] video_player.cpp saved successfully")

# 4. Patch app.cpp
app_path = Path("downloader/src/ui/app.cpp")
app_text = app_path.read_text(encoding="utf-8")

# Add loadTextureFromFile helper before App methods if not present
if "static SDL_Texture* loadTextureFromFile" not in app_text:
    helper_def = """#ifdef HAS_SDL2
static SDL_Texture* loadTextureFromFile(SDL_Renderer* renderer, const std::string& path) {
    if (!renderer || path.empty()) return nullptr;
    FILE* fp = fopen(path.c_str(), "rb");
    if (!fp) return nullptr;
    SDL_RWops* rw = SDL_RWFromFP(fp, SDL_TRUE);
    if (!rw) {
        fclose(fp);
        return nullptr;
    }
    SDL_Surface* surf = IMG_Load_RW(rw, 1);
    if (!surf) return nullptr;
    SDL_Texture* tex = SDL_CreateTextureFromSurface(renderer, surf);
    SDL_FreeSurface(surf);
    if (tex) {
        SDL_SetTextureBlendMode(tex, SDL_BLENDMODE_NONE);
    }
    return tex;
}
#endif
"""
    app_text = helper_def + "\n" + app_text
    print("[+] Added loadTextureFromFile helper function")

# Replace IMG_LoadTexture in update()
old_upd_tex = """    if (!previewPath.empty() && m_renderer) {
        SDL_Texture* newTex = IMG_LoadTexture(m_renderer, previewPath.c_str());
        if (newTex) {
            if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
            m_previewTexture = newTex;
            SDL_SetTextureBlendMode(m_previewTexture, SDL_BLENDMODE_NONE);
        }
    }"""

new_upd_tex = """    if (!previewPath.empty() && m_renderer) {
        SDL_Texture* newTex = loadTextureFromFile(m_renderer, previewPath);
        if (newTex) {
            if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
            m_previewTexture = newTex;
        }
    }"""

if old_upd_tex in app_text:
    app_text = app_text.replace(old_upd_tex, new_upd_tex)
    print("[+] Replaced IMG_LoadTexture in update()")
else:
    old_ut_crlf = old_upd_tex.replace("\n", "\r\n")
    new_ut_crlf = new_upd_tex.replace("\n", "\r\n")
    if old_ut_crlf in app_text:
        app_text = app_text.replace(old_ut_crlf, new_ut_crlf)
        print("[+] Replaced IMG_LoadTexture in update() (CRLF)")

# Replace IMG_LoadTexture in loadPreviewTexture()
old_prev_tex = """    // 2. Load static image if exists
    if (std::filesystem::exists(thumbFile, ec)) {
        SDL_Texture* newTex = IMG_LoadTexture(m_renderer, thumbFile.c_str());
        if (newTex) {
            if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
            m_previewTexture = newTex;
            SDL_SetTextureBlendMode(m_previewTexture, SDL_BLENDMODE_NONE);
        }
    }"""

new_prev_tex = """    // 2. Load static image if exists
    if (std::filesystem::exists(thumbFile, ec)) {
        SDL_Texture* newTex = loadTextureFromFile(m_renderer, thumbFile);
        if (newTex) {
            if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
            m_previewTexture = newTex;
        }
    }"""

if old_prev_tex in app_text:
    app_text = app_text.replace(old_prev_tex, new_prev_tex)
    print("[+] Replaced IMG_LoadTexture in loadPreviewTexture()")
else:
    old_pt_crlf = old_prev_tex.replace("\n", "\r\n")
    new_pt_crlf = new_prev_tex.replace("\n", "\r\n")
    if old_pt_crlf in app_text:
        app_text = app_text.replace(old_pt_crlf, new_pt_crlf)
        print("[+] Replaced IMG_LoadTexture in loadPreviewTexture() (CRLF)")

# Patch renderFullscreenPreview with SDL_RenderClear and explicit screenRect dstRect
old_rfp = """void App::renderFullscreenPreview() {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    // 1. Draw Live Motion Video or Static Background Image or Dark Frosted Canvas
    if (m_videoPlayer.isPlaying()) {
        m_videoPlayer.render(m_renderer, nullptr);

        // Status badge: LIVE VIDEO
        drawRect(30, 20, 280, 32, {0x0F, 0x17, 0x2A, 0xDD});
        drawRectOutline(30, 20, 280, 32, Theme::COLOR_SUCCESS, 1);
        drawText("▶ ЖИВОЙ ВИДЕОФОН (30 FPS)", 45, 28, Theme::COLOR_SUCCESS, 13);
    } else if (m_previewTexture) {
        SDL_RenderCopy(m_renderer, m_previewTexture, nullptr, nullptr);"""

new_rfp = """void App::renderFullscreenPreview() {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    SDL_SetRenderDrawColor(m_renderer, 0, 0, 0, 255);
    SDL_RenderClear(m_renderer);

    SDL_Rect fullScreenRect = {0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT};

    // 1. Draw Live Motion Video or Static Background Image or Dark Frosted Canvas
    if (m_videoPlayer.isPlaying()) {
        m_videoPlayer.render(m_renderer, &fullScreenRect);

        // Status badge: LIVE VIDEO
        drawRect(30, 20, 280, 32, {0x0F, 0x17, 0x2A, 0xDD});
        drawRectOutline(30, 20, 280, 32, Theme::COLOR_SUCCESS, 1);
        drawText("▶ ЖИВОЙ ВИДЕОФОН (30 FPS)", 45, 28, Theme::COLOR_SUCCESS, 13);
    } else if (m_previewTexture) {
        SDL_RenderCopy(m_renderer, m_previewTexture, nullptr, &fullScreenRect);"""

if old_rfp in app_text:
    app_text = app_text.replace(old_rfp, new_rfp)
    print("[+] Patched renderFullscreenPreview with SDL_RenderClear and fullScreenRect")
else:
    old_rfp_crlf = old_rfp.replace("\n", "\r\n")
    new_rfp_crlf = new_rfp.replace("\n", "\r\n")
    if old_rfp_crlf in app_text:
        app_text = app_text.replace(old_rfp_crlf, new_rfp_crlf)
        print("[+] Patched renderFullscreenPreview with SDL_RenderClear and fullScreenRect (CRLF)")
    else:
        print("[-] Warning: old_rfp not found")

# Patch App::render with SDL_RenderClear in normal mode too
old_app_render = """    // Clear background
    drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, Theme::COLOR_BG_BASE);"""

new_app_render = """    // Clear background with hardware buffer clear
    SDL_SetRenderDrawColor(m_renderer, Theme::COLOR_BG_BASE.r, Theme::COLOR_BG_BASE.g, Theme::COLOR_BG_BASE.b, 255);
    SDL_RenderClear(m_renderer);"""

if old_app_render in app_text:
    app_text = app_text.replace(old_app_render, new_app_render)
    print("[+] Patched App::render with SDL_RenderClear")
else:
    old_ar_crlf = old_app_render.replace("\n", "\r\n")
    new_ar_crlf = new_app_render.replace("\n", "\r\n")
    if old_ar_crlf in app_text:
        app_text = app_text.replace(old_ar_crlf, new_ar_crlf)
        print("[+] Patched App::render with SDL_RenderClear (CRLF)")

app_path.write_text(app_text, encoding="utf-8")
print("[+] app.cpp saved successfully")
