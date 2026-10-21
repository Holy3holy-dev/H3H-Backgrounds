from pathlib import Path

# 1. Update config.hpp
cfg_path = Path("downloader/include/core/config.hpp")
c = cfg_path.read_text(encoding="utf-8")
c = c.replace('"1.2.5"', '"1.2.6"')
cfg_path.write_text(c, encoding="utf-8")
print("[+] config.hpp updated to v1.2.6")

# 2. Update version.json
vjson_path = Path("version.json")
vjson = """{
  "latestVersion": "1.2.6",
  "minRequiredVersion": "1.0.0",
  "downloadUrl": "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-Backgrounds.nro",
  "afterDarkDownloadUrl": "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-AfterDark.nro",
  "releaseNotes": "v1.2.6: Direct HEVC/AVC pass-through upload, After Dark standalone in-app updater support, 17 curated mature video themes across NieR/FF7/Zelda/Bayonetta, and fast ffmpeg encoding"
}
"""
vjson_path.write_text(vjson, encoding="utf-8")
print("[+] version.json updated to v1.2.6")

# 3. Update app.cpp updater
app_cpp_path = Path("downloader/src/ui/app.cpp")
app_cpp = app_cpp_path.read_text(encoding="utf-8")

old_update_block = """        // Step 2: New version found -> download and install
        m_dialogTitle = (m_language == Language::Russian)
            ? ("Загрузка обновления v" + latestVer)
            : ("Downloading update v" + latestVer);
        m_dialogMessage = (m_language == Language::Russian)
            ? "Загрузка H3H-Backgrounds.nro с GitHub..."
            : "Downloading H3H-Backgrounds.nro from GitHub...";

        std::string nroUrl = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-Backgrounds.nro";
        std::string appDir = m_platform->getAppDirectory();
        std::string tempNro = appDir + "/H3H-Backgrounds.nro.tmp";
        
        std::vector<std::string> targetNros = {
            appDir + "/H3H-Backgrounds.nro",
            "sdmc:/switch/H3H-Backgrounds/H3H-Backgrounds.nro",
            "sdmc:/switch/H3H-Backgrounds.nro"
        };"""

new_update_block = """        // Step 2: New version found -> download and install
#ifdef H3H_AFTER_DARK
        std::string nroFileName = "H3H-AfterDark.nro";
        std::string defaultNroUrl = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-AfterDark.nro";
        std::string targetSubdir = "H3H-AfterDark";
#else
        std::string nroFileName = "H3H-Backgrounds.nro";
        std::string defaultNroUrl = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-Backgrounds.nro";
        std::string targetSubdir = "H3H-Backgrounds";
#endif

        m_dialogTitle = (m_language == Language::Russian)
            ? ("Загрузка обновления v" + latestVer)
            : ("Downloading update v" + latestVer);
        m_dialogMessage = (m_language == Language::Russian)
            ? ("Загрузка " + nroFileName + " с GitHub...")
            : ("Downloading " + nroFileName + " from GitHub...");

        std::string nroUrl = defaultNroUrl;
        if (!versionJsonStr.empty()) {
            try {
                auto vJson = nlohmann::json::parse(versionJsonStr);
#ifdef H3H_AFTER_DARK
                if (vJson.contains("afterDarkDownloadUrl")) {
                    nroUrl = vJson["afterDarkDownloadUrl"].get<std::string>();
                }
#else
                if (vJson.contains("downloadUrl")) {
                    nroUrl = vJson["downloadUrl"].get<std::string>();
                }
#endif
            } catch (...) {}
        }

        std::string appDir = m_platform->getAppDirectory();
        std::string tempNro = appDir + "/" + nroFileName + ".tmp";
        
        std::vector<std::string> targetNros = {
            appDir + "/" + nroFileName,
            "sdmc:/switch/" + targetSubdir + "/" + nroFileName,
            "sdmc:/switch/" + nroFileName
        };"""

if old_update_block in app_cpp:
    app_cpp = app_cpp.replace(old_update_block, new_update_block)
    app_cpp_path.write_text(app_cpp, encoding="utf-8")
    print("[+] app.cpp updated for After Dark updater!")
else:
    print("[-] Warning: old_update_block not found in app.cpp")
