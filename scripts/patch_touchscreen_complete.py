import re
from pathlib import Path

# 1. Update switch_platform.cpp
p_plat = Path(r"E:\videofon\downloader\src\platform\switch_platform.cpp")
txt_plat = p_plat.read_text(encoding="utf-8")
if "hidInitializeTouchScreen" not in txt_plat:
    old_plat = '''        if (curl_global_init(CURL_GLOBAL_DEFAULT) == CURLE_OK) {
            m_curlInitialized = true;
        }

        m_initialized = true;'''
    new_plat = '''        if (curl_global_init(CURL_GLOBAL_DEFAULT) == CURLE_OK) {
            m_curlInitialized = true;
        }

        // Initialize capacitive touchscreen HID polling in libnx
        hidInitializeTouchScreen();

        m_initialized = true;'''
    txt_plat = txt_plat.replace(old_plat, new_plat, 1)
    p_plat.write_text(txt_plat, encoding="utf-8")
    print("[+] Patched switch_platform.cpp")

# 2. Update config.hpp
p_cfg = Path(r"E:\videofon\downloader\include\core\config.hpp")
txt_cfg = p_cfg.read_text(encoding="utf-8")
txt_cfg = txt_cfg.replace('APP_VERSION = "1.3.0"', 'APP_VERSION = "1.3.1"')
p_cfg.write_text(txt_cfg, encoding="utf-8")
print("[+] Patched config.hpp (v1.3.1)")

# 3. Update Makefile
p_mk = Path(r"E:\videofon\downloader\Makefile")
txt_mk = p_mk.read_text(encoding="utf-8")
txt_mk = txt_mk.replace('APP_VERSION := 1.3.0', 'APP_VERSION := 1.3.1')
p_mk.write_text(txt_mk, encoding="utf-8")
print("[+] Patched Makefile (v1.3.1)")

# 4. Update version.json
p_vj = Path(r"E:\videofon\version.json")
vj_content = '''{
  "latestVersion": "1.3.1",
  "minRequiredVersion": "1.0.0",
  "downloadUrl": "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.3.1/H3H-Backgrounds.nro",
  "afterDarkDownloadUrl": "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.3.1/H3H-AfterDark.nro",
  "releaseNotes": "v1.3.1: 👆 Сенсорное управление на Nintendo Switch (FINGERDOWN/UP/MOTION + свайпы и drag-скролл), ☁️ Фикс авторизации Google Drive в Telegram боте"
}'''
p_vj.write_text(vj_content, encoding="utf-8")
print("[+] Patched version.json (v1.3.1)")

# 5. Update app.hpp
p_hpp = Path(r"E:\videofon\downloader\include\ui\app.hpp")
txt_hpp = p_hpp.read_text(encoding="utf-8")

if "handleTouchTap" not in txt_hpp:
    old_input_hdr = '''    void handleInput();

    void update();

    void onButtonPress(int button);'''
    new_input_hdr = '''    void handleInput();

    void update();

    void onButtonPress(int button);

    void handleTouchTap(int mx, int my);

    void handleTouchDrag(int startX, int startY, int deltaY);

    void handleTouchSwipe(int startX, int startY, int endX, int endY);'''
    txt_hpp = txt_hpp.replace(old_input_hdr, new_input_hdr, 1)

if "m_touchDown" not in txt_hpp:
    old_batch_var = '''    // Feature 7: Batch Selection
    std::set<std::string> m_batchSelectedTitleIds;

};'''
    new_batch_var = '''    // Feature 7: Batch Selection
    std::set<std::string> m_batchSelectedTitleIds;

    // Capacitive Touchscreen state
    bool m_touchDown{false};
    int m_touchStartX{0};
    int m_touchStartY{0};
    int m_touchLastX{0};
    int m_touchLastY{0};
    uint32_t m_touchStartTime{0};
    bool m_isTouchDragging{false};
    int m_touchDragAccumulator{0};
    SDL_FingerID m_activeFingerId{0};

};'''
    txt_hpp = txt_hpp.replace(old_batch_var, new_batch_var, 1)

p_hpp.write_text(txt_hpp, encoding="utf-8")
print("[+] Patched app.hpp")

# 6. Update app.cpp
p_cpp = Path(r"E:\videofon\downloader\src\ui\app.cpp")
txt_cpp = p_cpp.read_text(encoding="utf-8")

# Hint setup in App::init()
if 'SDL_HINT_TOUCH_MOUSE_EVENTS' not in txt_cpp:
    old_init_sdl = '''#ifdef HAS_SDL2
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_GAMECONTROLLER) != 0) {'''
    new_init_sdl = '''#ifdef HAS_SDL2
    SDL_SetHint(SDL_HINT_TOUCH_MOUSE_EVENTS, "0");
    SDL_SetHint(SDL_HINT_MOUSE_TOUCH_EVENTS, "0");

    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_GAMECONTROLLER) != 0) {'''
    txt_cpp = txt_cpp.replace(old_init_sdl, new_init_sdl, 1)

if 'SDL_RenderSetLogicalSize' not in txt_cpp:
    old_renderer_blend = '''    // Enable high-quality alpha blending for 4IFIR frosted glass effects
    SDL_SetRenderDrawBlendMode(m_renderer, SDL_BLENDMODE_BLEND);'''
    new_renderer_blend = '''    SDL_RenderSetLogicalSize(m_renderer, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT);

    // Enable high-quality alpha blending for 4IFIR frosted glass effects
    SDL_SetRenderDrawBlendMode(m_renderer, SDL_BLENDMODE_BLEND);'''
    txt_cpp = txt_cpp.replace(old_renderer_blend, new_renderer_blend, 1)

# Now replace the touch event handling block in handleInput
# Find from `} else if (event.type == SDL_MOUSEBUTTONDOWN) {` to `} else if (event.type == SDL_KEYDOWN) {`
pattern_mouse = re.compile(r'(\} else if \(event\.type == SDL_MOUSEWHEEL\) \{[\s\S]*?\n\s*\}) else if \(event\.type == SDL_MOUSEBUTTONDOWN\) \{([\s\S]*?)\n\s*\} else if \(event\.type == SDL_KEYDOWN\) \{', re.MULTILINE)

m = pattern_mouse.search(txt_cpp)
if m:
    touch_logic_body = m.group(2)
    # The touch_logic_body is lines 1043 to 1325
    replacement = r'''\1 else if (event.type == SDL_FINGERDOWN) {
            if (!m_touchDown) {
                int mx = static_cast<int>(std::round(event.tfinger.x * static_cast<float>(Theme::SCREEN_WIDTH)));
                int my = static_cast<int>(std::round(event.tfinger.y * static_cast<float>(Theme::SCREEN_HEIGHT)));
                mx = std::max(0, std::min(mx, Theme::SCREEN_WIDTH - 1));
                my = std::max(0, std::min(my, Theme::SCREEN_HEIGHT - 1));

                m_touchDown = true;
                m_activeFingerId = event.tfinger.fingerId;
                m_touchStartX = mx;
                m_touchStartY = my;
                m_touchLastX = mx;
                m_touchLastY = my;
                m_touchStartTime = SDL_GetTicks();
                m_isTouchDragging = false;
                m_touchDragAccumulator = 0;
            }
        } else if (event.type == SDL_FINGERMOTION) {
            if (m_touchDown && event.tfinger.fingerId == m_activeFingerId) {
                int mx = static_cast<int>(std::round(event.tfinger.x * static_cast<float>(Theme::SCREEN_WIDTH)));
                int my = static_cast<int>(std::round(event.tfinger.y * static_cast<float>(Theme::SCREEN_HEIGHT)));
                mx = std::max(0, std::min(mx, Theme::SCREEN_WIDTH - 1));
                my = std::max(0, std::min(my, Theme::SCREEN_HEIGHT - 1));

                int diffX = mx - m_touchStartX;
                int diffY = my - m_touchStartY;
                if (!m_isTouchDragging && (std::abs(diffX) > 15 || std::abs(diffY) > 15)) {
                    m_isTouchDragging = true;
                }

                if (m_isTouchDragging) {
                    int dy = my - m_touchLastY;
                    handleTouchDrag(m_touchStartX, m_touchStartY, dy);
                }
                m_touchLastX = mx;
                m_touchLastY = my;
            }
        } else if (event.type == SDL_FINGERUP) {
            if (m_touchDown && event.tfinger.fingerId == m_activeFingerId) {
                int mx = static_cast<int>(std::round(event.tfinger.x * static_cast<float>(Theme::SCREEN_WIDTH)));
                int my = static_cast<int>(std::round(event.tfinger.y * static_cast<float>(Theme::SCREEN_HEIGHT)));
                mx = std::max(0, std::min(mx, Theme::SCREEN_WIDTH - 1));
                my = std::max(0, std::min(my, Theme::SCREEN_HEIGHT - 1));

                if (!m_isTouchDragging) {
                    handleTouchTap(m_touchStartX, m_touchStartY);
                } else {
                    handleTouchSwipe(m_touchStartX, m_touchStartY, mx, my);
                }
                m_touchDown = false;
                m_isTouchDragging = false;
            }
        } else if (event.type == SDL_MOUSEBUTTONDOWN) {
            if (event.button.which != SDL_TOUCH_MOUSEID) {
                handleTouchTap(event.button.x, event.button.y);
            }
        } else if (event.type == SDL_KEYDOWN) {'''

    txt_cpp = pattern_mouse.sub(replacement, txt_cpp)

    # Now define handleTouchTap, handleTouchDrag, handleTouchSwipe at end of app.cpp or before onButtonPress
    # Clean touch_logic_body: remove initial `// Touch / mouse support on Nintendo Switch\n int mx = event.button.x;\n int my = event.button.y;`
    cleaned_tap_body = re.sub(r'^\s*// Touch / mouse support on Nintendo Switch\s*\n\s*int mx = event\.button\.x;\s*\n\s*int my = event\.button\.y;\s*', '', touch_logic_body)

    # Replace `continue;` in tap body with `return;`
    cleaned_tap_body = cleaned_tap_body.replace('continue;', 'return;')

    methods_to_add = f'''
void App::handleTouchTap(int mx, int my) {{
{cleaned_tap_body}
}}

void App::handleTouchDrag(int startX, int startY, int deltaY) {{
    m_touchDragAccumulator += deltaY;

    // Threshold of 32 pixels for one scroll step
    while (m_touchDragAccumulator <= -32) {{
        // Dragging UP -> scroll DOWN
        m_touchDragAccumulator += 32;
        if (m_isCollectionBrowserOpen) {{
            if (m_collectionScrollOffset + 5 < static_cast<int>(m_collectionVariants.size())) {{
                m_collectionScrollOffset++;
            }}
        }} else if (m_isGamePickerOpen) {{
            if (m_gamePickerScrollOffset + 5 < static_cast<int>(m_installedGames.size())) {{
                m_gamePickerScrollOffset++;
            }}
        }} else if (m_isRecordingsBrowserOpen) {{
            if (m_recordingsScrollOffset + 5 < static_cast<int>(m_localRecordings.size())) {{
                m_recordingsScrollOffset++;
            }}
        }} else if (m_activeTab == Tab::Catalog && startX >= 60 && startX <= 1220 && startY >= 160 && startY <= 660) {{
            if (m_catalogScrollOffset + 5 < static_cast<int>(m_filteredCatalogGames.size())) {{
                m_catalogScrollOffset++;
            }}
        }} else if (m_activeTab == Tab::MyGames && startX >= 30 && startX <= 480) {{
            if (m_myGamesScrollOffset + 7 < static_cast<int>(m_installedGames.size())) {{
                m_myGamesScrollOffset++;
            }}
        }} else if (m_activeTab == Tab::MyGames && startX >= 525 && startX <= 1225) {{
            if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {{
                const auto& selGame = m_installedGames[m_myGamesSelectedIndex];
                int totalV = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
                if (m_variantScrollOffset + 4 < totalV) {{
                    m_variantScrollOffset++;
                }}
            }}
        }}
    }}

    while (m_touchDragAccumulator >= 32) {{
        // Dragging DOWN -> scroll UP
        m_touchDragAccumulator -= 32;
        if (m_isCollectionBrowserOpen) {{
            if (m_collectionScrollOffset > 0) {{
                m_collectionScrollOffset--;
            }}
        }} else if (m_isGamePickerOpen) {{
            if (m_gamePickerScrollOffset > 0) {{
                m_gamePickerScrollOffset--;
            }}
        }} else if (m_isRecordingsBrowserOpen) {{
            if (m_recordingsScrollOffset > 0) {{
                m_recordingsScrollOffset--;
            }}
        }} else if (m_activeTab == Tab::Catalog && startX >= 60 && startX <= 1220 && startY >= 160 && startY <= 660) {{
            if (m_catalogScrollOffset > 0) {{
                m_catalogScrollOffset--;
            }}
        }} else if (m_activeTab == Tab::MyGames && startX >= 30 && startX <= 480) {{
            if (m_myGamesScrollOffset > 0) {{
                m_myGamesScrollOffset--;
            }}
        }} else if (m_activeTab == Tab::MyGames && startX >= 525 && startX <= 1225) {{
            if (m_variantScrollOffset > 0) {{
                m_variantScrollOffset--;
            }}
        }}
    }}
}}

void App::handleTouchSwipe(int startX, int startY, int endX, int endY) {{
    int diffX = endX - startX;
    int diffY = endY - startY;

    if (m_isFullscreenPreview) {{
        if (diffX < -60) {{
            // Swiped Left -> Next Video
            onButtonPress(14 /* DPAD_RIGHT - Next */);
        }} else if (diffX > 60) {{
            // Swiped Right -> Prev Video
            onButtonPress(13 /* DPAD_LEFT - Prev */);
        }} else if (diffY > 80) {{
            // Swiped Down -> Close Preview
            closeFullscreenPreview();
        }}
    }}
}}
'''
    # Append methods before closing namespace
    txt_cpp = txt_cpp.replace('} // namespace ui\n} // namespace h3h', methods_to_add + '\n} // namespace ui\n} // namespace h3h')
    p_cpp.write_text(txt_cpp, encoding="utf-8")
    print("[+] Patched app.cpp with native touch routing, drag-scroll, and swipe!")
else:
    print("[-] Could not find mouse block in app.cpp")
