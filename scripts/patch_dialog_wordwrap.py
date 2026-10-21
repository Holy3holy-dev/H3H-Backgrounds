from pathlib import Path

app_cpp = Path("downloader/src/ui/app.cpp")
text = app_cpp.read_text(encoding="utf-8")

old_block = """    // Standard Confirmation Dialogs
    std::stringstream ss(m_dialogMessage);
    std::string line;
    int msgY = dy + 70;
    while (std::getline(ss, line, '\\n')) {
        drawText(line, dx + 35, msgY, Theme::COLOR_TEXT_MUTED, 14);
        msgY += 24;
    }"""

# Normalizing newlines
text = text.replace("\r\n", "\n")

old_block_n = """    // Standard Confirmation Dialogs
    std::stringstream ss(m_dialogMessage);
    std::string line;
    int msgY = dy + 70;
    while (std::getline(ss, line, '\\n')) {
        drawText(line, dx + 35, msgY, Theme::COLOR_TEXT_MUTED, 14);
        msgY += 24;
    }"""

new_block_n = """    // Standard Confirmation Dialogs with auto word-wrap
    std::stringstream ss(m_dialogMessage);
    std::string rawLine;
    int msgY = dy + 70;
    while (std::getline(ss, rawLine, '\\n')) {
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

old_alert_n = """    // Specialized dialog: Alert
    if (m_activeDialog == DialogType::MessageAlert) {
        std::stringstream ss(m_dialogMessage);
        std::string line;
        int msgY = dy + 70;
        while (std::getline(ss, line, '\\n')) {
            drawText(line, dx + 35, msgY, Theme::COLOR_WARNING, 15);
            msgY += 26;
        }"""

new_alert_n = """    // Specialized dialog: Alert with auto word-wrap
    if (m_activeDialog == DialogType::MessageAlert) {
        std::stringstream ss(m_dialogMessage);
        std::string rawLine;
        int msgY = dy + 70;
        while (std::getline(ss, rawLine, '\\n')) {
            std::stringstream wordStream(rawLine);
            std::string word;
            std::string currentLine;
            while (wordStream >> word) {
                if (currentLine.empty()) {
                    currentLine = word;
                } else if (currentLine.length() + 1 + word.length() <= 54) {
                    currentLine += " " + word;
                } else {
                    drawText(currentLine, dx + 35, msgY, Theme::COLOR_WARNING, 15, dw - 70);
                    msgY += 26;
                    currentLine = word;
                }
            }
            if (!currentLine.empty()) {
                drawText(currentLine, dx + 35, msgY, Theme::COLOR_WARNING, 15, dw - 70);
                msgY += 26;
            }
        }"""

if old_block_n in text:
    text = text.replace(old_block_n, new_block_n, 1)
    print("[+] Patched confirmation dialog word-wrap!")
else:
    print("[-] old_block_n not found")

if old_alert_n in text:
    text = text.replace(old_alert_n, new_alert_n, 1)
    print("[+] Patched alert dialog word-wrap!")
else:
    print("[-] old_alert_n not found")

app_cpp.write_text(text, encoding="utf-8")
