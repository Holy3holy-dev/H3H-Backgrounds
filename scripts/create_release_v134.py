"""
Creates GitHub Release v1.3.4 and uploads:
1. H3H-Backgrounds.nro
2. H3H-AfterDark.nro
3. H3H-Background-Studio.exe (Portable Windows Executable)
4. H3H-Background-Studio-v1.3.4-Portable.zip (Full Portable Package with FFmpeg)
"""

import sys
import os
import json
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.github_publisher import GitHubPublisher

ROOT_DIR = Path(r"E:\videofon")

def upload_asset(rel_id, token, file_path, asset_name):
    path = Path(file_path)
    if not path.exists():
        print(f"    [!] File does not exist: {file_path}")
        return False

    list_url = f"https://api.github.com/repos/Holy3holy-dev/H3H-Backgrounds/releases/{rel_id}/assets"
    headers_get = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio-Uploader"
    }
    try:
        req = urllib.request.Request(list_url, headers=headers_get)
        with urllib.request.urlopen(req) as resp:
            assets = json.loads(resp.read().decode())
            for a in assets:
                if a["name"] == asset_name:
                    print(f"[*] Asset {asset_name} already exists (ID: {a['id']}), deleting to overwrite...")
                    del_url = f"https://api.github.com/repos/Holy3holy-dev/H3H-Backgrounds/releases/assets/{a['id']}"
                    del_req = urllib.request.Request(del_url, headers=headers_get, method="DELETE")
                    urllib.request.urlopen(del_req)
                    break
    except Exception as e:
        print(f"[*] Note during asset check for {asset_name}: {e}")

    file_size = path.stat().st_size
    print(f"[*] Uploading {asset_name} ({file_size / (1024 * 1024):.2f} MB)...")

    upload_url = f"https://uploads.github.com/repos/Holy3holy-dev/H3H-Backgrounds/releases/{rel_id}/assets?name={asset_name}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio-Uploader"
    }

    with open(path, "rb") as f:
        data = f.read()

    req = urllib.request.Request(upload_url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status in (200, 201):
                print(f"    [+] Successfully uploaded {asset_name} ({len(data):,} bytes)")
                return True
    except Exception as e:
        print(f"    [!] Error uploading {asset_name}: {e}")
    return False

def main():
    print("=== H3H Release v1.3.4 Publisher ===")
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("[!] GitHub token not found.")
        return 1

    tag = "v1.3.4"
    name = "H3H Backgrounds & Studio v1.3.4 (4IFIR Video Icons, Prominent Badges & Portable Studio)"
    body = (
        "## Release v1.3.4 / Релиз v1.3.4\n\n"
        "### 🔲 1. Поддержка видеоиконок 4IFIR и заметные плашки\n"
        "- **Яркая неоновая плашка `[ИКОНКА]`**: для иконок добавлена заметная издалека неоновая плашка цвета Electric Cyan, работающая в паре со звуковой зелёной плашкой `[ЗВУК]`/`[БЕЗ ЗВУКА]`.\n"
        "- **Отображение во всех режимах**: плашки теперь видны на карточках в Каталоге, в списке вариантов «Моих игр», в Коллекциях и в окне полноэкранного предпросмотра (HUD).\n"
        "- **Новый фильтр каталога**: добавлен фильтр `Фильтр: Только с видеоиконками [ИКОНКА]`, переключаемый кнопкой `[X]`.\n"
        "- **Автоматическая установка на SD**: при выборе фона с иконкой приложение автоматически загружает и устанавливает видеоиконку в `sdmc:/recordings/icons/<TitleID>.mp4`.\n\n"
        "### 🖥 2. Портативная программа H3H Background Studio для Windows\n"
        "- **Готовый портативный .exe**: работает сразу на любом ПК без установки Python.\n"
        "- **Встроенный плеер видеоиконки 1:1**: отдельный предпросмотр квадратной иконки с независимым скраббером времени.\n"
        "- **Независимые тайминги**: выбор интервала для иконки с кнопками-пресетами (2с, 4с, 6с, 8с) и кнопкой `[📋 Как у фона]`.\n"
        "- **Прямая публикация**: авторы и игроки могут загружать готовые работы прямо в общее облако каталога!\n"
        "- **FFmpeg в комплекте**: версия в zip-архиве содержит FFmpeg и запускается в один клик без дополнительных настроек.\n\n"
        "### 🤖 3. Исправления в Telegram-боте\n"
        "- **Исправлен подсчёт игр**: команда `/status` теперь отображает реальное число игр в каталоге вместо общего справочника Title ID.\n"
        "- **Поддержка загрузки иконок**: добавлены режимы загрузки (Фон + Иконка / Только фон / Только иконка) и команда `/icon`.\n\n"
        "### ⚡️ 4. Быстрое OTA-обновление\n"
        "- Доступно мгновенное OTA-обновление прямо из вкладки «Настройки» на Nintendo Switch!"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio-Uploader"
    }

    rel_url = f"https://api.github.com/repos/Holy3holy-dev/H3H-Backgrounds/releases/tags/{tag}"
    rel_id = None
    try:
        req = urllib.request.Request(rel_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            rel_data = json.loads(resp.read().decode())
            rel_id = rel_data["id"]
            print(f"[+] Release {tag} already exists (ID: {rel_id})")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            create_url = "https://api.github.com/repos/Holy3holy-dev/H3H-Backgrounds/releases"
            payload = {
                "tag_name": tag,
                "name": name,
                "body": body,
                "draft": False,
                "prerelease": False
            }
            req = urllib.request.Request(create_url, data=json.dumps(payload).encode(), headers=headers, method="POST")
            with urllib.request.urlopen(req) as resp:
                rel_data = json.loads(resp.read().decode())
                rel_id = rel_data["id"]
                print(f"[+] Created GitHub Release {tag} (ID: {rel_id})")

    if not rel_id:
        print("[!] Could not obtain release ID")
        return 1

    # Upload assets
    print(f"\n[*] Uploading assets to Release {tag} (ID: {rel_id})...")
    assets_to_upload = [
        (ROOT_DIR / "downloader" / "H3H-Backgrounds.nro", "H3H-Backgrounds.nro"),
        (ROOT_DIR / "downloader" / "H3H-AfterDark.nro", "H3H-AfterDark.nro"),
        (ROOT_DIR / "H3H-Background-Studio.exe", "H3H-Background-Studio.exe"),
        (ROOT_DIR / "H3H-Background-Studio-v1.3.4-Portable.zip", "H3H-Background-Studio-v1.3.4-Portable.zip"),
    ]

    all_ok = True
    for file_path, asset_name in assets_to_upload:
        if not upload_asset(rel_id, token, str(file_path), asset_name):
            all_ok = False

    if all_ok:
        print(f"\n[SUCCESS] Release {tag} published with all assets successfully!")
        return 0
    else:
        print("\n[!] Warning: Some assets could not be uploaded.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
