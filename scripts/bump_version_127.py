import json
from pathlib import Path

# 1. Update version.json
v_path = Path("version.json")
v_data = {
    "latestVersion": "1.2.7",
    "minRequiredVersion": "1.0.0",
    "downloadUrl": "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.2.7/H3H-Backgrounds.nro",
    "afterDarkDownloadUrl": "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.2.7/H3H-AfterDark.nro",
    "releaseNotes": "v1.2.7: Collection Browser with static mini-previews, Plus/B exit buttons, startup update notification, and expanded After Dark & Main catalogs"
}
v_path.write_text(json.dumps(v_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("[+] version.json updated to 1.2.7")

# 2. Update config.hpp
cfg_path = Path("downloader/include/core/config.hpp")
cfg_text = cfg_path.read_text(encoding="utf-8")
cfg_text = cfg_text.replace('static constexpr const char* APP_VERSION = "1.2.6";', 'static constexpr const char* APP_VERSION = "1.2.7";')
cfg_path.write_text(cfg_text, encoding="utf-8")
print("[+] config.hpp updated to 1.2.7")

# 3. Update build scripts nacp version
for script_name in ["scripts/build_nro.py", "scripts/build_nro_after_dark.py"]:
    sp = Path(script_name)
    if sp.exists():
        st = sp.read_text(encoding="utf-8")
        st = st.replace('app_version = "1.2.5"', 'app_version = "1.2.7"')
        st = st.replace('app_version = "1.2.6"', 'app_version = "1.2.7"')
        sp.write_text(st, encoding="utf-8")
        print(f"[+] {script_name} updated to 1.2.7")
