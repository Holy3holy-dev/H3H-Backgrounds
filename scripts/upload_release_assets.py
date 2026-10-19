"""
Upload updated H3H-Backgrounds.nro and H3H-Studio.exe to GitHub Releases v1.0.0.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "studio"))
from h3h_studio.core.github_publisher import GitHubPublisher

def main():
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("ERROR: GitHub token not found.")
        return 1

    repo = "Holy3holy-dev/H3H-Backgrounds"
    tag = "v1.0.0"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio"
    }

    rel_url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    req = urllib.request.Request(rel_url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        rel_data = json.loads(resp.read().decode("utf-8"))

    upload_base = rel_data["upload_url"].split("{")[0]

    files_to_upload = [
        ("H3H-Backgrounds.nro", Path(r"E:\videofon\downloader\H3H-Backgrounds.nro")),
        ("H3H-Studio.exe", Path(r"E:\videofon\dist\H3H-Studio.exe")),
    ]

    for name, path in files_to_upload:
        print(f"[*] Processing {name} ({path.stat().st_size} bytes)...")
        for asset in rel_data.get("assets", []):
            if asset["name"] == name:
                asset_id = asset["id"]
                print(f"[-] Deleting existing asset {name} (ID: {asset_id})...")
                del_req = urllib.request.Request(asset["url"], headers=headers, method="DELETE")
                with urllib.request.urlopen(del_req) as del_resp:
                    pass
                print(f"[+] Deleted old {name}")

        upload_url = f"{upload_base}?name={urllib.parse.quote(name)}"
        print(f"[*] Reading and uploading {name}...")
        with open(path, "rb") as f:
            data = f.read()

        u_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "User-Agent": "H3H-Studio"
        }
        u_req = urllib.request.Request(upload_url, data=data, headers=u_headers, method="POST")
        with urllib.request.urlopen(u_req, timeout=300) as u_resp:
            res = json.loads(u_resp.read().decode("utf-8"))
        print(f"[+] Successfully uploaded {name} -> {res.get('browser_download_url')}")

    print("[*] All assets successfully updated!")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
