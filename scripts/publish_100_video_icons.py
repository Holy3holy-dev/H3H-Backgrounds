"""
Publishes 100 Nintendo Switch titles (300 video icons) to Google Drive and catalog/data/catalog.json.
Uses ThreadPoolExecutor for fast parallel uploads and persists an upload manifest.
Updates catalog.json with 4IFIR video icon variants and bundles icons into existing variants.
"""

import sys
import os
import json
import time
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "studio"))

from tg_bot.bot import get_gdrive_auth
from tg_bot.config import GDRIVE_ICONS_FOLDER_ID
from h3h_studio.core.google_drive import GoogleDriveClient

STAGE_DIR = Path(r"H:\h3h_stage\video_icons_100")
MANIFEST_PATH = PROJECT_ROOT / "tmp" / "video_icons_gdrive_manifest.json"
CATALOG_PATH = PROJECT_ROOT / "catalog" / "data" / "catalog.json"

import importlib.util
spec = importlib.util.spec_from_file_location('harvest', str(PROJECT_ROOT / 'scripts' / 'harvest_100_video_icons.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
TOP_100_GAMES = mod.TOP_100_GAMES

def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_manifest(manifest: dict):
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

def upload_single_icon(tid: str, var_idx: int, mp4_path: Path, token: str, folder_id: str) -> dict:
    upload_name = f"{tid}_var{var_idx}.mp4"
    retries = 3
    for attempt in range(1, retries + 1):
        try:
            # We temporarily copy or rename if needed, but GoogleDriveClient takes metadata name from file_path.name
            # So let's create a symbolic or temporary copy with the clean remote name if not already
            named_mp4 = mp4_path.parent / upload_name
            if not named_mp4.exists():
                import shutil
                shutil.copy2(mp4_path, named_mp4)
                
            res = GoogleDriveClient.upload_file(named_mp4, folder_id, token)
            return {
                "titleId": tid,
                "var": var_idx,
                "fileId": res.get("fileId"),
                "directUrl": res.get("directUrl"),
                "previewUrl": res.get("previewUrl"),
                "sizeBytes": mp4_path.stat().st_size,
                "remoteName": upload_name
            }
        except Exception as e:
            if attempt == retries:
                raise e
            time.sleep(1.5 * attempt)

def upload_all_icons():
    tok, _ = get_gdrive_auth("standard")
    if not tok:
        raise RuntimeError("Failed to obtain Google Drive token")

    manifest = load_manifest()
    tasks = []
    
    for tid, name, q, appid, cat in TOP_100_GAMES:
        game_stage = STAGE_DIR / tid
        if not game_stage.exists():
            continue
        for v in [1, 2, 3]:
            mp4_file = game_stage / f"var{v}.mp4"
            if not mp4_file.exists():
                continue
            key = f"{tid}_var{v}"
            if key in manifest and manifest[key].get("directUrl"):
                continue # Already uploaded
            tasks.append((tid, v, mp4_file, key))

    print(f"[*] Total icons to upload: {len(tasks)} (already cached: {len(manifest)})")
    
    if tasks:
        completed = 0
        with ThreadPoolExecutor(max_workers=6) as executor:
            future_to_key = {
                executor.submit(upload_single_icon, tid, v, path, tok, GDRIVE_ICONS_FOLDER_ID): key
                for tid, v, path, key in tasks
            }
            for future in as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    result = future.result()
                    manifest[key] = result
                    completed += 1
                    if completed % 10 == 0 or completed == len(tasks):
                        print(f"[{completed}/{len(tasks)}] Uploaded: {key} -> {result['directUrl']}")
                        save_manifest(manifest)
                except Exception as e:
                    print(f"[-] Error uploading {key}: {e}")

        save_manifest(manifest)
    print(f"[+] All uploads verified in manifest! Total entries: {len(manifest)}")
    return manifest

def update_catalog(manifest: dict):
    print(f"[*] Updating {CATALOG_PATH} with 100 titles (300 video icons)...")
    cat_data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    games_map = {g["titleId"].upper(): g for g in cat_data.get("games", [])}
    
    total_new_variants = 0
    total_updated_packs = 0
    
    for tid, name, q, appid, cat_name in TOP_100_GAMES:
        tid_u = tid.upper()
        game_stage = STAGE_DIR / tid
        meta_file = game_stage / "meta.json"
        
        meta = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                pass
                
        # Find or create game entry
        if tid_u not in games_map:
            publisher = "Nintendo" if cat_name == "Nintendo Exclusives" else "Community"
            g_entry = {
                "titleId": tid_u,
                "title": name,
                "publisher": publisher,
                "variants": []
            }
            cat_data["games"].append(g_entry)
            games_map[tid_u] = g_entry
        else:
            g_entry = games_map[tid_u]

        # 1. Update existing first variant into a 4IFIR Dynamic Pack (Cover + Icon)
        var1_info = manifest.get(f"{tid}_var1")
        if var1_info and g_entry.get("variants"):
            first_v = g_entry["variants"][0]
            if not first_v.get("hasIcon") or not first_v.get("iconUrl"):
                first_v["hasIcon"] = True
                first_v["iconUrl"] = var1_info["directUrl"]
                first_v["iconSizeBytes"] = var1_info["sizeBytes"]
                first_v["iconCodec"] = "h264"
                first_v["iconWidth"] = 256
                first_v["iconHeight"] = 256
                total_updated_packs += 1

        # 2. Add/update the 3 video icon variants
        var_meta_list = meta.get("variations", [
            {"var": 1, "name": "Hero Portrait Loop", "style": "Hero Close-Up"},
            {"var": 2, "name": "Dynamic Action Loop", "style": "Action Gameplay"},
            {"var": 3, "name": "Atmospheric Cinematic Loop", "style": "Cinematic Vista"}
        ])

        for v_meta in var_meta_list:
            v_idx = v_meta.get("var", 1)
            key = f"{tid}_var{v_idx}"
            v_upload = manifest.get(key)
            if not v_upload or not v_upload.get("directUrl"):
                continue

            var_slug = f"icon-{tid.lower()}-v{v_idx}"
            var_name = v_meta.get("name", f"Variation {v_idx}")
            var_style = v_meta.get("style", "Video Icon")
            display_name = f"4IFIR Иконка: {var_style}"

            # Check if this icon variant already exists in the game
            existing_v = None
            for v in g_entry.get("variants", []):
                if v.get("id") == var_slug:
                    existing_v = v
                    break

            if existing_v:
                existing_v["url"] = v_upload["directUrl"]
                existing_v["previewUrl"] = v_upload.get("previewUrl", v_upload["directUrl"])
                existing_v["iconUrl"] = v_upload["directUrl"]
                existing_v["sizeBytes"] = v_upload["sizeBytes"]
                existing_v["iconSizeBytes"] = v_upload["sizeBytes"]
                existing_v["name"] = display_name
                existing_v["notes"] = f"4IFIR 256x256 Video Icon ({var_name})"
            else:
                new_var = {
                    "id": var_slug,
                    "name": display_name,
                    "style": "4IFIR Dynamic Icon",
                    "version": "1.0",
                    "url": v_upload["directUrl"],
                    "previewUrl": v_upload.get("previewUrl", v_upload["directUrl"]),
                    "sizeBytes": v_upload["sizeBytes"],
                    "sha256": "",
                    "durationSec": 4.0,
                    "author": "@4IFIR / H3H",
                    "codec": "h264",
                    "width": 256,
                    "height": 256,
                    "fps": 30.0,
                    "hasAudio": False,
                    "hasIcon": True,
                    "iconUrl": v_upload["directUrl"],
                    "iconSizeBytes": v_upload["sizeBytes"],
                    "iconCodec": "h264",
                    "iconWidth": 256,
                    "iconHeight": 256,
                    "notes": f"4IFIR 256x256 Video Icon ({var_name})"
                }
                g_entry["variants"].append(new_var)
                total_new_variants += 1

    cat_data["totalGames"] = len(cat_data["games"])
    cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in cat_data["games"])
    now_iso = datetime.now(timezone.utc).isoformat()
    cat_data["updatedAt"] = now_iso
    cat_data["lastUpdated"] = now_iso

    CATALOG_PATH.write_text(json.dumps(cat_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[+] Successfully published to catalog.json!")
    print(f"    - Total registered games: {cat_data['totalGames']}")
    print(f"    - Total variants: {cat_data['totalVariants']}")
    print(f"    - New icon variants added: {total_new_variants}")
    print(f"    - Existing background variants updated with icon: {total_updated_packs}")

if __name__ == "__main__":
    manifest = upload_all_icons()
    update_catalog(manifest)
