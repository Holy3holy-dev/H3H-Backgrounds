# scripts/patch_app_hpp_v120.py
from pathlib import Path

p = Path("downloader/include/ui/app.hpp")
text = p.read_text(encoding="utf-8")

old_dialog = """enum class DialogType {
    None,
    ConfirmInstall,
    ConfirmInstallAll,
    ConfirmRestore,
    ConfirmDelete,
    MessageAlert,
    UpdateProgress,
    UpdateSuccess
};"""

new_dialog = """enum class DialogType {
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
};"""

text = text.replace(old_dialog, new_dialog)

old_renders = """    void renderFullscreenPreview();
    void loadPreviewTexture(const std::string& titleId, const Variant& variant);
    void openFullscreenPreviewForGame(const InstalledTitle& g, int variantIndex);
    void openFullscreenPreviewForCatalogGame(const GameCatalogEntry& entry, int variantIndex);
    void closeFullscreenPreview();"""

new_renders = """    void renderFullscreenPreview();
    void loadPreviewTexture(const std::string& titleId, const Variant& variant);
    void openFullscreenPreviewForGame(const InstalledTitle& g, int variantIndex);
    void openFullscreenPreviewForCatalogGame(const GameCatalogEntry& entry, int variantIndex);
    void closeFullscreenPreview();

    // Feature 3: Local 4IFIR Recordings Browser
    void openRecordingsBrowser(const std::string& titleId, const std::string& gameName);
    void closeRecordingsBrowser();
    void renderRecordingsBrowser();
    void executeInstallLocalRecording();

    // Feature 5: Integrity Scanner
    void runIntegrityCheck();
    void executeDeleteCorruptedCovers();"""

text = text.replace(old_renders, new_renders)

old_fields = """    uint32_t m_lastStickScrollTime{0};
};"""

new_fields = """    uint32_t m_lastStickScrollTime{0};

    // Local recordings browser (Feature 3)
    bool m_isRecordingsBrowserOpen{false};
    std::vector<LocalRecording> m_localRecordings;
    int m_recordingsSelectedIndex{0};
    int m_recordingsScrollOffset{0};
    std::string m_recordingsTargetTitleId;
    std::string m_recordingsTargetGameName;
    std::string m_pendingRecordingToInstallPath;
    std::string m_pendingRecordingToInstallName;

    // Integrity check state (Feature 5)
    std::vector<IntegrityIssue> m_detectedIntegrityIssues;
    int m_lastIntegrityTotalChecked{0};
};"""

text = text.replace(old_fields, new_fields)

p.write_text(text, encoding="utf-8")
print("Patched app.hpp successfully")
