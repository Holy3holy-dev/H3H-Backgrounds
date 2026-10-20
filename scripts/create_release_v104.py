"""
Create GitHub Release v1.0.4, update version.json on GitHub, and upload H3H-Backgrounds.nro.
"""

import json
import sys
import base64
import urllib.request
import urllib.error
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str((ROOT_DIR / "studio").resolve()))
from h3h_studio.core.github_publisher import GitHubPublisher
from h3h_studio.core.google_drive import GoogleDriveHelper


def update_github_file(repo: str, file_path: Path, repo_path: str, token: str, commit_msg: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio"
    }
    content_url = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    sha = None
    try:
        req = urllib.request.Request(content_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            sha = data.get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise e

    content_bytes = file_path.read_bytes()
    b64 = base64.b64encode(content_bytes).decode("ascii")
    payload = {
        "message": commit_msg,
        "content": b64
    }
    if sha:
        payload["sha"] = sha

    put_req = urllib.request.Request(
        content_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="PUT"
    )
    with urllib.request.urlopen(put_req, timeout=15):
        print(f"[+] Synced {repo_path} to GitHub!")


def main():
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("ERROR: GitHub token not found.")
        return 1

    repo = "Holy3holy-dev/H3H-Backgrounds"
    tag = "v1.0.4"
    name = "H3H Backgrounds v1.0.4 (1280x720 Fullscreen Preview, Two-Pane D-Pad Nav, 638 Games)"
    body = (
        "## Что нового в v1.0.4 / What's new in v1.0.4:\n\n"
        "- 🎬 **Полноэкранный предпросмотр на лету (1280x720 HD):** По нажатию кнопки [X] видеофон открывается на весь экран Switch. Переключайте варианты на лету кнопками D-Pad Влево / Вправо прямо на полном экране и устанавливайте понравившийся в 1 клик через [A]!\n"
        "- 🎮 **Удобная двухколоночная навигация в «Мои игры»:** Вверх/Вниз листает список игр. Нажатие Вправо или [A] переносит фокус к вариантам фонов, где Вверх/Вниз листает варианты. Влево или [B] плавно возвращает фокус к списку игр.\n"
        "- 🗑️ **Безопасная кнопка удаления видеофона:** Кнопка [Y] Удалить видеофон перенесена в удобное место под статусом игры (X=530), где она никогда не перекрывается оверлеем Tesla / Status Monitor.\n"
        "- 📊 **Отображение реального размера видео:** Исправлен баг «0 MB» — во всей базе (686 вариантов) проставлен точный вес файлов.\n"
        "- 🔊 **Индикаторы звука:** На карточках вариантов и в режиме предпросмотра отображаются бейджи [ЗВУК] / [БЕЗ ЗВУКА].\n"
        "- 🛡️ **Защита от наложения текста:** Строгие лимиты ширины текста и автоматический перенос длинных названий по словам (Word-Wrap) в окнах подтверждения установки.\n"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio"
    }

    # 1. Update version.json on GitHub main branch
    print("[*] Updating version.json on GitHub...")
    update_github_file(
        repo=repo,
        file_path=ROOT_DIR / "version.json",
        repo_path="version.json",
        token=token,
        commit_msg="release: bump version to 1.0.4"
    )

    # 2. Update catalog.json on GitHub main branch
    print("[*] Updating catalog.json on GitHub...")
    update_github_file(
        repo=repo,
        file_path=ROOT_DIR / "catalog" / "data" / "catalog.json",
        repo_path="catalog/data/catalog.json",
        token=token,
        commit_msg="feat(catalog): sync 638 games catalog with accurate file sizes and audio tags"
    )

    # 3. Create or fetch release v1.0.4
    rel_url = f"https://api.github.com/repos/{repo}/releases"
    payload = json.dumps({
        "tag_name": tag,
        "target_commitish": "main",
        "name": name,
        "body": body,
        "draft": False,
        "prerelease": False
    }).encode("utf-8")

    req = urllib.request.Request(rel_url, data=payload, headers=headers, method="POST")
    rel_data = None
    try:
        with urllib.request.urlopen(req) as resp:
            rel_data = json.loads(resp.read().decode("utf-8"))
            print(f"[+] Created release {tag}: {rel_data.get('html_url')}")
    except urllib.error.HTTPError as e:
        print(f"[*] Release status: {e.code}, fetching existing tag...")
        get_req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/tags/{tag}", headers=headers)
        with urllib.request.urlopen(get_req) as resp:
            rel_data = json.loads(resp.read().decode("utf-8"))

    upload_base = rel_data["upload_url"].split("{")[0]
    nro_path = ROOT_DIR / "H3H-Backgrounds.nro"

    if nro_path.exists():
        print(f"[*] Uploading H3H-Backgrounds.nro ({nro_path.stat().st_size} bytes)...")
        for asset in rel_data.get("assets", []):
            if asset["name"] == "H3H-Backgrounds.nro":
                del_req = urllib.request.Request(asset["url"], headers=headers, method="DELETE")
                with urllib.request.urlopen(del_req):
                    pass
                print("[-] Deleted old asset from v1.0.4")

        upload_url = f"{upload_base}?name=H3H-Backgrounds.nro"
        data = nro_path.read_bytes()

        up_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "User-Agent": "H3H-Studio"
        }
        up_req = urllib.request.Request(upload_url, data=data, headers=up_headers, method="POST")
        with urllib.request.urlopen(up_req) as up_resp:
            res = json.loads(up_resp.read().decode("utf-8"))
            print(f"[+] Uploaded to {tag}: {res.get('browser_download_url')}")

        # Also update v1.0.3 and v1.0.2 assets so any existing download URL immediately gets v1.0.4
        for compat_tag in ["v1.0.3", "v1.0.2", "v1.0.0"]:
            try:
                c_req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/tags/{compat_tag}", headers=headers)
                with urllib.request.urlopen(c_req) as resp:
                    c_rel = json.loads(resp.read().decode("utf-8"))
                    for asset in c_rel.get("assets", []):
                        if asset["name"] == "H3H-Backgrounds.nro":
                            del_req = urllib.request.Request(asset["url"], headers=headers, method="DELETE")
                            with urllib.request.urlopen(del_req):
                                pass
                    c_up_base = c_rel["upload_url"].split("{")[0]
                    c_up_req = urllib.request.Request(f"{c_up_base}?name=H3H-Backgrounds.nro", data=data, headers=up_headers, method="POST")
                    with urllib.request.urlopen(c_up_req):
                        print(f"[+] Updated {compat_tag} asset for backwards-compatibility!")
            except Exception as e:
                print(f"[-] Note on {compat_tag}: {e}")

    print("\n✅ Release v1.0.4 successfully published and live on GitHub!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
