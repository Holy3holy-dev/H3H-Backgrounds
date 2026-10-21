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
    tag = "v1.2.8"
    name = "H3H Backgrounds & After Dark v1.2.8 (Hotfix: Safe Updater & Crash Fix)"
    body = (
        "## Критическое исправление v1.2.8 / Critical Hotfix v1.2.8:\n\n"
        "### 🛡 1. Полностью безопасный атомарный встроенный апдейтер\n"
        "- **Аппаратная защита от повреждения файлов:** Новая версия загружается во временный файл в той же директории на MicroSD.\n"
        "- **Строгая верификация целостности:** Перед заменой приложение проверяет размер файла (>15 МБ) и сигнатуру заголовка NRO (`NRO0`). Если загрузка прервалась или файл поврежден, текущий NRO не затрагивается.\n"
        "- **Безопасная замена и откат:** Исходный NRO сначала переименовывается в `.bak`, затем подставляется новая версия. В случае ошибки на карте памяти происходит мгновенный автоматический откат.\n"
        "- **Исключены сбои Horizon OS / Atmosphère:** Устранено усечение запущенного файла и небезопасные попытки перемонтирования RomFS во время работы.\n\n"
        "### ⚡ 2. Стабильный запуск без вылетов\n"
        "- Удален небезопасный отсоединенный поток при старте приложения.\n"
        "- Проверка обновлений выполняется в отдельном управляемом потоке строго после инициализации графики SDL2.\n"
        "- Удалено устаревшее удаление дубликатов NRO в корне `/switch/`, приводившее к удалению исполняемого файла.\n\n"
        "### 📦 Как восстановить приложение, если обновление 1.2.7 зависло:\n"
        "1. Подключите Switch к ПК (через DBI MTP или кардридер).\n"
        "2. Скопируйте свежий `H3H-Backgrounds.nro` или `H3H-AfterDark.nro` в папку `switch/` (заменив поврежденный файл).\n"
        "3. Запустите приложение из Homebrew Menu — все будет работать стабильно!\n"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio"
    }

    # 1. Commit and push modified files
    print("[*] Committing modified files...")
    subprocess.run([
        "git", "add",
        "version.json",
        "downloader/include/core/config.hpp",
        "downloader/include/ui/app.hpp",
        "downloader/src/ui/app.cpp",
        "scripts/build_nro.py",
        "scripts/build_nro_after_dark.py"
    ], check=True)
    subprocess.run([
        "git", "commit", "-m",
        "fix(updater): atomic NRO replacement, integrity check with rollback, remove startup detached thread (v1.2.8)"
    ], check=False)

    repo_url = f"https://x-access-token:{token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"
    print("[*] Pushing to main...")
    subprocess.run(["git", "pull", "--rebase", repo_url, "main"], check=False)
    subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/main"], check=True)

    # 2. Check if release v1.2.8 exists
    rel_url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    req = urllib.request.Request(rel_url, headers=headers)
    release_data = None
    try:
        with urllib.request.urlopen(req) as resp:
            release_data = json.loads(resp.read().decode())
            print(f"[+] Release {tag} already exists (id: {release_data['id']})")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"[*] Release {tag} does not exist. Creating new release...")
            create_payload = json.dumps({
                "tag_name": tag,
                "target_commitish": "main",
                "name": name,
                "body": body,
                "draft": False,
                "prerelease": False
            }).encode()
            create_req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/releases",
                data=create_payload,
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(create_req) as resp:
                release_data = json.loads(resp.read().decode())
                print(f"[+] Created release {tag} (id: {release_data['id']})")
        else:
            print(f"[-] HTTP error: {e}")
            return 1

    upload_url_tmpl = release_data.get("upload_url", "")
    base_upload_url = upload_url_tmpl.split("{")[0]

    # Upload both NROs to v1.2.8
    nros = [
        ("H3H-Backgrounds.nro", Path("downloader/H3H-Backgrounds.nro")),
        ("H3H-AfterDark.nro", Path("downloader/H3H-AfterDark.nro"))
    ]

    for asset_name, nro_file in nros:
        if not nro_file.exists():
            print(f"[-] Missing file: {nro_file}")
            continue

        # Delete existing asset if any
        for existing in release_data.get("assets", []):
            if existing.get("name") == asset_name:
                print(f"[*] Deleting existing {asset_name} in {tag} (id: {existing['id']})...")
                del_req = urllib.request.Request(
                    f"https://api.github.com/repos/{repo}/releases/assets/{existing['id']}",
                    headers=headers,
                    method="DELETE"
                )
                try:
                    urllib.request.urlopen(del_req)
                except Exception:
                    pass

        print(f"[*] Uploading {asset_name} ({nro_file.stat().st_size} bytes)...")
        data = nro_file.read_bytes()
        up_req = urllib.request.Request(
            f"{base_upload_url}?name={asset_name}",
            data=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
                "User-Agent": "H3H-Studio"
            },
            method="POST"
        )
        with urllib.request.urlopen(up_req) as resp:
            up_res = json.loads(resp.read().decode())
            print(f"[+] Uploaded {asset_name}: {up_res.get('browser_download_url')}")

    # Also update v1.2.7 assets with the fixed binaries so any direct v1.2.7 download gets the fixed build!
    print("\n[*] Updating v1.2.7 release assets with fixed binaries...")
    try:
        rel_127_url = f"https://api.github.com/repos/{repo}/releases/tags/v1.2.7"
        req_127 = urllib.request.Request(rel_127_url, headers=headers)
        with urllib.request.urlopen(req_127) as resp_127:
            rel_127_data = json.loads(resp_127.read().decode())
            base_127_upload = rel_127_data.get("upload_url", "").split("{")[0]
            for asset_name, nro_file in nros:
                for existing in rel_127_data.get("assets", []):
                    if existing.get("name") == asset_name:
                        print(f"[*] Deleting old {asset_name} in v1.2.7 (id: {existing['id']})...")
                        del_req = urllib.request.Request(
                            f"https://api.github.com/repos/{repo}/releases/assets/{existing['id']}",
                            headers=headers,
                            method="DELETE"
                        )
                        try:
                            urllib.request.urlopen(del_req)
                        except Exception:
                            pass
                print(f"[*] Uploading fixed {asset_name} to v1.2.7...")
                data = nro_file.read_bytes()
                up_req = urllib.request.Request(
                    f"{base_127_upload}?name={asset_name}",
                    data=data,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/octet-stream",
                        "User-Agent": "H3H-Studio"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(up_req) as resp:
                    print(f"[+] Updated {asset_name} in v1.2.7!")
    except Exception as ex:
        print(f"[-] Warning updating v1.2.7: {ex}")

    print("\n[SUCCESS] Hotfix Release v1.2.8 published and v1.2.7 refreshed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
