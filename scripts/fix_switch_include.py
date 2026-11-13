with open("downloader/src/platform/switch_platform.cpp", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('#include <nlohmann/json.hpp>', '#include "core/json.hpp"')

with open("downloader/src/platform/switch_platform.cpp", "w", encoding="utf-8") as f:
    f.write(text)
print("Successfully fixed include to core/json.hpp!")
