import sys
from pathlib import Path

app_cpp = Path("downloader/src/ui/app.cpp")
text = app_cpp.read_text(encoding="utf-8")

# 1. Update refreshInstalledGames logic in app.cpp
old_reg_logic = """    // Resolve exact installed variant IDs from persistent registry
    InstalledRegistry::instance().load(m_platform->getAppDirectory());
    for (auto& game : m_installedGames) {
        if (game.hasInstalledCover) {
            std::string regVarId = InstalledRegistry::instance().getVariantId(game.titleId);
            if (!regVarId.empty()) {
                if (regVarId.rfind("local:", 0) == 0) {
                    game.installedVariantId = regVarId;
                    std::string clipName = regVarId.substr(6);
                    bool hasLocal = false;
                    for (const auto& v : game.catalogEntry.variants) {
                        if (v.id == regVarId) { hasLocal = true; break; }
                    }
                    if (!hasLocal) {
                        Variant localVar;
                        localVar.id = regVarId;
                        localVar.name = "Запись 4IFIR: " + clipName;
                        localVar.style = CoverStyle::Gameplay;
                        localVar.url = game.installedCoverPath;
                        localVar.previewUrl = game.installedCoverPath;
                        localVar.notes = "Собственный клип из sdmc:/recordings/";
                        game.catalogEntry.variants.insert(game.catalogEntry.variants.begin(), localVar);
                    }
                } else {
                    for (const auto& v : game.catalogEntry.variants) {
                        if (v.id == regVarId) {
                            game.installedVariantId = regVarId;
                            break;
                        }
                    }
                }
            }

            // If not found in registry (e.g. initial scan), match closest size
            if (game.installedVariantId.empty() && !game.catalogEntry.variants.empty()) {
                if (game.catalogEntry.variants.size() == 1) {
                    game.installedVariantId = game.catalogEntry.variants[0].id;
                } else {
                    int64_t bestDiff = INT64_MAX;
                    std::string bestId;
                    for (const auto& v : game.catalogEntry.variants) {
                        if (v.sizeBytes > 0 && game.installedCoverSizeBytes > 0) {
                            int64_t diff = std::abs((int64_t)v.sizeBytes - (int64_t)game.installedCoverSizeBytes);
                            if (diff < bestDiff) {
                                bestDiff = diff;
                                bestId = v.id;
                            }
                        }
                    }
                    if (!bestId.empty()) {
                        game.installedVariantId = bestId;
                    } else {
                        game.installedVariantId = game.catalogEntry.variants[0].id;
                    }
                }
                InstalledRegistry::instance().setVariantId(m_platform->getAppDirectory(), game.titleId, game.installedVariantId);
            }
        }
    }"""

new_reg_logic = """    // Resolve exact installed variant IDs from persistent registry
    InstalledRegistry::instance().load(m_platform->getAppDirectory());
    for (auto& game : m_installedGames) {
        if (game.hasInstalledCover) {
            std::string regVarId = InstalledRegistry::instance().getVariantId(game.titleId);
            if (!regVarId.empty()) {
                // Trust registry entry explicitly
                game.installedVariantId = regVarId;
                if (regVarId.rfind("local:", 0) == 0) {
                    std::string clipName = regVarId.substr(6);
                    bool hasLocal = false;
                    for (const auto& v : game.catalogEntry.variants) {
                        if (v.id == regVarId) { hasLocal = true; break; }
                    }
                    if (!hasLocal) {
                        Variant localVar;
                        localVar.id = regVarId;
                        localVar.name = "Запись 4IFIR: " + clipName;
                        localVar.style = CoverStyle::Gameplay;
                        localVar.url = game.installedCoverPath;
                        localVar.previewUrl = game.installedCoverPath;
                        localVar.notes = "Собственный клип из sdmc:/recordings/";
                        game.catalogEntry.variants.insert(game.catalogEntry.variants.begin(), localVar);
                    }
                }
            } else if (!game.catalogEntry.variants.empty()) {
                // If not found in registry (e.g. initial scan of manually dropped files):
                // Only associate automatically if exactly 1 variant exists
                if (game.catalogEntry.variants.size() == 1) {
                    game.installedVariantId = game.catalogEntry.variants[0].id;
                    InstalledRegistry::instance().setVariantId(m_platform->getAppDirectory(), game.titleId, game.installedVariantId);
                } else {
                    // Check if file size matches uniquely within 4 KB margin
                    int64_t bestDiff = INT64_MAX;
                    std::string bestId;
                    int matchCount = 0;
                    for (const auto& v : game.catalogEntry.variants) {
                        if (v.sizeBytes > 0 && game.installedCoverSizeBytes > 0) {
                            int64_t diff = std::abs((int64_t)v.sizeBytes - (int64_t)game.installedCoverSizeBytes);
                            if (diff < 4096) {
                                matchCount++;
                                if (diff < bestDiff) {
                                    bestDiff = diff;
                                    bestId = v.id;
                                }
                            }
                        }
                    }
                    if (matchCount == 1 && !bestId.empty()) {
                        game.installedVariantId = bestId;
                        InstalledRegistry::instance().setVariantId(m_platform->getAppDirectory(), game.titleId, game.installedVariantId);
                    }
                }
            }
        }
    }"""

if old_reg_logic in text:
    text = text.replace(old_reg_logic, new_reg_logic)
    print("[+] Patched refreshInstalledGames registry resolution")
else:
    # Try normalized CRLF
    old_crlf = old_reg_logic.replace("\n", "\r\n")
    if old_crlf in text:
        text = text.replace(old_crlf, new_reg_logic.replace("\n", "\r\n"))
        print("[+] Patched refreshInstalledGames registry resolution (CRLF)")
    else:
        print("[!] Warning: old_reg_logic pattern not found in app.cpp")

# 2. Update m_queueTaskFinished to immediately update in-memory m_installedGames
old_queue_done = """    // Process background queue task completion
    if (m_queueTaskFinished.exchange(false)) {
        refreshInstalledGames();
    }"""

new_queue_done = """    // Process background queue task completion
    if (m_queueTaskFinished.exchange(false)) {
        // Immediately sync completed tasks into in-memory m_installedGames for instant UI responsiveness
        {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            for (const auto& task : m_downloadQueue) {
                if (task.state == TaskState::Completed) {
                    for (auto& game : m_installedGames) {
                        if (Config::normalizeTitleId(game.titleId) == Config::normalizeTitleId(task.titleId)) {
                            game.hasInstalledCover = true;
                            game.installedVariantId = task.variant.id;
                            game.installedCoverPath = task.targetFilePath;
                            game.installedCoverSizeBytes = task.variant.sizeBytes;
                            game.status = CoverStatus::Installed;
                        }
                    }
                }
            }
        }
        refreshInstalledGames();
    }"""

if old_queue_done in text:
    text = text.replace(old_queue_done, new_queue_done)
    print("[+] Patched m_queueTaskFinished in-memory instant update")
else:
    old_crlf = old_queue_done.replace("\n", "\r\n")
    if old_crlf in text:
        text = text.replace(old_crlf, new_queue_done.replace("\n", "\r\n"))
        print("[+] Patched m_queueTaskFinished in-memory instant update (CRLF)")
    else:
        print("[!] Warning: old_queue_done pattern not found")

# 3. Reset touch accumulator on SDL_FINGERUP
old_fingerup = """                m_touchDown = false;
                m_isTouchDragging = false;
            }"""
new_fingerup = """                m_touchDown = false;
                m_isTouchDragging = false;
                m_touchDragAccumulator = 0;
            }"""

if old_fingerup in text:
    text = text.replace(old_fingerup, new_fingerup)
    print("[+] Patched SDL_FINGERUP accumulator reset")
else:
    old_crlf = old_fingerup.replace("\n", "\r\n")
    if old_crlf in text:
        text = text.replace(old_crlf, new_fingerup.replace("\n", "\r\n"))
        print("[+] Patched SDL_FINGERUP accumulator reset (CRLF)")

# 4. Replace handleTouchDrag with synchronized index & balanced threshold
old_touch_drag = """void App::handleTouchDrag(int startX, int startY, int deltaY) {
    m_touchDragAccumulator += deltaY;

    // Threshold of 32 pixels for one scroll step
    while (m_touchDragAccumulator <= -32) {
        // Dragging UP -> scroll DOWN
        m_touchDragAccumulator += 32;
        if (m_isCollectionBrowserOpen) {
            if (m_collectionScrollOffset + 5 < static_cast<int>(m_collectionVariants.size())) {
                m_collectionScrollOffset++;
            }
        } else if (m_isGamePickerOpen) {
            if (m_gamePickerScrollOffset + 5 < static_cast<int>(m_installedGames.size())) {
                m_gamePickerScrollOffset++;
            }
        } else if (m_isRecordingsBrowserOpen) {
            if (m_recordingsScrollOffset + 5 < static_cast<int>(m_localRecordings.size())) {
                m_recordingsScrollOffset++;
            }
        } else if (m_activeTab == Tab::Catalog && startX >= 60 && startX <= 1220 && startY >= 160 && startY <= 660) {
            if (m_catalogScrollOffset + 5 < static_cast<int>(m_filteredCatalogGames.size())) {
                m_catalogScrollOffset++;
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 30 && startX <= 480) {
            if (m_myGamesScrollOffset + 7 < static_cast<int>(m_installedGames.size())) {
                m_myGamesScrollOffset++;
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 525 && startX <= 1225) {
            if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& selGame = m_installedGames[m_myGamesSelectedIndex];
                int totalV = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
                if (m_variantScrollOffset + 4 < totalV) {
                    m_variantScrollOffset++;
                }
            }
        }
    }

    while (m_touchDragAccumulator >= 32) {
        // Dragging DOWN -> scroll UP
        m_touchDragAccumulator -= 32;
        if (m_isCollectionBrowserOpen) {
            if (m_collectionScrollOffset > 0) {
                m_collectionScrollOffset--;
            }
        } else if (m_isGamePickerOpen) {
            if (m_gamePickerScrollOffset > 0) {
                m_gamePickerScrollOffset--;
            }
        } else if (m_isRecordingsBrowserOpen) {
            if (m_recordingsScrollOffset > 0) {
                m_recordingsScrollOffset--;
            }
        } else if (m_activeTab == Tab::Catalog && startX >= 60 && startX <= 1220 && startY >= 160 && startY <= 660) {
            if (m_catalogScrollOffset > 0) {
                m_catalogScrollOffset--;
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 30 && startX <= 480) {
            if (m_myGamesScrollOffset > 0) {
                m_myGamesScrollOffset--;
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 525 && startX <= 1225) {
            if (m_variantScrollOffset > 0) {
                m_variantScrollOffset--;
            }
        }
    }
}"""

new_touch_drag = """void App::handleTouchDrag(int startX, int startY, int deltaY) {
    m_touchDragAccumulator += deltaY;

    // Smooth half-row threshold (48px) for natural, fluid scrolling on Switch screen
    const int scrollThreshold = 48;

    while (m_touchDragAccumulator <= -scrollThreshold) {
        // Dragging UP -> scroll DOWN
        m_touchDragAccumulator += scrollThreshold;
        if (m_isCollectionBrowserOpen) {
            if (m_collectionScrollOffset + 5 < static_cast<int>(m_collectionVariants.size())) {
                m_collectionScrollOffset++;
                if (m_collectionSelectedIndex < m_collectionScrollOffset) {
                    m_collectionSelectedIndex = m_collectionScrollOffset;
                }
            }
        } else if (m_isGamePickerOpen) {
            if (m_gamePickerScrollOffset + 5 < static_cast<int>(m_installedGames.size())) {
                m_gamePickerScrollOffset++;
                if (m_gamePickerSelectedIndex < m_gamePickerScrollOffset) {
                    m_gamePickerSelectedIndex = m_gamePickerScrollOffset;
                }
            }
        } else if (m_isRecordingsBrowserOpen) {
            if (m_recordingsScrollOffset + 5 < static_cast<int>(m_localRecordings.size())) {
                m_recordingsScrollOffset++;
                if (m_recordingsSelectedIndex < m_recordingsScrollOffset) {
                    m_recordingsSelectedIndex = m_recordingsScrollOffset;
                }
            }
        } else if (m_activeTab == Tab::Catalog && startY >= 130 && startY <= 670) {
            if (m_catalogScrollOffset + 5 < static_cast<int>(m_filteredCatalogGames.size())) {
                m_catalogScrollOffset++;
                if (m_catalogSelectedIndex < m_catalogScrollOffset) {
                    m_catalogSelectedIndex = m_catalogScrollOffset;
                }
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 30 && startX <= 480) {
            if (m_myGamesScrollOffset + 8 < static_cast<int>(m_installedGames.size())) {
                m_myGamesScrollOffset++;
                if (m_myGamesSelectedIndex < m_myGamesScrollOffset) {
                    m_myGamesSelectedIndex = m_myGamesScrollOffset;
                }
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 500 && startX <= 1250) {
            if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& selGame = m_installedGames[m_myGamesSelectedIndex];
                int totalV = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
                if (m_variantScrollOffset + 4 < totalV) {
                    m_variantScrollOffset++;
                    if (m_selectedVariantIndex < m_variantScrollOffset) {
                        m_selectedVariantIndex = m_variantScrollOffset;
                    }
                }
            }
        }
    }

    while (m_touchDragAccumulator >= scrollThreshold) {
        // Dragging DOWN -> scroll UP
        m_touchDragAccumulator -= scrollThreshold;
        if (m_isCollectionBrowserOpen) {
            if (m_collectionScrollOffset > 0) {
                m_collectionScrollOffset--;
                if (m_collectionSelectedIndex >= m_collectionScrollOffset + 5) {
                    m_collectionSelectedIndex = m_collectionScrollOffset + 4;
                }
            }
        } else if (m_isGamePickerOpen) {
            if (m_gamePickerScrollOffset > 0) {
                m_gamePickerScrollOffset--;
                if (m_gamePickerSelectedIndex >= m_gamePickerScrollOffset + 5) {
                    m_gamePickerSelectedIndex = m_gamePickerScrollOffset + 4;
                }
            }
        } else if (m_isRecordingsBrowserOpen) {
            if (m_recordingsScrollOffset > 0) {
                m_recordingsScrollOffset--;
                if (m_recordingsSelectedIndex >= m_recordingsScrollOffset + 5) {
                    m_recordingsSelectedIndex = m_recordingsScrollOffset + 4;
                }
            }
        } else if (m_activeTab == Tab::Catalog && startY >= 130 && startY <= 670) {
            if (m_catalogScrollOffset > 0) {
                m_catalogScrollOffset--;
                if (m_catalogSelectedIndex >= m_catalogScrollOffset + 5) {
                    m_catalogSelectedIndex = m_catalogScrollOffset + 4;
                }
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 30 && startX <= 480) {
            if (m_myGamesScrollOffset > 0) {
                m_myGamesScrollOffset--;
                if (m_myGamesSelectedIndex >= m_myGamesScrollOffset + 8) {
                    m_myGamesSelectedIndex = m_myGamesScrollOffset + 7;
                }
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 500 && startX <= 1250) {
            if (m_variantScrollOffset > 0) {
                m_variantScrollOffset--;
                if (m_selectedVariantIndex >= m_variantScrollOffset + 4) {
                    m_selectedVariantIndex = m_variantScrollOffset + 3;
                }
            }
        }
    }
}"""

if old_touch_drag in text:
    text = text.replace(old_touch_drag, new_touch_drag)
    print("[+] Patched handleTouchDrag with index sync")
else:
    old_crlf = old_touch_drag.replace("\n", "\r\n")
    if old_crlf in text:
        text = text.replace(old_crlf, new_touch_drag.replace("\n", "\r\n"))
        print("[+] Patched handleTouchDrag with index sync (CRLF)")
    else:
        print("[!] Warning: old_touch_drag pattern not found")

app_cpp.write_text(text, encoding="utf-8")
print("[+] Successfully wrote updated downloader/src/ui/app.cpp")
