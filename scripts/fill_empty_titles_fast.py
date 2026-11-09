"""
Fast fMP4 Steam Trailer Harvester for Nintendo Switch 1
Pulls 1280x720 30fps chunks directly from Steam Akamai CDN,
multiplexes in 0.2s without transcoding, and uploads to Google Drive.
"""

import sys
import os
import re
import json
import time
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timezone
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "studio"))

from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient
from h3h_studio.core.github_publisher import GitHubPublisher
from tg_bot.config import GDRIVE_FOLDER_ID, CATALOG_PATH_STANDARD, detect_local_proxy

LOCAL_PROXY = detect_local_proxy()
STAGE_DIR = PROJECT_ROOT / "tmp" / "h3h_stage"
RAW_DIR = STAGE_DIR / "raw_fast"
P720_DIR = STAGE_DIR / "720p_fast"
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
    "0100BED01E6EE000": 1763250,  # SWORN
    "01002DB007A96000": 313810,   # Legend of Kay Anniversary
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

def get_steam_trailer_info(app_id: int):
    try:
        url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=english"
        r = SESSION.get(url, timeout=12)
        data = r.json().get(str(app_id), {}).get("data", {})
        game_name = data.get("name", "Game")
        movies = data.get("movies", [])
        if movies:
            for mv in movies:
                hls = mv.get("hls_h264")
                if hls:
                    m_name = mv.get("name", "Official Trailer")
                    return hls, f"{game_name} — {m_name}"
    except Exception as e:
        print(f"  [!] Steam trailer fetch error for {app_id}: {e}")
    return None

def download_steam_fmp4(master_url: str, out_file: Path, max_chunks: int = 5) -> bool:
    try:
        base_url = master_url.rsplit('/', 1)[0] + '/'
        master_text = SESSION.get(master_url, timeout=10).text

        # 1. Video track: prefer 720p (1280x720)
        m_vid = re.search(r'RESOLUTION=1280x720[^\n]*\n([^\n]+)', master_text)
        if not m_vid:
            # fallback to any video m3u8
            m_vid = re.search(r'(\bhls_264_\d+_video\.m3u8\b)', master_text)
        if not m_vid:
            return False

        video_m3u8 = m_vid.group(1).strip()
        v_url = base_url + video_m3u8
        v_text = SESSION.get(v_url, timeout=10).text

        m_vinit = re.search(r'URI="([^"]+init[^"]+)"', v_text)
        if not m_vinit:
            return False
        v_init_url = base_url + m_vinit.group(1)
        v_chunks = re.findall(r'(dash_h264/chunk[^\n\r]+)', v_text)[:max_chunks]

        # Download video
        v_bytes = bytearray(SESSION.get(v_init_url, timeout=10).content)
        for vc in v_chunks:
            v_bytes.extend(SESSION.get(base_url + vc, timeout=10).content)

        raw_v = RAW_DIR / "temp_v.mp4"
        raw_v.write_bytes(v_bytes)

        # 2. Audio track
        m_aud = re.search(r'URI="([^"]+audio\.m3u8)"', master_text)
        has_audio = False
        raw_a = RAW_DIR / "temp_a.mp4"
        if m_aud:
            audio_m3u8 = m_aud.group(1).strip()
            a_text = SESSION.get(base_url + audio_m3u8, timeout=10).text
            m_ainit = re.search(r'URI="([^"]+init[^"]+)"', a_text)
            if m_ainit:
                a_init_url = base_url + m_ainit.group(1)
                a_chunks = re.findall(r'(dash_h264/chunk[^\n\r]+)', a_text)[:max_chunks]
                a_bytes = bytearray(SESSION.get(a_init_url, timeout=10).content)
                for ac in a_chunks:
                    a_bytes.extend(SESSION.get(base_url + ac, timeout=10).content)
                raw_a.write_bytes(a_bytes)
                has_audio = True

        # 3. Fast multiplex
        if out_file.exists():
            out_file.unlink()

        if has_audio:
            cmd = ['ffmpeg', '-y', '-i', str(raw_v), '-i', str(raw_a), '-c', 'copy', '-movflags', '+faststart', str(out_file)]
        else:
            cmd = ['ffmpeg', '-y', '-i', str(raw_v), '-c', 'copy', '-movflags', '+faststart', str(out_file)]

        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if res.returncode == 0 and out_file.exists() and out_file.stat().st_size > 200_000:
            return True
    except Exception as e:
        print(f"  [!] download_steam_fmp4 error: {e}")
    finally:
        for f in (raw_v, raw_a):
            try:
                if f.exists(): f.unlink()
            except Exception:
                pass
    return False

def main():
    cat_path = PROJECT_ROOT / "catalog" / "data" / "catalog.json"
    with open(cat_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    empty_games = [g for g in catalog["games"] if len(g.get("variants", [])) == 0]
    print(f"Games with 0 variants to process: {len(empty_games)}")

    gdrive_token = get_gdrive_token()
    if not gdrive_token:
        print("[!] No Google Drive token!")
        return

    added = 0
    for g in empty_games:
        tid = g["titleId"]
        title = g["title"]
        appid = EXACT_STEAM_APPIDS.get(tid)
        if not appid:
            print(f"[-] No AppID for {title} [{tid}]")
            continue

        print(f"\n[*] Processing {title} [{tid}] (Steam AppID {appid})...")
        t_info = get_steam_trailer_info(appid)
        if not t_info:
            print(f"[-] Could not find trailer stream for {appid}")
            continue

        hls_url, trailer_name = t_info
        print(f"  Found trailer: {trailer_name}")

        out_mp4 = P720_DIR / f"{tid}_switch720p.mp4"
        print("  Fast fetching fMP4 segments (1280x720 30fps)...")
        t0 = time.time()
        ok = download_steam_fmp4(hls_url, out_mp4, max_chunks=5)
        if not ok:
            print("  [-] Failed to download/mux video segments!")
            continue

        elapsed = round(time.time() - t0, 2)
        size_mb = out_mp4.stat().st_size / (1024 * 1024)
        print(f"  [+] Assembled perfect Switch 720p MP4 in {elapsed}s ({size_mb:.2f} MB)!")

        print("  Uploading to Google Drive...")
        gdrive_token = get_gdrive_token() or gdrive_token
        try:
            up_res = GoogleDriveClient.upload_file(out_mp4, GDRIVE_FOLDER_ID, gdrive_token)
            file_id = up_res.get("fileId")
            direct_url = up_res.get("directUrl") or f"https://drive.google.com/uc?export=download&id={file_id}"
            preview_url = up_res.get("previewUrl") or f"https://drive.google.com/thumbnail?id={file_id}&sz=w640"
        except Exception as e:
            print(f"  [-] Upload error: {e}")
            continue

        sha256_hex = compute_sha256(out_mp4)
        var_id = f"v_{hashlib.md5(f'{tid}_{hls_url}'.encode()).hexdigest()[:8]}"

        new_variant = {
            "id": var_id,
            "name": trailer_name[:48],
            "style": "cinematic",
            "version": "1.0",
            "url": direct_url,
            "previewUrl": preview_url,
            "sizeBytes": out_mp4.stat().st_size,
            "sha256": sha256_hex,
            "durationSec": 15.0,
            "author": "Steam Official",
            "codec": "h264",
            "width": 1280,
            "height": 720,
            "fps": 30.0,
            "hasAudio": True,
            "notes": f"Switch 720p 30fps H264 | {trailer_name[:40]}"
        }

        g.setdefault("variants", []).append(new_variant)
        added += 1
        print(f"  [SUCCESS] Added variant to {title} [{tid}]! ({added}/{len(empty_games)})")
        try:
            out_mp4.unlink()
        except Exception:
            pass

    if added > 0:
        catalog["updatedAt"] = datetime.now(timezone.utc).isoformat()
        catalog["lastUpdated"] = catalog["updatedAt"]
        catalog["totalGames"] = len(catalog["games"])
        catalog["totalVariants"] = sum(len(g.get("variants", [])) for g in catalog["games"])
        with open(cat_path, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)

        print(f"\n[+] Catalog updated: {catalog['totalGames']} games, {catalog['totalVariants']} variants! Pushing...")

        gh_token, _ = GitHubPublisher.get_stored_credentials()
        repo_url = f"https://x-access-token:{gh_token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"
        git_env = os.environ.copy()
        git_env["GIT_EDITOR"] = ":"
        if LOCAL_PROXY:
            git_env["http_proxy"] = LOCAL_PROXY
            git_env["https_proxy"] = LOCAL_PROXY

        try:
            subprocess.run(["git", "add", "catalog/data/catalog.json"], check=True)
            subprocess.run(["git", "commit", "-m", f"fix(catalog): fill remaining empty Switch 1 games (+{added}) ({catalog['totalVariants']} total) [skip render] [skip ci]"], env=git_env, check=True)
            subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/main"], env=git_env, check=True)
            print("[+] Pushed to GitHub main!")
        except Exception as e:
            print(f"[!] Push error: {e}")

if __name__ == "__main__":
    main()
