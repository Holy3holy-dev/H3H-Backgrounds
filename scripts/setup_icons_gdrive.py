import sys
import os
import json
import urllib.request
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "studio")

from tg_bot.bot import get_gdrive_auth
from h3h_studio.core.google_drive import GoogleDriveClient

tok, root_folder_id = get_gdrive_auth("standard")
print(f"[*] Access token obtained. Root folder: {root_folder_id}")

# 1. Query folders to see existing structure
url = "https://www.googleapis.com/drive/v3/files?q=mimeType%3D%27application%2Fvnd.google-apps.folder%27+and+trashed%3Dfalse&fields=files(id,name,parents)"
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})

existing_icons_folder = None
try:
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read().decode())
    print("[*] Existing Google Drive folders:")
    for f in data.get("files", []):
        fname = f.get("name")
        fid = f.get("id")
        print(f"    - {fname} ({fid})")
        if fname.lower() in ["h3h_video_icons", "video_icons", "icons", "h3h icons"]:
            existing_icons_folder = fid
except Exception as e:
    print(f"[!] Error querying folders: {e}")

# 2. Create H3H_Video_Icons folder if not found
if not existing_icons_folder:
    print("[*] Creating dedicated folder 'H3H_Video_Icons' inside root project folder...")
    folder_meta = {
        "name": "H3H_Video_Icons",
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [root_folder_id]
    }
    create_req = urllib.request.Request(
        "https://www.googleapis.com/drive/v3/files?fields=id,name",
        data=json.dumps(folder_meta).encode("utf-8"),
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(create_req) as r:
        res = json.loads(r.read().decode())
        existing_icons_folder = res.get("id")
    print(f"[+] Created 'H3H_Video_Icons' with Folder ID: {existing_icons_folder}")

    # Set public read permissions on the folder
    perm_meta = {"role": "reader", "type": "anyone"}
    perm_req = urllib.request.Request(
        f"https://www.googleapis.com/drive/v3/files/{existing_icons_folder}/permissions",
        data=json.dumps(perm_meta).encode("utf-8"),
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(perm_req) as r:
            print("[+] Set public permissions on 'H3H_Video_Icons' folder!")
    except Exception as ep:
        print(f"[!] Permission notice: {ep}")
else:
    print(f"[+] Found existing icons folder: {existing_icons_folder}")

print(f"\n[RESULT] GDRIVE_ICONS_FOLDER_ID = '{existing_icons_folder}'")
