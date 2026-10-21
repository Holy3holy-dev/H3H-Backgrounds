import json
import sys
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.github_publisher import GitHubPublisher

def main():
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("ERROR: GitHub token not found.")
        return 1

    repo = "Holy3holy-dev/H3H-Backgrounds"
    tag = "v1.2.6"
    name = "H3H Backgrounds & After Dark v1.2.6 (Target Game Picker, Direct Passthrough & In-App Updater)"
    body = (
        "## Что нового в v1.2.6 / What's new in v1.2.6:\n\n"
        "- **Свободный выбор игры для любого видеофона (Target Game Picker):**\n"
        "  - Теперь в полноэкранном предпросмотре любого фона можно нажать кнопку **[Y] Привязать к другой игре** и выбрать любую установленную на Nintendo Switch игру из красивого Cyber-Glass меню.\n"
        "  - Для фонов из свободной коллекции After Dark (★ Свободный выбор) кнопка **[A]** сразу открывает выбор игры на консоли.\n"
        "  - В «Моих играх» для тайтлов без прямого совпадения добавлена кнопка быстрого перехода в каталог.\n"
        "  - На главном экране карточка «Доступно в каталоге» теперь отображает точное суммарное количество всех доступных видеофонов, а не только категорий.\n\n"
        "- **Поддержка кодека HEVC (H.265) и прямая загрузка (-c copy):**\n"
        "  - Telegram-бот и Studio теперь поддерживают загрузку и транскодирование в HEVC (H.265) с тегом аппаратного декодирования `hvc1` под NVDEC Nintendo Switch.\n"
        "  - Добавлен автоматический детект готовых Switch 720p видео: если ролик уже 1280x720 AVC/HEVC, бот загружает его мгновенно через stream copy без потери качества.\n"
        "  - Исправлена сессия Telegram-бота и парсинг Title ID / названий из подписей файлов.\n\n"
        "- **Автономный In-App Updater для After Dark:**\n"
        "  - Сборка `H3H-AfterDark.nro` теперь автоматически скачивает обновление именно для After Dark через `afterDarkDownloadUrl` в `version.json`.\n\n"
        "- **Библиотека After Dark:**\n"
        "  - Каталог After Dark изолирован на отдельной ветке `after-dark` и наполнен 17 эксклюзивными видеофонами (NieR:Automata 2B, FF7 Tifa, Zelda, Bayonetta, Cyberpunk Lucy, Stellar Blade Eve, NIKKE, Azur Lane, Genshin, Honkai, Chainsaw Man).\n"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio"
    }

    # 1. Commit and push changes
    print("[*] Committing changes on main branch...")
    subprocess.run(["git", "add", "downloader/", "catalog/", "version.json", "tg_bot/", "scripts/title_id_resolver.py"], check=True)
    subprocess.run([
        "git", "commit", "-m",
        "feat(app): add target game picker, direct 720p passthrough, After Dark in-app updater, and WE mature config (v1.2.6)"
    ])

    repo_url = f"https://x-access-token:{token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"
    print("[*] Pushing to main...")
    subprocess.run(["git", "push", repo_url, "main"], check=True)

    # 2. Check if release already exists
    print(f"[*] Checking if release {tag} exists...")
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/tags/{tag}", headers=headers)
    release_id = None
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            release_id = data["id"]
            print(f"[+] Found existing release ID {release_id}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"[*] Release {tag} not found, creating new one...")
        else:
            print(f"[-] HTTP error: {e}")
            return 1

    # 3. Create release if not exists
    if not release_id:
        create_payload = {
            "tag_name": tag,
            "target_commitish": "main",
            "name": name,
            "body": body,
            "draft": False,
            "prerelease": False
        }
        create_req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/releases",
            data=json.dumps(create_payload).encode(),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(create_req) as resp:
                data = json.loads(resp.read().decode())
                release_id = data["id"]
                print(f"[+] Created release {tag} with ID {release_id}")
        except urllib.error.HTTPError as e:
            print(f"[-] Failed to create release: {e} - {e.read().decode()}")
            return 1

    # 4. Upload Assets (H3H-Backgrounds.nro and H3H-AfterDark.nro)
    assets_to_upload = [
        ("H3H-Backgrounds.nro", Path("H3H-Backgrounds.nro")),
        ("H3H-AfterDark.nro", Path("H3H-AfterDark.nro"))
    ]

    for asset_name, asset_path in assets_to_upload:
        if not asset_path.exists():
            print(f"[-] Asset {asset_path} does not exist!")
            continue

        # Check existing assets to avoid 422 duplicate
        req_assets = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/{release_id}/assets", headers=headers)
        with urllib.request.urlopen(req_assets) as resp:
            existing_assets = json.loads(resp.read().decode())
            for a in existing_assets:
                if a["name"] == asset_name:
                    del_req = urllib.request.Request(a["url"], headers=headers, method="DELETE")
                    urllib.request.urlopen(del_req)
                    print(f"[+] Deleted existing release asset {asset_name}")

        upload_url = f"https://uploads.github.com/repos/{repo}/releases/{release_id}/assets?name={asset_name}"
        data_bytes = asset_path.read_bytes()
        upload_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "User-Agent": "H3H-Studio"
        }
        print(f"[*] Uploading {asset_name} ({len(data_bytes)} bytes)...")
        up_req = urllib.request.Request(upload_url, data=data_bytes, headers=upload_headers, method="POST")
        with urllib.request.urlopen(up_req) as resp:
            up_data = json.loads(resp.read().decode())
            print(f"[+] Asset uploaded: {up_data.get('browser_download_url')}")

    print("\n[SUCCESS] Release v1.2.6 published with both NRO assets!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
