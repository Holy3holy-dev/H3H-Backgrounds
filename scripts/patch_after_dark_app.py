from pathlib import Path

app_path = Path("downloader/src/ui/app.cpp")
content = app_path.read_text(encoding="utf-8").replace("\r\n", "\n")

content = content.replace(
    'm_window = SDL_CreateWindow(\n        "H3H Backgrounds",',
    'm_window = SDL_CreateWindow(\n        Config::APP_NAME,'
)

content = content.replace(
    'std::cout << "[+] H3H Backgrounds App initialized successfully." << std::endl;',
    'std::cout << "[+] " << Config::APP_NAME << " App initialized successfully." << std::endl;'
)

content = content.replace(
    'drawText("4IFIR System Settings  |  H3H Backgrounds", 60, 105, Theme::COLOR_TEXT_PRIMARY, 22);',
    'drawText(std::string("4IFIR System Settings  |  ") + Config::APP_NAME, 60, 105, Theme::COLOR_TEXT_PRIMARY, 22);'
)

app_path.write_text(content, encoding="utf-8")
print("[+] app.cpp updated with dynamic Config::APP_NAME!")
