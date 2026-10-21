"""
Batch Harvest Animated Themes from SteamGridDB for Nintendo Switch.
Encodes to 4IFIR profile, uploads to Google Drive, and syncs catalog to GitHub.
"""

import os
import sys
import json
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.steamgriddb import SteamGridDBClient
from h3h_studio.core.google_drive import GoogleDriveClient

OUTPUT_DIR = Path(r"e:\videofon\downloaded_official_backgrounds")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FOLDER_ID = "1hI1klJ6t2ymVoBwGA6IzY79QMjp5dTJC"
TOKEN = "ya29.a0AX07CmuycNHtflqEeffh6XtbRgDmkTxLMoFcfPfk7XbXeAhJYE0voc0R6FT8cKBJCb14bSwIIrkDiH6q4TVHqB2RlS_FJ1NDxvQR8aNUc6akfxSEW4l29zPbik7WjPDVBonvWDuczIavEbNQcCgCvMRKqSZBDArZbTCVsMqVn-9GrR43xyb7FzkVvTKUrksapAs8G3kaCgYKAbASARISFQHGX2Mit3ABcTJRFKxY6VHf_HLbow0206"

client = SteamGridDBClient()

TARGETS = [
    ("0100B1A00D8CE000", "DOOM Eternal", "DOOM Eternal"),
    ("010021C000B6A000", "The Binding of Isaac: Repentance", "The Binding of Isaac: Rebirth"),
    ("01006560184E6000", "Mortal Kombat 1", "Mortal Kombat 1"),
    ("0100CB000A142000", "Phoenix Wright: Ace Attorney Trilogy", "Phoenix Wright: Ace Attorney Trilogy"),
    ("010050F00BC1A000", "Resident Evil HD Remaster", "Resident Evil"),
    ("0100FA501AF90000", "Castlevania Dominus Collection", "Castlevania"),
    ("0100E46006708000", "Terraria", "Terraria"),
    ("0100E5D00CC0C000", "Unravel Two", "Unravel Two"),
    ("0100344012028000", "Subnautica", "Subnautica"),
    ("0100E65002BB8000", "Stardew Valley", "Stardew Valley"),
    ("010064800F66A000", "Borderlands Legendary Collection", "Borderlands 2"),
    ("0100D560102C8000", "BioShock The Collection", "BioShock Infinite"),
    ("0100770008DD8000", "Monster Hunter Generations Ultimate", "Monster Hunter: World"),
    ("010086B00B41E000", "Resident Evil 4", "Resident Evil 4 (2005)"),
    ("0100A00019DE0000", "Hades", "Hades")
]

def main():
    print(f"=== Starting SteamGridDB Batch Harvest ({len(TARGETS)} Multiplatform Switch Games) ===\n")

    converted_files = []

    for idx, (tid, switch_title, sgdb_query) in enumerate(TARGETS, 1):
        clean_name = "".join(c if c.isalnum() or c in "._- " else "" for c in switch_title).replace(" ", "_")
        target_mp4 = OUTPUT_DIR / f"{tid}_{clean_name}.mp4"

        if target_mp4.exists() and target_mp4.stat().st_size > 100000:
            print(f"[{idx}/{len(TARGETS)}] Already converted locally: {target_mp4.name}")
            converted_files.append((tid, switch_title, target_mp4))
            continue

        print(f"[{idx}/{len(TARGETS)}] Searching SteamGridDB for '{sgdb_query}' ({tid})...")
        games = client.search_game(sgdb_query)
        if not games:
            print(f"  [-] No search results for {sgdb_query}")
            continue

        game_id = games[0]["id"]
        game_name = games[0]["name"]
        print(f"  [+] Matched: {game_name} (ID: {game_id})")

        # 1. Try animated heroes
        heroes = client.get_animated_heroes(game_id)
        selected_art = None
        if heroes:
            selected_art = heroes[0]["url"]
            print(f"  [+] Found animated Hero ({len(heroes)} available)")
        else:
            # 2. Try animated grids
            grids = client.get_animated_grids(game_id)
            if grids:
                selected_art = grids[0]["url"]
                print(f"  [+] Found animated Grid ({len(grids)} available)")

        if not selected_art:
            print(f"  [-] No animated art found for {game_name}")
            continue

        print(f"  [*] Downloading & converting to 4IFIR 720p 30fps...")
        ok = client.download_and_convert(selected_art, target_mp4)
        if ok and target_mp4.exists():
            print(f"  [SUCCESS] Created {target_mp4.name} ({target_mp4.stat().st_size} bytes)")
            converted_files.append((tid, switch_title, target_mp4))
        else:
            print(f"  [-] Failed to convert {selected_art}")

    print(f"\n=== Uploading {len(converted_files)} Harvested Themes to Google Drive ===")
    for idx, (tid, title, path) in enumerate(converted_files, 1):
        print(f"[{idx}/{len(converted_files)}] Uploading {path.name}...")
        try:
            res = GoogleDriveClient.upload_file(path, FOLDER_ID, TOKEN)
            print(f"  -> Uploaded! Drive ID: {res.get('id')}")
        except Exception as e:
            print(f"  -> Upload note: {e}")

    print("\n=== Running Final Catalog Sync to GitHub ===")
    from scripts.sync_drive_to_catalog import main as sync_catalog
    sync_catalog()

if __name__ == "__main__":
    main()
