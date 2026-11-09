import os

hpp_path = "e:/videofon/downloader/include/ui/app.hpp"
with open(hpp_path, "r", encoding="utf-8") as f:
    hpp = f.read().replace("\r\n", "\n")

# Add declarations
old_decl = """    void drawCategoryCard(int x, int y, int w, int h, const std::string& iconType, const std::string& title, const std::string& desc, const std::string& countText, bool isFocused, Color accentCol);
    void drawPillButton(int x, int y, int w, int h, const std::string& text, bool isFocused, Color textCol = Theme::COLOR_TEXT_PRIMARY);

private:"""

new_decl = """    void drawCategoryCard(int x, int y, int w, int h, const std::string& iconType, const std::string& title, const std::string& desc, const std::string& countText, bool isFocused, Color accentCol);
    void drawPillButton(int x, int y, int w, int h, const std::string& text, bool isFocused, Color textCol = Theme::COLOR_TEXT_PRIMARY);

    void loadTabIcons();
    void freeTabIcons();

private:"""

assert old_decl in hpp, "old_decl not found"
hpp = hpp.replace(old_decl, new_decl, 1)

# Add member variables
old_members = """    // Home Dashboard State
    int m_homeFocusedTile{0}; // 0: Catalog, 1: VideoIcons, 2: MyGames, 3: Downloads, 4: Settings"""

new_members = """    // Dynamic 60 FPS UI Animation states
    float m_tileAnimScale[5] {1.0f, 1.0f, 1.0f, 1.0f, 1.0f};
    float m_tabTransitionAlpha {255.0f};
    float m_buttonPressAnim {0.0f};
    float m_gearAngle {0.0f};
    float m_downloadArrowBob {0.0f};
    float m_equalizerHeights[3] {18.0f, 26.0f, 16.0f};
    float m_glowPulse {1.0f};

    // Tab Icon Textures (160x160 4IFIR Cyber-Glass Assets)
    SDL_Texture* m_tabIconTextures[5] {nullptr, nullptr, nullptr, nullptr, nullptr};

    // Home Dashboard State
    int m_homeFocusedTile{0}; // 0: Catalog, 1: VideoIcons, 2: MyGames, 3: Downloads, 4: Settings"""

assert old_members in hpp, "old_members not found"
hpp = hpp.replace(old_members, new_members, 1)

with open(hpp_path, "w", encoding="utf-8") as f:
    f.write(hpp)

print("Updated app.hpp with animations and tab icon textures!")
