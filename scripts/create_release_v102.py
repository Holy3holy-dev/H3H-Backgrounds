"""
Create GitHub Release v1.0.2 and upload H3H-Backgrounds.nro and H3H-Studio.exe.
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
    tag = "v1.0.2"
    name = "H3H Backgrounds v1.0.2 (Hotfix: Filesize Mismatch & Homebrew Ports)"
    body = (
        "## Что нового в v1.0.2 / What's new in v1.0.2:\n\n"
        "- **Fix Filesize Mismatch:** Отключена строгая проверка размера файлов при скачивании, устранена ошибка `File size mismatch` при установке видеофонов (Zelda BotW и др.).\n"
        "- **Homebrew Ports Support:** Снято ограничение `0x1FFF` — теперь отображаются и поддерживаются любые Title ID для неофициальных портов (Call of Duty 4: Modern Warfare, Need for Speed и др.).\n"
        "- **Автоочистка дубликатов:** При обновлении старый `sdmc:/switch/H3H-Backgrounds.nro` автоматически удаляется из корня, предотвращая появление двух иконок в hbmenu.\n"
        "- **Каталог 187+ игр:** В онлайн-библиотеке уже доступно более 204 видеофонов для Switch (4IFIR 720p 30fps).\n"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio"
    }

    # 1. Create or get Release
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
    try:
        with urllib.request.urlopen(req) as resp:
            rel_data = json.loads(resp.read().decode("utf-8"))
            print(f"[+] Created release {tag}: {rel_data.get('html_url')}")
    except urllib.error.HTTPError as e:
        print(f"[*] Release creation status: {e.code}, checking existing tag...")
        get_req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/tags/{tag}", headers=headers)
        with urllib.request.urlopen(get_req) as resp:
            rel_data = json.loads(resp.read().decode("utf-8"))

    upload_base = rel_data["upload_url"].split("{")[0]

    files_to_upload = [
        ("H3H-Backgrounds.nro", Path(r"E:\videofon\downloader\H3H-Backgrounds.nro")),
        ("H3H-Studio.exe", Path(r"E:\videofon\dist\H3H-Studio.exe")),
    ]

    for filename, filepath in files_to_upload:
        if not filepath.exists():
            print(f"[-] File not found: {filepath}")
            continue

        print(f"[*] Uploading {filename} ({filepath.stat().st_size} bytes)...")
        # Check existing assets in release
        for asset in rel_data.get("assets", []):
            if asset["name"] == filename:
                del_req = urllib.request.Request(asset["url"], headers=headers, method="DELETE")
                with urllib.request.urlopen(del_req):
                    pass
                print(f"[-] Deleted old asset {filename}")

        upload_url = f"{upload_base}?name={filename}"
        with open(filepath, "rb") as f:
            data = f.read()

        up_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "User-Agent": "H3H-Studio"
        }
        up_req = urllib.request.Request(upload_url, data=data, headers=up_headers, method="POST")
        with urllib.request.urlopen(up_req) as up_resp:
            res = json.loads(up_resp.read().decode("utf-8"))
            print(f"[+] Uploaded {filename} -> {res.get('browser_download_url')}")

    print("\n[+] Release v1.0.2 published successfully!")

if __name__ == "__main__":
    main()
