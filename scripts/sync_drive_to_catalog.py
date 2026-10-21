"""
Sync all files in Google Drive folder directly to catalog/data/catalog.json and push to GitHub.
Uses sizeBytes: 0 and sha256: "" for safe downloads on all Switch versions.
"""

import os
import sys
import json
import urllib.request
import re
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path("studio").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))

from h3h_studio.core.github_publisher import GitHubPublisher
from h3h_studio.core.google_drive import GoogleDriveHelper
from auto_harvest_pipeline import get_gdrive_credentials

CAT_PATH = Path("catalog/data/catalog.json")
LOG_PATH = Path("catalog/data/steamgriddb_harvest_log.json")
DB_PATH = Path("studio/h3h_studio/data/switch_titles_db.json")

def load_title_db():
    name_map = {}
    if DB_PATH.exists():
        with open(DB_PATH, "r", encoding="utf-8") as f:
            for entry in json.load(f):
                tid = entry.get("titleId", "").upper()
                if tid:
                    name_map[tid] = entry.get("title", "")
    return name_map

def main():
    token, folder_id = get_gdrive_credentials()

    print("[*] Loading database and existing catalog...")
    db_names = load_title_db()

    with open(CAT_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    # Index existing games by titleId
    games_by_id = {g["titleId"].upper(): g for g in catalog.get("games", [])}

    print("[*] Fetching file list from Google Drive folder...")
    headers = {"Authorization": f"Bearer {token}"}
    drive_files = []
    page_token = None
    while True:
        url = f"https://www.googleapis.com/drive/v3/files?q='{folder_id}'+in+parents+and+trashed=false&pageSize=1000&fields=nextPageToken,files(id,name,size)"
        if page_token:
            url += f"&pageToken={page_token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            drive_files.extend(data.get('files', []))
            page_token = data.get('nextPageToken')
            if not page_token:
                break

    print(f"[+] Total files in Google Drive: {len(drive_files)}")

    added_games = 0
    updated_variants = 0

    for f in drive_files:
        fname = f["name"]
        fid = f["id"]
        if not fname.lower().endswith(".mp4"):
            continue

        # Extract 16-hex Title ID from filename prefix
        m = re.match(r"^([0-9A-Fa-f]{16})[_\.-]?(.*)\.mp4$", fname)
        if not m:
            continue

        tid = m.group(1).upper()
        raw_name = m.group(2).strip("_-. ")
        clean_name = raw_name.replace("_", " ") if raw_name else "Default"

        direct_url = f"https://drive.google.com/uc?export=download&id={fid}"
        preview_url = f"https://drive.google.com/thumbnail?id={fid}&sz=w640"

        variant_obj = {
            "id": f"var-{fid[:8]}",
            "name": clean_name if clean_name else "Default",
            "style": "Animated Art",
            "version": "1.0",
            "url": direct_url,
            "previewUrl": preview_url,
            "sizeBytes": 0,
            "sha256": "",
            "durationSec": 20.0,
            "author": "Holy3holy-dev",
            "codec": "h264",
            "width": 1280,
            "height": 720,
            "fps": 30.0,
            "hasAudio": False,
            "notes": f"Google Drive: {fname}"
        }

        if tid in games_by_id:
            game = games_by_id[tid]
            variants = game.setdefault("variants", [])
            # Check if variant already exists with this URL
            if not any(v.get("url") == direct_url for v in variants):
                variants.append(variant_obj)
                updated_variants += 1
        else:
            game_title = db_names.get(tid, clean_name if clean_name else f"Game {tid}")
            new_game = {
                "titleId": tid,
                "title": game_title,
                "publisher": "Unknown",
                "variants": [variant_obj]
            }
            games_by_id[tid] = new_game
            catalog.setdefault("games", []).append(new_game)
            added_games += 1

    catalog["totalGames"] = len(catalog.get("games", []))
    catalog["totalVariants"] = sum(len(g.get("variants", [])) for g in catalog.get("games", []))

    print(f"\n[+] Added {added_games} new games to catalog")
    print(f"[+] Added {updated_variants} new variants to existing games")
    print(f"[+] Total games now in catalog: {catalog['totalGames']}")
    print(f"[+] Total variants now in catalog: {catalog['totalVariants']}")

    with open(CAT_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print("\n[*] Pushing catalog to GitHub...")
    gh_token, _ = GitHubPublisher.get_stored_credentials()
    if gh_token:
        GoogleDriveHelper.sync_catalog_to_github(
            catalog_path=CAT_PATH,
            token=gh_token,
            progress_cb=print
        )
        if LOG_PATH.exists():
            GoogleDriveHelper.sync_file_to_github(
                file_path=LOG_PATH,
                repo_path="catalog/data/steamgriddb_harvest_log.json",
                token=gh_token,
                commit_message="feat(catalog): sync harvest tracking log",
                progress_cb=print
            )
        print("✅ Catalog successfully pushed to GitHub!")

if __name__ == "__main__":
    main()
