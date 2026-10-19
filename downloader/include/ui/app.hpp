#pragma once

#include "core/types.hpp"
#include "core/catalog_manager.hpp"
#include "core/installer.hpp"
#include "platform/platform_interface.hpp"
#include "ui/theme.hpp"
#include "ui/i18n.hpp"

#include <memory>
#include <vector>
#include <string>
#include <atomic>
#include <map>

struct SDL_Window;
struct SDL_Renderer;
typedef struct _TTF_Font TTF_Font;

namespace h3h {
namespace ui {

enum class Tab {
    Home = 0,
    MyGames = 1,
    Catalog = 2,
    Downloads = 3,
    Settings = 4
};

enum class DialogType {
    None,
    ConfirmInstall,
    ConfirmRestore,
    ConfirmDelete,
    MessageAlert
};

class App {
public:
    App(std::unique_ptr<IPlatform> platform);
    ~App();

    bool init();
    void run();
    void shutdown();

    // Event handling
    void handleInput();
    void onButtonPress(int button);

    // Business Logic
    void refreshInstalledGames();
    void fetchRemoteCatalog();
    void queueDownload(const InstalledTitle& title, const Variant& variant);
    void executeRestoreBackup(const std::string& titleId);
    void executeDeleteCover(const std::string& titleId);

    // Render Passes
    void render();
    void renderHeader();
    void renderFooter();
    void renderTabHome();
    void renderTabMyGames();
    void renderTabCatalog();
    void renderTabDownloads();
    void renderTabSettings();
    void renderDialog();

    // Drawing helpers
    void drawRect(int x, int y, int w, int h, Color color);
    void drawRectOutline(int x, int y, int w, int h, Color color, int thickness = 2);
    void drawText(const std::string& text, int x, int y, Color color, int sizePx = 16);
    void drawBitmapTextFallback(const std::string& text, int x, int y, Color color);
    TTF_Font* getFont(int sizePx);

private:
    std::unique_ptr<IPlatform> m_platform;
    CatalogManager m_catalogManager;

    // Window and Renderer
    SDL_Window* m_window{nullptr};
    SDL_Renderer* m_renderer{nullptr};
    std::map<int, TTF_Font*> m_fonts;
    const void* m_fontMemBuffer{nullptr};
    size_t m_fontMemSize{0};

    // State
    bool m_running{true};
    Language m_language{Language::Russian};
    Tab m_activeTab{Tab::Home};

    std::vector<InstalledTitle> m_installedGames;
    std::vector<DownloadTask> m_downloadQueue;
    SystemInfo m_sysInfo;

    // Selection & Scroll state
    int m_myGamesSelectedIndex{0};
    int m_myGamesScrollOffset{0};
    int m_selectedVariantIndex{0};

    int m_catalogSelectedIndex{0};
    int m_catalogScrollOffset{0};

    // Dialog state
    DialogType m_activeDialog{DialogType::None};
    std::string m_dialogTitle;
    std::string m_dialogMessage;
    int m_dialogFocus{0}; // 0 = Confirm, 1 = Cancel
    std::string m_pendingActionTitleId;
    Variant m_pendingActionVariant;

    std::string m_statusNotification;
    int m_notificationFramesRemaining{0};
};

} // namespace ui
} // namespace h3h
