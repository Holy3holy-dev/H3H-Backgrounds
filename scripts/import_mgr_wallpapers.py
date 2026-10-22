"""
Dedicated script to download, transcode, upload, and catalog Metal Gear Rising & Metal Gear Solid
video backgrounds into catalog/data/catalog.json.
"""

import os
import sys
import re
import json
import uuid
import hashlib
import subprocess
import urllib.request
from pathlib import Path
from typing import Dict, Any, List

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "studio"))

from tg_bot.config import GDRIVE_FOLDER_ID, GDRIVE_REFRESH_TOKEN, detect_local_proxy
from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient
from scripts.auto_video_harvester import AutoVideoHarvester

# Setup local proxy for robust downloads
local_p = detect_local_proxy()
if local_p:
    print(f"[*] Using local proxy: {local_p}")
    proxy_handler = urllib.request.ProxyHandler({'http': local_p, 'https': local_p})
    opener = urllib.request.build_opener(proxy_handler)
    urllib.request.install_opener(opener)

MGR_SOURCES = [
    {
        "name": "Cyborg Ninja Raiden",
        "page_url": "https://moewalls.com/games/cyborg-ninja-raiden-metal-gear-rising-revengeance-live-wallpaper/",
        "style": "Cinematic 3D",
        "author": "Moewalls Community"
    },
    {
        "name": "Raiden Crimson Blade",
        "page_url": "https://moewalls.com/games/raiden-crimson-blade-metal-gear-rising-revengeance-live-wallpaper/",
        "style": "Dynamic Action",
        "author": "Moewalls Community"
    },
    {
        "name": "Raiden Jack the Ripper",
        "page_url": "https://moewalls.com/games/raiden-jack-metal-gear-rising-revengeance-live-wallpaper/",
        "style": "Cinematic 3D",
        "author": "Moewalls Community"
    },
    {
        "name": "Raiden Black & White Noir",
        "page_url": "https://moewalls.com/games/raiden-black-and-white-metal-gear-rising-live-wallpaper/",
        "style": "Minimalist Art",
        "author": "Moewalls Community"
    },
    {
        "name": "Raiden High-Frequency Blade",
        "page_url": "https://moewalls.com/games/raiden-metal-gear-rising-revengeance-live-wallpaper/",
        "style": "Official Theme",
        "author": "Moewalls Community"
    },
    {
        "name": "Solid Snake Shadow Moses",
        "page_url": "https://moewalls.com/games/solid-snake-metal-gear-solid-live-wallpaper/",
        "style": "Cinematic Gameplay",
        "author": "Moewalls Community"
    },
    {
        "name": "Big Boss Naked Snake",
        "page_url": "https://moewalls.com/games/big-boss-metal-gear-solid-live-wallpaper/",
        "style": "Atmospheric 2D",
        "author": "Moewalls Community"
    }
]

def harvest_mgr():
    harvester = AutoVideoHarvester(mode="main", codec="h264")
    
    # 1. Authenticate with Google Drive
    print("[*] Authenticating with Google Drive...")
    gdrive_cfg = GoogleDriveHelper.get_stored_config()
    refresh_tok = GDRIVE_REFRESH_TOKEN or gdrive_cfg.get("refresh_token")
    access_tok = GoogleDriveHelper.refresh_access_token(refresh_tok) or gdrive_cfg.get("token")
    if not access_tok:
        print("[-] Failed to get Google Drive access token!")
        return False
    print("[+] Google Drive OAuth token verified.")

    # 2. Load catalog.json
    cat_file = ROOT_DIR / "catalog" / "data" / "catalog.json"
    cat_data = json.loads(cat_file.read_text(encoding="utf-8"))
    games_map = {g.get("titleId"): g for g in cat_data.get("games", [])}

    mgr_tid = "01004D4752000000"
    if mgr_tid not in games_map:
        mgr_entry = {
            "titleId": mgr_tid,
            "title": "Metal Gear Rising: Revengeance",
            "publisher": "Konami / PlatinumGames",
            "variants": []
        }
        cat_data["games"].append(mgr_entry)
        games_map[mgr_tid] = mgr_entry
        print(f"[+] Added new game entry: Metal Gear Rising: Revengeance ({mgr_tid})")

    # MGS Master Collection Vol 1
    mgs_tid = "0100C1301A9C2000"

    added_count = 0
    for item in MGR_SOURCES:
        p_url = item["page_url"]
        name = item["name"]
        print(f"\n[*] Processing: {name}...")

        direct_v_url = harvester.extract_direct_video_url(p_url)
        if not direct_v_url:
            print(f"[-] Could not extract direct video from {p_url}")
            continue

        print(f"    Direct URL: {direct_v_url}")
        target_tid = mgs_tid if "Snake" in name or "Boss" in name else mgr_tid
        target_title = games_map[target_tid]["title"]

        ok = harvester.process_and_upload_asset(
            asset_url=direct_v_url,
            title_id=target_tid,
            game_title=target_title,
            var_name=name,
            author=item["author"],
            style=item["style"],
            catalog=cat_data,
            games_map=games_map,
            gdrive_token=access_tok
        )
        if ok:
            added_count += 1
            print(f"[+] Successfully harvested and cataloged: {name} for {target_title}")

    if added_count > 0:
        cat_file.write_text(json.dumps(cat_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[+] Saved catalog.json with {added_count} new Metal Gear backgrounds!")
        
        # Git commit & push
        try:
            subprocess.run(["git", "add", "catalog/data/catalog.json"], cwd=str(ROOT_DIR), check=True)
            subprocess.run(["git", "commit", "-m", f"feat(catalog): add {added_count} Metal Gear Rising & Solid video backgrounds"], cwd=str(ROOT_DIR), check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=str(ROOT_DIR), check=True)
            print("[+] Successfully pushed updated catalog to GitHub main!")
        except Exception as ge:
            print(f"[!] Git push notice: {ge}")

    return added_count

if __name__ == "__main__":
    harvest_mgr()
