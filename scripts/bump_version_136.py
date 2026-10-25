import json
from pathlib import Path

# 1. Update config.hpp
cfg_path = Path("downloader/include/core/config.hpp")
cfg_text = cfg_path.read_text(encoding="utf-8")
cfg_text = cfg_text.replace('APP_VERSION = "1.3.5"', 'APP_VERSION = "1.3.6"')
cfg_path.write_text(cfg_text, encoding="utf-8")
print("[+] Updated config.hpp to 1.3.6")

# 2. Update Makefile
mk_path = Path("downloader/Makefile")
mk_text = mk_path.read_text(encoding="utf-8")
mk_text = mk_text.replace("APP_VERSION := 1.3.5", "APP_VERSION := 1.3.6")
mk_path.write_text(mk_text, encoding="utf-8")
print("[+] Updated Makefile to 1.3.6")

# 3. Update version.json
v_path = Path("version.json")
v_data = json.loads(v_path.read_text(encoding="utf-8"))
v_data["latestVersion"] = "1.3.6"
v_data["releaseDate"] = "2026-10-25"
v_data["releaseUrl"] = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/tag/v1.3.6"
v_data["downloadUrl"] = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.3.6/H3H-Backgrounds.nro"
v_data["changelog"] = (
    "v1.3.6: Resilient Cloud Downloader for Switch\\n"
    "- Direct Google Drive download bypassing slow 303 redirects & redundant TLS handshakes\\n"
    "- Increased connection and stall timeouts to 45s with automatic 3x retry on network hiccups\\n"
    "- Partial download resume (HTTP Range support) preserving progress on Wi-Fi drops\\n"
    "- Interactive Downloads tab: tap any failed card or error badge to instantly retry"
)
v_data["changelogRu"] = (
    "v1.3.6: Сверхнадёжный загрузчик видеофонов и иконок\\n"
    "- Прямой доступ к хранилищу Google Drive в обход промежуточных редиректов 303 (в 2 раза быстрее старт)\\n"
    "- Увеличены таймауты подключения и ожидания до 45 сек, принудительный IPv4 (защита от сбоев DNS)\\n"
    "- Автодокачка файлов (HTTP Range): при разрыве Wi-Fi скачивание продолжается с места остановки\\n"
    "- Тройной автоповтор при сбоях сети + возможность перезапустить задачу касанием по карточке"
)
v_path.write_text(json.dumps(v_data, ensure_ascii=False, indent=2), encoding="utf-8")
print("[+] Updated version.json to 1.3.6")
