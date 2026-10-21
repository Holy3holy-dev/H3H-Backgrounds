from pathlib import Path

p = Path("downloader/include/ui/app.hpp")
text = p.read_text(encoding="utf-8").replace("\r\n", "\n")

# 1. Add MyGamesPane enum
old_tab = """enum class Tab {
    Home = 0,
    MyGames = 1,
    Catalog = 2,
    Downloads = 3,
    Settings = 4
};"""

new_tab = """enum class Tab {
    Home = 0,
    MyGames = 1,
    Catalog = 2,
    Downloads = 3,
    Settings = 4
};

enum class MyGamesPane {
    GamesList,
    VariantsList
};"""

text = text.replace(old_tab, new_tab)

# 2. Add methods
old_render = "    void renderDialog();"
new_render = """    void renderDialog();
    void renderFullscreenPreview();
    void loadPreviewTexture(const Variant& variant);
    void closeFullscreenPreview();"""

text = text.replace(old_render, new_render)

# 3. Add members
old_members = "    int m_downloadsScrollOffset{0};"
new_members = """    int m_downloadsScrollOffset{0};

    // MyGames two-pane navigation & Fullscreen Preview
    MyGamesPane m_myGamesActivePane{MyGamesPane::GamesList};
    bool m_isFullscreenPreview{false};
    SDL_Texture* m_previewTexture{nullptr};
    std::string m_previewCurrentVariantId;
    std::string m_pendingPreviewFileToLoad;
    std::atomic<bool> m_previewLoading{false};"""

text = text.replace(old_members, new_members)

p.write_text(text, encoding="utf-8")
print("[+] Successfully updated downloader/include/ui/app.hpp!")
