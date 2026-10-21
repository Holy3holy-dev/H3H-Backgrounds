from pathlib import Path

p = Path("downloader/src/ui/app.cpp")
text = p.read_text(encoding="utf-8").replace("\r\n", "\n")

old_hints = """    } else if (m_activeTab == Tab::MyGames) {
        bool hasCover = false;
        if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
            hasCover = m_installedGames[m_myGamesSelectedIndex].hasInstalledCover;
        }
        if (m_language == Language::Russian) {
            hints = hasCover ?
                "[L/R] Вкладки   [A] Сменить вариант   [Y] Удалить фон   [X] Восстановить   [B] Главная   [-] Каталог" :
                "[L/R] Вкладки   [A] Установить   [Y] Установить все   [B] Главная   [-] Каталог";
        } else {
            hints = hasCover ?
                "[L/R] Tabs   [A] Change variant   [Y] Delete background   [X] Restore   [B] Home   [-] Catalog" :
                "[L/R] Tabs   [A] Install   [Y] Install all   [B] Home   [-] Catalog";
        }
    } else if (m_activeTab == Tab::Catalog) {"""

new_hints = """    } else if (m_activeTab == Tab::MyGames) {
        if (m_language == Language::Russian) {
            hints = "[A] Выбрать   [X] На весь экран   [Y] Удалить фон   [B] Назад   [L/R] Вкладки   [-] Каталог";
        } else {
            hints = "[A] Select   [X] Fullscreen   [Y] Delete   [B] Back   [L/R] Tabs   [-] Catalog";
        }
    } else if (m_activeTab == Tab::Catalog) {"""

if old_hints in text:
    text = text.replace(old_hints, new_hints, 1)
    p.write_text(text, encoding="utf-8")
    print("[+] Updated MyGames footer hints!")
else:
    print("[-] Old hints not found")
