import re
from pathlib import Path

# 1. Update config.hpp
cfg_path = Path("downloader/include/core/config.hpp")
cfg_text = cfg_path.read_text(encoding="utf-8")
cfg_text = cfg_text.replace('APP_VERSION = "1.2.2";', 'APP_VERSION = "1.2.3";')
cfg_path.write_text(cfg_text, encoding="utf-8")
print("[+] config.hpp updated to 1.2.3")

# 2. Update version.json
ver_path = Path("version.json")
ver_text = ver_path.read_text(encoding="utf-8")
ver_text = re.sub(r'"latestVersion":\s*"[^"]+"', '"latestVersion": "1.2.3"', ver_text)
ver_text = re.sub(r'"releaseNotes":\s*"[^"]+"', '"releaseNotes": "Fix controller double-dispatch (tab jumping & catalog preview controls), map ZL/ZR tabs, debounce preview transitions"', ver_text)
ver_path.write_text(ver_text, encoding="utf-8")
print("[+] version.json updated to 1.2.3")

# 3. Update app.hpp
app_hpp_path = Path("downloader/include/ui/app.hpp")
app_hpp_text = app_hpp_path.read_text(encoding="utf-8")
if "m_previewOpenedAt" not in app_hpp_text:
    old_hpp_target = "    int m_lastIntegrityTotalChecked{0};\n};"
    new_hpp_target = """    int m_lastIntegrityTotalChecked{0};

    // State transition debouncing to protect against rapid multi-dispatches
    uint32_t m_previewOpenedAt{0};
    uint32_t m_dialogOpenedAt{0};
    uint32_t m_recordingsOpenedAt{0};
    uint32_t m_lastTabSwitchTime{0};
    uint32_t m_lastTriggerTime{0};
};"""
    if old_hpp_target in app_hpp_text:
        app_hpp_text = app_hpp_text.replace(old_hpp_target, new_hpp_target)
    else:
        # try CRLF
        old_hpp_crlf = old_hpp_target.replace("\n", "\r\n")
        new_hpp_crlf = new_hpp_target.replace("\n", "\r\n")
        app_hpp_text = app_hpp_text.replace(old_hpp_crlf, new_hpp_crlf)
    app_hpp_path.write_text(app_hpp_text, encoding="utf-8")
    print("[+] app.hpp updated with debounce timestamps")
else:
    print("[*] app.hpp already has debounce fields")

# 4. Update app.cpp
app_cpp_path = Path("downloader/src/ui/app.cpp")
app_cpp_text = app_cpp_path.read_text(encoding="utf-8")

# Remove SDL_JOYBUTTONDOWN block and add SDL_CONTROLLERDEVICEADDED + triggers
old_joy_block = """        } else if (event.type == SDL_CONTROLLERBUTTONDOWN) {
            onButtonPress(event.cbutton.button);
        } else if (event.type == SDL_JOYBUTTONDOWN) {
            // Direct hardware fallback for Switch Joy-Cons and Pro Controllers
            int btn = -1;
            switch (event.jbutton.button) {
                case 0: btn = 0; break;  // A
                case 1: btn = 1; break;  // B
                case 2: btn = 2; break;  // X
                case 3: btn = 3; break;  // Y
                case 10: btn = 6; break; // Plus (+) -> SDL_CONTROLLER_BUTTON_START (6)
                case 11: btn = 4; break; // Minus (-) -> SDL_CONTROLLER_BUTTON_BACK (4)
                case 6: btn = 9; break;  // L (LEFTSHOULDER)
                case 7: btn = 10; break; // R (RIGHTSHOULDER)
                case 4: btn = 7; break;  // Left stick click (L3)
                case 5: btn = 8; break;  // Right stick click (R3)
                case 13: btn = 11; break; // D-Pad Up
                case 15: btn = 12; break; // D-Pad Down
                case 12: btn = 13; break; // D-Pad Left
                case 14: btn = 14; break; // D-Pad Right
                default: break;
            }
            if (btn != -1) onButtonPress(btn);
        } else if (event.type == SDL_CONTROLLERAXISMOTION) {"""

new_joy_block = """        } else if (event.type == SDL_CONTROLLERBUTTONDOWN) {
            onButtonPress(event.cbutton.button);
        } else if (event.type == SDL_CONTROLLERDEVICEADDED) {
            if (SDL_IsGameController(event.cdevice.which)) {
                SDL_GameControllerOpen(event.cdevice.which);
            }
        } else if (event.type == SDL_CONTROLLERAXISMOTION) {"""

if old_joy_block in app_cpp_text:
    app_cpp_text = app_cpp_text.replace(old_joy_block, new_joy_block)
    print("[+] Replaced SDL_JOYBUTTONDOWN with SDL_CONTROLLERDEVICEADDED")
else:
    old_crlf = old_joy_block.replace("\n", "\r\n")
    new_crlf = new_joy_block.replace("\n", "\r\n")
    if old_crlf in app_cpp_text:
        app_cpp_text = app_cpp_text.replace(old_crlf, new_crlf)
        print("[+] Replaced SDL_JOYBUTTONDOWN with SDL_CONTROLLERDEVICEADDED (CRLF)")
    else:
        print("[-] Could not find old_joy_block in app.cpp")

# Add ZL / ZR trigger handling
old_stick = """                    } else if (event.caxis.value < -18000) {
                        onButtonPress(13 /* DPAD_LEFT */);
                        m_lastStickScrollTime = now;
                    }
                }
            }
        } else if (event.type == SDL_MOUSEWHEEL) {"""

new_stick = """                    } else if (event.caxis.value < -18000) {
                        onButtonPress(13 /* DPAD_LEFT */);
                        m_lastStickScrollTime = now;
                    }
                }
            } else if (event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERLEFT) {
                uint32_t now = SDL_GetTicks();
                if (event.caxis.value > 16000 && (now - m_lastTriggerTime > 250)) {
                    onButtonPress(9 /* LEFTSHOULDER / ZL */);
                    m_lastTriggerTime = now;
                }
            } else if (event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERRIGHT) {
                uint32_t now = SDL_GetTicks();
                if (event.caxis.value > 16000 && (now - m_lastTriggerTime > 250)) {
                    onButtonPress(10 /* RIGHTSHOULDER / ZR */);
                    m_lastTriggerTime = now;
                }
            }
        } else if (event.type == SDL_MOUSEWHEEL) {"""

if old_stick in app_cpp_text:
    app_cpp_text = app_cpp_text.replace(old_stick, new_stick)
    print("[+] Added ZL / ZR trigger handling")
else:
    old_stick_crlf = old_stick.replace("\n", "\r\n")
    new_stick_crlf = new_stick.replace("\n", "\r\n")
    if old_stick_crlf in app_cpp_text:
        app_cpp_text = app_cpp_text.replace(old_stick_crlf, new_stick_crlf)
        print("[+] Added ZL / ZR trigger handling (CRLF)")
    else:
        print("[-] Could not find old_stick in app.cpp")

# Recordings browser debounce:
old_rec = """void App::onButtonPress(int button) {
    // Local Recordings Browser Handler (Feature 3)
    if (m_isRecordingsBrowserOpen && m_activeDialog == DialogType::None && !m_isFullscreenPreview) {"""

new_rec = """void App::onButtonPress(int button) {
    // Local Recordings Browser Handler (Feature 3)
    if (m_isRecordingsBrowserOpen && m_activeDialog == DialogType::None && !m_isFullscreenPreview) {
        if (SDL_GetTicks() - m_recordingsOpenedAt < 150) {
            return;
        }"""

if old_rec in app_cpp_text:
    app_cpp_text = app_cpp_text.replace(old_rec, new_rec)
    print("[+] Added recordings browser debounce")
else:
    old_rec_crlf = old_rec.replace("\n", "\r\n")
    new_rec_crlf = new_rec.replace("\n", "\r\n")
    if old_rec_crlf in app_cpp_text:
        app_cpp_text = app_cpp_text.replace(old_rec_crlf, new_rec_crlf)
        print("[+] Added recordings browser debounce (CRLF)")

# Fullscreen Preview debounce:
old_prev = """    // Fullscreen Preview Input Handler
    if (m_isFullscreenPreview) {"""

new_prev = """    // Fullscreen Preview Input Handler
    if (m_isFullscreenPreview) {
        if (SDL_GetTicks() - m_previewOpenedAt < 200) {
            return;
        }"""

if old_prev in app_cpp_text:
    app_cpp_text = app_cpp_text.replace(old_prev, new_prev)
    print("[+] Added fullscreen preview debounce")
else:
    old_prev_crlf = old_prev.replace("\n", "\r\n")
    new_prev_crlf = new_prev.replace("\n", "\r\n")
    if old_prev_crlf in app_cpp_text:
        app_cpp_text = app_cpp_text.replace(old_prev_crlf, new_prev_crlf)
        print("[+] Added fullscreen preview debounce (CRLF)")

# Dialog debounce:
old_dlg = """    // If Dialog is active, route all input to dialog
    if (m_activeDialog != DialogType::None) {"""

new_dlg = """    // If Dialog is active, route all input to dialog
    if (m_activeDialog != DialogType::None) {
        if (SDL_GetTicks() - m_dialogOpenedAt < 150) {
            return;
        }"""

if old_dlg in app_cpp_text:
    app_cpp_text = app_cpp_text.replace(old_dlg, new_dlg)
    print("[+] Added dialog debounce")
else:
    old_dlg_crlf = old_dlg.replace("\n", "\r\n")
    new_dlg_crlf = new_dlg.replace("\n", "\r\n")
    if old_dlg_crlf in app_cpp_text:
        app_cpp_text = app_cpp_text.replace(old_dlg_crlf, new_dlg_crlf)
        print("[+] Added dialog debounce (CRLF)")

# Tab switching debounce:
old_tabs = """    // Tab switching with Shoulder buttons (L/R)
    if (button == 9 /* LEFTSHOULDER */) {
        int tabInt = static_cast<int>(m_activeTab);
        tabInt = (tabInt == 0) ? 4 : tabInt - 1;
        m_activeTab = static_cast<Tab>(tabInt);
        return;
    }
    if (button == 10 /* RIGHTSHOULDER */) {
        int tabInt = static_cast<int>(m_activeTab);
        tabInt = (tabInt == 4) ? 0 : tabInt + 1;
        m_activeTab = static_cast<Tab>(tabInt);
        return;
    }"""

new_tabs = """    // Tab switching with Shoulder buttons (L/R)
    if (button == 9 /* LEFTSHOULDER */) {
        uint32_t now = SDL_GetTicks();
        if (now - m_lastTabSwitchTime > 150) {
            int tabInt = static_cast<int>(m_activeTab);
            tabInt = (tabInt == 0) ? 4 : tabInt - 1;
            m_activeTab = static_cast<Tab>(tabInt);
            m_lastTabSwitchTime = now;
        }
        return;
    }
    if (button == 10 /* RIGHTSHOULDER */) {
        uint32_t now = SDL_GetTicks();
        if (now - m_lastTabSwitchTime > 150) {
            int tabInt = static_cast<int>(m_activeTab);
            tabInt = (tabInt == 4) ? 0 : tabInt + 1;
            m_activeTab = static_cast<Tab>(tabInt);
            m_lastTabSwitchTime = now;
        }
        return;
    }"""

if old_tabs in app_cpp_text:
    app_cpp_text = app_cpp_text.replace(old_tabs, new_tabs)
    print("[+] Added tab switching debounce")
else:
    old_tabs_crlf = old_tabs.replace("\n", "\r\n")
    new_tabs_crlf = new_tabs.replace("\n", "\r\n")
    if old_tabs_crlf in app_cpp_text:
        app_cpp_text = app_cpp_text.replace(old_tabs_crlf, new_tabs_crlf)
        print("[+] Added tab switching debounce (CRLF)")

# Home tab: handle button 6 (Plus)
old_home = """    if (m_activeTab == Tab::Home) {
        if (button == 0 /* A - Enter My Games */) {
            m_activeTab = Tab::MyGames;
        } else if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
        } else if (button == 2 /* X - Refresh */) {
            fetchRemoteCatalog();
        }
    }"""

new_home = """    if (m_activeTab == Tab::Home) {
        if (button == 0 /* A - Enter My Games */ || button == 6 /* Plus */) {
            m_activeTab = Tab::MyGames;
        } else if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
        } else if (button == 2 /* X - Refresh */) {
            fetchRemoteCatalog();
        }
    }"""

if old_home in app_cpp_text:
    app_cpp_text = app_cpp_text.replace(old_home, new_home)
    print("[+] Added Plus button handling on Home tab")
else:
    old_home_crlf = old_home.replace("\n", "\r\n")
    new_home_crlf = new_home.replace("\n", "\r\n")
    if old_home_crlf in app_cpp_text:
        app_cpp_text = app_cpp_text.replace(old_home_crlf, new_home_crlf)
        print("[+] Added Plus button handling on Home tab (CRLF)")

# MyGames tab: ensure clamp and safe handling for button 6 / 7
old_mygames_plus = """        // Feature 3: Plus (+) or L3 button opens 4IFIR SD Recordings browser immediately
        if (button == 6 /* SDL_CONTROLLER_BUTTON_START (Plus / +) */ ||
            button == 7 /* SDL_CONTROLLER_BUTTON_LEFTSTICK (L3) */) {
            if (!m_installedGames.empty() && m_myGamesSelectedIndex >= 0 &&
                m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& g = m_installedGames[m_myGamesSelectedIndex];
                openRecordingsBrowser(g.titleId, g.name);
                return;
            }
        }"""

new_mygames_plus = """        // Feature 3: Plus (+) or L3 button opens 4IFIR SD Recordings browser immediately
        if (button == 6 /* SDL_CONTROLLER_BUTTON_START (Plus / +) */ ||
            button == 7 /* SDL_CONTROLLER_BUTTON_LEFTSTICK (L3) */) {
            if (!m_installedGames.empty()) {
                int idx = std::clamp(m_myGamesSelectedIndex, 0, static_cast<int>(m_installedGames.size()) - 1);
                const auto& g = m_installedGames[idx];
                openRecordingsBrowser(g.titleId, g.name);
                return;
            } else {
                m_statusNotification = "Нет установленных игр для привязки";
                m_notificationFramesRemaining = 120;
                return;
            }
        }"""

if old_mygames_plus in app_cpp_text:
    app_cpp_text = app_cpp_text.replace(old_mygames_plus, new_mygames_plus)
    print("[+] Added safe clamp for Plus on MyGames tab")
else:
    old_mygames_crlf = old_mygames_plus.replace("\n", "\r\n")
    new_mygames_crlf = new_mygames_plus.replace("\n", "\r\n")
    if old_mygames_crlf in app_cpp_text:
        app_cpp_text = app_cpp_text.replace(old_mygames_crlf, new_mygames_crlf)
        print("[+] Added safe clamp for Plus on MyGames tab (CRLF)")

# Update m_previewOpenedAt in openFullscreenPreviewForGame
old_open_prev_g = """void App::openFullscreenPreviewForGame(const InstalledTitle& g, int variantIndex) {
#ifdef HAS_SDL2
    if (!g.hasCatalogMatch || g.catalogEntry.variants.empty()) return;

    m_previewTitleId = g.titleId;
    m_previewGameName = g.name;
    m_previewVariants = g.catalogEntry.variants;
    m_previewVariantIndex = std::clamp(variantIndex, 0, static_cast<int>(m_previewVariants.size()) - 1);
    m_previewIsGameInstalled = true;
    m_previewHasInstalledCover = g.hasInstalledCover;
    m_previewInstalledVariantId = g.installedVariantId;
    m_previewInstalledCoverSizeBytes = g.installedCoverSizeBytes;
    m_previewInstalledCoverPath = g.installedCoverPath;

    m_isFullscreenPreview = true;
    loadPreviewTexture(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
#endif
}"""

new_open_prev_g = """void App::openFullscreenPreviewForGame(const InstalledTitle& g, int variantIndex) {
#ifdef HAS_SDL2
    if (!g.hasCatalogMatch || g.catalogEntry.variants.empty()) return;

    m_previewTitleId = g.titleId;
    m_previewGameName = g.name;
    m_previewVariants = g.catalogEntry.variants;
    m_previewVariantIndex = std::clamp(variantIndex, 0, static_cast<int>(m_previewVariants.size()) - 1);
    m_previewIsGameInstalled = true;
    m_previewHasInstalledCover = g.hasInstalledCover;
    m_previewInstalledVariantId = g.installedVariantId;
    m_previewInstalledCoverSizeBytes = g.installedCoverSizeBytes;
    m_previewInstalledCoverPath = g.installedCoverPath;

    m_previewOpenedAt = SDL_GetTicks();
    m_isFullscreenPreview = true;
    loadPreviewTexture(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
#endif
}"""

if old_open_prev_g in app_cpp_text:
    app_cpp_text = app_cpp_text.replace(old_open_prev_g, new_open_prev_g)
    print("[+] Added m_previewOpenedAt in openFullscreenPreviewForGame")
else:
    old_g_crlf = old_open_prev_g.replace("\n", "\r\n")
    new_g_crlf = new_open_prev_g.replace("\n", "\r\n")
    if old_g_crlf in app_cpp_text:
        app_cpp_text = app_cpp_text.replace(old_g_crlf, new_g_crlf)
        print("[+] Added m_previewOpenedAt in openFullscreenPreviewForGame (CRLF)")

# Update m_previewOpenedAt in openFullscreenPreviewForCatalogGame
old_open_prev_cat = """    m_isFullscreenPreview = true;
    loadPreviewTexture(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
#endif
}

void App::loadPreviewTexture"""

new_open_prev_cat = """    m_previewOpenedAt = SDL_GetTicks();
    m_isFullscreenPreview = true;
    loadPreviewTexture(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
#endif
}

void App::loadPreviewTexture"""

if old_open_prev_cat in app_cpp_text:
    app_cpp_text = app_cpp_text.replace(old_open_prev_cat, new_open_prev_cat)
    print("[+] Added m_previewOpenedAt in openFullscreenPreviewForCatalogGame")
else:
    old_cat_crlf = old_open_prev_cat.replace("\n", "\r\n")
    new_cat_crlf = new_open_prev_cat.replace("\n", "\r\n")
    if old_cat_crlf in app_cpp_text:
        app_cpp_text = app_cpp_text.replace(old_cat_crlf, new_cat_crlf)
        print("[+] Added m_previewOpenedAt in openFullscreenPreviewForCatalogGame (CRLF)")

# Update m_recordingsOpenedAt in openRecordingsBrowser
old_open_rec = """void App::openRecordingsBrowser(const std::string& titleId, const std::string& gameName) {
    m_recordingsTargetTitleId = titleId;
    m_recordingsTargetGameName = gameName;
    m_localRecordings = Installer::listLocalRecordings(m_platform->getRecordingsDirectory());
    m_recordingsSelectedIndex = 0;
    m_recordingsScrollOffset = 0;
    m_isRecordingsBrowserOpen = true;
}"""

new_open_rec = """void App::openRecordingsBrowser(const std::string& titleId, const std::string& gameName) {
    m_recordingsTargetTitleId = titleId;
    m_recordingsTargetGameName = gameName;
    m_localRecordings = Installer::listLocalRecordings(m_platform->getRecordingsDirectory());
    m_recordingsSelectedIndex = 0;
    m_recordingsScrollOffset = 0;
    m_recordingsOpenedAt = SDL_GetTicks();
    m_isRecordingsBrowserOpen = true;
}"""

if old_open_rec in app_cpp_text:
    app_cpp_text = app_cpp_text.replace(old_open_rec, new_open_rec)
    print("[+] Added m_recordingsOpenedAt in openRecordingsBrowser")
else:
    old_rec_crlf = old_open_rec.replace("\n", "\r\n")
    new_rec_crlf = new_open_rec.replace("\n", "\r\n")
    if old_rec_crlf in app_cpp_text:
        app_cpp_text = app_cpp_text.replace(old_rec_crlf, new_rec_crlf)
        print("[+] Added m_recordingsOpenedAt in openRecordingsBrowser (CRLF)")

# Update m_dialogOpenedAt across dialog triggers
app_cpp_text = re.sub(
    r'(m_activeDialog\s*=\s*DialogType::[A-Za-z0-9_]+;)',
    lambda m: m.group(1) + "\n    m_dialogOpenedAt = SDL_GetTicks();" if "None" not in m.group(1) else m.group(1),
    app_cpp_text
)

app_cpp_path.write_text(app_cpp_text, encoding="utf-8")
print("[+] app.cpp modifications saved successfully")
