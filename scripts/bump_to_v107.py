from pathlib import Path

# 1. Update config.hpp
cfg_path = Path(r"e:\videofon\downloader\include\core\config.hpp")
text = cfg_path.read_text(encoding="utf-8")
text = text.replace('APP_VERSION = "1.0.6";', 'APP_VERSION = "1.0.7";')
cfg_path.write_text(text, encoding="utf-8")
print("[+] config.hpp updated to v1.0.7")

# 2. Update version.json
ver_path = Path(r"e:\videofon\version.json")
ver_text = '''{
  "latestVersion": "1.0.7",
  "minRequiredVersion": "1.0.0",
  "downloadUrl": "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-Backgrounds.nro",
  "releaseNotes": "Pixel-perfect UI layout, clean 30fps player, and version indicator fix"
}'''
ver_path.write_text(ver_text, encoding="utf-8")
print("[+] version.json updated to v1.0.7")

# 3. Update app.cpp setting label
app_path = Path(r"e:\videofon\downloader\src\ui\app.cpp")
app_text = app_path.read_text(encoding="utf-8")
app_text = app_text.replace('std::string("v") + Config::APP_VERSION + " [A - Обновить]"',
                            'std::string("v") + Config::APP_VERSION + " [A - Проверить]"')
app_path.write_text(app_text, encoding="utf-8")
print("[+] app.cpp updated setting row to [A - Проверить]")
