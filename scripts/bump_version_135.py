"""
Bumps version to 1.3.5 across config.hpp, Makefile, and version.json.
"""
import json
from pathlib import Path

def bump():
    # 1. config.hpp
    cfg_path = Path("downloader/include/core/config.hpp")
    cfg_text = cfg_path.read_text(encoding="utf-8")
    cfg_text = cfg_text.replace('APP_VERSION = "1.3.3";', 'APP_VERSION = "1.3.5";')
    cfg_text = cfg_text.replace('APP_VERSION = "1.3.4";', 'APP_VERSION = "1.3.5";')
    cfg_path.write_text(cfg_text, encoding="utf-8")
    print("[+] Bumped downloader/include/core/config.hpp to 1.3.5")

    # 2. Makefile
    mk_path = Path("downloader/Makefile")
    mk_text = mk_path.read_text(encoding="utf-8")
    mk_text = mk_text.replace('APP_VERSION := 1.3.3', 'APP_VERSION := 1.3.5')
    mk_text = mk_text.replace('APP_VERSION := 1.3.4', 'APP_VERSION := 1.3.5')
    mk_path.write_text(mk_text, encoding="utf-8")
    print("[+] Bumped downloader/Makefile to 1.3.5")

    # 3. version.json
    v_path = Path("version.json")
    v_data = {
        "latestVersion": "1.3.5",
        "minRequiredVersion": "1.0.0",
        "downloadUrl": "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.3.5/H3H-Backgrounds.nro",
        "afterDarkDownloadUrl": "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.3.5/H3H-AfterDark.nro",
        "releaseNotes": "v1.3.5: 🔲 Раздельная установка видеоиконок 4IFIR и видеофонов, кнопка [⚡ Иконка] на карточках, независимое удаление и шаблон Switch Home"
    }
    v_path.write_text(json.dumps(v_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[+] Bumped version.json to 1.3.5")

if __name__ == "__main__":
    bump()
