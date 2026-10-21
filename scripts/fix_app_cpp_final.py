from pathlib import Path
import re

app_cpp_path = Path("downloader/src/ui/app.cpp")
text = app_cpp_path.read_text(encoding="utf-8")

# 1. Remove the misplaced collection_methods from after the closing namespaces
tag = "// ----------------- Collection / Variant Browser Implementation -----------------"
assert tag in text, "tag not found"

parts = text.split(tag)
main_part = parts[0]
methods_part = tag + parts[1]

# In main_part, find the trailing namespace closures:
# } // namespace ui\n} // namespace h3h
ns_close = "} // namespace ui\n} // namespace h3h"
assert ns_close in main_part, "ns_close not found in main_part"

main_without_close = main_part.replace(ns_close, "")
methods_part = methods_part.strip()

new_text = main_without_close.rstrip() + "\n\n" + methods_part + "\n\n" + ns_close + "\n"

# 2. Add Global Exit Handler on '+' (button == 6 / SDL_CONTROLLER_BUTTON_START)
exit_handler = """    // Global Exit Handler: Plus (+) button exits to Homebrew Menu (universal Switch standard)
    if (button == 6 /* SDL_CONTROLLER_BUTTON_START (Plus / +) */) {
        if (m_isCollectionBrowserOpen) {
            closeCollectionBrowser();
            return;
        }
        if (m_isGamePickerOpen) {
            closeGamePicker();
            return;
        }
        if (m_isRecordingsBrowserOpen) {
            closeRecordingsBrowser();
            return;
        }
        if (m_isFullscreenPreview) {
            closeFullscreenPreview();
            return;
        }
        if (m_activeDialog != DialogType::None) {
            m_activeDialog = DialogType::None;
            return;
        }
        // Exit application cleanly to hbmenu
        m_running = false;
        return;
    }
"""

target_hook = "    // Target Game Picker Handler (Assign video theme to any installed game)"
assert target_hook in new_text, "target_hook not found"
new_text = new_text.replace(target_hook, exit_handler + "\n" + target_hook, 1)

# In MyGames left column, add button == 1 (B) to exit app
m = re.search(r'(// LEFT COLUMN: Games List navigation\s+)(if \(button == 11)', new_text)
assert m, "Games List navigation not found"
new_text = new_text[:m.start()] + m.group(1) + "if (button == 1 /* B - Exit to hbmenu */) {\n                m_running = false;\n                return;\n            }\n            " + m.group(2) + new_text[m.end():]

# In Home tab, add button == 1 (B) to exit app, and remove button == 6 since + now exits globally
target_home = """    // View-specific input handling
    if (m_activeTab == Tab::Home) {
        if (button == 0 /* A - Enter My Games */ || button == 6 /* Plus */) {
            m_activeTab = Tab::MyGames;
        } else if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
        } else if (button == 2 /* X - Refresh */) {
            fetchRemoteCatalog();
        }
    }"""
repl_home = """    // View-specific input handling
    if (m_activeTab == Tab::Home) {
        if (button == 1 /* B - Exit to hbmenu */) {
            m_running = false;
            return;
        }
        if (button == 0 /* A - Enter My Games */) {
            m_activeTab = Tab::MyGames;
        } else if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
        } else if (button == 2 /* X - Refresh */) {
            fetchRemoteCatalog();
        }
    }"""
assert target_home in new_text, "target_home not found"
new_text = new_text.replace(target_home, repl_home, 1)

# In MyGames, change button 6 (which was Plus) to just button 7 (L3) so Plus does not conflict
target_mygames_plus = """        // Feature 3: Plus (+) or L3 button opens 4IFIR SD Recordings browser immediately
        if (button == 6 /* SDL_CONTROLLER_BUTTON_START (Plus / +) */ ||
            button == 7 /* SDL_CONTROLLER_BUTTON_LEFTSTICK (L3) */) {"""
repl_mygames_plus = """        // Feature 3: L3 (Left Stick click) opens 4IFIR SD Recordings browser immediately
        if (button == 7 /* SDL_CONTROLLER_BUTTON_LEFTSTICK (L3) */) {"""
assert target_mygames_plus in new_text, "target_mygames_plus not found"
new_text = new_text.replace(target_mygames_plus, repl_mygames_plus, 1)

with open(app_cpp_path, "w", newline="\n", encoding="utf-8") as f:
    f.write(new_text)

print("[SUCCESS] app.cpp fixed!")
