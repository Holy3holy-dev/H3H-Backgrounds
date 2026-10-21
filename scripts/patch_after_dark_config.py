from pathlib import Path

config_path = Path("downloader/include/core/config.hpp")
content = config_path.read_text(encoding="utf-8")

old_block = """    static constexpr const char* DEFAULT_SWITCH_APP_DIR    = "sdmc:/switch/H3H-Backgrounds";
    
    // Default remote catalog URL (GitHub CDN raw)
        // Application Version
    static constexpr const char* APP_VERSION = "1.2.5";
    static constexpr const char* VERSION_CHECK_URL =
        "https://raw.githubusercontent.com/Holy3holy-dev/H3H-Backgrounds/main/version.json";

    // Default remote catalog URL (GitHub CDN raw)
    static constexpr const char* DEFAULT_CATALOG_URL = 
        "https://raw.githubusercontent.com/Holy3holy-dev/H3H-Backgrounds/main/catalog/data/catalog.json";"""

new_block = """#ifdef H3H_AFTER_DARK
    static constexpr const char* DEFAULT_SWITCH_APP_DIR    = "sdmc:/switch/H3H-AfterDark";
    static constexpr const char* APP_NAME                  = "H3H After Dark (18+)";
    static constexpr const char* DEFAULT_CATALOG_URL       = "https://raw.githubusercontent.com/Holy3holy-dev/H3H-Backgrounds/main/catalog/data/catalog_after_dark.json";
#else
    static constexpr const char* DEFAULT_SWITCH_APP_DIR    = "sdmc:/switch/H3H-Backgrounds";
    static constexpr const char* APP_NAME                  = "H3H Backgrounds";
    static constexpr const char* DEFAULT_CATALOG_URL       = "https://raw.githubusercontent.com/Holy3holy-dev/H3H-Backgrounds/main/catalog/data/catalog.json";
#endif
    
    // Application Version
    static constexpr const char* APP_VERSION = "1.2.5";
    static constexpr const char* VERSION_CHECK_URL =
        "https://raw.githubusercontent.com/Holy3holy-dev/H3H-Backgrounds/main/version.json";"""

# Normalize CRLF
content_norm = content.replace("\r\n", "\n")
old_block_norm = old_block.replace("\r\n", "\n")
new_block_norm = new_block.replace("\r\n", "\n")

assert old_block_norm in content_norm, "Target block not found in config.hpp"
content_norm = content_norm.replace(old_block_norm, new_block_norm)
config_path.write_text(content_norm, encoding="utf-8")
print("[+] config.hpp updated successfully!")
