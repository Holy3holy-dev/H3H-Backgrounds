# Bump version to v1.3.0 across config.hpp, Makefile, and version.json
import json
from pathlib import Path

# 1. Update config.hpp
cfg_path = Path("downloader/include/core/config.hpp")
cfg_text = cfg_path.read_text(encoding="utf-8")
assert 'APP_VERSION = "1.2.9"' in cfg_text, "1.2.9 not in config.hpp"
cfg_text = cfg_text.replace('APP_VERSION = "1.2.9"', 'APP_VERSION = "1.3.0"')
cfg_path.write_text(cfg_text, encoding="utf-8")
print("[+] config.hpp updated to v1.3.0")

# 2. Update Makefile
mk_path = Path("downloader/Makefile")
mk_text = mk_path.read_text(encoding="utf-8")
mk_text = mk_text.replace("APP_VERSION := 1.0.0", "APP_VERSION := 1.3.0")
mk_text = mk_text.replace("APP_VERSION := 1.2.9", "APP_VERSION := 1.3.0")
mk_path.write_text(mk_text, encoding="utf-8")
print("[+] Makefile updated to v1.3.0")

# 3. Update version.json
v_path = Path("version.json")
version_data = {
    "latestVersion": "1.3.0",
    "minRequiredVersion": "1.0.0",
    "downloadUrl": "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.3.0/H3H-Backgrounds.nro",
    "afterDarkDownloadUrl": "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.3.0/H3H-AfterDark.nro",
    "releaseNotes": "v1.3.0: 🎮 Metal Gear Rising & Solid фоны, ⚡ Быстрый скролл ZL/ZR во всех вкладках, 👆 Сенсорное управление 2.0 (тачскрин плеера и модалок), 🔤 Полноценный поиск на русском (UTF-8 Cyrillic) и фиксы плеера"
}
v_path.write_text(json.dumps(version_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("[+] version.json updated to v1.3.0")
