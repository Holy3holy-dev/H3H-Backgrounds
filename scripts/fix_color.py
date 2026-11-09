from pathlib import Path

p = Path(r"E:\videofon\downloader\src\ui\app.cpp")
txt = p.read_text(encoding="utf-8")

old_code = """                // Install / Reinstall Button (Interactive touch zone)
                bool isFocused = (m_myGamesActivePane == MyGamesPane::VariantsList && isVarSelected);
                SDL_Color btnFill = isFocused ? Theme::COLOR_FOCUS_FILL : (isVarSelected ? SDL_Color{0x00, 0x55, 0x77, 0x33} : SDL_Color{0x15, 0x20, 0x30, 0x55});
                SDL_Color btnBorder = (isFocused || isVarSelected) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER;
                SDL_Color btnTextCol = (isFocused || isVarSelected) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_SECONDARY;

                drawRect(1005, vY + 18, 205, 36, btnFill);
                drawRectOutline(1005, vY + 18, 205, 36, btnBorder, 1);
                std::string btnText = isActiveOnConsole ? "[A] Переустановить" : "[A] Установить";
                drawText(btnText, 1025, vY + 27, btnTextCol, 13);"""

new_code = """                // Install / Reinstall Button (Interactive touch zone)
                bool isFocused = (m_myGamesActivePane == MyGamesPane::VariantsList && isVarSelected);
                Color btnFill = isFocused ? Theme::COLOR_FOCUS_FILL : (isVarSelected ? Color{0x00, 0x55, 0x77, 0x33} : Color{0x15, 0x20, 0x30, 0x55});
                Color btnBorder = (isFocused || isVarSelected) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER;
                Color btnTextCol = (isFocused || isVarSelected) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED;

                drawRect(1005, vY + 18, 205, 36, btnFill);
                drawRectOutline(1005, vY + 18, 205, 36, btnBorder, 1);
                std::string btnText = isActiveOnConsole ? "[A] Переустановить" : "[A] Установить";
                drawText(btnText, 1025, vY + 27, btnTextCol, 13);"""

assert old_code in txt, "old_code not found in app.cpp"
txt = txt.replace(old_code, new_code, 1)
p.write_text(txt, encoding="utf-8")
print("[+] Successfully fixed Color types in app.cpp")
