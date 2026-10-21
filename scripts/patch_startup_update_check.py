from pathlib import Path

# 1. Update app.hpp
app_hpp_path = Path("downloader/include/ui/app.hpp")
app_hpp_text = app_hpp_path.read_text(encoding="utf-8")

target_hpp = "    void openCollectionBrowser(const GameCatalogEntry& entry);"
repl_hpp = "    void checkForUpdatesStartupAsync();\n    void openCollectionBrowser(const GameCatalogEntry& entry);"

assert target_hpp in app_hpp_text
app_hpp_text = app_hpp_text.replace(target_hpp, repl_hpp, 1)
with open(app_hpp_path, "w", newline="\n", encoding="utf-8") as f:
    f.write(app_hpp_text)
print("[+] app.hpp updated with checkForUpdatesStartupAsync")

# 2. Update app.cpp
app_cpp_path = Path("downloader/src/ui/app.cpp")
app_cpp_text = app_cpp_path.read_text(encoding="utf-8")

# Add call in init() right before returning true
target_init_end = "    return true;\n}"
repl_init_end = "    checkForUpdatesStartupAsync();\n    return true;\n}"

# Find the end of App::init()
assert "bool App::init() {" in app_cpp_text
init_idx = app_cpp_text.find("bool App::init() {")
init_end_idx = app_cpp_text.find("    return true;\n}", init_idx)
assert init_end_idx != -1
app_cpp_text = app_cpp_text[:init_end_idx] + "    checkForUpdatesStartupAsync();\n" + app_cpp_text[init_end_idx:]

# Add implementation of checkForUpdatesStartupAsync
impl = """
void App::checkForUpdatesStartupAsync() {
    std::thread([this]() {
        // Sleep 1 second after startup so the main UI settles cleanly
        std::this_thread::sleep_for(std::chrono::milliseconds(1000));
        
        std::string versionJsonStr;
        std::string checkErr;
        std::string checkUrl = std::string(Config::VERSION_CHECK_URL) + "?t=" + std::to_string(std::chrono::system_clock::now().time_since_epoch().count());
        bool checkOk = m_platform->fetchCatalog(checkUrl, versionJsonStr, checkErr);

        if (checkOk && !versionJsonStr.empty()) {
            try {
                auto vJson = nlohmann::json::parse(versionJsonStr);
                if (vJson.contains("latestVersion")) {
                    std::string latestVer = vJson["latestVersion"].get<std::string>();
                    if (latestVer != Config::APP_VERSION) {
                        m_statusNotification = (m_language == Language::Russian)
                            ? ("✨ Обнаружено обновление v" + latestVer + "! Нажмите [-] в Настройках")
                            : ("✨ New update v" + latestVer + " detected! Press [-] in Settings");
                        m_notificationFramesRemaining = 240; // ~4 seconds toast at 60 FPS
                    }
                }
            } catch (...) {}
        }
    }).detach();
}
"""

# Place it right before openCollectionBrowser
target_coll = "void App::openCollectionBrowser(const GameCatalogEntry& entry) {"
assert target_coll in app_cpp_text
app_cpp_text = app_cpp_text.replace(target_coll, impl + "\n" + target_coll, 1)

with open(app_cpp_path, "w", newline="\n", encoding="utf-8") as f:
    f.write(app_cpp_text)

print("[SUCCESS] Startup update check added to app.hpp and app.cpp!")
