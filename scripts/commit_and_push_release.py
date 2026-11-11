"""
Единый публикатор релиза v1.5.0 (Main + AfterDark):
1. Коммитит исходники v1.5.0, оба бинарника NRO, каталоги и сжатые турбо-индексы (.min.json + .min.json.gz).
2. Пушит изменения в ветку main и синхронизирует ветку after-dark.
3. Создает/обновляет GitHub Release v1.5.0 и загружает оба OTA-бинарника: H3H-Backgrounds.nro и H3H-AfterDark.nro.
"""

import json
import os
import sys
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "studio"))
sys.path.insert(0, str(PROJECT_ROOT))

from h3h_studio.core.github_publisher import GitHubPublisher
from tg_bot.config import detect_local_proxy


def upload_release_asset(opener, api_base: str, rel_id: int, upload_base: str, gh_token: str, file_path: Path, asset_name: str) -> None:
    if not file_path.exists():
        print(f"[-] Файл ассета не найден: {file_path}")
        return

    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "H3H-Release-Publisher/1.5.0",
    }

    # Если ассет с таким именем уже есть в релизе — удаляем перед перезаписью
    try:
        list_req = urllib.request.Request(f"{api_base}/releases/{rel_id}/assets", headers=headers)
        with opener.open(list_req, timeout=30) as resp:
            existing_assets = json.loads(resp.read().decode("utf-8"))
            for a in existing_assets:
                if a.get("name") == asset_name:
                    del_req = urllib.request.Request(
                        f"{api_base}/releases/assets/{a['id']}",
                        headers=headers,
                        method="DELETE",
                    )
                    opener.open(del_req, timeout=30).close()
                    print(f"[*] Предыдущий ассет {asset_name} удален для обновления")
                    break
    except Exception as exc:
        print(f"[*] Проверка существующих ассетов ({asset_name}): {exc}")

    data = file_path.read_bytes()
    print(f"[*] Загрузка {asset_name} ({len(data) / (1024 * 1024):.2f} MB) в GitHub Release v1.5.0...")
    up_req = urllib.request.Request(
        f"{upload_base}?name={asset_name}",
        data=data,
        headers={**headers, "Content-Type": "application/octet-stream"},
        method="POST",
    )
    with opener.open(up_req, timeout=180) as resp:
        if resp.status in (200, 201):
            print(f"[+] Успешно загружен {asset_name} ({len(data):,} байт)!")


def main() -> int:
    gh_token, _ = GitHubPublisher.get_stored_credentials()
    if not gh_token:
        print("[-] GitHub token not found!")
        return 1

    local_proxy = detect_local_proxy()
    repo_url = f"https://x-access-token:{gh_token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"

    git_env = os.environ.copy()
    git_env["GIT_EDITOR"] = ":"
    git_env["GIT_TERMINAL_PROMPT"] = "0"
    if local_proxy:
        git_env["http_proxy"] = local_proxy
        git_env["https_proxy"] = local_proxy

    files_to_add = [
        ("H3H-Backgrounds.nro", True),
        ("H3H-AfterDark.nro", True),
        ("downloader/H3H-Backgrounds.nro", True),
        ("downloader/H3H-AfterDark.nro", True),
        ("downloader/romfs/catalog.json", False),
        ("catalog/data/catalog.json", False),
        ("catalog/data/catalog.min.json", False),
        ("catalog/data/catalog.min.json.gz", False),
        ("catalog/data/catalog_after_dark.json", False),
        ("catalog/data/catalog_after_dark.min.json", False),
        ("catalog/data/catalog_after_dark.min.json.gz", False),
        ("downloader/include/core/config.hpp", False),
        ("downloader/include/core/types.hpp", False),
        ("downloader/include/core/installer.hpp", False),
        ("downloader/include/ui/app.hpp", False),
        ("downloader/src/core/installer.cpp", False),
        ("downloader/src/platform/switch_platform.cpp", False),
        ("downloader/src/ui/app.cpp", False),
        ("studio/h3h_studio/core/express_processor.py", False),
        ("scripts/build_min_catalog.py", False),
        ("scripts/build_nro.py", False),
        ("scripts/build_nro_after_dark.py", False),
        ("scripts/generate_batch_hq_icons.py", False),
        ("scripts/auto_video_harvester.py", False),
        ("scripts/commit_and_push_release.py", False),
        ("version.json", False),
    ]

    print("[*] Индексация файлов релиза v1.5.0 (Main + AfterDark)...")
    for f, force in files_to_add:
        full_p = PROJECT_ROOT / f
        if full_p.exists():
            cmd = ["git", "add", "-f", f] if force else ["git", "add", f]
            subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)

    msg = (
        "feat(release): v1.5.0 Main & AfterDark — live console radar, Split-Studio 16:9+1:1 catalog, "
        "unified controls, Ultra-HQ 256x256 v2 icons & gzipped turbo index [skip render] [skip ci]"
    )
    print(f"[*] Коммит: {msg}")
    res = subprocess.run(["git", "commit", "-m", msg], cwd=str(PROJECT_ROOT), env=git_env, capture_output=True, text=True)
    print("Commit STDOUT:", res.stdout)
    if res.stderr:
        print("Commit STDERR:", res.stderr)

    print("[*] Отправка в ветку main...")
    res_main = subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/main"], cwd=str(PROJECT_ROOT), env=git_env, capture_output=True, text=True)
    print("Main Push Exit:", res_main.returncode, res_main.stdout, res_main.stderr)
    if res_main.returncode != 0:
        print("[-] Ошибка отправки в main!")
        return 1

    print("[*] Отправка каталога и сборки в ветку after-dark...")
    res_ad = subprocess.run(["git", "push", "--force", repo_url, "HEAD:refs/heads/after-dark"], cwd=str(PROJECT_ROOT), env=git_env, capture_output=True, text=True)
    print("After-Dark Push Exit:", res_ad.returncode, res_ad.stderr)

    # Создание / обновление GitHub Release v1.5.0 с обоими NRO
    try:
        opener = (
            urllib.request.build_opener(urllib.request.ProxyHandler({"http": local_proxy, "https": local_proxy}))
            if local_proxy else urllib.request.build_opener()
        )
        ver_data = json.loads((PROJECT_ROOT / "version.json").read_text(encoding="utf-8"))
        body_text = ver_data.get("changelogRu", "") + "\n\n---\n\n" + ver_data.get("changelog", "")
        api_base = "https://api.github.com/repos/Holy3holy-dev/H3H-Backgrounds"
        headers = {
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "H3H-Release-Publisher/1.5.0",
        }

        rel_obj = None
        try:
            req = urllib.request.Request(f"{api_base}/releases/tags/v1.5.0", headers=headers)
            with opener.open(req, timeout=30) as resp:
                rel_obj = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                payload = json.dumps({
                    "tag_name": "v1.5.0",
                    "target_commitish": "main",
                    "name": "H3H Backgrounds & After Dark v1.5.0 — Split-Studio, Live Console Radar & Ultra-HQ Icons",
                    "body": body_text,
                    "draft": False,
                    "prerelease": False,
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{api_base}/releases",
                    data=payload,
                    headers={**headers, "Content-Type": "application/json"},
                    method="POST",
                )
                with opener.open(req, timeout=30) as resp:
                    rel_obj = json.loads(resp.read().decode("utf-8"))

        if rel_obj and "upload_url" in rel_obj and "id" in rel_obj:
            upload_base = rel_obj["upload_url"].split("{")[0]
            rel_id = int(rel_obj["id"])
            upload_release_asset(
                opener, api_base, rel_id, upload_base, gh_token,
                PROJECT_ROOT / "H3H-Backgrounds.nro", "H3H-Backgrounds.nro"
            )
            upload_release_asset(
                opener, api_base, rel_id, upload_base, gh_token,
                PROJECT_ROOT / "H3H-AfterDark.nro", "H3H-AfterDark.nro"
            )
            print("[SUCCESS] Релиз v1.5.0 опубликован с обоими NRO бинарниками!")
    except Exception as exc:
        print(f"[!] Примечание при публикации GitHub Release: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
