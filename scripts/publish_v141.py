"""
Publishes Release v1.4.1 to GitHub:
1. Commits polish changes & version.json v1.4.1
2. Pushes to origin/main using GitHub access token
3. Creates GitHub Release v1.4.1 and uploads H3H-Backgrounds.nro and H3H-AfterDark.nro
"""
import sys
import os
import json
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.github_publisher import GitHubPublisher

ROOT_DIR = Path(r"E:\videofon")

def upload_asset(rel_id, token, file_path, asset_name):
    path = Path(file_path)
    if not path.exists():
        print(f"    [!] File does not exist: {file_path}", flush=True)
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
                    print(f"[*] Asset {asset_name} already exists (ID: {a['id']}), deleting to overwrite...", flush=True)
                    del_url = f"https://api.github.com/repos/Holy3holy-dev/H3H-Backgrounds/releases/assets/{a['id']}"
                    del_req = urllib.request.Request(del_url, headers=headers_get, method="DELETE")
                    urllib.request.urlopen(del_req)
                    break
    except Exception as e:
        print(f"[*] Note during asset check for {asset_name}: {e}", flush=True)

    file_size = path.stat().st_size
    print(f"[*] Uploading {asset_name} ({file_size / (1024 * 1024):.2f} MB)...", flush=True)

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
                print(f"    [+] Successfully uploaded {asset_name} ({len(data):,} bytes)", flush=True)
                return True
    except Exception as e:
        print(f"    [!] Error uploading {asset_name}: {e}", flush=True)
    return False

def main():
    print("=== H3H Release v1.4.1 Publisher ===", flush=True)
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("[!] GitHub token not found.", flush=True)
        return 1

    repo_name = "Holy3holy-dev/H3H-Backgrounds"
    repo_url = f"https://x-access-token:{token}@github.com/{repo_name}.git"

    # 1. Stage and commit files
    files_to_stage = [
        "version.json",
        "downloader/include/core/config.hpp",
        "downloader/include/ui/app.hpp",
        "downloader/src/ui/app.cpp",
        "downloader/H3H-Backgrounds.nro",
        "downloader/H3H-AfterDark.nro",
        "H3H-Backgrounds.nro",
        "H3H-AfterDark.nro"
    ]
    print("[*] Staging files...", flush=True)
    for f in files_to_stage:
        if os.path.exists(f):
            subprocess.run(["git", "add", f], check=False)

    subprocess.run(["git", "commit", "-m", "fix(ui): v1.4.1 hotfix - fix broken Switch emojis/symbols, add rounded glass corners & fix text overflows"], check=False)

    print("[*] Pushing 'main' to GitHub via access token...", flush=True)
    res = subprocess.run(["git", "push", repo_url, "main"], capture_output=True, text=True)
    if res.returncode != 0:
        print("[!] Git push failed:", res.stderr, flush=True)
        return 1
    print("[+] Main branch pushed successfully!", flush=True)

    # 2. Create GitHub Release v1.4.1
    print("[*] Creating GitHub Release v1.4.1...", flush=True)
    rel_url = f"https://api.github.com/repos/{repo_name}/releases"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio-Uploader"
    }

    body = {
        "tag_name": "v1.4.1",
        "target_commitish": "main",
        "name": "v1.4.1 - 4IFIR Cyber-Glass Polish & Switch Fixes",
        "body": """## 🚀 H3H-Backgrounds & H3H-AfterDark v1.4.1 Hotfix

Срочное обновление с полировкой интерфейса 4IFIR Cyber-Glass и исправлением замечаний на реальном экране Nintendo Switch OLED:

### 🛠️ Что исправлено:
1. **Устранены все битые символы (☒ / [X] tofu boxes на Switch):**
   - Заменен emoji Wi-Fi `📶` в нижнем статус-баре на четкую векторную иконку антенны (drawWifiIcon).
   - Заменен emoji лупы `🔍` в поиске на векторный инструмент с линзой и ручкой.
   - Заменены все неподдерживаемые глифы (`🔲`, `🎬`, `⚡`, `✨`, `✔`, `✖`, `≡`, `★`, `▶`, `▲`, `▼`) на чистый текст и векторные элементы.
2. **Скругленные углы (True Rounded Glass Corners):**
   - Реализована математическая отрисовка скруглений `drawRoundedRect`, `drawRoundedOutline` и `drawNeonRoundedOutline` с плавным неоновым градиентом Cyan-to-Magenta.
   - Плитки дашборда теперь имеют гладкие радиусы r=24, карточки r=16, пилюли r=6-10.
3. **Исправлены наезды и съезжание текста (Text Overflow & Alignment):**
   - Добавлен точный замер ширины строк `measureTextWidth` через `TTF_SizeUTF8` с учетом кириллицы UTF-8.
   - Название плашки `"Полная база"` больше не наезжает на `"112 тайтлов с иконками"`.
   - Названия плиток дашборда (`"Видеоиконки"`, `"Менеджер игр"`, `"Настройки"`) теперь выровнены строго по центру.
   - Бейдж `"MY GAMES"` в плитке 2 расширен до 68px с центрированием текста.
   - Версионный бейдж `NX` в шапке привязан вплотную к названию, правые метаданные выровнены по правому краю экрана.
   - Кнопки управления в подвале форматируются динамически справа налево с фиксированными отступами.
   - Список игр слева в «Моих играх» ограничен шириной 265px, исключая пересечение со статусной плашкой.

### 📦 Файлы релиза:
- **H3H-Backgrounds.nro** — основное приложение видеофонов и видеоиконок.
- **H3H-AfterDark.nro** — After Dark (18+) версия с неоново-розовой темой.
""",
        "draft": False,
        "prerelease": False
    }

    rel_id = None
    try:
        req = urllib.request.Request(rel_url, data=json.dumps(body).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            rel_id = data["id"]
            print(f"[+] Created Release v1.4.1 with ID: {rel_id}", flush=True)
    except urllib.error.HTTPError as e:
        if e.code == 422: # Already exists
            print("[*] Release v1.4.1 already exists, looking up existing release...", flush=True)
            get_req = urllib.request.Request(f"https://api.github.com/repos/{repo_name}/releases/tags/v1.4.1", headers=headers)
            with urllib.request.urlopen(get_req) as resp:
                data = json.loads(resp.read().decode())
                rel_id = data["id"]
                print(f"[+] Found existing Release ID: {rel_id}", flush=True)
        else:
            print(f"[!] HTTP error: {e.code} - {e.read().decode()}", flush=True)
            return 1

    if not rel_id:
        print("[!] Could not obtain release ID.", flush=True)
        return 1

    # 3. Upload assets
    assets = [
        (ROOT_DIR / "downloader" / "H3H-Backgrounds.nro", "H3H-Backgrounds.nro"),
        (ROOT_DIR / "downloader" / "H3H-AfterDark.nro", "H3H-AfterDark.nro"),
    ]
    for path, name in assets:
        upload_asset(rel_id, token, path, name)

    print("\n🎉 Release v1.4.1 successfully published!", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
