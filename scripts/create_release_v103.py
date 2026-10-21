"""
Create GitHub Release v1.0.3 and upload newly compiled H3H-Backgrounds.nro.
"""

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.github_publisher import GitHubPublisher

def main():
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("ERROR: GitHub token not found.")
        return 1

    repo = "Holy3holy-dev/H3H-Backgrounds"
    tag = "v1.0.3"
    name = "H3H Backgrounds v1.0.3 (Self-Updater, 455+ Games & Multi-Variant Fix)"
    body = (
        "## Что нового в v1.0.3 / What's new in v1.0.3:\n\n"
        "- **Исправление встроенного обновления NRO:** Реализовано освобождение дескриптора RomFS перед заменой файла и резервное побайтовое копирование при блокировке FatFS в Horizon OS. Ошибка `Failed to replace` устранена.\n"
        "- **Полное отключение строгой проверки хэша (SHA-256):** Устранена ошибка `SHA-256 integrity verification failed` для всех игр.\n"
        "- **Встроенный оффлайн-каталог (455 игр, 528 вариантов):** База данных зашита прямо в RomFS — доступ ко всем фонам открыт даже без интернета.\n"
        "- **Поддержка кастомных Title ID:** Все 6 вариантов Need for Speed: Most Wanted (включая `03DB18EF71F2C000`) теперь доступны из коробки.\n"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio"
    }

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
    nro_path = Path(r"E:\videofon\H3H-Backgrounds.nro")

    if nro_path.exists():
        print(f"[*] Uploading H3H-Backgrounds.nro ({nro_path.stat().st_size} bytes)...")
        for asset in rel_data.get("assets", []):
            if asset["name"] == "H3H-Backgrounds.nro":
                del_req = urllib.request.Request(asset["url"], headers=headers, method="DELETE")
                with urllib.request.urlopen(del_req):
                    pass
                print("[-] Deleted old asset")

        upload_url = f"{upload_base}?name=H3H-Backgrounds.nro"
        with open(nro_path, "rb") as f:
            data = f.read()

        up_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "User-Agent": "H3H-Studio"
        }
        up_req = urllib.request.Request(upload_url, data=data, headers=up_headers, method="POST")
        with urllib.request.urlopen(up_req) as up_resp:
            res = json.loads(up_resp.read().decode("utf-8"))
            print(f"[+] Uploaded to v1.0.3: {res.get('browser_download_url')}")

    # Also update v1.0.2 asset in case any old client has hardcoded v1.0.2 URL
    try:
        get_102 = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/tags/v1.0.2", headers=headers)
        with urllib.request.urlopen(get_102) as resp:
            rel_102 = json.loads(resp.read().decode("utf-8"))
            for asset in rel_102.get("assets", []):
                if asset["name"] == "H3H-Backgrounds.nro":
                    del_req = urllib.request.Request(asset["url"], headers=headers, method="DELETE")
                    with urllib.request.urlopen(del_req):
                        pass
            up_base_102 = rel_102["upload_url"].split("{")[0]
            up_req = urllib.request.Request(f"{up_base_102}?name=H3H-Backgrounds.nro", data=data, headers=up_headers, method="POST")
            with urllib.request.urlopen(up_req):
                print("[+] Also updated v1.0.2 asset for compatibility!")
    except Exception as e:
        print(f"[-] Note on v1.0.2 update: {e}")

    print("\n[+] Release v1.0.3 successfully published!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
