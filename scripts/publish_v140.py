"""
Publishes Release v1.4.0 to GitHub:
1. Commits redesign changes & version.json v1.4.0
2. Merges into main and pushes to origin/main
3. Creates GitHub Release v1.4.0 and uploads H3H-Backgrounds.nro and H3H-AfterDark.nro
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
    print("=== H3H Release v1.4.0 Publisher ===")
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("[!] GitHub token not found.")
        return 1

    repo_name = "Holy3holy-dev/H3H-Backgrounds"
    repo_url = f"https://x-access-token:{token}@github.com/{repo_name}.git"

    # 1. Stage and commit files on current branch
    files_to_stage = [
        "version.json",
        "downloader/include/core/config.hpp",
        "downloader/include/ui/app.hpp",
        "downloader/include/ui/i18n.hpp",
        "downloader/include/ui/theme.hpp",
        "downloader/src/ui/app.cpp",
        "downloader/romfs/catalog.json",
        "downloader/H3H-Backgrounds.nro",
        "REDESIGN_AUDIT.md",
        "REDESIGN_REPORT.md"
    ]
    print("[*] Staging files...")
    subprocess.run(["git", "add"] + files_to_stage, check=False)
    subprocess.run(["git", "commit", "-m", "feat(ui): release v1.4.0 4IFIR Cyber-Glass redesign with Video Icons tab, list view, search & live 1:1 preview"], check=False)

    # 2. Merge into main and push
    print("[*] Switching to main and merging feature/redesign-ui-torrentshop...")
    subprocess.run(["git", "checkout", "main"], check=True)
    subprocess.run(["git", "merge", "feature/redesign-ui-torrentshop", "--no-edit"], check=True)

    print("[*] Pushing 'main' to GitHub...")
    res = subprocess.run(["git", "push", repo_url, "main"], capture_output=True, text=True)
    if res.returncode != 0:
        print("[!] Git push failed:", res.stderr)
        return 1
    print("[+] Main branch pushed successfully!")

    # 3. Create / update GitHub Release v1.4.0
    tag = "v1.4.0"
    name = "H3H Backgrounds v1.4.0 — Полный редизайн 4IFIR Cyber-Glass, раздел «Видеоиконки» и живое превью 1:1"
    body = (
        "## Release v1.4.0 / Релиз v1.4.0 — Полный редизайн 4IFIR Cyber-Glass\n\n"
        "### ✨ 1. Новый главный экран (5 плиток + инфо-дашборд)\n"
        "- Пять центральных плиток (`225×208`, скругление `28px`, прозрачность стекла `90%`, увеличение в фокусе `1.05x`, векторные 4IFIR-иллюстрации и подписи внутри):\n"
        "  1. **Каталог**\n"
        "  2. **Видеоиконки**\n"
        "  3. **Менеджер игр**\n"
        "  4. **Загрузки**\n"
        "  5. **Настройки**\n"
        "- Лаконичная нижняя панель из 2 широких карточек со статистикой базы и быстрыми действиями (без лишних карточек путей).\n"
        "- Фирменная цветовая палитра **Чифира (4IFIR Cyber-Glass)**: глубокий обсидиан `#090C13`, электрический циан `#00D2FF` и неоновая маджента `#EC4899` (плюс специальный профиль `#FF2E93` для **After Dark 18+**).\n\n"
        "### 🔲 2. Самостоятельный раздел «Видеоиконки» (112 тайтлов / 433 иконки)\n"
        "- Просмотр всей базы доступных видеоиконок `256×256` удобным списком.\n"
        "- **Живой 1:1 предпросмотр (`[X] ▶ Превью`)**: воспроизведение квадратных анимированных видеоиконок прямо на экране Switch с переключением вариантов `◀`/`▶`.\n"
        "- **Строка поиска (`[Y] Поиск`)** по названию игры или TitleID и фильтр (`[-]` Все / Установленные / Не установленные).\n\n"
        "### 📂 3. Обновлённый «Каталог» (Категории + Полный список + Поиск)\n"
        "- 18 тематических и жанровых карточек с фирменными иконками.\n"
        "- Кнопка **`[X] ≡ Весь список`** для мгновенного переключения в полный прокручиваемый список всех игр базы.\n"
        "- Интерактивная строка поиска **`[Y] Поиск`** прямо в шапке каталога.\n\n"
        "### ⚡️ 4. OTA-обновление на Switch\n"
        "- Доступно прямо с консоли в разделе **Настройки → Проверить и установить обновление (.nro OTA)**!"
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
                "target_commitish": "main",
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

    print(f"\n[*] Uploading NRO binaries to Release {tag} (ID: {rel_id})...")
    assets_to_upload = [
        (ROOT_DIR / "downloader" / "H3H-Backgrounds.nro", "H3H-Backgrounds.nro"),
        (ROOT_DIR / "downloader" / "H3H-AfterDark.nro", "H3H-AfterDark.nro"),
    ]

    all_ok = True
    for file_path, asset_name in assets_to_upload:
        if not upload_asset(rel_id, token, str(file_path), asset_name):
            all_ok = False

    if all_ok:
        print(f"\n[SUCCESS] Release {tag} published with all NRO assets successfully!")
        return 0
    else:
        print("\n[!] Warning: Some assets could not be uploaded.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
