from pathlib import Path

app_cpp = Path("downloader/src/ui/app.cpp")
text = app_cpp.read_text(encoding="utf-8")

if '#include "core/installer.hpp"' not in text:
    text = text.replace('#include "core/config.hpp"', '#include "core/config.hpp"\n#include "core/installer.hpp"')

# Also silence unused s in renderTabSettings
text = text.replace(
    'void App::renderTabSettings() {\n    const auto& s = getStrings(m_language);',
    'void App::renderTabSettings() {\n    const auto& s = getStrings(m_language);\n    (void)s;'
)

app_cpp.write_text(text, encoding="utf-8")
print("[+] App includes patched successfully")
