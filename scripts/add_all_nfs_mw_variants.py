"""
Convert SGDB NFS Most Wanted animated heroes, upload to Google Drive,
and link all existing and new variants to the user's Title ID (03DB18EF71F2C000)
and all other known NFS Most Wanted Title IDs.
"""

import sys
import json
import re
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, 'studio')
sys.path.insert(0, 'scripts')

from h3h_studio.core.steamgriddb import SteamGridDBClient
from h3h_studio.core.google_drive import GoogleDriveClient, GoogleDriveHelper
from h3h_studio.core.github_publisher import GitHubPublisher
from auto_harvest_pipeline import get_gdrive_credentials

OUTPUT_DIR = Path("downloaded_official_backgrounds")
CAT_PATH = Path("catalog/data/catalog.json")

USER_MW_TID = "03DB18EF71F2C000"
ALL_MW_TIDS = [
    "03DB18EF71F2C000",
    "01004E46534D0000",
    "01004D5700000000",
    "0100000000000001",
    "0100000000000004",
]

# 1. First, grab the 4 existing variants already on Google Drive
EXISTING_VARIANTS = [
    {
        "id": "var-mw-intro",
        "name": "NFS MW: BMW M3 GTR Intro",
        "style": "Cinematic",
        "version": "1.0",
        "url": "https://drive.google.com/uc?export=download&id=1FsdxfgiWtZn5FZULpVsGXxmBMcK4IE4_",
        "previewUrl": "https://drive.google.com/thumbnail?id=1FsdxfgiWtZn5FZULpVsGXxmBMcK4IE4_&sz=w640",
        "sizeBytes": 0,
        "sha256": "",
        "durationSec": 20.0,
        "author": "Holy3holy-dev",
        "codec": "h264",
        "width": 1280,
        "height": 720,
        "fps": 30.0,
        "hasAudio": False,
        "notes": "Classic M3 GTR Cutscene Intro"
    },
    {
        "id": "var-mw-blacklist",
        "name": "NFS MW: Blacklist Pursuit",
        "style": "Cinematic",
        "version": "1.0",
        "url": "https://drive.google.com/uc?export=download&id=1vkXU_2eWSjAVAlYEYIZGFBMKINUUsAM-",
        "previewUrl": "https://drive.google.com/thumbnail?id=1vkXU_2eWSjAVAlYEYIZGFBMKINUUsAM-&sz=w640",
        "sizeBytes": 0,
        "sha256": "",
        "durationSec": 20.0,
        "author": "Holy3holy-dev",
        "codec": "h264",
        "width": 1280,
        "height": 720,
        "fps": 30.0,
        "hasAudio": False,
        "notes": "Rockport Blacklist Pursuit"
    },
    {
        "id": "var-mw-highway",
        "name": "NFS MW: Rockport Highway",
        "style": "Gameplay",
        "version": "1.0",
        "url": "https://drive.google.com/uc?export=download&id=185FEVgKFc4lp9sxh3Xz0Dqh-YKDytjnJ",
        "previewUrl": "https://drive.google.com/thumbnail?id=185FEVgKFc4lp9sxh3Xz0Dqh-YKDytjnJ&sz=w640",
        "sizeBytes": 0,
        "sha256": "",
        "durationSec": 20.0,
        "author": "Holy3holy-dev",
        "codec": "h264",
        "width": 1280,
        "height": 720,
        "fps": 30.0,
        "hasAudio": False,
        "notes": "High Speed Police Evade"
    },
    {
        "id": "var-mw-chase",
        "name": "NFS MW: Police Chase Action",
        "style": "Action",
        "version": "1.0",
        "url": "https://drive.google.com/uc?export=download&id=1PhhoQiuu8b9edT_EMAhVl6jrT7E0LU1s",
        "previewUrl": "https://drive.google.com/thumbnail?id=1PhhoQiuu8b9edT_EMAhVl6jrT7E0LU1s&sz=w640",
        "sizeBytes": 0,
        "sha256": "",
        "durationSec": 20.0,
        "author": "Holy3holy-dev",
        "codec": "h264",
        "width": 1280,
        "height": 720,
        "fps": 30.0,
        "hasAudio": False,
        "notes": "Heat Level 5 Police Pursuit"
    }
]

def main():
    print("[*] Preparing all NFS Most Wanted variants...")
    gdrive_token, folder_id = get_gdrive_credentials()
    client = SteamGridDBClient()

    all_variants = list(EXISTING_VARIANTS)

    # 2. Download and convert the 2 additional animated heroes from SteamGridDB
    sgdb_heroes = [
        ("https://cdn2.steamgriddb.com/hero/22b4c1794c97f3cd5d4dbdccebe478c8.webp", "NFS MW: Animated Artwork Hero", "var-mw-sgdb1"),
        ("https://cdn2.steamgriddb.com/hero/3e247b248fcf4cf04a2e8a72222f6690.webp", "NFS MW: City Skyline Neon", "var-mw-sgdb2")
    ]

    for hero_url, hero_name, var_id in sgdb_heroes:
        target_file = OUTPUT_DIR / f"03DB18EF71F2C000_{var_id}.mp4"
        print(f"\n[*] Processing SGDB hero: {hero_name}...")
        ok = client.download_and_convert(hero_url, target_file)
        if ok and target_file.exists():
            print(f"  [✓] Converted to {target_file.name} ({target_file.stat().st_size} bytes)")
            try:
                g_res = GoogleDriveClient.upload_file(target_file, folder_id, gdrive_token)
                d_id = g_res["id"]
                dl_url = f"https://drive.google.com/uc?export=download&id={d_id}"
                pr_url = f"https://drive.google.com/thumbnail?id={d_id}&sz=w640"
                print(f"  [✓] Uploaded! Drive ID: {d_id}")
                all_variants.append({
                    "id": var_id,
                    "name": hero_name,
                    "style": "Animated Art",
                    "version": "1.0",
                    "url": dl_url,
                    "previewUrl": pr_url,
                    "sizeBytes": 0,
                    "sha256": "",
                    "durationSec": 20.0,
                    "author": "Holy3holy-dev",
                    "codec": "h264",
                    "width": 1280,
                    "height": 720,
                    "fps": 30.0,
                    "hasAudio": False,
                    "notes": f"SteamGridDB Animated Hero: {hero_name}"
                })
            except Exception as e:
                print(f"  [-] Failed to upload {target_file.name}: {e}")

    # 3. Update catalog.json
    with open(CAT_PATH, "r", encoding="utf-8") as f:
        cat = json.load(f)

    games_by_id = {g["titleId"].upper(): g for g in cat.get("games", [])}

    print(f"\n[*] Attaching {len(all_variants)} variants to all Need for Speed: Most Wanted Title IDs...")

    for tid in ALL_MW_TIDS:
        if tid in games_by_id:
            game = games_by_id[tid]
            game["title"] = "Need for Speed: Most Wanted"
            game["variants"] = all_variants
            print(f"  [✓] Updated {tid} with {len(all_variants)} variants.")
        else:
            new_game = {
                "titleId": tid,
                "title": "Need for Speed: Most Wanted",
                "publisher": "Electronic Arts",
                "variants": all_variants
            }
            games_by_id[tid] = new_game
            cat.setdefault("games", []).append(new_game)
            print(f"  [+] Created {tid} with {len(all_variants)} variants.")

    cat["totalGames"] = len(cat.get("games", []))
    cat["totalVariants"] = sum(len(g.get("variants", [])) for g in cat.get("games", []))

    with open(CAT_PATH, "w", encoding="utf-8") as f:
        json.dump(cat, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Total games now: {cat['totalGames']}, variants: {cat['totalVariants']}")

    # 4. Push to GitHub
    gh_token, _ = GitHubPublisher.get_stored_credentials()
    if gh_token:
        print("[*] Pushing catalog to GitHub...")
        GoogleDriveHelper.sync_catalog_to_github(CAT_PATH, token=gh_token, progress_cb=print)
        print("✅ Live sync complete! Switch will now see all variants!")

if __name__ == "__main__":
    main()
