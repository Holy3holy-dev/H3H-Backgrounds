"""
Massive Automated SteamGridDB Harvester for Nintendo Switch (4IFIR 720p 30fps).
Iterates over top multiplatform Switch titles, fetches animated community heroes,
encodes, uploads to Google Drive, and syncs live to catalog and GitHub.
"""

import os
import sys
import json
import time
import re
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.steamgriddb import SteamGridDBClient
from h3h_studio.core.google_drive import GoogleDriveClient

OUTPUT_DIR = Path(r"e:\videofon\downloaded_official_backgrounds")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FOLDER_ID = "1hI1klJ6t2ymVoBwGA6IzY79QMjp5dTJC"
TOKEN = "ya29.a0AX07CmuycNHtflqEeffh6XtbRgDmkTxLMoFcfPfk7XbXeAhJYE0voc0R6FT8cKBJCb14bSwIIrkDiH6q4TVHqB2RlS_FJ1NDxvQR8aNUc6akfxSEW4l29zPbik7WjPDVBonvWDuczIavEbNQcCgCvMRKqSZBDArZbTCVsMqVn-9GrR43xyb7FzkVvTKUrksapAs8G3kaCgYKAbASARISFQHGX2Mit3ABcTJRFKxY6VHf_HLbow0206"
DB_PATH = Path("studio/h3h_studio/data/switch_titles_db.json")

client = SteamGridDBClient()

TOP_GAMES = [
    # Top Action & Shooters
    ("DOOM", "DOOM (2016)"),
    ("DOOM 3", "DOOM 3"),
    ("DOOM 64", "DOOM 64"),
    ("Wolfenstein II", "Wolfenstein II: The New Colossus"),
    ("Wolfenstein: Youngblood", "Wolfenstein: Youngblood"),
    ("Metro 2033", "Metro 2033 Redux"),
    ("Metro: Last Light", "Metro: Last Light Redux"),
    ("Crysis Remastered", "Crysis Remastered"),
    ("Alien: Isolation", "Alien: Isolation"),
    ("Dying Light", "Dying Light: Definitive Edition"),
    ("Borderlands 2", "Borderlands 2"),
    ("Borderlands: The Pre-Sequel", "Borderlands: The Pre-Sequel"),
    ("BioShock Remastered", "BioShock Remastered"),
    ("BioShock 2 Remastered", "BioShock 2 Remastered"),
    ("BioShock Infinite", "BioShock Infinite"),
    ("Saints Row: The Third", "Saints Row: The Third"),
    ("Saints Row IV", "Saints Row IV"),
    ("Batman: Arkham Asylum", "Batman: Arkham Asylum"),
    ("Batman: Arkham City", "Batman: Arkham City"),
    ("Batman: Arkham Knight", "Batman: Arkham Knight"),
    ("South Park: The Stick of Truth", "South Park: The Stick of Truth"),
    ("South Park: The Fractured but Whole", "South Park: The Fractured but Whole"),

    # Top RPGs & Adventures
    ("The Elder Scrolls V: Skyrim", "The Elder Scrolls V: Skyrim"),
    ("Dragon's Dogma", "Dragon's Dogma: Dark Arisen"),
    ("NieR:Automata", "NieR:Automata"),
    ("No Man's Sky", "No Man's Sky"),
    ("Persona 3 Portable", "Persona 3 Portable"),
    ("Persona 4 Golden", "Persona 4 Golden"),
    ("Persona 5 Tactica", "Persona 5 Tactica"),
    ("Shin Megami Tensei III", "Shin Megami Tensei III: Nocturne"),
    ("Final Fantasy VII", "Final Fantasy VII"),
    ("Final Fantasy VIII", "Final Fantasy VIII"),
    ("Final Fantasy IX", "Final Fantasy IX"),
    ("Final Fantasy X", "Final Fantasy X/X-2 HD Remaster"),
    ("Final Fantasy XII", "Final Fantasy XII: The Zodiac Age"),
    ("Disco Elysium", "Disco Elysium"),
    ("Diablo II", "Diablo II: Resurrected"),
    ("Diablo III", "Diablo III: Eternal Collection"),
    ("Monster Hunter Rise", "Monster Hunter Rise"),
    ("Monster Hunter Stories 2", "Monster Hunter Stories 2: Wings of Ruin"),
    ("Ys VIII", "Ys VIII: Lacrimosa of DANA"),
    ("Ys IX", "Ys IX: Monstrum Nox"),
    ("Tales of Symphonia", "Tales of Symphonia"),
    ("Danganronpa: Trigger Happy Havoc", "Danganronpa: Trigger Happy Havoc"),
    ("Danganronpa 2", "Danganronpa 2: Goodbye Despair"),
    ("Danganronpa V3", "Danganronpa V3: Killing Harmony"),
    ("The Great Ace Attorney", "The Great Ace Attorney Chronicles"),

    # Top Platformers & Indies
    ("Sonic Frontiers", "Sonic Frontiers"),
    ("Sonic Superstars", "Sonic Superstars"),
    ("Sonic Mania", "Sonic Mania"),
    ("Crash Bandicoot N. Sane Trilogy", "Crash Bandicoot N. Sane Trilogy"),
    ("Crash Bandicoot 4", "Crash Bandicoot 4: It's About Time"),
    ("Crash Team Racing", "Crash Team Racing Nitro-Fueled"),
    ("Spyro Reignited Trilogy", "Spyro Reignited Trilogy"),
    ("Tony Hawk's Pro Skater 1 + 2", "Tony Hawk's Pro Skater 1 + 2"),
    ("Mega Man 11", "Mega Man 11"),
    ("Shovel Knight: Treasure Trove", "Shovel Knight: Treasure Trove"),
    ("A Hat in Time", "A Hat in Time"),
    ("Balatro", "Balatro"),
    ("Dave the Diver", "Dave the Diver"),
    ("Cult of the Lamb", "Cult of the Lamb"),
    ("Inscryption", "Inscryption"),
    ("Enter the Gungeon", "Enter the Gungeon"),
    ("Risk of Rain 2", "Risk of Rain 2"),
    ("Blasphemous", "Blasphemous"),
    ("Blasphemous 2", "Blasphemous 2"),
    ("Katana ZERO", "Katana ZERO"),
    ("Hotline Miami", "Hotline Miami"),
    ("My Friend Pedro", "My Friend Pedro"),
    ("Gris", "Gris"),
    ("Tunic", "Tunic"),
    ("Signalis", "Signalis"),
    ("Sea of Stars", "Sea of Stars"),
    ("Chained Echoes", "Chained Echoes"),
    ("Stray", "Stray"),
    ("Dredge", "Dredge"),
    ("Cocoon", "Cocoon"),
    ("Animal Well", "Animal Well"),
    ("Untitled Goose Game", "Untitled Goose Game"),
    ("Overcooked! 2", "Overcooked! 2"),
    ("Moving Out", "Moving Out"),
    ("It Takes Two", "It Takes Two"),
    ("Inside", "Inside"),
    ("Limbo", "Limbo"),
    ("Little Nightmares", "Little Nightmares"),
    ("Little Nightmares II", "Little Nightmares II")
]

def find_title_id_in_db(switch_db, keyword):
    kw_lower = keyword.lower()
    for entry in switch_db:
        t = entry.get("title", "").lower()
        tid = entry.get("titleId", "").upper()
        if tid and len(tid) == 16:
            if kw_lower in t:
                return tid, entry.get("title", "")
    return None, None

def main():
    print(f"=== Starting SteamGridDB Harvester ({len(TOP_GAMES)} High-Priority Multiplatform Titles) ===\n")
    with open(DB_PATH, "r", encoding="utf-8") as f:
        switch_db = json.load(f)

    with open("catalog/data/catalog.json", "r", encoding="utf-8") as f:
        cat = json.load(f)
    cat_tids = {g["titleId"].upper() for g in cat.get("games", [])}

    converted = []

    for idx, (kw, sgdb_query) in enumerate(TOP_GAMES, 1):
        tid, switch_title = find_title_id_in_db(switch_db, kw)
        if not tid:
            print(f"[{idx}/{len(TOP_GAMES)}] No Switch Title ID found in DB for: {kw}")
            continue

        clean_name = re.sub(r'[^0-9A-Za-z_-]', '_', kw)
        target_mp4 = OUTPUT_DIR / f"{tid}_{clean_name}.mp4"

        if target_mp4.exists() and target_mp4.stat().st_size > 100000:
            print(f"[{idx}/{len(TOP_GAMES)}] Already ready locally: {target_mp4.name}")
            converted.append((tid, kw, target_mp4))
            continue

        print(f"[{idx}/{len(TOP_GAMES)}] SteamGridDB search: '{sgdb_query}' (Switch ID: {tid})...")
        games = client.search_game(sgdb_query)
        if not games:
            # fallback search
            games = client.search_game(kw)
            if not games:
                print(f"  [-] No SGDB results for {sgdb_query}")
                continue

        game_id = games[0]["id"]
        game_name = games[0]["name"]
        print(f"  [+] Matched: {game_name} (ID: {game_id})")

        # Check animated heroes first
        heroes = client.get_animated_heroes(game_id)
        selected_art = None
        if heroes:
            selected_art = heroes[0]["url"]
            print(f"  [+] Found animated Hero ({len(heroes)} available)")
        else:
            # fallback animated grids
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
            print(f"  [SUCCESS] {target_mp4.name} ({target_mp4.stat().st_size} bytes)")
            converted.append((tid, kw, target_mp4))
        else:
            print(f"  [-] Failed to convert {selected_art}")

    print(f"\n=== Uploading {len(converted)} Harvested Themes to Google Drive ===")
    from scripts.upload_remaining_to_drive import main as upload_all
    upload_all()

    print("\n=== Syncing with Catalog and Pushing to GitHub ===")
    from scripts.sync_drive_to_catalog import main as sync_catalog
    sync_catalog()

    print("\n✅ SteamGridDB Batch Harvest Complete!")

if __name__ == "__main__":
    main()
