"""
Batch High-Quality 4IFIR Video Icon Generator & Uploader.
Standard:
- Resolution: 256x256 (1:1 square)
- Filter: Lanczos downsampling + Unsharp mask (flags=lanczos,unsharp=3:3:0.6:3:3:0.0)
- Codec: H.264 Main Profile, 30fps, faststart, no audio
- Bitrate: 1.2 Mbps (CRF 18, maxrate 1.8M, bufsize 2.4M)
- Fast staging & direct parallel upload to Google Drive
- Syncs with catalog.json and commits to GitHub main
"""

import os
import sys
import json
import time
import shutil
import argparse
import subprocess

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)
from pathlib import Path
from typing import Optional, Tuple, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "studio"))

from tg_bot.bot import get_gdrive_auth
from tg_bot.config import GDRIVE_ICONS_FOLDER_ID
from h3h_studio.core.google_drive import GoogleDriveClient
from h3h_studio.core.github_publisher import GitHubPublisher
from tg_bot.config import detect_local_proxy

STAGE_720P_DIR = Path(r"H:\h3h_stage\720p")
TMP_ICONS_DIR = PROJECT_ROOT / "tmp" / "batch_hq_icons"
TMP_ICONS_DIR.mkdir(parents=True, exist_ok=True)
CATALOG_PATH = PROJECT_ROOT / "catalog" / "data" / "catalog.json"

def find_source_video(title_id: str, game_variants: list, local_files_map: dict) -> Optional[Path]:
    tid_lower = title_id.lower()
    candidates = [
        f"{tid_lower}.mp4",
        f"{tid_lower}_expand.mp4",
        f"{tid_lower}_variant.mp4",
        f"{tid_lower}_1.mp4",
        f"{tid_lower}_2.mp4",
        f"{tid_lower}_cover.mp4"
    ]
    for c in candidates:
        if c in local_files_map:
            return local_files_map[c]

    for v in game_variants:
        vid = (v.get("id") or "").lower()
        if vid:
            for ext in [".mp4", "_expand.mp4"]:
                v_cand = f"{vid}{ext}"
                if v_cand in local_files_map:
                    return local_files_map[v_cand]
    return None

def download_full_video(url: str, dest_path: Path) -> bool:
    try:
        import requests
        with requests.get(url, stream=True, timeout=25) as r:
            if r.status_code == 200:
                with open(dest_path, "wb") as f_out:
                    for chunk in r.iter_content(chunk_size=512*1024):
                        if chunk:
                            f_out.write(chunk)
                return dest_path.exists() and dest_path.stat().st_size >= 100000
    except Exception as e:
        print(f"    [!] Video download failed: {e}")
    return False

def transcode_hq_video_icon(src_video: Path, out_mp4: Path, duration_sec: float = 4.0) -> bool:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    crop_expr = "crop=min(iw\\,ih):min(iw\\,ih):(iw-ow)*0.5:(ih-oh)/2,scale=256:256:flags=lanczos,unsharp=3:3:0.6:3:3:0.0,fps=30,format=yuv420p"
    
    cmd = [
        "ffmpeg", "-y", "-nostdin",
        "-ss", "0.5",
        "-i", str(src_video),
        "-t", str(duration_sec),
        "-vf", crop_expr,
        "-c:v", "libx264",
        "-preset", "fast",
        "-profile:v", "main",
        "-crf", "18",
        "-b:v", "1200k",
        "-maxrate", "1800k",
        "-bufsize", "2400k",
        "-an",
        "-movflags", "+faststart",
        str(out_mp4)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"    [!] FFmpeg error (code {res.returncode}):\n" + "\n".join(res.stderr.splitlines()[-8:]))
    return res.returncode == 0 and out_mp4.exists() and out_mp4.stat().st_size >= 50000

def run_batch(batch_size: int = 50) -> int:
    print("=" * 60)
    print(f"[*] H3H High-Quality Video Icon Harvester (Batch size: {batch_size})")
    print("=" * 60)

    token, account_id = get_gdrive_auth("standard")
    if not token:
        print("[-] Failed to authenticate with Google Drive")
        return 0

    local_files_map = {}
    if STAGE_720P_DIR.exists():
        for f in STAGE_720P_DIR.glob("*.mp4"):
            try:
                if f.stat().st_size >= 100000:
                    local_files_map[f.name.lower()] = f
            except Exception:
                pass

    print(f"[*] Cached local 720p files: {len(local_files_map)}")

    cat_data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    games = cat_data.get("games", [])

    candidates = []
    for g in games:
        tid = g.get("titleId", "").upper()
        if not tid or tid == "0000000000000000":
            continue
        variants = g.get("variants", [])
        has_icon = any(v.get("hasIcon") and v.get("iconUrl") for v in variants)
        if not has_icon and variants:
            candidates.append(g)

    print(f"[*] Games in queue needing video icons: {len(candidates)}")
    if not candidates:
        print("[+] All games currently have video icons!")
        return 0

    processed_count = 0
    batch_candidates = candidates[:batch_size]

    for idx, g in enumerate(batch_candidates, 1):
        tid = g["titleId"].upper()
        title = g.get("title", tid)
        print(f"\n[{idx}/{len(batch_candidates)}] Processing Video Icon for {title} [{tid}]...")

        src_file = find_source_video(tid, g.get("variants", []), local_files_map)
        temp_src = None

        if src_file:
            print(f"  [+] Using local source: {src_file.name} ({src_file.stat().st_size // 1024} KB)")
        else:
            # Download stream chunk from variant URL
            primary_var = g["variants"][0]
            var_url = primary_var.get("url")
            if var_url:
                print(f"  [*] Downloading video sample from Google Drive...")
                temp_src = TMP_ICONS_DIR / f"{tid}_sample.mp4"
                if download_full_video(var_url, temp_src):
                    src_file = temp_src
                    print(f"  [+] Sample downloaded ({temp_src.stat().st_size // 1024} KB)")

        if not src_file or not src_file.exists():
            print(f"  [-] No source footage found for {title}, skipping")
            continue

        out_icon_mp4 = TMP_ICONS_DIR / f"{tid}.mp4"
        print(f"  [*] Transcoding 256x256 1.2M Lanczos+Unsharp HQ icon...")
        ok = transcode_hq_video_icon(src_file, out_icon_mp4, duration_sec=4.0)

        if temp_src and temp_src.exists():
            try:
                temp_src.unlink()
            except Exception:
                pass

        if not ok or not out_icon_mp4.exists():
            print(f"  [-] Failed to transcode video icon for {title}")
            continue

        icon_size = out_icon_mp4.stat().st_size
        print(f"  [+] Transcoded icon: {icon_size // 1024} KB (Lanczos+Unsharp 1.2M)")

        print(f"  [*] Uploading to Google Drive (folder {GDRIVE_ICONS_FOLDER_ID})...")
        try:
            upload_res = GoogleDriveClient.upload_file(out_icon_mp4, GDRIVE_ICONS_FOLDER_ID, token)
            direct_url = upload_res.get("directUrl")
            if not direct_url:
                print(f"  [-] Upload returned empty URL: {upload_res}")
                continue

            print(f"  [SUCCESS] Uploaded to Google Drive: {direct_url}")

            # Update catalog variants
            first_v = g["variants"][0]
            first_v["hasIcon"] = True
            first_v["iconUrl"] = direct_url
            first_v["iconSizeBytes"] = icon_size
            first_v["iconCodec"] = "h264"
            first_v["iconWidth"] = 256
            first_v["iconHeight"] = 256

            # Add separate icon variant
            icon_slug = f"icon-{tid.lower()}"
            existing_icon_var = next((v for v in g["variants"] if v.get("id") == icon_slug), None)
            if not existing_icon_var:
                g["variants"].append({
                    "id": icon_slug,
                    "name": f"4IFIR Иконка: {title}",
                    "style": "4IFIR Dynamic Icon",
                    "version": "1.0",
                    "url": direct_url,
                    "previewUrl": direct_url,
                    "sizeBytes": icon_size,
                    "sha256": "",
                    "durationSec": 4.0,
                    "author": "@4IFIR / H3H",
                    "codec": "h264",
                    "width": 256,
                    "height": 256,
                    "fps": 30.0,
                    "hasAudio": False,
                    "hasIcon": True,
                    "iconUrl": direct_url,
                    "iconSizeBytes": icon_size,
                    "iconCodec": "h264",
                    "iconWidth": 256,
                    "iconHeight": 256,
                    "notes": "4IFIR 256x256 HQ Video Icon (Lanczos + Unsharp 1.2M)"
                })

            processed_count += 1

            # Cleanup local mp4
            try:
                out_icon_mp4.unlink()
            except Exception:
                pass

        except Exception as e:
            print(f"  [-] Error uploading icon: {e}")

    if processed_count > 0:
        cat_data["totalGames"] = len(cat_data["games"])
        cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in cat_data["games"])
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        cat_data["updatedAt"] = now_iso
        cat_data["lastUpdated"] = now_iso
        with open(CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(cat_data, f, indent=2, ensure_ascii=False)
        print(f"\n[+] Saved catalog.json with +{processed_count} new HQ video icons!")

        # Sync and push with authenticated GitHub token
        gh_token, _ = GitHubPublisher.get_stored_credentials()
        local_proxy = detect_local_proxy()
        repo_url = f"https://x-access-token:{gh_token}@github.com/Holy3holy-dev/H3H-Backgrounds.git" if gh_token else "origin"
        git_env = os.environ.copy()
        git_env["GIT_EDITOR"] = ":"
        git_env["GIT_TERMINAL_PROMPT"] = "0"
        if local_proxy:
            git_env["http_proxy"] = local_proxy
            git_env["https_proxy"] = local_proxy

        subprocess.run(["git", "pull", "--rebase", repo_url, "main"], env=git_env, check=False)
        subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "build_min_catalog.py")], check=False)
        subprocess.run([
            "git", "add",
            "catalog/data/catalog.json",
            "catalog/data/catalog.min.json",
            "catalog/data/catalog.min.json.gz"
        ], check=False)
        msg = f"feat(icons): add {processed_count} high-quality 4IFIR video icons (Lanczos 1.2M) [skip render] [skip ci]"
        subprocess.run(["git", "commit", "-m", msg], env=git_env, check=False)
        res_push = subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/main"], env=git_env, capture_output=True, text=True)
        if res_push.returncode == 0:
            print(f"[+] Pushed to GitHub main: {msg}")
        else:
            print(f"[-] Git push notice: {res_push.stderr}")

    return processed_count

def main():
    parser = argparse.ArgumentParser(description="Batch HQ Video Icon Generator")
    parser.add_argument("--batch", type=int, default=30, help="Number of icons per batch")
    parser.add_argument("--continuous", action="store_true", help="Keep running continuously")
    parser.add_argument("--interval", type=int, default=15, help="Interval between batches")
    args = parser.parse_args()

    if args.continuous:
        while True:
            processed = run_batch(args.batch)
            if processed == 0:
                print(f"[*] Queue empty or resting. Sleeping {args.interval}s...")
            time.sleep(args.interval)
    else:
        run_batch(args.batch)

if __name__ == "__main__":
    main()
