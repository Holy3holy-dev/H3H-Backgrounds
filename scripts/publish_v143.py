"""
Publishes Release v1.4.3 to GitHub:
1. Commits new 3D AI tab icons, redesigned unified Catalog, animations, config & version.json v1.4.3
2. Pushes to origin/main using GitHub access token
3. Creates GitHub Release v1.4.3 and uploads H3H-Backgrounds.nro and H3H-AfterDark.nro
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
    print("=== H3H Release v1.4.3 Publisher ===", flush=True)
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
        "downloader/romfs/icons/tab_catalog.png",
        "downloader/romfs/icons/tab_video_icons.png",
        "downloader/romfs/icons/tab_my_games.png",
        "downloader/romfs/icons/tab_downloads.png",
        "downloader/romfs/icons/tab_settings.png",
        "downloader/H3H-Backgrounds.nro",
        "downloader/H3H-AfterDark.nro",
        "H3H-Backgrounds.nro",
        "H3H-AfterDark.nro"
    ]
    print("[*] Staging files...", flush=True)
    for f in files_to_stage:
        if os.path.exists(f):
            subprocess.run(["git", "add", f], check=False)

    commit_msg = (
        "feat(release): v1.4.3 - High-res 3D Cyber-Glass tab icons, "
        "direct catalog browser with [L] All / [R] Favorites tabs and [-] instant favorite toggle"
    )
    subprocess.run(["git", "commit", "-m", commit_msg], check=False)

    print("[*] Pushing 'main' to GitHub via access token...", flush=True)
    res = subprocess.run(["git", "push", repo_url, "main"], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[!] Push error: {res.stderr}", flush=True)
    else:
        print("[+] Pushed main branch to GitHub successfully!", flush=True)

    # 2. Create GitHub Release v1.4.3
    tag_name = "v1.4.3"
    rel_title = "v1.4.3: 3D кибер-иконки разделов и полное обновление интерфейса каталога"
    rel_body = """## H3H Backgrounds & After Dark v1.4.3 — 3D Cyber-Glass & Direct Catalog Redesign

### 🚀 Что нового в этом релизе:

1. **Новые профессиональные 3D Cyber-Glass иконки для всех разделов**:
   - Сгенерированы высокодетализированные 3D-модели иконок в фирменной палитре 4IFIR Cyber-Glass (обсидиановое стекло, полированный титан, неоновые акценты Electric Cyan `#00D2FF` и Magenta `#EC4899`):
     - **Каталог**: Голографический картридж Nintendo Switch в кибер-докстанции.
     - **Видеоиконки**: Парящий 3D-фрейм 1:1 со светящимся неоновым ядром Play и звуковыми волнами.
     - **Менеджер игр**: Кибернетическое хранилище с неоновой стопкой картриджей.
     - **Загрузки**: Кибер-консоль Switch с нисходящим лазерным лучом загрузки и голографическими кольцами.
     - **Настройки**: Прецизионная механическая кибер-шестерня с реакторным неоновым ядром.
   - Иконки отмасштабированы до 96px на плитках и встроены прямо в `romfs:/icons/` внутри NRO.

2. **Полностью переработанный каталог видеофонов**:
   - **Удалены все промежуточные категории и меню**: при входе в Каталог сразу открывается единый, чистый и удобный список игр.
   - **Две быстрые сегментные вкладки** в самом верху:
     - `[L] Весь каталог (1073 игр)`
     - `[R] Избранное (N тем)`
     - Моментальное переключение на клавиши `[L]`, `[R]` или `[X]`.
   - **Быстрое добавление в избранное**: кнопка `[-]` (Minus) на любой игре моментально добавляет её в избранное или удаляет со звуковым уведомлением и автосохранением на SD-карту.
   - **Быстрый полноэкранный просмотр**: кнопка `[ZL]` прямо в каталоге мгновенно запускает живой видеоплеер со звуком для выбранной игры.
   - **Информативные бейджи**: `N вар. фона`, `256x256` (наличие видеоиконки) и `★ В избранном`.
   - Красивое пустое состояние для Избранного с подсказкой и быстрой кнопкой перехода.

3. **Синхронизация главного экрана и подсказок**:
   - Нажатие `[B]` из каталога сразу возвращает на Главный экран.
   - Нижняя плашка подсказок теперь содержит: `(A) Выбрать  (ZL) Просмотр  (-) В избр. ★  (L/R) Разделы  (Y) Поиск  (X) Сортировка  (B) Назад`.
"""

    rel_url = f"https://api.github.com/repos/{repo_name}/releases"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio-Uploader"
    }

    tag_check_url = f"https://api.github.com/repos/{repo_name}/releases/tags/{tag_name}"
    req_chk = urllib.request.Request(tag_check_url, headers=headers)
    rel_id = None
    try:
        with urllib.request.urlopen(req_chk) as resp:
            data = json.loads(resp.read().decode())
            rel_id = data["id"]
            print(f"[*] Release {tag_name} already exists (ID: {rel_id})", flush=True)
    except urllib.error.HTTPError:
        pass

    if not rel_id:
        print(f"[*] Creating GitHub Release {tag_name}...", flush=True)
        payload = {
            "tag_name": tag_name,
            "target_commitish": "main",
            "name": rel_title,
            "body": rel_body,
            "draft": False,
            "prerelease": False
        }
        req_create = urllib.request.Request(
            rel_url,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req_create) as resp:
                data = json.loads(resp.read().decode())
                rel_id = data["id"]
                print(f"[+] Created GitHub Release ID: {rel_id}", flush=True)
        except Exception as e:
            print(f"[!] Failed to create release: {e}", flush=True)
            return 1

    # 3. Upload assets
    assets = [
        (ROOT_DIR / "H3H-Backgrounds.nro", "H3H-Backgrounds.nro"),
        (ROOT_DIR / "H3H-AfterDark.nro", "H3H-AfterDark.nro")
    ]
    for p, name in assets:
        upload_asset(rel_id, token, str(p), name)

    print("\n=======================================================", flush=True)
    print(f"SUCCESS! Release {tag_name} published with OTA binaries!", flush=True)
    print(f"Release URL: https://github.com/{repo_name}/releases/tag/{tag_name}", flush=True)
    print("=======================================================", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
