# scripts/apply_v122_blackscreen_fix.py
from pathlib import Path

print("[*] Applying v1.2.2 Black Screen & Joystick Fixes...")

# 1. Update VideoPlayer::open in video_player.cpp:
# Set SDL_BLENDMODE_NONE on m_texture so alpha channel from swscale never causes 100% transparency!
vp_path = Path("downloader/src/ui/video_player.cpp")
vp = vp_path.read_text(encoding="utf-8")

old_create_tex = """    m_texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA32,
                                  SDL_TEXTUREACCESS_STREAMING, m_width, m_height);
    if (!m_texture) {
        close();
        return false;
    }"""

new_create_tex = """    m_texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA32,
                                  SDL_TEXTUREACCESS_STREAMING, m_width, m_height);
    if (!m_texture) {
        close();
        return false;
    }
    // Disable alpha blending so video frames render at 100% full opacity, eliminating black transparent textures
    SDL_SetTextureBlendMode(m_texture, SDL_BLENDMODE_NONE);"""

if old_create_tex in vp:
    vp = vp.replace(old_create_tex, new_create_tex)
    vp_path.write_text(vp, encoding="utf-8")
    print("[+] Patched VideoPlayer::open with SDL_BLENDMODE_NONE")
else:
    print("[-] Could not find old_create_tex in video_player.cpp")

# 2. Update app.cpp:
app_path = Path("downloader/src/ui/app.cpp")
app = app_path.read_text(encoding="utf-8")

# A. Add IMG_Init in App::init() and IMG_Quit in App::shutdown()
old_init_ttf = """    if (TTF_Init() != 0) {
        std::cerr << "[-] TTF_Init failed: " << TTF_GetError() << std::endl;
    }"""

new_init_ttf = """    if (TTF_Init() != 0) {
        std::cerr << "[-] TTF_Init failed: " << TTF_GetError() << std::endl;
    }

    int imgFlags = IMG_INIT_JPG | IMG_INIT_PNG;
    if ((IMG_Init(imgFlags) & imgFlags) != imgFlags) {
        std::cerr << "[-] IMG_Init warning: " << IMG_GetError() << std::endl;
    }"""

if old_init_ttf in app:
    app = app.replace(old_init_ttf, new_init_ttf)
    print("[+] Added IMG_Init(IMG_INIT_JPG | IMG_INIT_PNG) to App::init()")
else:
    print("[-] Could not find old_init_ttf")

old_shutdown_ttf = """    TTF_Quit();
    SDL_Quit();"""

new_shutdown_ttf = """    TTF_Quit();
    IMG_Quit();
    SDL_Quit();"""

if old_shutdown_ttf in app:
    app = app.replace(old_shutdown_ttf, new_shutdown_ttf)
    print("[+] Added IMG_Quit() to App::shutdown()")

# B. Add SDL_JOYBUTTONDOWN in handleInput()
old_joy_handle = """        } else if (event.type == SDL_CONTROLLERBUTTONDOWN) {
            onButtonPress(event.cbutton.button);
        } else if (event.type == SDL_CONTROLLERAXISMOTION) {"""

new_joy_handle = """        } else if (event.type == SDL_CONTROLLERBUTTONDOWN) {
            onButtonPress(event.cbutton.button);
        } else if (event.type == SDL_JOYBUTTONDOWN) {
            // Direct hardware fallback for Switch Joy-Cons and Pro Controllers
            int btn = -1;
            switch (event.jbutton.button) {
                case 0: btn = 0; break;  // A
                case 1: btn = 1; break;  // B
                case 2: btn = 2; break;  // X
                case 3: btn = 3; break;  // Y
                case 10: btn = 6; break; // Plus (+) -> SDL_CONTROLLER_BUTTON_START (6)
                case 11: btn = 4; break; // Minus (-) -> SDL_CONTROLLER_BUTTON_BACK (4)
                case 6: btn = 9; break;  // L (LEFTSHOULDER)
                case 7: btn = 10; break; // R (RIGHTSHOULDER)
                case 4: btn = 7; break;  // Left stick click (L3)
                case 5: btn = 8; break;  // Right stick click (R3)
                case 13: btn = 11; break; // D-Pad Up
                case 15: btn = 12; break; // D-Pad Down
                case 12: btn = 13; break; // D-Pad Left
                case 14: btn = 14; break; // D-Pad Right
                default: break;
            }
            if (btn != -1) onButtonPress(btn);
        } else if (event.type == SDL_CONTROLLERAXISMOTION) {"""

if old_joy_handle in app:
    app = app.replace(old_joy_handle, new_joy_handle)
    print("[+] Added SDL_JOYBUTTONDOWN hardware fallback for Switch controllers")
else:
    print("[-] Could not find old_joy_handle")

# C. Use IMG_LoadTexture with SDL_BLENDMODE_NONE in App::update() and loadPreviewTexture()
old_update_tex = """    if (!previewPath.empty() && m_renderer) {
        SDL_RWops* rw = SDL_RWFromFile(previewPath.c_str(), "rb");
        if (rw) {
            SDL_Surface* surf = IMG_LoadJPG_RW(rw);
            if (surf) {
                if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
                m_previewTexture = SDL_CreateTextureFromSurface(m_renderer, surf);
                SDL_FreeSurface(surf);
            }
            SDL_RWclose(rw);
        }
    }"""

new_update_tex = """    if (!previewPath.empty() && m_renderer) {
        SDL_Texture* newTex = IMG_LoadTexture(m_renderer, previewPath.c_str());
        if (newTex) {
            if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
            m_previewTexture = newTex;
            SDL_SetTextureBlendMode(m_previewTexture, SDL_BLENDMODE_NONE);
        }
    }"""

if old_update_tex in app:
    app = app.replace(old_update_tex, new_update_tex)
    print("[+] Patched App::update() with IMG_LoadTexture and SDL_BLENDMODE_NONE")
else:
    print("[-] Could not find old_update_tex")

old_load_tex = """    // 2. Load static image if exists
    if (std::filesystem::exists(thumbFile, ec)) {
        SDL_RWops* rw = SDL_RWFromFile(thumbFile.c_str(), "rb");
        if (rw) {
            SDL_Surface* surf = IMG_LoadJPG_RW(rw);
            if (surf) {
                m_previewTexture = SDL_CreateTextureFromSurface(m_renderer, surf);
                SDL_FreeSurface(surf);
            }
            SDL_RWclose(rw);
        }
    }"""

new_load_tex = """    // 2. Load static image if exists
    if (std::filesystem::exists(thumbFile, ec)) {
        SDL_Texture* newTex = IMG_LoadTexture(m_renderer, thumbFile.c_str());
        if (newTex) {
            if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
            m_previewTexture = newTex;
            SDL_SetTextureBlendMode(m_previewTexture, SDL_BLENDMODE_NONE);
        }
    }"""

if old_load_tex in app:
    app = app.replace(old_load_tex, new_load_tex)
    print("[+] Patched loadPreviewTexture with IMG_LoadTexture and SDL_BLENDMODE_NONE")
else:
    print("[-] Could not find old_load_tex")

# D. In renderFullscreenPreview, add animated buffering dots
old_render_buffering = """        if (m_videoDownloading) {
            drawRect(30, 20, 270, 32, {0x0F, 0x17, 0x2A, 0xDD});
            drawRectOutline(30, 20, 270, 32, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("▶ Буферизация ролика...", 45, 28, Theme::COLOR_FOCUS_CYAN, 13);
        }"""

new_render_buffering = """        if (m_videoDownloading) {
            drawRect(30, 20, 270, 32, {0x0F, 0x17, 0x2A, 0xDD});
            drawRectOutline(30, 20, 270, 32, Theme::COLOR_FOCUS_CYAN, 1);
            int dotCount = (SDL_GetTicks() / 350) % 4;
            std::string dots = std::string(dotCount, '.');
            drawText("▶ Буферизация ролика" + dots, 45, 28, Theme::COLOR_FOCUS_CYAN, 13);
        }"""

if old_render_buffering in app:
    app = app.replace(old_render_buffering, new_render_buffering)
    print("[+] Added animated dots to buffering badge")

app_path.write_text(app, encoding="utf-8")
print("[+] Finished patching app.cpp")

# 3. Bump version to 1.2.2 in config.hpp and version.json
cfg_path = Path("downloader/include/core/config.hpp")
cfg = cfg_path.read_text(encoding="utf-8")
cfg = cfg.replace('APP_VERSION = "1.2.1"', 'APP_VERSION = "1.2.2"')
cfg_path.write_text(cfg, encoding="utf-8")
print("[+] Bumped config.hpp to v1.2.2")

ver_path = Path("version.json")
ver_path.write_text("""{
  "latestVersion": "1.2.2",
  "minRequiredVersion": "1.0.0",
  "downloadUrl": "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-Backgrounds.nro",
  "releaseNotes": "Fix black screen on static preview and video playback via SDL_BLENDMODE_NONE & full SDL_JOYBUTTONDOWN mapping"
}
""", encoding="utf-8")
print("[+] Bumped version.json to v1.2.2")
