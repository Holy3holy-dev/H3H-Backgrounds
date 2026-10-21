"""
Uploads H3H-AfterDark.nro directly to the official GitHub Release v1.2.5.
"""

import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT / "studio"))
from h3h_studio.core.github_publisher import GitHubPublisher

def main():
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("ERROR: GitHub token not found.")
        return 1

    repo = "Holy3holy-dev/H3H-Backgrounds"
    tag = "v1.2.5"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio"
    }

    # 1. Fetch release info
    print(f"[*] Fetching release info for {tag}...")
    get_req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/tags/{tag}", headers=headers)
    try:
        with urllib.request.urlopen(get_req) as resp:
            rel_data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[-] Could not find release {tag}: {e}")
        return 1

    upload_url_tmpl = rel_data.get("upload_url", "")
    upload_base = upload_url_tmpl.split("{")[0]

    # Check if H3H-AfterDark.nro already exists in assets, delete if updating
    existing_asset_id = None
    for asset in rel_data.get("assets", []):
        if asset.get("name") == "H3H-AfterDark.nro":
            existing_asset_id = asset.get("id")
            break

    if existing_asset_id:
        print(f"[*] Deleting existing H3H-AfterDark.nro asset ({existing_asset_id}) to overwrite...")
        del_req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/releases/assets/{existing_asset_id}",
            headers=headers,
            method="DELETE"
        )
        try:
            with urllib.request.urlopen(del_req) as resp:
                print("[+] Deleted old asset.")
        except Exception as e:
            print(f"[-] Warning deleting old asset: {e}")

    # 2. Upload H3H-AfterDark.nro
    nro_path = PROJECT_ROOT / "H3H-AfterDark.nro"
    if not nro_path.exists():
        nro_path = PROJECT_ROOT / "downloader" / "H3H-AfterDark.nro"

    if not nro_path.exists():
        print(f"ERROR: {nro_path} not found.")
        return 1

    nro_data = nro_path.read_bytes()
    asset_url = f"{upload_base}?name=H3H-AfterDark.nro"
    upload_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "User-Agent": "H3H-Studio"
    }

    print(f"[*] Uploading H3H-AfterDark.nro ({len(nro_data)} bytes)...")
    up_req = urllib.request.Request(asset_url, data=nro_data, headers=upload_headers, method="POST")
    try:
        with urllib.request.urlopen(up_req) as resp:
            asset_data = json.loads(resp.read().decode("utf-8"))
            dl_url = asset_data.get("browser_download_url")
            print(f"[+] UPLOAD SUCCESSFUL!")
            print(f"    Download URL: {dl_url}")
            return 0
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        print(f"[-] Upload error ({e.code}): {err_msg}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
