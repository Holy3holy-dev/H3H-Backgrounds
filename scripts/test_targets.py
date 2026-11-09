import os

with open('e:/videofon/downloader/src/ui/app.cpp', 'r', encoding='utf-8') as f:
    code = f.read().replace('\r\n', '\n')

def check(name, target):
    target = target.replace('\r\n', '\n')
    idx = code.find(target)
    if idx != -1:
        print(f"[OK] {name} found at index {idx}")
        return True
    else:
        print(f"[FAIL] {name} NOT found!")
        # Print first line of target
        first_line = target.strip().split('\n')[0]
        print(f"  First line: {repr(first_line)}")
        return False

# 1. App::~App()
check("App::~App()", "App::~App()")

# 2. init renderer
check("init_renderer", """    m_renderer = SDL_CreateRenderer(
        m_window,
        -1,
        SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC
    );

    if (!m_renderer) {""")

# 3. shutdown
check("shutdown", """#ifdef HAS_SDL2
    if (m_collectionThumbTexture) {""")

# 4. update head
check("update_head", """void App::update() {
#ifdef HAS_SDL2""")

# 5. button press head
check("btn_press_head", "void App::onButtonPress(int button) {\n")

# 6. header eq
check("header_eq", """    // Left Branding: App Name + Tag Badge
    // Triple accent bars (TorrentShopNX style logo)
    drawRoundedRect(30, 24, 4, 18, 2, Theme::COLOR_FOCUS_CYAN);
    drawRoundedRect(38, 20, 4, 26, 2, Theme::COLOR_FOCUS_CYAN);
    drawRoundedRect(46, 25, 4, 16, 2, Theme::COLOR_FOCUS_CYAN);""")

# 7. drawDashboardTile
check("drawDashboardTile", "void App::drawDashboardTile(int x, int y, int w, int h, int tileIdx, const std::string& title, const std::string& sub, bool isFocused) {")

# 8. drawTileIconVector
check("drawTileIconVector", "void App::drawTileIconVector(int cx, int cy, int tileIdx, bool isFocused) {")

# 9. renderCategoriesView
check("renderCategoriesView", "void App::renderCategoriesView() {")
check("renderTabVideoIcons", "void App::renderTabVideoIcons() {")

# 10. grid_head
check("grid_head", """    // Breadcrumb Header
    std::string navTitle = "Каталог  >  " + m_activeCategoryName;
    drawText(navTitle, 60, 95, Theme::COLOR_TEXT_PRIMARY, 22);

    // Back to Categories Pill Button
    drawPillButton(1040, 90, 185, 34, "(B) К разделам", false, Theme::COLOR_FOCUS_CYAN);""")

# 11. cat input
check("cat_input", "if (m_catalogViewMode == CatalogViewMode::Categories) {")

# 12. grid toggle
check("grid_toggle", """        } else if (button == 2 /* X - Cycle Sort Mode */) {
            cycleCatalogSortMode();""")

# 13. home sub2
check("home_sub2", """    // 3 4IFIR Cyber-Glass pills with dynamically measured widths
    struct PillData {
        std::string label;
        Color borderCol;
        Color fillCol;
    };
    PillData pData[3] = {
        {"Эксклюзивы Switch (40)", Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_FILL},
        {"RPG и Экшен (45)", Theme::COLOR_FOCUS_PINK, Color{0xEC, 0x48, 0x99, 0x24}},
        {"Инди-хиты (27)", Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_FILL}
    };""")
