from pathlib import Path

app_cpp_path = Path("downloader/src/ui/app.cpp")
text = app_cpp_path.read_text(encoding="utf-8")

# 1. Remove the global exit handler on button 6 (Plus / +)
exit_handler = """    // Global Exit Handler: Plus (+) button exits to Homebrew Menu (universal Switch standard)
    if (button == 6 /* SDL_CONTROLLER_BUTTON_START (Plus / +) */) {
        if (m_isCollectionBrowserOpen) {
            closeCollectionBrowser();
            return;
        }
        if (m_isGamePickerOpen) {
            closeGamePicker();
            return;
        }
        if (m_isRecordingsBrowserOpen) {
            closeRecordingsBrowser();
            return;
        }
        if (m_isFullscreenPreview) {
            closeFullscreenPreview();
            return;
        }
        if (m_activeDialog != DialogType::None) {
            m_activeDialog = DialogType::None;
            return;
        }
        // Exit application cleanly to hbmenu
        m_running = false;
        return;
    }
"""

assert exit_handler in text, "exit_handler not found in app.cpp"
text = text.replace(exit_handler, "")

# 2. Update footer hints to show [B] Выход in Home and MyGames
old_home_hint = 'hints = "[L/R] Вкладки   [A] Мои игры   [Y] Установить все недостающие   [X] Обновить   [-] GitHub";'
new_home_hint = 'hints = "[L/R] Вкладки   [A] Мои игры   [B] Выход из приложения   [Y] Установить все   [-] Обновить";'
if old_home_hint in text:
    text = text.replace(old_home_hint, new_home_hint)

old_mygames_hint = 'hints = "[A] Выбрать   [X] На весь экран   [Y] Удалить фон   [B] Назад   [L/R] Вкладки   [-] Каталог";'
new_mygames_hint = 'hints = "[A] Выбрать   [X] Видео   [Y] Удалить   [B] Назад / Выход   [L/R] Вкладки   [-] Каталог";'
if old_mygames_hint in text:
    text = text.replace(old_mygames_hint, new_mygames_hint)

with open(app_cpp_path, "w", newline="\n", encoding="utf-8") as f:
    f.write(text)

print("[SUCCESS] Global Plus exit handler removed. Only [B] from main menu exits!")
