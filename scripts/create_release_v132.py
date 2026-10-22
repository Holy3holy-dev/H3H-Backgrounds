"""
Creates GitHub Release v1.3.2 and uploads H3H-Backgrounds.nro and H3H-AfterDark.nro.
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
    print("=== H3H Release v1.3.2 Publisher ===")
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("[!] GitHub token not found.")
        return 1

    tag = "v1.3.2"
    name = "H3H Backgrounds & After Dark v1.3.2 (Split Touch Actions: Preview on Title & Instant Download)"
    body = (
        "## Release v1.3.2 / Релиз v1.3.2\n\n"
        "### 👆 1. Раздельные сенсорные зоны в списке вариантов игры\n"
        "- **Зелёная зона (название и характеристики видеофона)**: при касании пальцем теперь мгновенно открывается полноэкранный видеоплеер (30 FPS живое видео со звуком).\n"
        "- **Жёлтая зона (кнопка [A] Установить справа)**: при касании пальцем видеофон сразу отправляется в очередь скачивания без лишних всплывающих диалогов.\n"
        "- Кнопка установки справа теперь отображается на всех видимых карточках вариантов в полупрозрачном стиле 4IFIR Cyber-Glass, а активная карточка подсвечивается неоновым цианом.\n\n"
        "### ⚡️ 2. Бесшовное управление на Switch\n"
        "- Доступно мгновенное обновление по воздуху прямо со Свича!"
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
    print("\n[*] Uploading NRO binaries to Release v1.3.2...")
    nro1 = ROOT_DIR / "downloader" / "H3H-Backgrounds.nro"
    nro2 = ROOT_DIR / "downloader" / "H3H-AfterDark.nro"
    ok1 = upload_asset(rel_id, token, str(nro1), "H3H-Backgrounds.nro")
    ok2 = upload_asset(rel_id, token, str(nro2), "H3H-AfterDark.nro")

    if ok1 and ok2:
        print("\n[SUCCESS] Release v1.3.2 published with both NRO binaries!")
        return 0
    else:
        print("\n[!] Warning: One or more uploads had issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
