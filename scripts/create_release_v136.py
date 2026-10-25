"""
Creates GitHub Release v1.3.6 and uploads:
1. H3H-Backgrounds.nro
2. H3H-AfterDark.nro
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
        print(f"    [!] Error checking existing assets: {e}")

    upload_url = f"https://uploads.github.com/repos/Holy3holy-dev/H3H-Backgrounds/releases/{rel_id}/assets?name={asset_name}"
    size = path.stat().st_size
    print(f"[*] Uploading {asset_name} ({size / (1024*1024):.2f} MB)...")

    with open(path, "rb") as f:
        data = f.read()

    headers_post = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "Content-Length": str(size),
        "User-Agent": "H3H-Studio-Uploader"
    }

    req = urllib.request.Request(upload_url, data=data, headers=headers_post, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            if resp.status in (200, 201):
                print(f"[+] Successfully uploaded {asset_name}!")
                return True
            else:
                print(f"[!] Upload returned status {resp.status}")
                return False
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"[!] Failed to upload {asset_name}: {e.code} - {err_body}")
        return False
    except Exception as e:
        print(f"[!] Failed to upload {asset_name}: {e}")
        return False

def main():
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("[-] Error: GitHub token not found.")
        sys.exit(1)

    tag = "v1.3.6"
    release_name = "H3H Backgrounds v1.3.6 (Resilient Cloud Downloader, Direct Google Drive & Range Resume)"
    body = (
        "## H3H Backgrounds & After Dark v1.3.6\n\n"
        "### 🚀 Обновление загрузчика (Решение Timeout / Сетевых сбоев):\n"
        "- **Прямое скачивание с Google Drive**: Автоматическое преобразование ссылок в прямой эндпоинт `drive.usercontent.google.com` (без медленного 303-редиректа и повторного SSL/TLS рукопожатия).\n"
        "- **Увеличенные таймауты до 45 секунд**: Connect timeout и Stall timeout увеличены с 10-15s до 45s, исключая ошибку `Download failed: Timeout was reached` при замедлениях сети и слабом сигнале Wi-Fi Switch.\n"
        "- **Принудительный IPv4 (`CURL_IPRESOLVE_V4`)**: Устраняет подвисания DNS на домашних роутерах, когда Switch безуспешно ждёт IPv6 ответ.\n"
        "- **Автодокачка (HTTP Range)**: Если загрузка видеофона прервалась на середине, загрузчик не удаляет файл, а возобновляет скачивание с сохранённого байта.\n"
        "- **Тройной автоматический повтор (3x Retry)**: При кратковременной потере пакетов загрузчик автоматически повторяет попытку с паузой 1-2 секунды.\n"
        "- **Интерактивная вкладка «Загрузки»**: Теперь можно нажать на любую упавшую карточку (или бейдж `[ ✖ Ошибка ]`), чтобы мгновенно перезапустить скачивание прямо с экрана Switch.\n"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio-Uploader"
    }

    # 1. Check if release already exists
    get_rel_url = f"https://api.github.com/repos/Holy3holy-dev/H3H-Backgrounds/releases/tags/{tag}"
    rel_id = None
    try:
        req = urllib.request.Request(get_rel_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            rel_id = data.get("id")
            print(f"[*] Release {tag} already exists (ID: {rel_id})")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"[!] Error checking release: {e.code}")

    # 2. Create release if not exists
    if not rel_id:
        create_url = "https://api.github.com/repos/Holy3holy-dev/H3H-Backgrounds/releases"
        payload = {
            "tag_name": tag,
            "target_commitish": "main",
            "name": release_name,
            "body": body,
            "draft": False,
            "prerelease": False
        }
        req = urllib.request.Request(create_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                rel_id = data.get("id")
                print(f"[+] Created release {tag} (ID: {rel_id})")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"[!] Failed to create release: {e.code} - {err_body}")
            sys.exit(1)

    # 3. Upload assets
    assets = [
        (ROOT_DIR / "downloader" / "H3H-Backgrounds.nro", "H3H-Backgrounds.nro"),
        (ROOT_DIR / "downloader" / "H3H-AfterDark.nro", "H3H-AfterDark.nro"),
    ]

    for fpath, name in assets:
        upload_asset(rel_id, token, fpath, name)

    print("\n[SUCCESS] Release v1.3.6 published successfully!")

if __name__ == "__main__":
    main()
