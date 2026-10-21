from pathlib import Path

p = Path("downloader/src/ui/app.cpp")
text = p.read_text(encoding="utf-8")

old_touch = """            // MyGames Tab: "Восстановить (.bak)" button: x in [950, 1230], y in [205, 250]
            else if (m_activeTab == Tab::MyGames && mx >= 950 && mx <= 1230 && my >= 205 && my <= 250) {
                onButtonPress(2 /* X - Restore */);
            }"""

new_touch = """            // MyGames Tab: "[+] Записи 4IFIR (SD)" button: x in [1000, 1230], y in [195, 240]
            else if (m_activeTab == Tab::MyGames && mx >= 1000 && mx <= 1230 && my >= 195 && my <= 240) {
                if (!m_installedGames.empty() && m_myGamesSelectedIndex >= 0 &&
                    m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    openRecordingsBrowser(g.titleId, g.name);
                }
            }
            // MyGames Tab: "Восстановить (.bak)" button: x in [950, 1230], y in [205, 250]
            else if (m_activeTab == Tab::MyGames && mx >= 950 && mx <= 1230 && my >= 205 && my <= 250) {
                onButtonPress(2 /* X - Restore */);
            }"""

text = text.replace(old_touch, new_touch)
p.write_text(text, encoding="utf-8")
print("[+] Added touch handler for [+] Записи 4IFIR")
