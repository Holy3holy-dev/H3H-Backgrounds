"""
H3H Wallpaper Engine Direct Bridge & Continuous Harvester.
Integrates directly with the user's local Wallpaper Engine Steam installation
(E:\\SteamLibrary\\steamapps\\workshop\\content\\431960) and online Wallpaper Engine archives.

Capabilities:
1. Scan local Wallpaper Engine workshop directory for video wallpapers (.mp4, .webm).
2. Intelligent routing:
   - High-confidence Switch games -> Main Catalog (catalog/data/catalog.json)
   - Atmospheric, memes, anime, waifu, mature -> After Dark Catalog (0000000000000000 or specific games)
3. Convert to Nintendo Switch 720p 30fps H.264 High Profile (+faststart) with crisp stereo audio.
4. Auto-generate Ultra-HQ 256x256 Video Icons v2 for Switch titles.
5. Upload to Google Drive (Main, After Dark, Icons).
6. Auto-rebuild turbo catalogs (catalog.min.json.gz) and push directly to GitHub main.
7. Continuous background watcher: automatically detects newly subscribed wallpapers in Steam!
"""

import os
import sys
import re
import json
import time
import shutil
import hashlib
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

# Enforce UTF-8 output
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "studio"))

from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient
from h3h_studio.core.github_publisher import GitHubPublisher
from scripts.title_id_resolver import TitleIdResolver
from tg_bot.config import (
    GDRIVE_FOLDER_ID,
    GDRIVE_AFTER_DARK_FOLDER_ID,
    GDRIVE_ICONS_FOLDER_ID,
    CATALOG_PATH_STANDARD,
    detect_local_proxy
)
detect_local_proxy()

LOCAL_WE_WORKSHOP_DIR = Path(r"E:\SteamLibrary\steamapps\workshop\content\431960")
STAGE_DIR = PROJECT_ROOT / "tmp" / "we_stage"
OUT_VIDEO_DIR = STAGE_DIR / "720p"
OUT_ICON_DIR = STAGE_DIR / "icons"
for d in (STAGE_DIR, OUT_VIDEO_DIR, OUT_ICON_DIR):
    d.mkdir(parents=True, exist_ok=True)

MAIN_CATALOG_PATH = PROJECT_ROOT / "catalog" / "data" / "catalog.json"
AD_CATALOG_PATH = PROJECT_ROOT / "catalog" / "data" / "catalog_after_dark.json"
PROCESSED_DB_PATH = PROJECT_ROOT / "catalog" / "data" / "we_imported_items.json"

# Explicit Switch keyword matchers to ensure zero false positives for Main catalog
EXPLICIT_SWITCH_KEYWORDS = {
    "dark souls": ("01004AB00A260000", "Dark Souls: Remastered"),
    "fire keeper": ("01004AB00A260000", "Dark Souls: Remastered"),
    "bonfire": ("01004AB00A260000", "Dark Souls: Remastered"),
    "witcher": ("0100E8B00BDC6000", "The Witcher 3: Wild Hunt"),
    "geralt": ("0100E8B00BDC6000", "The Witcher 3: Wild Hunt"),
    "zelda": ("01007EF00011E000", "The Legend of Zelda: Breath of the Wild"),
    "breath of the wild": ("01007EF00011E000", "The Legend of Zelda: Breath of the Wild"),
    "tears of the kingdom": ("0100F2C0115B6000", "The Legend of Zelda: Tears of the Kingdom"),
    "super mario": ("0100000000010000", "Super Mario Odyssey"),
    "mario odyssey": ("0100000000010000", "Super Mario Odyssey"),
    "red dead redemption": ("01007820196A6000", "Red Dead Redemption"),
    "nier": ("01005C000B2AE000", "NieR:Automata The End of YoRHa Edition"),
    "2b": ("01005C000B2AE000", "NieR:Automata The End of YoRHa Edition"),
    "lunar tears": ("01005C000B2AE000", "NieR:Automata The End of YoRHa Edition"),
    "poppy playtime": ("010035301980C000", "Poppy Playtime"),
    "catnap": ("010035301980C000", "Poppy Playtime"),
    "minecraft": ("0100D71004694000", "Minecraft"),
    "persona 5": ("010091200CDA4000", "Persona 5 Royal"),
    "persona 4": ("010062B01525C000", "Persona 4 Golden"),
    "persona 3": ("0100DCD01525A000", "Persona 3 Portable"),
    "hollow knight": ("010036500ECF2000", "Hollow Knight"),
    "hades": ("010052300B254000", "Hades"),
    "ghostrunner": ("01008DF01290C000", "Ghostrunner"),
    "skyrim": ("010028D005A3C000", "The Elder Scrolls V: Skyrim"),
    "stardew valley": ("010093800B8C8000", "Stardew Valley"),
    "cuphead": ("010079C009494000", "Cuphead"),
    "celeste": ("01002B30028F6000", "Celeste"),
    "outer wilds": ("01003DC0144B6000", "Outer Wilds"),
    "subnautica": ("0100E5F00E88C000", "Subnautica"),
    "plants vs zombies": ("01008C50239BE000", "Plants vs. Zombies"),
    "pvz": ("01008C50239BE000", "Plants vs. Zombies"),
    "warhammer 40k": ("010031201307A000", "Warhammer 40,000"),
    "jojo": ("010017A0128C4000", "JoJo's Bizarre Adventure"),
    "stalker": ("010063201416E000", "S.T.A.L.K.E.R. Legends of the Zone"),
    "doom": ("0100B9F00BD34000", "DOOM"),
}

def load_processed_db() -> Dict[str, Any]:
    if PROCESSED_DB_PATH.exists():
        try:
            return json.loads(PROCESSED_DB_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"processed_workshop_ids": {}, "processed_hashes": []}

def save_processed_db(db: Dict[str, Any]):
    PROCESSED_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_DB_PATH.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")

def get_gdrive_token() -> Optional[str]:
    cfg = GoogleDriveHelper.get_stored_config()
    ref = cfg.get("refresh_token")
    if ref:
        tok = GoogleDriveHelper.refresh_access_token(ref)
        if tok:
            cfg["token"] = tok
            GoogleDriveHelper.save_stored_config(cfg)
            return tok
    return cfg.get("token")

def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def probe_video_has_audio(file_path: Path) -> bool:
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            str(file_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return "audio" in res.stdout.lower()
    except Exception:
        return False

def convert_to_switch_720p(input_file: Path, output_file: Path, duration_sec: int = 24) -> bool:
    """
    Converts video to standard Nintendo Switch 720p 30fps H.264 High Profile with +faststart.
    Includes clean stereo AAC audio if present in the source video.
    """
    if output_file.exists():
        try:
            output_file.unlink()
        except Exception:
            pass

    has_audio = probe_video_has_audio(input_file)
    cmd = [
        "ffmpeg", "-y", "-nostdin",
        "-i", str(input_file),
        "-t", str(duration_sec),
        "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=30",
        "-c:v", "libx264",
        "-profile:v", "high",
        "-level", "4.1",
        "-pix_fmt", "yuv420p",
        "-preset", "veryfast",
        "-crf", "22",
        "-maxrate", "3500k",
        "-bufsize", "7000k",
        "-movflags", "+faststart"
    ]
    if has_audio:
        cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"])
    else:
        cmd.append("-an")

    cmd.append(str(output_file))

    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return output_file.exists() and output_file.stat().st_size > 100000
    except Exception as e:
        print(f"[-] FFmpeg conversion error for {input_file.name}: {e}")
        return False

def generate_video_icon(video_path: Path, output_icon_mp4: Path, duration_sec: int = 6) -> bool:
    """
    Generates an Ultra-HQ 256x256 30fps H.264 video icon (v2 standard) from the video.
    """
    if output_icon_mp4.exists():
        return True
    output_icon_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-nostdin",
        "-ss", "1",
        "-i", str(video_path),
        "-t", str(duration_sec),
        "-vf", "scale=256:256:force_original_aspect_ratio=increase,crop=256:256,fps=30",
        "-c:v", "libx264",
        "-profile:v", "high",
        "-pix_fmt", "yuv420p",
        "-preset", "veryfast",
        "-crf", "22",
        "-an",
        "-movflags", "+faststart",
        str(output_icon_mp4)
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return output_icon_mp4.exists() and output_icon_mp4.stat().st_size > 20000
    except Exception:
        return False

def determine_destination(
    title: str,
    rating: str,
    tags: List[str],
    resolver: TitleIdResolver
) -> Tuple[str, str, str, str]:
    """
    Determines whether the wallpaper goes to:
    - 'MAIN' (catalog/data/catalog.json) -> Title ID & Name
    - 'AFTER_DARK' (catalog/data/catalog_after_dark.json) -> Title ID & Name
    Returns: (target_catalog, title_id, game_name, category_notes)
    """
    t_low = title.lower()
    r_low = (rating or "everyone").lower()
    tag_str = " ".join(tags).lower()

    # 1. Mature content always goes to After Dark
    if r_low in ("mature", "questionable", "nsfw", "18+"):
        # Check if matches specific game in After Dark
        res = resolver.resolve(title)
        if res:
            return ("AFTER_DARK", res[0], res[1], f"Mature Wallpaper: {title}")
        return ("AFTER_DARK", "0000000000000000", "★ Коллекция After Dark (Свободный выбор)", f"Mature: {title}")

    # 2. Check explicit Switch hits
    for kw, (tid, gname) in EXPLICIT_SWITCH_KEYWORDS.items():
        if kw in t_low:
            return ("MAIN", tid, gname, f"Wallpaper Engine: {title}")

    # 3. Fuzzy match against Switch database
    res = resolver.resolve(title)
    if res:
        tid, gname = res
        # If it's a very confident clean match, route to Main
        clean_g = gname.lower()
        if any(w in t_low for w in clean_g.split() if len(w) > 4):
            return ("MAIN", tid, gname, f"Wallpaper Engine: {title}")

    # 4. Memes, Anime, Landscapes, Abstract -> After Dark Universal Collection
    return ("AFTER_DARK", "0000000000000000", "★ Коллекция After Dark (Свободный выбор)", f"Wallpaper Engine: {title}")

def add_variant_to_catalog(
    catalog_path: Path,
    title_id: str,
    game_title: str,
    variant_name: str,
    video_url: str,
    preview_url: str,
    size_bytes: int,
    sha256: str,
    has_audio: bool,
    notes: str = ""
) -> bool:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    games = data.get("games", [])
    
    target_game = None
    for g in games:
        if g.get("titleId", "").upper() == title_id.upper():
            target_game = g
            break

    if not target_game:
        target_game = {
            "titleId": title_id.upper(),
            "title": game_title,
            "publisher": "Wallpaper Engine Community",
            "iconUrl": f"https://raw.githubusercontent.com/Langegen/switch-game-collection/main/covers/{title_id.upper()}.jpg",
            "variants": []
        }
        games.append(target_game)
        data["games"] = games

    # Check for duplicate variant by sha256 or exact name
    for v in target_game.get("variants", []):
        if v.get("sha256") == sha256 or v.get("name", "").lower() == variant_name.lower():
            return False  # Already exists

    var_prefix = "var-we" if "after_dark" not in catalog_path.name else "var-ad-we"
    var_id = f"{var_prefix}-{hashlib.md5(f'{title_id}_{variant_name}_{sha256}'.encode()).hexdigest()[:8]}"
    
    new_variant = {
        "id": var_id,
        "name": variant_name[:50],
        "style": "Wallpaper Engine Live",
        "version": "1.0",
        "url": video_url,
        "previewUrl": preview_url,
        "sizeBytes": size_bytes,
        "sha256": sha256,
        "durationSec": 24.0,
        "author": "Wallpaper Engine",
        "codec": "h264",
        "width": 1280,
        "height": 720,
        "fps": 30.0,
        "hasAudio": has_audio,
        "notes": notes
    }
    target_game.setdefault("variants", []).append(new_variant)
    data["totalGames"] = len(data["games"])
    data["totalVariants"] = sum(len(g.get("variants", [])) for g in data["games"])
    
    catalog_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return True

def run_catalog_rebuild():
    """Runs build_min_catalog.py to recompile catalog.min.json.gz."""
    print("[*] Rebuilding compressed gzip catalogs...")
    subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "build_min_catalog.py")], check=True)

def git_commit_and_push(commit_msg: str):
    """Commits and pushes updated catalogs to GitHub."""
    print(f"[*] Committing changes: {commit_msg}")
    try:
        subprocess.run(["git", "add", "catalog/data/"], cwd=str(PROJECT_ROOT), check=True)
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=str(PROJECT_ROOT), check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=str(PROJECT_ROOT), check=True)
        print("[+] Successfully pushed to GitHub main!")
    except subprocess.CalledProcessError as e:
        print(f"[-] Git push warning: {e}")

def process_local_wallpaper_engine(limit: int = 15) -> int:
    """
    Scans E:\\SteamLibrary\\steamapps\\workshop\\content\\431960,
    converts new wallpapers, uploads to Google Drive, and updates catalogs.
    """
    if not LOCAL_WE_WORKSHOP_DIR.exists():
        print(f"[-] Local Wallpaper Engine workshop directory not found: {LOCAL_WE_WORKSHOP_DIR}")
        return 0

    print(f"[*] Scanning local Wallpaper Engine workshop: {LOCAL_WE_WORKSHOP_DIR}")
    resolver = TitleIdResolver()
    processed_db = load_processed_db()
    processed_ids = processed_db.setdefault("processed_workshop_ids", {})

    gdrive_token = get_gdrive_token()
    if not gdrive_token:
        print("[-] Could not acquire Google Drive access token!")
        return 0

    items_to_process = []
    video_exts = {".mp4", ".webm", ".mkv"}

    for d in sorted(LOCAL_WE_WORKSHOP_DIR.iterdir()):
        if not d.is_dir():
            continue
        ws_id = d.name
        if ws_id in processed_ids:
            continue

        p_json = d / "project.json"
        if not p_json.exists():
            continue

        try:
            p_data = json.loads(p_json.read_text(encoding="utf-8", errors="ignore"))
            title = p_data.get("title", f"Wallpaper #{ws_id}").strip()
            rating = p_data.get("contentrating", "Everyone")
            tags = p_data.get("tags", [])
            
            # Find video file
            vids = [f for f in d.iterdir() if f.suffix.lower() in video_exts]
            if not vids:
                continue

            items_to_process.append({
                "ws_id": ws_id,
                "title": title,
                "rating": rating,
                "tags": tags,
                "video_path": vids[0],
                "dir_path": d
            })
        except Exception as e:
            pass

    print(f"[*] Found {len(items_to_process)} unprocessed video wallpapers.")
    if not items_to_process:
        print("[+] Local Wallpaper Engine library is already up to date!")
        return 0

    imported_count = 0
    main_changed = False
    ad_changed = False

    for item in items_to_process[:limit]:
        ws_id = item["ws_id"]
        title = item["title"]
        rating = item["rating"]
        tags = item["tags"]
        raw_vid = item["video_path"]

        print(f"\n[{imported_count + 1}/{min(len(items_to_process), limit)}] Importing: '{title}' (Workshop ID: {ws_id})")
        target_cat, tid, gname, notes = determine_destination(title, rating, tags, resolver)
        print(f"  -> Routing to: [{target_cat}] {gname} ({tid})")

        # Encode for Switch 720p 30fps
        clean_slug = re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_")[:25]
        out_mp4 = OUT_VIDEO_DIR / f"{tid}_{ws_id}_{clean_slug}.mp4"
        print(f"  -> Encoding to Switch 720p 30fps H.264...")
        if not convert_to_switch_720p(raw_vid, out_mp4):
            print("  [-] Encoding failed, skipping.")
            continue

        has_audio = probe_video_has_audio(out_mp4)
        file_sha256 = compute_sha256(out_mp4)
        size_bytes = out_mp4.stat().st_size

        # Select Google Drive folder
        target_folder = GDRIVE_FOLDER_ID if target_cat == "MAIN" else GDRIVE_AFTER_DARK_FOLDER_ID
        print(f"  -> Uploading to Google Drive ({size_bytes / 1024 / 1024:.2f} MB)...")
        gdrive_token = get_gdrive_token() or gdrive_token
        try:
            up_res = GoogleDriveClient.upload_file(out_mp4, target_folder, gdrive_token)
            file_id = up_res.get("id") or up_res.get("fileId")
            direct_url = up_res.get("directUrl") or f"https://drive.google.com/uc?export=download&id={file_id}"
            preview_url = up_res.get("previewUrl") or f"https://drive.google.com/thumbnail?id={file_id}&sz=w640"
            print(f"  [+] Uploaded! File ID: {file_id}")
        except Exception as e:
            print(f"  [-] Google Drive upload failed: {e}")
            continue

        # Generate and upload Video Icon if needed (for Switch Main titles)
        if target_cat == "MAIN" and tid != "0000000000000000":
            icon_mp4 = OUT_ICON_DIR / f"{tid}_icon.mp4"
            if not icon_mp4.exists():
                print(f"  -> Generating Ultra-HQ 256x256 Video Icon for {gname}...")
                if generate_video_icon(out_mp4, icon_mp4):
                    try:
                        GoogleDriveClient.upload_file(icon_mp4, GDRIVE_ICONS_FOLDER_ID, gdrive_token)
                        print(f"  [+] Video Icon uploaded to Google Drive!")
                    except Exception as ie:
                        print(f"  [-] Icon upload warning: {ie}")

        # Add to appropriate catalog
        cat_file = MAIN_CATALOG_PATH if target_cat == "MAIN" else AD_CATALOG_PATH
        ok = add_variant_to_catalog(
            catalog_path=cat_file,
            title_id=tid,
            game_title=gname,
            variant_name=title,
            video_url=direct_url,
            preview_url=preview_url,
            size_bytes=size_bytes,
            sha256=file_sha256,
            has_audio=has_audio,
            notes=notes
        )
        if ok:
            print(f"  [+] Successfully registered in {cat_file.name}!")
            if target_cat == "MAIN":
                main_changed = True
            else:
                ad_changed = True
            imported_count += 1
            processed_ids[ws_id] = {
                "title": title,
                "titleId": tid,
                "catalog": target_cat,
                "timestamp": int(time.time()),
                "fileId": file_id
            }
            save_processed_db(processed_db)
        else:
            print(f"  [!] Variant already existed in catalog.")

    if main_changed or ad_changed:
        run_catalog_rebuild()
        git_commit_and_push(f"feat(wallpaper-engine): imported {imported_count} live wallpapers from local workshop")

    print(f"\n[+] Batch complete. Imported {imported_count} new wallpapers from Wallpaper Engine.")
    return imported_count

def watch_wallpaper_engine(interval_sec: int = 20):
    """
    Watches the local Wallpaper Engine workshop directory continuously.
    Automatically imports any newly downloaded wallpapers when the user subscribes in Steam!
    """
    print("\n========================================================")
    print("  H3H WALLPAPER ENGINE CONTINUOUS WATCHER STARTED")
    print(f"  Watching: {LOCAL_WE_WORKSHOP_DIR}")
    print(f"  Check interval: {interval_sec} seconds")
    print("========================================================\n")
    
    while True:
        try:
            imported = process_local_wallpaper_engine(limit=10)
            if imported > 0:
                print(f"[+] Synced {imported} new wallpapers! Waiting for next change...")
        except KeyboardInterrupt:
            print("\n[*] Watcher stopped by user.")
            break
        except Exception as e:
            print(f"[-] Watcher error: {e}")
        time.sleep(interval_sec)

def main():
    parser = argparse.ArgumentParser(description="H3H Wallpaper Engine Direct Bridge")
    parser.add_argument("--local", action="store_true", help="Scan and import local Wallpaper Engine workshop wallpapers")
    parser.add_argument("--watch", action="store_true", help="Run background watcher for new Steam Workshop subscriptions")
    parser.add_argument("--limit", type=int, default=15, help="Max items to process in one batch")
    parser.add_argument("--interval", type=int, default=20, help="Watcher check interval in seconds")
    args = parser.parse_args()

    if args.watch:
        watch_wallpaper_engine(interval_sec=args.interval)
    else:
        process_local_wallpaper_engine(limit=args.limit)

if __name__ == "__main__":
    main()
