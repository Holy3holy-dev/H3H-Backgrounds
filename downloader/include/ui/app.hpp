#pragma once

#include "core/types.hpp"
#include "core/catalog_manager.hpp"
#include "platform/platform_interface.hpp"
#include "ui/theme.hpp"
#include "ui/i18n.hpp"
#include "ui/video_player.hpp"
#include <memory>
#include <vector>
#include <string>
#include <map>
#include <thread>
#include <mutex>
#include <atomic>

struct SDL_Window;
struct SDL_Renderer;
struct SDL_Texture;
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

enum class MyGamesPane {
    GamesList,
    VariantsList
};

enum class DialogType {
    None,
    ConfirmInstall,
    ConfirmInstallAll,
    ConfirmRestore,
    ConfirmDelete,
    ConfirmInstallLocalRecording,
    ConfirmDeleteCorrupted,
    IntegrityCheckResult,
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
    void renderFullscreenPreview();
    void loadPreviewTexture(const std::string& titleId, const Variant& variant);
    void openFullscreenPreviewForGame(const InstalledTitle& g, int variantIndex);
    void openFullscreenPreviewForCatalogGame(const GameCatalogEntry& entry, int variantIndex);
    void closeFullscreenPreview();

    // Feature 3: Local 4IFIR Recordings Browser
    void openRecordingsBrowser(const std::string& titleId, const std::string& gameName);
    void closeRecordingsBrowser();
    void renderRecordingsBrowser();
    void executeInstallLocalRecording();

    // Target Game Picker (Assign background to any installed game)
    void openGamePicker(const Variant& variant, const std::string& sourceGameName);
    void closeGamePicker();
    void renderGamePicker();

    // Feature 5: Integrity Scanner
    void runIntegrityCheck();
    void executeDeleteCorruptedCovers();

    // Drawing helpers (4IFIR Glass Theme)
    void drawRect(int x, int y, int w, int h, Color color);
    void drawRectOutline(int x, int y, int w, int h, Color color, int thickness = 2);
    void drawNeonGradientOutline(int x, int y, int w, int h, int thickness = 2);
    void drawGlassCard(int x, int y, int w, int h, bool isFocused, bool isElevated = false);
    void drawCapsuleProgressBar(int x, int y, int w, int h, double percent);
    void drawText(const std::string& text, int x, int y, Color color, int sizePx = 16, int maxWidth = 0);
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

    // MyGames two-pane navigation & Fullscreen Preview
    MyGamesPane m_myGamesActivePane{MyGamesPane::GamesList};
    bool m_isFullscreenPreview{false};
    SDL_Texture* m_previewTexture{nullptr};
    std::string m_previewCurrentVariantId;
    std::string m_pendingPreviewFileToLoad;
    std::atomic<bool> m_previewLoading{false};
    std::thread m_previewThread;
    std::atomic<bool> m_cancelPreview{false};
    std::mutex m_previewMutex;

    // Live Video Playback inside Fullscreen Preview
    VideoPlayer m_videoPlayer;
    std::string m_pendingVideoToOpen;
    std::atomic<bool> m_videoDownloading{false};

    // Unified Fullscreen Preview metadata (for both MyGames & Catalog tabs)
    std::string m_previewTitleId;
    std::string m_previewGameName;
    std::vector<Variant> m_previewVariants;
    int m_previewVariantIndex{0};
    bool m_previewIsGameInstalled{false};
    bool m_previewHasInstalledCover{false};
    std::string m_previewInstalledVariantId;
    uint64_t m_previewInstalledCoverSizeBytes{0};
    std::string m_previewInstalledCoverPath;

    uint32_t m_lastStickScrollTime{0};

    // Local recordings browser (Feature 3)
    bool m_isRecordingsBrowserOpen{false};
    std::vector<LocalRecording> m_localRecordings;
    int m_recordingsSelectedIndex{0};
    int m_recordingsScrollOffset{0};
    std::string m_recordingsTargetTitleId;
    std::string m_recordingsTargetGameName;
    std::string m_pendingRecordingToInstallPath;
    std::string m_pendingRecordingToInstallName;

    // Game Picker state (Assign background to any installed game)
    bool m_isGamePickerOpen{false};
    int m_gamePickerSelectedIndex{0};
    int m_gamePickerScrollOffset{0};
    uint32_t m_gamePickerOpenedAt{0};
    Variant m_gamePickerPendingVariant;
    std::string m_gamePickerSourceGameName;

    // Integrity check state (Feature 5)
    std::vector<IntegrityIssue> m_detectedIntegrityIssues;
    int m_lastIntegrityTotalChecked{0};

    // State transition debouncing to protect against rapid multi-dispatches
    uint32_t m_previewOpenedAt{0};
    uint32_t m_dialogOpenedAt{0};
    uint32_t m_recordingsOpenedAt{0};
    uint32_t m_lastTabSwitchTime{0};
    uint32_t m_lastTriggerTime{0};
};

} // namespace ui
} // namespace h3h
