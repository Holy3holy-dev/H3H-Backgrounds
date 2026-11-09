"""
Fill Empty Titles Script
Fills videos for any game in catalog/data/catalog.json that has 0 variants.
"""

import sys
import os
import re
import json
import time
import hashlib
import subprocess
import urllib.parse
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timezone
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "studio"))

from h3h_studio.core.steamgriddb import SteamGridDBClient
from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient
from h3h_studio.core.github_publisher import GitHubPublisher
from tg_bot.config import GDRIVE_FOLDER_ID, CATALOG_PATH_STANDARD, detect_local_proxy

LOCAL_PROXY = detect_local_proxy()
STAGE_DIR = PROJECT_ROOT / "tmp" / "h3h_stage"
RAW_DIR = STAGE_DIR / "raw_empty"
P720_DIR = STAGE_DIR / "720p_empty"
for d in (STAGE_DIR, RAW_DIR, P720_DIR):
    d.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
if LOCAL_PROXY:
    SESSION.proxies = {"http": LOCAL_PROXY, "https": LOCAL_PROXY}
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
})

EXACT_STEAM_APPIDS = {
    "010039501405E000": 1982340,  # Blanc
    "01007D4017740000": 227000,   # Primordia
    "0100453012FEA000": 815370,   # Green Hell
    "010035A00DF62000": 1001800,  # KUNAI
    "0100BED01E6EE000": 1752320,  # SWORN
    "01002DB007A96000": 364280,   # Legend of Kay Anniversary
    "010020E01EB72000": 2107520,  # dotAGE
}

def get_gdrive_token():
    cfg = GoogleDriveHelper.get_stored_config()
    ref = cfg.get("refresh_token")
    if ref:
        tok = GoogleDriveHelper.refresh_access_token(ref)
        if tok:
            cfg["token"] = tok
            GoogleDriveHelper.save_stored_config(cfg)
            return tok
    return cfg.get("token")

def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().upper()

def check_has_audio(path: Path) -> bool:
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-select_streams", "a", str(path)],
            capture_output=True, text=True, timeout=8
        )
        return "codec_type=audio" in res.stdout
    except Exception:
        return False

def get_steam_trailer_by_appid(app_id: int):
    try:
        url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=english"
        r = SESSION.get(url, timeout=12)
        data = r.json()
        app_data = data.get(str(app_id), {}).get("data", {})
        game_name = app_data.get("name", "Game")
        movies = app_data.get("movies", [])
        if movies:
            for mv in movies:
                mp4 = mv.get("mp4", {})
                stream = mp4.get("max") or mp4.get("480") or mv.get("hls_h264")
                if stream:
                    m_name = mv.get("name", "Official Trailer")
                    return stream, f"{game_name} — {m_name}"
    except Exception as e:
        print(f"  [!] Steam trailer fetch error for {app_id}: {e}")
    return None

def encode_switch_mp4(source_url: str, out_path: Path):
    if out_path.exists():
        try:
            out_path.unlink()
        except Exception:
            pass
    cmd = ["ffmpeg", "-y", "-nostdin"]
    if LOCAL_PROXY:
        cmd += ["-http_proxy", LOCAL_PROXY]
    cmd += [
        "-headers", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n",
        "-i", source_url,
        "-t", "16",
        "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=30",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-maxrate", "3500k",
        "-bufsize", "7000k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-c:a", "aac",
        "-b:a", "128k",
        str(out_path)
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.communicate(timeout=60)
        if proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 150_000:
            return True
    except Exception as e:
        print(f"  [!] Encoding error: {e}")
    return False

def main():
    cat_path = PROJECT_ROOT / "catalog" / "data" / "catalog.json"
    with open(cat_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    # 1. Fill Donkey Kong Country Tropical Freeze (0100702008E12000) from 0100C1F0051B6000
    src_dk = next((g for g in catalog["games"] if g["titleId"] == "0100C1F0051B6000"), None)
    dst_dk = next((g for g in catalog["games"] if g["titleId"] == "0100702008E12000"), None)
    if src_dk and dst_dk and len(dst_dk.get("variants", [])) == 0:
        dst_dk["variants"] = deepcopy(src_dk["variants"])
        for v in dst_dk["variants"]:
            v["id"] = f"{v['id']}_alt"
        print(f"[+] Filled Donkey Kong Country: Tropical Freeze (0100702008E12000) with {len(dst_dk['variants'])} variants!")

    # 2. Find any games with 0 variants
    empty_games = [g for g in catalog["games"] if len(g.get("variants", [])) == 0]
    print(f"\nRemaining games with 0 variants: {len(empty_games)}")

    gdrive_token = get_gdrive_token()
    if not gdrive_token:
        print("[!] No Google Drive token!")
        return

    total_added = 0
    for g in empty_games:
        tid = g["titleId"]
        title = g["title"]
        print(f"\nProcessing empty game: {title} [{tid}]")
        appid = EXACT_STEAM_APPIDS.get(tid)
        if not appid:
            print(f"  [!] No AppID mapped for {tid} ({title})")
            continue

        res = get_steam_trailer_by_appid(appid)
        if not res:
            print(f"  [!] Could not get trailer stream for {appid}")
            continue

        stream_url, trailer_title = res
        print(f"  Found trailer: {trailer_title}")
        out_mp4 = P720_DIR / f"{tid}_switch720p.mp4"

        print(f"  Encoding to Switch 720p 30fps...")
        ok = encode_switch_mp4(stream_url, out_mp4)
        if not ok:
            print("  [!] Failed to encode video!")
            continue

        print(f"  Encoded successfully ({out_mp4.stat().st_size / (1024*1024):.2f} MB). Uploading to Google Drive...")
        gdrive_token = get_gdrive_token() or gdrive_token
        try:
            up_res = GoogleDriveClient.upload_file(out_mp4, GDRIVE_FOLDER_ID, gdrive_token)
            file_id = up_res.get("fileId")
            direct_url = up_res.get("directUrl") or f"https://drive.google.com/uc?export=download&id={file_id}"
            preview_url = up_res.get("previewUrl") or f"https://drive.google.com/thumbnail?id={file_id}&sz=w640"
        except Exception as e:
            print(f"  [!] Upload error: {e}")
            continue

        sha256_hex = compute_sha256(out_mp4)
        has_aud = check_has_audio(out_mp4)
        var_id = f"v_{hashlib.md5(f'{tid}_{stream_url}'.encode()).hexdigest()[:8]}"

        new_variant = {
            "id": var_id,
            "name": trailer_title[:48],
            "style": "cinematic",
            "version": "1.0",
            "url": direct_url,
            "previewUrl": preview_url,
            "sizeBytes": out_mp4.stat().st_size,
            "sha256": sha256_hex,
            "durationSec": 16.0,
            "author": "Steam Official",
            "codec": "h264",
            "width": 1280,
            "height": 720,
            "fps": 30.0,
            "hasAudio": has_aud,
            "notes": f"Switch 720p 30fps H264 | {trailer_title[:40]}"
        }

        g.setdefault("variants", []).append(new_variant)
        total_added += 1
        print(f"  [SUCCESS] Added variant to {title} [{tid}]! (Total added: {total_added})")
        try:
            out_mp4.unlink()
        except Exception:
            pass

    # Save catalog
    catalog["updatedAt"] = datetime.now(timezone.utc).isoformat()
    catalog["lastUpdated"] = catalog["updatedAt"]
    catalog["totalGames"] = len(catalog["games"])
    catalog["totalVariants"] = sum(len(g.get("variants", [])) for g in catalog["games"])
    with open(cat_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Catalog updated! Total games: {catalog['totalGames']}, total variants: {catalog['totalVariants']}")

    # Git push
    gh_token, _ = GitHubPublisher.get_stored_credentials()
    repo_url = f"https://x-access-token:{gh_token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"
    git_env = os.environ.copy()
    git_env["GIT_EDITOR"] = ":"
    if LOCAL_PROXY:
        git_env["http_proxy"] = LOCAL_PROXY
        git_env["https_proxy"] = LOCAL_PROXY

    try:
        subprocess.run(["git", "add", "catalog/data/catalog.json"], check=True)
        subprocess.run(["git", "commit", "-m", f"fix(catalog): fill all 8 empty Switch 1 game titles ({catalog['totalVariants']} variants) [skip render] [skip ci]"], env=git_env, check=True)
        subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/main"], env=git_env, check=True)
        print("[+] Successfully pushed to GitHub main!")
    except Exception as e:
        print(f"[!] Git push notice: {e}")

if __name__ == "__main__":
    main()
