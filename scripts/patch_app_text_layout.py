from pathlib import Path

app_cpp = Path("downloader/src/ui/app.cpp")
text = app_cpp.read_text(encoding="utf-8")

# 1. Update drawText definition
old_drawText = """void App::drawText(const std::string& text, int x, int y, Color color, int sizePx) {
#ifdef HAS_SDL2
    if (text.empty() || !m_renderer) return;

    TTF_Font* font = getFont(sizePx);
    if (font) {
        SDL_Color sdlColor = {color.r, color.g, color.b, color.a};
        SDL_Surface* surf = TTF_RenderUTF8_Blended(font, text.c_str(), sdlColor);
        if (surf) {
            SDL_Texture* tex = SDL_CreateTextureFromSurface(m_renderer, surf);
            if (tex) {
                SDL_Rect dstRect = {x, y, surf->w, surf->h};
                SDL_RenderCopy(m_renderer, tex, nullptr, &dstRect);
                SDL_DestroyTexture(tex);
            }
            SDL_FreeSurface(surf);
            return;
        }
    }

    drawBitmapTextFallback(text, x, y, color);
#else
    (void)text; (void)x; (void)y; (void)color; (void)sizePx;
#endif
}"""

new_drawText = """void App::drawText(const std::string& text, int x, int y, Color color, int sizePx, int maxWidth) {
#ifdef HAS_SDL2
    if (text.empty() || !m_renderer) return;

    TTF_Font* font = getFont(sizePx);
    if (font) {
        SDL_Color sdlColor = {color.r, color.g, color.b, color.a};
        SDL_Surface* surf = TTF_RenderUTF8_Blended(font, text.c_str(), sdlColor);
        if (surf) {
            SDL_Texture* tex = SDL_CreateTextureFromSurface(m_renderer, surf);
            if (tex) {
                int drawW = surf->w;
                if (maxWidth > 0 && drawW > maxWidth) {
                    drawW = maxWidth;
                }
                SDL_Rect srcRect = {0, 0, drawW, surf->h};
                SDL_Rect dstRect = {x, y, drawW, surf->h};
                SDL_RenderCopy(m_renderer, tex, &srcRect, &dstRect);
                SDL_DestroyTexture(tex);
            }
            SDL_FreeSurface(surf);
            return;
        }
    }

    drawBitmapTextFallback(text, x, y, color);
#else
    (void)text; (void)x; (void)y; (void)color; (void)sizePx; (void)maxWidth;
#endif
}"""

if old_drawText in text:
    text = text.replace(old_drawText, new_drawText, 1)
    print("[+] Patched drawText with maxWidth clipping!")
else:
    print("[-] old_drawText not matched directly")

# 2. Update renderDialog confirmation word wrap
old_dialog = """    // Standard Confirmation Dialogs
    std::stringstream ss(m_dialogMessage);
    std::string line;
    int msgY = dy + 70;
    while (std::getline(ss, line, '\n')) {
        drawText(line, dx + 35, msgY, Theme::COLOR_TEXT_MUTED, 14);
        msgY += 24;
    }"""

new_dialog = """    // Standard Confirmation Dialogs with auto word-wrap
    std::stringstream ss(m_dialogMessage);
    std::string rawLine;
    int msgY = dy + 68;
    while (std::getline(ss, rawLine, '\n')) {
        std::stringstream wordStream(rawLine);
        std::string word;
        std::string currentLine;
        while (wordStream >> word) {
            if (currentLine.empty()) {
                currentLine = word;
            } else if (currentLine.length() + 1 + word.length() <= 54) {
                currentLine += " " + word;
            } else {
                drawText(currentLine, dx + 35, msgY, Theme::COLOR_TEXT_MUTED, 14, dw - 70);
                msgY += 24;
                currentLine = word;
            }
        }
        if (!currentLine.empty()) {
            drawText(currentLine, dx + 35, msgY, Theme::COLOR_TEXT_MUTED, 14, dw - 70);
            msgY += 24;
        }
    }"""

if old_dialog in text:
    text = text.replace(old_dialog, new_dialog, 1)
    print("[+] Patched renderDialog with word-wrapping!")
else:
    print("[-] old_dialog not matched directly")

# 3. Update MessageAlert word wrap
old_alert = """    // Specialized dialog: Alert
    if (m_activeDialog == DialogType::MessageAlert) {
        std::stringstream ss(m_dialogMessage);
        std::string line;
        int msgY = dy + 70;
        while (std::getline(ss, line, '\n')) {
            drawText(line, dx + 35, msgY, Theme::COLOR_WARNING, 15);
            msgY += 26;
        }"""

new_alert = """    // Specialized dialog: Alert with auto word-wrap
    if (m_activeDialog == DialogType::MessageAlert) {
        std::stringstream ss(m_dialogMessage);
        std::string rawLine;
        int msgY = dy + 68;
        while (std::getline(ss, rawLine, '\n')) {
            std::stringstream wordStream(rawLine);
            std::string word;
            std::string currentLine;
            while (wordStream >> word) {
                if (currentLine.empty()) {
                    currentLine = word;
                } else if (currentLine.length() + 1 + word.length() <= 54) {
                    currentLine += " " + word;
                } else {
                    drawText(currentLine, dx + 35, msgY, Theme::COLOR_WARNING, 14, dw - 70);
                    msgY += 24;
                    currentLine = word;
                }
            }
            if (!currentLine.empty()) {
                drawText(currentLine, dx + 35, msgY, Theme::COLOR_WARNING, 14, dw - 70);
                msgY += 24;
            }
        }"""

if old_alert in text:
    text = text.replace(old_alert, new_alert, 1)
    print("[+] Patched MessageAlert with word-wrapping!")
else:
    print("[-] old_alert not matched directly")

# 4. Update renderTabMyGames bounds and audio indicator pill
old_var_card = """                // Variant Title & Style
                std::string vTitle = std::to_string(vIdx + 1) + ". " + v.name + " (" + styleToString(v.style) + ")";
                drawText(vTitle, 545, vY + 12, isVarSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16);

                // Tech Specs Line
                std::string meta = "Автор: " + v.author + "  |  " + std::to_string(v.width) + "x" +
                                   std::to_string(v.height) + " @" + std::to_string(static_cast<int>(v.fps)) + "fps  |  " +
                                   std::to_string(v.sizeBytes / (1024 * 1024)) + " MB";
                drawText(meta, 545, vY + 40, Theme::COLOR_TEXT_MUTED, 12);"""

new_var_card = """                // Variant Title & Style (bounded so it never overlaps install button)
                std::string vTitle = std::to_string(vIdx + 1) + ". " + v.name + " (" + styleToString(v.style) + ")";
                drawText(vTitle, 545, vY + 12, isVarSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, 510);

                // Tech Specs Line
                std::string meta = "Автор: " + v.author + "  |  " + std::to_string(v.width) + "x" +
                                   std::to_string(v.height) + " @" + std::to_string(static_cast<int>(v.fps)) + "fps  |  " +
                                   std::to_string(v.sizeBytes / (1024 * 1024)) + " MB";
                drawText(meta, 545, vY + 40, Theme::COLOR_TEXT_MUTED, 12, 420);

                // Audio Status Pill
                if (v.hasAudio) {
                    drawRect(975, vY + 38, 80, 20, {0x10, 0xB9, 0x81, 0x33});
                    drawRectOutline(975, vY + 38, 80, 20, Theme::COLOR_SUCCESS, 1);
                    drawText("ЗВУК", 998, vY + 42, Theme::COLOR_SUCCESS, 10);
                } else {
                    drawRect(975, vY + 38, 80, 20, {0x28, 0x33, 0x47, 0x44});
                    drawRectOutline(975, vY + 38, 80, 20, Theme::COLOR_BORDER, 1);
                    drawText("БЕЗ ЗВУКА", 982, vY + 42, Theme::COLOR_TEXT_MUTED, 10);
                }"""

if old_var_card in text:
    text = text.replace(old_var_card, new_var_card, 1)
    print("[+] Patched variant card with bounds and audio indicator pill!")
else:
    print("[-] old_var_card not matched directly")

# 5. Bound game list on left
text = text.replace(
    "drawText(game.name, 48, startY + 10, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15);",
    "drawText(game.name, 48, startY + 10, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15, 310);"
)
text = text.replace(
    "drawText(game.titleId, 48, startY + 34, Theme::COLOR_TEXT_MUTED, 12);",
    "drawText(game.titleId, 48, startY + 34, Theme::COLOR_TEXT_MUTED, 12, 310);"
)

# 6. Bound right pane game title
text = text.replace(
    "drawText(selGame.name, 530, 110, Theme::COLOR_TEXT_PRIMARY, 22);",
    "drawText(selGame.name, 530, 110, Theme::COLOR_TEXT_PRIMARY, 22, 410);"
)
text = text.replace(
    'drawText("Title ID: " + selGame.titleId + "  |  " + selGame.author, 530, 145, Theme::COLOR_TEXT_MUTED, 14);',
    'drawText("Title ID: " + selGame.titleId + "  |  " + selGame.author, 530, 145, Theme::COLOR_TEXT_MUTED, 14, 410);'
)

# 7. Bound catalog tab game title
text = text.replace(
    "drawText(g.title, 85, y + 16, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 17);",
    "drawText(g.title, 85, y + 16, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 17, 960);"
)

app_cpp.write_text(text, encoding="utf-8")
print("[+] Finished patching downloader/src/ui/app.cpp!")
