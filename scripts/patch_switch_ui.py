from pathlib import Path

app_path = Path("downloader/src/ui/app.cpp")
c = app_path.read_text(encoding="utf-8")
is_crlf = "\r\n" in c
if is_crlf:
    c = c.replace("\r\n", "\n")

# 1. Collection Browser: add ZL / ZR navigation
target_cb_buttons = """        if (button == 14 /* RIGHT - Page Down 5 */) {
            m_collectionSelectedIndex = std::min(vCount - 1, m_collectionSelectedIndex + 5);
            if (m_collectionSelectedIndex >= m_collectionScrollOffset + 5) {
                m_collectionScrollOffset = std::max(0, m_collectionSelectedIndex - 5 + 1);
            }
            if (!m_collectionVariants.empty()) {
                loadCollectionThumbnail(m_collectionVariants[m_collectionSelectedIndex]);
            }
            return;
        }"""

replacement_cb_buttons = """        if (button == 14 /* RIGHT - Page Down 5 */) {
            m_collectionSelectedIndex = std::min(vCount - 1, m_collectionSelectedIndex + 5);
            if (m_collectionSelectedIndex >= m_collectionScrollOffset + 5) {
                m_collectionScrollOffset = std::max(0, m_collectionSelectedIndex - 5 + 1);
            }
            if (!m_collectionVariants.empty()) {
                loadCollectionThumbnail(m_collectionVariants[m_collectionSelectedIndex]);
            }
            return;
        }
        if (button == 15 /* ZL - Fast Page Up 15 */) {
            m_collectionSelectedIndex = std::max(0, m_collectionSelectedIndex - 15);
            if (m_collectionSelectedIndex < m_collectionScrollOffset) {
                m_collectionScrollOffset = m_collectionSelectedIndex;
            }
            if (!m_collectionVariants.empty()) {
                loadCollectionThumbnail(m_collectionVariants[m_collectionSelectedIndex]);
            }
            return;
        }
        if (button == 16 /* ZR - Fast Page Down 15 */) {
            m_collectionSelectedIndex = std::min(vCount - 1, m_collectionSelectedIndex + 15);
            if (m_collectionSelectedIndex >= m_collectionScrollOffset + 5) {
                m_collectionScrollOffset = std::max(0, m_collectionSelectedIndex - 5 + 1);
            }
            if (!m_collectionVariants.empty()) {
                loadCollectionThumbnail(m_collectionVariants[m_collectionSelectedIndex]);
            }
            return;
        }"""

if target_cb_buttons in c:
    c = c.replace(target_cb_buttons, replacement_cb_buttons)
    print("[+] Patched CollectionBrowser ZL/ZR fast scrolling")
else:
    print("[-] target_cb_buttons not found")

# 2. Fix Double-Escape in Fullscreen Preview (remove closeCollectionBrowser())
target_preview_close = """        if (button == 1 /* B */ || button == 2 /* X */) {
            closeFullscreenPreview();
    closeCollectionBrowser();
            return;
        }"""

replacement_preview_close = """        if (button == 1 /* B */ || button == 2 /* X */) {
            closeFullscreenPreview();
            return;
        }"""

if target_preview_close in c:
    c = c.replace(target_preview_close, replacement_preview_close)
    print("[+] Patched FullscreenPreview B-button return")
else:
    print("[-] target_preview_close not found")

# 3. MyGames Tab: ZL/ZR fast scrolling and polite notification for games without variants
target_mygames_a = """            } else if (button == 14 /* DPAD_RIGHT */ || button == 0 /* A */) {
                // Move focus to right variants column or open collection browser
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.titleId == "0000000000000000" || g.catalogEntry.variants.size() > 8) {
                        openCollectionBrowser(g.catalogEntry);
                    } else if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        m_myGamesActivePane = MyGamesPane::VariantsList;
                        m_selectedVariantIndex = 0;
                    }
                }
            } else if (button == 2 /* X - Fullscreen Preview */) {
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        openFullscreenPreviewForGame(g, m_selectedVariantIndex);
                    } else {
                        m_activeTab = Tab::Catalog;
                    }
                }"""

replacement_mygames_a = """            } else if (button == 15 /* ZL - Fast Page Up 10 */) {
                m_myGamesSelectedIndex = std::max(0, m_myGamesSelectedIndex - 10);
                m_selectedVariantIndex = 0;
                m_variantScrollOffset = 0;
                return;
            } else if (button == 16 /* ZR - Fast Page Down 10 */) {
                if (!m_installedGames.empty()) {
                    m_myGamesSelectedIndex = std::min(static_cast<int>(m_installedGames.size()) - 1, m_myGamesSelectedIndex + 10);
                    m_selectedVariantIndex = 0;
                    m_variantScrollOffset = 0;
                }
                return;
            } else if (button == 14 /* DPAD_RIGHT */ || button == 0 /* A */) {
                // Move focus to right variants column or open collection browser
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.titleId == "0000000000000000" || g.catalogEntry.variants.size() > 8) {
                        openCollectionBrowser(g.catalogEntry);
                    } else if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        m_myGamesActivePane = MyGamesPane::VariantsList;
                        m_selectedVariantIndex = 0;
                    } else {
                        m_statusNotification = (m_language == Language::Russian)
                            ? "Для этой игры пока нет видеофонов в каталоге"
                            : "No video themes available for this game yet";
                        m_notificationFramesRemaining = 120;
                    }
                }
            } else if (button == 2 /* X - Fullscreen Preview */) {
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        openFullscreenPreviewForGame(g, m_selectedVariantIndex);
                    } else {
                        m_statusNotification = (m_language == Language::Russian)
                            ? "Нет доступных видео для предпросмотра"
                            : "No video preview available";
                        m_notificationFramesRemaining = 120;
                    }
                }"""

if target_mygames_a in c:
    c = c.replace(target_mygames_a, replacement_mygames_a)
    print("[+] Patched MyGames navigation & dead-end feedback")
else:
    print("[-] target_mygames_a not found")

# 4. Catalog Tab: hook button 15 (ZL) for batch install or fast scroll, and button 16 (ZR) for fast scroll
target_catalog_nav = """        } else if (button == 13 /* DPAD_LEFT - Page Up 5 */) {
            m_catalogSelectedIndex = std::max(0, m_catalogSelectedIndex - 5);
        } else if (button == 14 /* DPAD_RIGHT - Page Down 5 */) {
            if (totalGames > 0) m_catalogSelectedIndex = std::min(totalGames - 1, m_catalogSelectedIndex + 5);
        } else if (button == 0 /* A - Enter Collection Browser */) {"""

replacement_catalog_nav = """        } else if (button == 13 /* DPAD_LEFT - Page Up 5 */) {
            m_catalogSelectedIndex = std::max(0, m_catalogSelectedIndex - 5);
        } else if (button == 14 /* DPAD_RIGHT - Page Down 5 */) {
            if (totalGames > 0) m_catalogSelectedIndex = std::min(totalGames - 1, m_catalogSelectedIndex + 5);
        } else if (button == 15 /* ZL - Batch Install or Fast Scroll Up 15 */) {
            if (!m_batchSelectedTitleIds.empty()) {
                installBatchSelected();
            } else {
                m_catalogSelectedIndex = std::max(0, m_catalogSelectedIndex - 15);
            }
            return;
        } else if (button == 16 /* ZR - Fast Scroll Down 15 */) {
            if (totalGames > 0) {
                m_catalogSelectedIndex = std::min(totalGames - 1, m_catalogSelectedIndex + 15);
            }
            return;
        } else if (button == 0 /* A - Enter Collection Browser */) {"""

if target_catalog_nav in c:
    c = c.replace(target_catalog_nav, replacement_catalog_nav)
    print("[+] Patched Catalog ZL batch install and ZL/ZR fast scrolling")
else:
    print("[-] target_catalog_nav not found")

# 5. Footer Hints update
target_footer = """        } else if (!m_catalogSearchQuery.empty()) {
            hints = "[▲/▼] Выбор   [◀/▶] ±5   [A] Фоны   [R3/L3] Чекбокс [✓]   [X] Сорт   [Y] Поиск   [-] Сброс   [B] Назад";
        } else {
            hints = "[▲/▼] Выбор   [◀/▶] ±5   [A] Фоны   [R3/L3] Чекбокс [✓]   [X] Сорт   [Y] Поиск   [-] Обновить   [B] Назад";
        }"""

replacement_footer = """        } else if (!m_catalogSearchQuery.empty()) {
            hints = "[▲/▼] Выбор   [ZL/ZR] ±15   [A] Фоны   [R3] Чекбокс   [X] Сорт   [Y] Поиск   [-] Сброс   [B] Назад";
        } else {
            hints = "[▲/▼] Выбор   [ZL/ZR] ±15   [A] Фоны   [R3] Чекбокс   [X] Сорт   [Y] Поиск   [-] Обновить   [B] Назад";
        }"""

if target_footer in c:
    c = c.replace(target_footer, replacement_footer)
    print("[+] Patched Footer hints")
else:
    print("[-] target_footer not found")

if is_crlf:
    c = c.replace("\n", "\r\n")

app_path.write_text(c, encoding="utf-8")
print("[+] Finished updating downloader/src/ui/app.cpp!")
