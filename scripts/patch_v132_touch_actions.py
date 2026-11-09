from pathlib import Path

# 1. Update config.hpp
p_cfg = Path(r"E:\videofon\downloader\include\core\config.hpp")
txt_cfg = p_cfg.read_text(encoding="utf-8")
txt_cfg = txt_cfg.replace('APP_VERSION = "1.3.1"', 'APP_VERSION = "1.3.2"')
p_cfg.write_text(txt_cfg, encoding="utf-8")
print("[+] Patched config.hpp (v1.3.2)")

# 2. Update Makefile
p_mk = Path(r"E:\videofon\downloader\Makefile")
txt_mk = p_mk.read_text(encoding="utf-8")
txt_mk = txt_mk.replace('APP_VERSION := 1.3.1', 'APP_VERSION := 1.3.2')
p_mk.write_text(txt_mk, encoding="utf-8")
print("[+] Patched Makefile (v1.3.2)")

# 3. Update version.json
p_vj = Path(r"E:\videofon\version.json")
vj_content = '''{
  "latestVersion": "1.3.2",
  "minRequiredVersion": "1.0.0",
  "downloadUrl": "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.3.2/H3H-Backgrounds.nro",
  "afterDarkDownloadUrl": "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.3.2/H3H-AfterDark.nro",
  "releaseNotes": "v1.3.2: 👆 Интуитивный тач: тап по названию видеофона открывает полноэкранный предпросмотр, тап по кнопке справа — мгновенно начинает скачивание"
}'''
p_vj.write_text(vj_content, encoding="utf-8")
print("[+] Patched version.json (v1.3.2)")

# 4. Update app.cpp
p_cpp = Path(r"E:\videofon\downloader\src\ui\app.cpp")
txt_cpp = p_cpp.read_text(encoding="utf-8")

# A) Render install button on all variant rows
old_btn_render = '''                if (isVarSelected) {
                    drawRect(1005, vY + 18, 205, 36, Theme::COLOR_FOCUS_FILL);
                    drawRectOutline(1005, vY + 18, 205, 36, Theme::COLOR_FOCUS_CYAN, 1);
                    std::string btnText = isActiveOnConsole ? "[A] Переустановить" : "[A] Установить";
                    drawText(btnText, 1025, vY + 27, Theme::COLOR_FOCUS_CYAN, 13);
                }'''

new_btn_render = '''                // Install / Reinstall Button (Interactive touch zone)
                bool isFocused = (m_myGamesActivePane == MyGamesPane::VariantsList && isVarSelected);
                SDL_Color btnFill = isFocused ? Theme::COLOR_FOCUS_FILL : (isVarSelected ? SDL_Color{0x00, 0x55, 0x77, 0x33} : SDL_Color{0x15, 0x20, 0x30, 0x55});
                SDL_Color btnBorder = (isFocused || isVarSelected) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER;
                SDL_Color btnTextCol = (isFocused || isVarSelected) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_SECONDARY;

                drawRect(1005, vY + 18, 205, 36, btnFill);
                drawRectOutline(1005, vY + 18, 205, 36, btnBorder, 1);
                std::string btnText = isActiveOnConsole ? "[A] Переустановить" : "[A] Установить";
                drawText(btnText, 1025, vY + 27, btnTextCol, 13);'''

if old_btn_render in txt_cpp:
    txt_cpp = txt_cpp.replace(old_btn_render, new_btn_render, 1)
    print("[+] Patched variant card button rendering in app.cpp")
else:
    print("[-] Could not find old_btn_render")

# B) Touch tap handling for green and yellow zones
old_touch_var = '''                                if (mx >= 1005 && mx <= 1210) {
                                    onButtonPress(0 /* A - Install */);
                                }'''

new_touch_var = '''                                if (mx >= 1000 && mx <= 1220) {
                                    // Yellow Zone: direct instant download/installation
                                    queueDownload(selGame, selGame.catalogEntry.variants[vClicked]);
                                } else {
                                    // Green Zone (left 525..999): open fullscreen video preview
                                    openFullscreenPreviewForGame(selGame, vClicked);
                                }'''

if old_touch_var in txt_cpp:
    txt_cpp = txt_cpp.replace(old_touch_var, new_touch_var, 1)
    print("[+] Patched touch handling for green (preview) and yellow (download) zones")
else:
    print("[-] Could not find old_touch_var")

p_cpp.write_text(txt_cpp, encoding="utf-8")
print("[+] Updated app.cpp")
