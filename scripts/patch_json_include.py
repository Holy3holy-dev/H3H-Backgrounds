from pathlib import Path

app_cpp = Path("downloader/src/ui/app.cpp")
text = app_cpp.read_text(encoding="utf-8")

if '#include "core/json.hpp"' not in text:
    text = text.replace('#include "core/installer.hpp"', '#include "core/installer.hpp"\n#include "core/json.hpp"')
    app_cpp.write_text(text, encoding="utf-8")
    print("[+] Added #include \"core/json.hpp\" to app.cpp")
else:
    print("[*] json.hpp already included")
