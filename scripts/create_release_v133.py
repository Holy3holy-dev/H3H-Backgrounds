"""
Creates GitHub Release v1.3.3 and uploads H3H-Backgrounds.nro and H3H-AfterDark.nro.
Enables instant OTA update from Nintendo Switch!
"""

import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.github_publisher import GitHubPublisher

ROOT_DIR = Path(r"E:\videofon")

def upload_asset(rel_id, token, file_path, asset_name):
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
    print("=== H3H Release v1.3.3 Publisher ===")
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("[!] GitHub token not found.")
        return 1

    tag = "v1.3.3"
    name = "H3H Backgrounds & After Dark v1.3.3 (Accurate Variant Detection & Smooth Touch Scroll)"
    body = (
        "## Release v1.3.3 / Релиз v1.3.3\n\n"
        "### 🎯 1. Точное распознавание установленного варианта фона\n"
        "- **Исправлено определение активного варианта** (включая GTA 5 и игры с несколькими темами): теперь приложение сохраняет и точно отслеживает выбранный вариант на SD-карте без сброса на вариант #1.\n"
        "- **Мгновенный статус установки**: после завершения загрузки бейдж `[УСТАНОВЛЕН]` и кнопка `[A] Переустановить` моментально появляются в «Моих играх» без необходимости перезапуска программы.\n"
        "- **Атомарная запись реестра на FatFs / Switch**: предотвращена ошибка переименования временных файлов на SD-карте при сохранении `installed_variants.json`.\n\n"
        "### 👆 2. Плавный скролл пальцем в каталоге и списках\n"
        "- Исправлен конфликт между жестом скролла и авто-фокусом карточек: экран больше не дёргается и не сбрасывает позицию при перелистывании пальцем.\n"
        "- Сбалансированный порог жеста (48px) для максимальной отзывчивости на сенсорном экране Switch.\n\n"
        "### ⚡️ 3. Бесшовное обновление\n"
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

    # Upload NRO binaries
    print("\n[*] Uploading NRO binaries to Release v1.3.3...")
    nro1 = ROOT_DIR / "downloader" / "H3H-Backgrounds.nro"
    nro2 = ROOT_DIR / "downloader" / "H3H-AfterDark.nro"
    ok1 = upload_asset(rel_id, token, str(nro1), "H3H-Backgrounds.nro")
    ok2 = upload_asset(rel_id, token, str(nro2), "H3H-AfterDark.nro")

    if ok1 and ok2:
        print("\n[SUCCESS] Release v1.3.3 published with both NRO binaries!")
        return 0
    else:
        print("\n[!] Warning: One or more uploads had issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
