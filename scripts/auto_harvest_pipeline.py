import os
import sys
import json
import time
import re
import argparse
import tempfile
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

def check_has_audio(file_path: Path) -> bool:
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-select_streams", "a", str(file_path)],
            capture_output=True, text=True, timeout=5
        )
        return "codec_type=audio" in res.stdout
    except Exception:
        return False

"""
H3H-Backgrounds: Automated SteamGridDB Harvester Pipeline
Downloads, converts to 4IFIR 720p 30fps MP4, uploads to Google Drive in batches of 50,
logs everything into catalog/data/steamgriddb_harvest_log.json,
and pushes live catalog updates to GitHub.
"""

# Ensure studio is on path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str((ROOT_DIR / "studio").resolve()))

from h3h_studio.core.steamgriddb import SteamGridDBClient
from h3h_studio.core.google_drive import GoogleDriveClient, GoogleDriveHelper
from h3h_studio.core.github_publisher import GitHubPublisher

# Primary high-capacity storage on drive H: to save C: disk space
H_STORAGE_DIR = Path(r"H:\H3H_Backgrounds")
if H_STORAGE_DIR.exists():
    OUTPUT_DIR = H_STORAGE_DIR
    TEMP_DIR = H_STORAGE_DIR / "temp"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(TEMP_DIR)
    os.environ["TEMP"] = str(TEMP_DIR)
    os.environ["TMP"] = str(TEMP_DIR)
    print(f"[*] Использование хранилища высокой ёмкости: {OUTPUT_DIR} (temp: {TEMP_DIR})")
else:
    OUTPUT_DIR = ROOT_DIR / "downloaded_official_backgrounds"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CATALOG_PATH = ROOT_DIR / "catalog" / "data" / "catalog.json"
LOG_PATH = ROOT_DIR / "catalog" / "data" / "steamgriddb_harvest_log.json"
SWITCH_DB_PATH = ROOT_DIR / "studio" / "h3h_studio" / "data" / "switch_titles_db.json"
GDRIVE_CFG_PATH = Path.home() / ".h3h_google_drive.json"

DEFAULT_FOLDER_ID = "1hI1klJ6t2ymVoBwGA6IzY79QMjp5dTJC"
DEFAULT_TOKEN = ""
DEFAULT_SGDB_KEY = "4200e73768d97fa592e9d9b7eed012fb"


def get_gdrive_credentials() -> Tuple[str, str]:
    if GDRIVE_CFG_PATH.exists():
        try:
            cfg = json.loads(GDRIVE_CFG_PATH.read_text(encoding="utf-8"))
            tok = cfg.get("token") or DEFAULT_TOKEN
            ref = cfg.get("refresh_token")
            f_id = cfg.get("folder_id") or cfg.get("project_folder_id") or DEFAULT_FOLDER_ID

            # If token expired or close to expiry, auto-refresh via refresh_token silently
            test_res = GoogleDriveClient.test_connection(tok)
            if not test_res.get("ok") and ref:
                print("  [*] Автоматическое обновление токена Google Drive через Refresh Token...")
                new_tok = GoogleDriveHelper.refresh_access_token(ref)
                if new_tok:
                    cfg["token"] = new_tok
                    GDRIVE_CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
                    return new_tok.strip(), f_id.strip()

            return tok.strip(), f_id.strip()
        except Exception:
            pass
    return DEFAULT_TOKEN, DEFAULT_FOLDER_ID



def save_gdrive_token(new_token: str) -> None:
    try:
        cfg = {}
        if GDRIVE_CFG_PATH.exists():
            cfg = json.loads(GDRIVE_CFG_PATH.read_text(encoding="utf-8"))
        cfg["token"] = new_token.strip()
        GDRIVE_CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[-] Failed to save updated token to {GDRIVE_CFG_PATH}: {e}")


def prompt_new_gdrive_token() -> str:
    """Interactive recovery handler when Google Drive access token expires."""
    # 1. First, check if we have a saved refresh_token that can automatically give us a fresh token
    if GDRIVE_CFG_PATH.exists():
        try:
            cfg = json.loads(GDRIVE_CFG_PATH.read_text(encoding="utf-8"))
            saved_ref = cfg.get("refresh_token")
            if saved_ref:
                print("  [*] Попытка автоматического обновления токена через сохраненный Refresh Token...")
                auto_tok = GoogleDriveHelper.refresh_access_token(saved_ref)
                if auto_tok:
                    res = GoogleDriveClient.test_connection(auto_tok)
                    if res.get("ok"):
                        print(f"  [✓] Токен автоматически обновлен без вашего участия! Аккаунт: {res.get('user', 'OK')}\n")
                        save_gdrive_token(auto_tok)
                        return auto_tok
        except Exception:
            pass

    print("\n" + "=" * 70)
    print("  🔑 [ВНИМАНИЕ] Срок действия токена Google Drive (1 час) истек!")
    print("=" * 70)
    print("  Как решить проблему НАВСЕГДА (чтобы не вводить каждый час):")
    print("  1. В Google OAuth Playground (Step 2) скопируйте поле 'Refresh token'")
    print("     (начинается с 1//04... или 1//0...) и вставьте его сюда.")
    print("     Скрипт сохранит его и будет САМ обновлять токены вечно в фоне!")
    print()
    print("  Либо скопируйте обычный 'Access token' (ya29... - действует 1 час).")
    print("=" * 70)

    while True:
        try:
            val = input(">> Вставьте Refresh Token (1//...) или Access Token (ya29...): ").strip()
        except (EOFError, KeyboardInterrupt):
            val = ""

        if not val:
            # Re-read from disk in case user updated file
            cfg_tok, _ = get_gdrive_credentials()
            val = cfg_tok

        # If user entered a Refresh token starting with 1//
        if val.startswith("1//") or val.startswith("1/"):
            print("  [*] Пробуем получить постоянный доступ через введенный Refresh Token...")
            new_acc_tok = GoogleDriveHelper.refresh_access_token(val)
            if new_acc_tok:
                test_res = GoogleDriveClient.test_connection(new_acc_tok)
                if test_res.get("ok"):
                    # Save both refresh_token and token permanently!
                    try:
                        cfg = {}
                        if GDRIVE_CFG_PATH.exists():
                            cfg = json.loads(GDRIVE_CFG_PATH.read_text(encoding="utf-8"))
                        cfg["refresh_token"] = val
                        cfg["token"] = new_acc_tok
                        GDRIVE_CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
                    except Exception:
                        pass
                    user_name = test_res.get("displayName") or test_res.get("user") or "Успешно"
                    print(f"  🎉 [УСПЕХ] Refresh Token сохранен! Доступ настроен НАВСЕГДА!")
                    print(f"  Аккаунт: {user_name}. Теперь токены будут обновляться сами без вопросов.\n")
                    return new_acc_tok
            print("  [-] Не удалось обновить токен через этот Refresh Token. Попробуйте еще раз.")
            continue

        print("  [*] Проверка токена связи с Google Drive...")
        res = GoogleDriveClient.test_connection(val)
        if res.get("ok"):
            user_name = res.get("displayName") or res.get("user") or "Успешно"
            print(f"  [✓] Авторизация успешна! Аккаунт: {user_name}\n")
            save_gdrive_token(val)
            return val
        else:
            err = res.get("error", "Неверный токен")
            print(f"  [-] Токен не подошел: {err}. Пожалуйста, попробуйте еще раз.")


def atomic_save_game_to_catalog(game_tid: str, title: str, publisher: str, variant_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely merges a single game variant into catalog.json on disk without losing
    any external additions or other variants.
    """
    cat_data = {"version": "1.0", "games": []}
    if CATALOG_PATH.exists():
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                cat_data = json.load(f)
        except Exception as e:
            print(f"[-] Error reading catalog for merge: {e}")

    games_list = cat_data.get("games", [])
    games_by_id = {g.get("titleId", "").upper(): g for g in games_list}

    tid = game_tid.upper()
    if tid in games_by_id:
        existing = games_by_id[tid]
        variants = existing.setdefault("variants", [])
        var_urls = {v.get("url") for v in variants if v.get("url")}
        var_ids = {v.get("id") for v in variants if v.get("id")}
        if variant_obj.get("url") not in var_urls and variant_obj.get("id") not in var_ids:
            variants.append(variant_obj)
    else:
        new_g = {
            "titleId": tid,
            "title": title,
            "publisher": publisher or "Unknown",
            "variants": [variant_obj]
        }
        games_list.append(new_g)
        games_by_id[tid] = new_g

    cat_data["totalGames"] = len(games_list)
    cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in games_list)
    cat_data["lastUpdated"] = datetime.now(timezone.utc).isoformat()

    safe_write_json(CATALOG_PATH, cat_data)

    return cat_data


def clean_game_title(raw_title: str) -> str:
    """Removes release tags, brackets, format notes, and language tags."""
    t = re.sub(r'\[.*?\]', '', raw_title)
    t = re.sub(r'\(.*?\)', '', t)
    t = re.sub(r'\b(v\d+(\.\d+)*|Update|DLC|RePack|NSP|XCI|NSZ|RUS|ENG|Multi\d+|JPN|Complete edition|Edition)\b', '', t, flags=re.IGNORECASE)
    if '/' in t:
        t = t.split('/')[0]
    t = re.sub(r'\s+', ' ', t).strip(' -:_')
    return t


def init_harvest_log(cat_data: Dict[str, Any]) -> Dict[str, Any]:
    """Loads existing harvest log or initializes from catalog.json."""
    if LOG_PATH.exists():
        try:
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[-] Warning: Failed to parse existing harvest log: {e}")

    # Seed initial harvest log from catalog.json
    log_data = {
        "version": "1.0",
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "totalHarvested": 0,
        "items": {}
    }

    count = 0
    for g in cat_data.get("games", []):
        tid = g.get("titleId", "").upper()
        if not tid:
            continue
        variants = g.get("variants", [])
        drive_id = ""
        dl_url = ""
        if variants:
            v = variants[0]
            dl_url = v.get("url", "")
            m = re.search(r'id=([a-zA-Z0-9_-]+)', dl_url)
            if m:
                drive_id = m.group(1)

        log_data["items"][tid] = {
            "titleId": tid,
            "gameTitle": g.get("title", ""),
            "sgdbGameId": None,
            "sgdbName": None,
            "assetType": "existing_catalog",
            "assetUrl": None,
            "driveFileId": drive_id,
            "downloadUrl": dl_url,
            "fileSizeBytes": 0,
            "status": "published",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        count += 1

    log_data["totalHarvested"] = count
    save_harvest_log(log_data)
    print(f"[+] Initialized harvest log with {count} existing catalog games.")
    return log_data


def safe_write_json(path: Path, data: Any) -> None:
    """Atomically writes JSON to disk via a temporary file with retry for Windows file locking."""
    path = Path(path).resolve()
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    text_data = json.dumps(data, ensure_ascii=False, indent=2)
    
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(text_data)
        f.flush()

    for attempt in range(5):
        try:
            os.replace(tmp_path, path)
            return
        except OSError:
            if attempt == 4:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text_data)
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
                return
            time.sleep(0.15)


def save_harvest_log(log_data: Dict[str, Any]) -> None:
    log_data["lastUpdated"] = datetime.now(timezone.utc).isoformat()
    log_data["totalHarvested"] = sum(1 for v in log_data.get("items", {}).values() if v.get("status") == "published")
    safe_write_json(LOG_PATH, log_data)



def sync_all_to_github(cat_data: Dict[str, Any], log_data: Dict[str, Any]) -> bool:
    """Commits and syncs catalog.json and steamgriddb_harvest_log.json to GitHub."""
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("[-] GitHub Token not found, skipping remote GitHub sync.")
        return False

    print("\n[*] Pushing catalog and harvest log to GitHub via API...")
    try:
        # 1. Sync catalog.json
        GoogleDriveHelper.sync_catalog_to_github(
            catalog_path=CATALOG_PATH,
            token=token,
            progress_cb=print
        )

        # 2. Sync harvest log
        GoogleDriveHelper.sync_file_to_github(
            file_path=LOG_PATH,
            repo_path="catalog/data/steamgriddb_harvest_log.json",
            token=token,
            commit_message="feat(harvest): update SteamGridDB harvest tracking log",
            progress_cb=print
        )
        print("✅ Remote GitHub sync completed successfully!")
        return True
    except Exception as e:
        print(f"[-] GitHub sync error: {e}")
        return False


def run_harvest_batch(
    batch_size: int = 50,
    continuous: bool = False,
    sgdb_key: str = DEFAULT_SGDB_KEY
) -> None:
    gdrive_token, folder_id = get_gdrive_credentials()
    client = SteamGridDBClient(api_key=sgdb_key)

    # Verify Google Drive token upfront before processing
    test_res = GoogleDriveClient.test_connection(gdrive_token)
    if not test_res.get("ok"):
        print(f"\n[⚠️] Текущий токен Google Drive истек или недействителен: {test_res.get('error', 'HTTP 401')}")
        gdrive_token = prompt_new_gdrive_token()
    else:
        u_name = test_res.get("displayName") or test_res.get("user") or "OK"
        print(f"[*] Связь с Google Drive подтверждена: {u_name}")

    if not CATALOG_PATH.exists():
        print(f"[-] Catalog not found at {CATALOG_PATH}")
        return

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        cat_data = json.load(f)

    if not SWITCH_DB_PATH.exists():
        print(f"[-] Switch DB not found at {SWITCH_DB_PATH}")
        return

    with open(SWITCH_DB_PATH, "r", encoding="utf-8") as f:
        switch_titles = json.load(f)

    log_data = init_harvest_log(cat_data)
    catalog_games = {g["titleId"].upper(): g for g in cat_data.get("games", [])}

    print("\n==================================================================")
    print(f"   🚀 H3H SteamGridDB Harvester: Batch Processing Pipeline")
    print(f"   Batch Size: {batch_size} | Mode: {'Continuous' if continuous else 'Single Batch'}")
    print(f"   Current Catalog: {len(catalog_games)} games | Tracked in log: {len(log_data['items'])}")
    print("==================================================================\n")

    batch_run_count = 0

    while True:
        batch_run_count += 1
        # Safely reload latest catalog from disk before every batch
        if CATALOG_PATH.exists():
            try:
                with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                    cat_data = json.load(f)
                catalog_games = {g["titleId"].upper(): g for g in cat_data.get("games", [])}
            except Exception:
                pass
        print(f"\n--- Starting Batch #{batch_run_count} (Target: {batch_size} new backgrounds) ---")
        harvested_this_batch = 0
        checked_titles = 0

        for entry in switch_titles:
            tid = entry.get("titleId", "").upper()
            if not tid or not re.match(r'^[0-9A-F]{16}$', tid):
                continue

            # Check if already in catalog or already processed in harvest log
            logged = log_data["items"].get(tid)
            if tid in catalog_games and logged and logged.get("status") == "published":
                continue
            if logged and logged.get("status") in ("published", "no_animated_art"):
                continue

            raw_title = entry.get("title", "")
            clean_title = clean_game_title(raw_title)
            if len(clean_title) < 2:
                continue

            checked_titles += 1
            print(f"\n[{harvested_this_batch + 1}/{batch_size}] Searching: '{clean_title}' (Switch TID: {tid})...")

            # Search SteamGridDB
            sgdb_results = client.search_game(clean_title)
            if not sgdb_results and ":" in clean_title:
                sgdb_results = client.search_game(clean_title.split(":")[0].strip())
            if not sgdb_results and " - " in clean_title:
                sgdb_results = client.search_game(clean_title.split(" - ")[0].strip())

            if not sgdb_results:
                print(f"  [-] No match found on SteamGridDB for '{clean_title}'")
                log_data["items"][tid] = {
                    "titleId": tid,
                    "gameTitle": raw_title,
                    "sgdbGameId": None,
                    "status": "no_animated_art",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                save_harvest_log(log_data)
                continue

            sgdb_game = sgdb_results[0]
            game_id = sgdb_game["id"]
            game_name = sgdb_game["name"]
            print(f"  [+] SGDB Matched: '{game_name}' (ID: {game_id})")

            # Collect animated candidate artworks (heroes first, then grids)
            candidates = []
            try:
                for h in client.get_animated_heroes(game_id):
                    u = h.get("url")
                    if u:
                        candidates.append(("hero", u))
                for g in client.get_animated_grids(game_id):
                    u = g.get("url")
                    if u:
                        candidates.append(("grid", u))
            except Exception as e:
                print(f"  [-] Error querying assets for '{game_name}': {e}")

            if not candidates:
                print(f"  [-] No animated Hero or Grid found on SGDB for '{game_name}'")
                log_data["items"][tid] = {
                    "titleId": tid,
                    "gameTitle": raw_title,
                    "sgdbGameId": game_id,
                    "sgdbName": game_name,
                    "status": "no_animated_art",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                save_harvest_log(log_data)
                continue

            safe_name = re.sub(r'[^0-9A-Za-z_-]', '_', clean_title)[:40]
            out_file = OUTPUT_DIR / f"{tid}_{safe_name}.mp4"

            converted_art_type = None
            used_art_url = None

            print(f"  [*] Downloading & converting ({len(candidates)} candidates available)...")
            for art_type, art_url in candidates:
                try:
                    ok = client.download_and_convert(art_url, out_file)
                    if ok and out_file.exists() and out_file.stat().st_size >= 1000:
                        converted_art_type = art_type
                        used_art_url = art_url
                        break
                    else:
                        print(f"  [-] Candidate {art_url[:60]}... failed or returned error, trying next...")
                except Exception as ce:
                    print(f"  [-] Error on {art_url[:60]}...: {ce}, trying next...")

            if not converted_art_type or not out_file.exists() or out_file.stat().st_size < 1000:
                print(f"  [-] All artwork candidates failed for '{game_name}'")
                log_data["items"][tid] = {
                    "titleId": tid,
                    "gameTitle": raw_title,
                    "sgdbGameId": game_id,
                    "sgdbName": game_name,
                    "status": "no_animated_art",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                save_harvest_log(log_data)
                continue

            art_type = converted_art_type
            art_url = used_art_url
            file_size = out_file.stat().st_size
            print(f"  [✓] Converted ({art_type}): {out_file.name} ({file_size} bytes)")

            # Upload to Google Drive (with automatic 401 expiry recovery)
            print(f"  [*] Uploading to Google Drive...")
            uploaded = False
            drive_id = ""
            dl_url = ""
            thumb_url = ""

            for upload_attempt in range(3):
                try:
                    gdrive_res = GoogleDriveClient.upload_file(
                        file_path=out_file,
                        folder_id=folder_id,
                        token=gdrive_token
                    )
                    drive_id = gdrive_res["id"]
                    dl_url = f"https://drive.google.com/uc?export=download&id={drive_id}"
                    thumb_url = f"https://drive.google.com/thumbnail?id={drive_id}&sz=w640"
                    print(f"  [✓] Uploaded! Drive ID: {drive_id}")
                    uploaded = True
                    break
                except Exception as ue:
                    err_str = str(ue)
                    if "401" in err_str or "Unauthorized" in err_str or "Invalid Credentials" in err_str:
                        gdrive_token = prompt_new_gdrive_token()
                        continue
                    else:
                        print(f"  [-] Google Drive upload failed: {ue}")
                        break

            if not uploaded:
                print(f"  [-] Skipping {clean_title} due to upload error.")
                continue

            # Update Harvest Log
            log_data["items"][tid] = {
                "titleId": tid,
                "gameTitle": raw_title,
                "cleanTitle": clean_title,
                "sgdbGameId": game_id,
                "sgdbName": game_name,
                "assetType": art_type,
                "assetUrl": art_url,
                "driveFileId": drive_id,
                "downloadUrl": dl_url,
                "fileSizeBytes": file_size,
                "status": "published",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            save_harvest_log(log_data)

            # Update catalog.json
            variant_obj = {
                "id": f"var-{drive_id[:8]}",
                "name": clean_title,
                "style": "Animated Art",
                "version": "1.0",
                "url": dl_url,
                "previewUrl": thumb_url,
                "sizeBytes": 0,
                "sha256": "",
                "durationSec": 20.0,
                "author": "Holy3holy-dev",
                "codec": "h264",
                "width": 1280,
                "height": 720,
                "fps": 30.0,
                "hasAudio": check_has_audio(out_file),
                "notes": f"SteamGridDB Animated {art_type.capitalize()}: {out_file.name}"
            }

            # Atomically save to catalog on disk without losing any existing variants
            cat_data = atomic_save_game_to_catalog(tid, raw_title, entry.get("publisher", "Unknown"), variant_obj)
            catalog_games = {g["titleId"].upper(): g for g in cat_data.get("games", [])}

            harvested_this_batch += 1
            print(f"  🎉 [{harvested_this_batch}/{batch_size}] Added to catalog: '{clean_title}'")

            # Check if batch limit reached
            if harvested_this_batch >= batch_size:
                break

        save_harvest_log(log_data)

        print("\n==================================================================")
        print(f"   ✅ Batch #{batch_run_count} Completed!")
        print(f"   Successfully Harvested & Uploaded: {harvested_this_batch} games")
        print(f"   Total Live Games in Catalog: {cat_data['totalGames']}")
        print(f"   Total Live Variants in Catalog: {cat_data['totalVariants']}")
        print("==================================================================")

        # Sync to GitHub
        if harvested_this_batch > 0:
            sync_all_to_github(cat_data, log_data)

        if not continuous:
            print("\nBatch finished. Exiting as requested.")
            break

        if harvested_this_batch == 0:
            print("\nNo more unharvested games found with animated art. Pipeline complete.")
            break

        print("\nWaiting 5 seconds before beginning next batch of 50...")
        time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="H3H SteamGridDB Batch Harvester")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of games per batch (default: 50)")
    parser.add_argument("--continuous", action="store_true", help="Run batches continuously until stopped")
    parser.add_argument("--key", type=str, default=DEFAULT_SGDB_KEY, help="SteamGridDB API key")
    args = parser.parse_args()

    run_harvest_batch(
        batch_size=args.batch_size,
        continuous=args.continuous,
        sgdb_key=args.key
    )
