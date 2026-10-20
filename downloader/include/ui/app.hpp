#pragma once

#include "core/types.hpp"
#include "core/catalog_manager.hpp"
#include "platform/platform_interface.hpp"
#include "ui/theme.hpp"
#include "ui/i18n.hpp"
#include <memory>
#include <vector>
#include <string>
#include <map>
#include <thread>
#include <mutex>
#include <atomic>

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
    ConfirmInstallAll,
    ConfirmRestore,
    ConfirmDelete,
    MessageAlert,
    UpdateProgress,
    UpdateSuccess
};

class App {
public:
    App(std::unique_ptr<IPlatform> platform);
    ~App();

    bool init();
    void run();
    void shutdown();
    void setRunningNroPath(const std::string& path) { m_runningNroPath = path; }

    // Event handling & Frame update
    void handleInput();
    void update();
    void onButtonPress(int button);

    // Business Logic
    void refreshInstalledGames();
    void fetchRemoteCatalog();
    void installAllMissing();
    int getMissingCoversCount() const;
    void queueDownload(const InstalledTitle& title, const Variant& variant);
    void executeRestoreBackup(const std::string& titleId);
    void executeDeleteCover(const std::string& titleId);
    void updateApplicationNro();

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

    // Drawing helpers (4IFIR Glass Theme)
    void drawRect(int x, int y, int w, int h, Color color);
    void drawRectOutline(int x, int y, int w, int h, Color color, int thickness = 2);
    void drawNeonGradientOutline(int x, int y, int w, int h, int thickness = 2);
    void drawGlassCard(int x, int y, int w, int h, bool isFocused, bool isElevated = false);
    void drawCapsuleProgressBar(int x, int y, int w, int h, double percent);
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
    std::string m_runningNroPath;

    // Selection & Scroll state
    int m_myGamesSelectedIndex{0};
    int m_myGamesScrollOffset{0};
    int m_selectedVariantIndex{0};
    int m_variantScrollOffset{0};

    int m_catalogSelectedIndex{0};
    int m_catalogScrollOffset{0};

    int m_settingsSelectedIndex{0};

    // Dialog state
    DialogType m_activeDialog{DialogType::None};
    std::string m_dialogTitle;
    std::string m_dialogMessage;
    int m_dialogFocus{0}; // 0 = Confirm, 1 = Cancel
    std::string m_pendingActionTitleId;
    Variant m_pendingActionVariant;

    std::string m_statusNotification;
    int m_notificationFramesRemaining{0};

    // Thread-safe async catalog fetching
    std::thread m_catalogThread;
    std::atomic<bool> m_isFetchingCatalog{false};
    std::atomic<bool> m_catalogFetchDone{false};
    std::string m_fetchedJson;
    std::string m_fetchError;
    bool m_fetchSuccess{false};
    std::mutex m_catalogMutex;

    // Thread-safe async NRO updating
    std::thread m_nroUpdateThread;
    std::atomic<bool> m_isUpdatingNro{false};
    std::atomic<bool> m_nroUpdateDone{false};
    std::string m_nroUpdateError;
    bool m_nroUpdateSuccess{false};
    std::mutex m_nroMutex;
    std::atomic<uint64_t> m_nroUpdateBytesDownloaded{0};
    std::atomic<uint64_t> m_nroUpdateTotalBytes{0};

    // Thread-safe async download queue processing
    void processSingleDownloadTask(int taskIdx);
    std::thread m_queueThread;
    std::atomic<bool> m_isProcessingQueue{false};
    std::atomic<bool> m_cancelQueue{false};
    std::atomic<bool> m_queueTaskFinished{false};
    std::mutex m_queueMutex;
    int m_downloadsScrollOffset{0};

    uint32_t m_lastStickScrollTime{0};
};

} // namespace ui
} // namespace h3h
