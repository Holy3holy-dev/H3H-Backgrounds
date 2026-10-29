#pragma once

#include <string>

namespace h3h {
namespace ui {

enum class Language {
    Russian,
    English
};

struct StringTable {
    const char* appTitle;
    const char* tabHome;
    const char* tabCatalog;
    const char* tabVideoIcons;
    const char* tabMyGames;
    const char* tabDownloads;
    const char* tabSettings;

    // Dashboard
    const char* statDetectedGames;
    const char* statInstalledCovers;
    const char* statAvailableCatalog;
    const char* appletWarning;
    const char* cfwActiveStatus;

    // Games List
    const char* statusInstalled;
    const char* statusNoCover;
    const char* statusHasBackup;
    const char* actionInstall;
    const char* actionInstallAll;
    const char* actionRestore;
    const char* actionDelete;
    const char* actionSelect;
    const char* actionBack;
    const char* actionRefresh;
    const char* actionRefreshCatalog;
    const char* updateAppBtn;
    const char* refreshCatalogBtn;

    // Dialogs
    const char* confirmRestoreTitle;
    const char* confirmRestoreMsg;
    const char* confirmDeleteTitle;
    const char* confirmDeleteMsg;
    const char* confirmInstallTitle;
    const char* confirmInstallMsg;
    const char* confirmInstallAllTitle;
    const char* confirmInstallAllMsg;

    // Settings
    const char* catalogUrlLabel;
    const char* clearCacheBtn;
    const char* cacheClearedMsg;
    const char* languageLabel;
    const char* storageFreeLabel;
};

inline const StringTable& getStrings(Language lang) {
    static const StringTable ru = {
        "H3H Backgrounds (4IFIR)",
        "Главная",
        "Каталог",
        "Видеоиконки",
        "Мои игры",
        "Загрузки",
        "Настройки",

        "Обнаружено игр",
        "Установлено фонов",
        "Доступно в каталоге",
        "Режим апплета (ограниченная память). Рекомендуется запуск через [R] над игрой.",
        "4IFIR: Активен (sdmc:/recordings/covers/)",

        "Установлен",
        "Нет фона",
        "Есть копия",
        "Установить",
        "Установить все",
        "Восстановить",
        "Удалить",
        "Выбрать",
        "Назад",
        "Обновить",
        "Обновить каталог",
        "Обновить .NRO",
        "[-] Обновить каталог",

        "Восстановление копии",
        "Восстановить предыдущий видеофон (.bak) для этой игры?",
        "Удаление видеофона",
        "Вы уверены, что хотите удалить видеофон этой игры?",
        "Установка видеофона",
        "Загрузить и установить выбранный видеофон на SD-карту?",
        "Установка всех недостающих",
        "Загрузить и установить видеофоны для всех игр без обложки?",

        "Источник каталога",
        "Очистить кэш каталога",
        "Кэш каталога успешно очищен",
        "Язык интерфейса",
        "Свободно на SD"
    };

    static const StringTable en = {
        "H3H Backgrounds (4IFIR)",
        "Home",
        "Catalog",
        "Video Icons",
        "My Games",
        "Downloads",
        "Settings",

        "Detected Games",
        "Installed Covers",
        "Available in Catalog",
        "Applet Mode (Limited RAM). Launching via [R] over a game is recommended.",
        "4IFIR: Active (sdmc:/recordings/covers/)",

        "Installed",
        "No Cover",
        "Backup Avail",
        "Install",
        "Install All",
        "Restore",
        "Delete",
        "Select",
        "Back",
        "Refresh",
        "Refresh Catalog",
        "Update .NRO",
        "[-] Refresh Catalog",

        "Restore Backup",
        "Restore previous video cover (.bak) for this title?",
        "Delete Cover",
        "Are you sure you want to delete the video cover for this title?",
        "Install Cover",
        "Download and install the selected video cover to SD card?",
        "Install All Missing",
        "Download and install video covers for all games without covers?",

        "Catalog Source URL",
        "Clear Catalog Cache",
        "Catalog cache cleared successfully",
        "Interface Language",
        "Free SD Storage"
    };

    return (lang == Language::Russian) ? ru : en;
}

} // namespace ui
} // namespace h3h
