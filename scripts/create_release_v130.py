"""
Creates GitHub Release v1.3.0 and uploads H3H-Backgrounds.nro and H3H-AfterDark.nro.
Enables OTA update directly from the Nintendo Switch!
"""

import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.github_publisher import GitHubPublisher

ROOT_DIR = Path(r"E:\videofon")

def upload_asset(rel_id, token, file_path, asset_name):
    # Check if asset already exists
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
        print(f"[*] Note during asset check: {e}")

    upload_url = f"https://uploads.github.com/repos/Holy3holy-dev/H3H-Backgrounds/releases/{rel_id}/assets?name={asset_name}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio-Uploader"
    }
    with open(file_path, "rb") as f:
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
    print("=== H3H Release v1.3.0 Publisher ===")
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("[!] GitHub token not found.")
        return 1

    tag = "v1.3.0"
    name = "H3H Backgrounds & After Dark v1.3.0 (Metal Gear Themes, ZL/ZR Fast Nav, Touch 2.0, Cyrillic Search)"
    body = (
        "## Release v1.3.0 / Релиз v1.3.0\n\n"
        "### 🎮 1. Новые видеофоны Metal Gear Rising & Metal Gear Solid\n"
        "- 5 динамических живых видеофонов для **Metal Gear Rising: Revengeance** (`01004D4752000000`):\n"
        "  - *Cyborg Ninja Raiden* (Cinematic 3D)\n"
        "  - *Raiden Crimson Blade* (Dynamic Action)\n"
        "  - *Raiden Jack the Ripper* (Cinematic 3D)\n"
        "  - *Raiden Black & White Noir* (Minimalist Art)\n"
        "  - *Raiden High-Frequency Blade* (Official Theme)\n"
        "- 2 живых фона для **Metal Gear Solid Master Collection Vol. 1** (`0100C1301A9C2000`):\n"
        "  - *Solid Snake Shadow Moses* (Cinematic Gameplay)\n"
        "  - *Big Boss Naked Snake* (Atmospheric 2D)\n\n"
        "### ⚡ 2. Быстрая навигация [ZL] / [ZR] во всех меню\n"
        "- Во вкладках Каталога и Коллекций: прыжок на ±15 элементов.\n"
        "- Во вкладках «Мои игры», Записи 4IFIR, Выбор игры и Очередь загрузок: прыжок на ±5..10 элементов.\n"
        "- Быстрая пакетная установка по `[ZL]` прямо из каталога.\n\n"
        "### 👆 3. Сенсорное управление 2.0 (Pixel-Perfect Touch)\n"
        "- Полноэкранный видеоплеер теперь поддерживает нажатия на экран: `[A]` Установить, `[★]` В избранное, `[Y]` Назначить, а также свайпы влево/вправо для переключения вариантов.\n"
        "- Выверены все координаты кнопок в меню «Мои игры» (Удалить, Восстановить из .bak, Записи 4IFIR).\n"
        "- Исправлена кнопка избранного в браузере коллекций — больше не закрывает окно при нажатии.\n\n"
        "### 🔤 4. Полноценный регистронезависимый поиск на русском (UTF-8 Cyrillic)\n"
        "- Поиск по каталогу теперь полностью поддерживает русскую кириллицу (А-Я, а-я, Ё, ё) без искажения регистра.\n"
        "- Динамический заголовок системной клавиатуры SwitchOS для H3H Backgrounds и H3H After Dark.\n\n"
        "### 🎬 5. Стабильность видеоплеера и модальных окон\n"
        "- Бесшовный возврат из полноэкранного видео в окно вариантов без сброса иерархии.\n"
        "- Корректная установка локальных клипов 4IFIR напрямую на карту памяти без сетевых ошибок cURL.\n"
        "- Защита от зацикливания при чтении поврежденных видеофайлов."
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

    # Upload NRO binaries
    print("\n[*] Uploading NRO binaries to Release v1.3.0...")
    nro1 = ROOT_DIR / "downloader" / "H3H-Backgrounds.nro"
    nro2 = ROOT_DIR / "downloader" / "H3H-AfterDark.nro"
    ok1 = upload_asset(rel_id, token, str(nro1), "H3H-Backgrounds.nro")
    ok2 = upload_asset(rel_id, token, str(nro2), "H3H-AfterDark.nro")

    if ok1 and ok2:
        print("\n[SUCCESS] Release v1.3.0 published with both NRO binaries!")
        return 0
    else:
        print("\n[!] Warning: One or more uploads had issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
