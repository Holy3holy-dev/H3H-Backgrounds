with open('downloader/src/ui/app.cpp', 'r', encoding='utf-8') as f:
    code = f.read().replace('\r\n', '\n')

# 1. Remove the mistakenly placed drawPrompt block from onButtonPress (around line 2251)
bad_block = """    } else if (m_activeTab == Tab::Catalog) {
        drawPrompt("A", "Выбрать", Theme::COLOR_FOCUS_CYAN);
        drawPrompt("B", "Назад", Theme::COLOR_TEXT_MUTED);
        drawPrompt("ZL", "Просмотр", Theme::COLOR_FOCUS_CYAN);
        drawPrompt("-", "В избр. ★", Theme::COLOR_FOCUS_PINK);
        drawPrompt("L/R", "Разделы", Theme::COLOR_FOCUS_CYAN);
        drawPrompt("Y", "Поиск", Theme::COLOR_TEXT_PRIMARY);
        drawPrompt("X", "Сортировка", Theme::COLOR_TEXT_PRIMARY);
    } else if (m_activeTab == Tab::MyGames) {"""

clean_block = """    } else if (m_activeTab == Tab::MyGames) {"""

assert bad_block in code, "bad_block not found"
code = code.replace(bad_block, clean_block, 1)
print("[+] Removed drawPrompt from onButtonPress")

# 2. Fix openFullscreenPreview -> openFullscreenPreviewForCatalogGame
bad_preview = "openFullscreenPreview(curGame.titleId, curGame.variants, 0);"
good_preview = "openFullscreenPreviewForCatalogGame(curGame, 0);"
assert bad_preview in code, "bad_preview not found"
code = code.replace(bad_preview, good_preview, 1)
print("[+] Fixed openFullscreenPreviewForCatalogGame call")

# 3. Update renderFooter for Tab::Catalog properly
old_footer_cat = """    } else if (m_activeTab == Tab::Catalog) {
        if (m_catalogViewMode == CatalogViewMode::Categories) {
            drawPrompt("A", "OK", Theme::COLOR_FOCUS_CYAN);
            drawPrompt("B", "Назад", Theme::COLOR_TEXT_PRIMARY);
            drawPrompt("-", "Сброс", Theme::COLOR_TEXT_PRIMARY);
            drawPrompt("Y", "Поиск", Theme::COLOR_FOCUS_CYAN);
        } else {
            drawPrompt("A", "Выбрать", Theme::COLOR_FOCUS_CYAN);
            drawPrompt("B", "Назад", Theme::COLOR_TEXT_MUTED);
            drawPrompt("ZL", "Просмотр", Theme::COLOR_TEXT_MUTED);
            drawPrompt("Y", "Поиск", Theme::COLOR_TEXT_PRIMARY);
            drawPrompt("X", "Сортировка", Theme::COLOR_TEXT_PRIMARY);
        }"""

# Find by regex/prefix because of possible encoding
idx_fc = code.find("} else if (m_activeTab == Tab::Catalog) {\n        if (m_catalogViewMode == CatalogViewMode::Categories) {")
idx_fc_next = code.find("} else if (m_activeTab == Tab::MyGames) {", idx_fc)
assert idx_fc != -1 and idx_fc_next != -1, "Footer Tab::Catalog block not found"

new_footer_cat = """} else if (m_activeTab == Tab::Catalog) {
        drawPrompt("A", "Выбрать", Theme::COLOR_FOCUS_CYAN);
        drawPrompt("B", "Назад", Theme::COLOR_TEXT_MUTED);
        drawPrompt("ZL", "Просмотр", Theme::COLOR_FOCUS_CYAN);
        drawPrompt("-", "В избр. ★", Theme::COLOR_FOCUS_PINK);
        drawPrompt("L/R", "Разделы", Theme::COLOR_FOCUS_CYAN);
        drawPrompt("Y", "Поиск", Theme::COLOR_TEXT_PRIMARY);
        drawPrompt("X", "Сортировка", Theme::COLOR_TEXT_PRIMARY);
    """

code = code[:idx_fc] + new_footer_cat + code[idx_fc_next:]
print("[+] Updated renderFooter for Tab::Catalog")

with open('downloader/src/ui/app.cpp', 'w', encoding='utf-8') as f:
    f.write(code)

print("[+] All compiler errors fixed!")
