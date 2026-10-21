from pathlib import Path

cfg_path = Path("downloader/include/core/config.hpp")
text = cfg_path.read_text(encoding="utf-8")

if "APP_VERSION" not in text:
    old_target = 'static constexpr const char* DEFAULT_CATALOG_URL ='
    replacement = '''    // Application Version
    static constexpr const char* APP_VERSION = "1.0.3";
    static constexpr const char* VERSION_CHECK_URL =
        "https://raw.githubusercontent.com/Holy3holy-dev/H3H-Backgrounds/main/version.json";

    // Default remote catalog URL (GitHub CDN raw)
    static constexpr const char* DEFAULT_CATALOG_URL ='''
    text = text.replace(old_target, replacement, 1)
    cfg_path.write_text(text, encoding="utf-8")
    print("[+] Added APP_VERSION and VERSION_CHECK_URL to config.hpp")
else:
    print("[*] APP_VERSION already present in config.hpp")
