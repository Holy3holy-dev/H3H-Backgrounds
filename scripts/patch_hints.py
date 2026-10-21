with open('downloader/src/ui/app.cpp', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'hints = "[L/R] Вкладки   [A] Установить   [B] Назад   [X] Восстановить   [Y] Удалить / Все   [-] Обновить";' in line:
        new_lines.append("""        bool hasCover = false;
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
        }\n""")
    else:
        new_lines.append(line)

with open('downloader/src/ui/app.cpp', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Updated footer hints in app.cpp")
