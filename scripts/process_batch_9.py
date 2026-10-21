"""
Batch 9: Massive 50-Game Expansion for Nintendo Switch.
Covers Mario, Zelda, Pokemon, JRPGs, Indies & Sports hits.
Encodes strictly for 4IFIR compliance (1280x720, 30fps, High 4.1, -an).
"""

import sys
import os
import json
import subprocess
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.analyzer import VideoAnalyzer
from h3h_studio.core.google_drive import GoogleDriveClient, GoogleDriveHelper

OUTPUT_DIR = Path(r"e:\videofon\downloaded_official_backgrounds")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FOLDER_ID = "1hI1klJ6t2ymVoBwGA6IzY79QMjp5dTJC"

with open("scripts/batch_9_targets.json", "r", encoding="utf-8") as f:
    TARGETS = json.load(f)

def encode_to_4ifir(input_path: Path, output_path: Path) -> bool:
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "fast", "-profile:v", "high", "-level", "4.1",
        "-crf", "20", "-maxrate", "3500k", "-bufsize", "7000k",
        "-an", str(output_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if res.returncode == 0 and output_path.exists():
        analysis = VideoAnalyzer.analyze_file(output_path)
        return analysis.is_compliant
    return False

def main():
    print(f"=== Starting Batch 9 Processing ({len(TARGETS)} Flagship Switch Titles) ===\n")
    newly_encoded = []

    for idx, item in enumerate(TARGETS, 1):
        target = OUTPUT_DIR / item["filename"]
        if target.exists() and target.stat().st_size > 50000:
            print(f"[{idx}/{len(TARGETS)}] Skipping existing: {target.name}")
            newly_encoded.append(target)
            continue

        print(f"[{idx}/{len(TARGETS)}] Searching & Fetching: {item['name']} ({item['titleId']})...")
        tmp_raw = OUTPUT_DIR / f"raw_b9_{idx}.mp4"

        # Step A: Download with ytsearch
        dl_cmd = [
            "C:/Users/HL/AppData/Local/Python/bin/python.exe", "-m", "yt_dlp",
            "-f", "bestvideo[height<=1080][ext=mp4]/best[ext=mp4]/best",
            "--download-sections", item["time_range"],
            "--force-keyframes-at-cuts",
            "-o", str(tmp_raw),
            f"ytsearch1:{item['query']}"
        ]

        try:
            res = subprocess.run(dl_cmd, capture_output=True, text=True, timeout=90, stdin=subprocess.DEVNULL)
            if tmp_raw.exists() and tmp_raw.stat().st_size > 10000:
                if encode_to_4ifir(tmp_raw, target):
                    sz_mb = target.stat().st_size / (1024 * 1024)
                    print(f"    [+] OK: {target.name} ({sz_mb:.2f} MB)")
                    newly_encoded.append(target)
                else:
                    print(f"    [-] FFmpeg encode failed for {item['name']}")
            else:
                # Fallback full dl with manual cut
                print(f"    [*] Fallback full download for {item['name']}...")
                dl_fallback = [
                    "C:/Users/HL/AppData/Local/Python/bin/python.exe", "-m", "yt_dlp",
                    "-f", "bestvideo[height<=1080][ext=mp4]/best[ext=mp4]/best",
                    "-o", str(tmp_raw),
                    f"ytsearch1:{item['query']}"
                ]
                subprocess.run(dl_fallback, capture_output=True, text=True, timeout=90, stdin=subprocess.DEVNULL)
                if tmp_raw.exists() and tmp_raw.stat().st_size > 10000:
                    start_s = item["time_range"].replace("*", "").split("-")[0]
                    end_s = item["time_range"].replace("*", "").split("-")[1]
                    cmd_cut = [
                        "ffmpeg", "-y", "-ss", start_s, "-to", end_s, "-i", str(tmp_raw),
                        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
                        "-c:v", "libx264", "-preset", "fast", "-profile:v", "high", "-level", "4.1",
                        "-crf", "20", "-maxrate", "3500k", "-bufsize", "7000k",
                        "-an", str(target)
                    ]
                    subprocess.run(cmd_cut, capture_output=True, text=True, stdin=subprocess.DEVNULL)
                    if target.exists() and VideoAnalyzer.analyze_file(target).is_compliant:
                        sz_mb = target.stat().st_size / (1024 * 1024)
                        print(f"    [+] OK (via fallback): {target.name} ({sz_mb:.2f} MB)")
                        newly_encoded.append(target)
                    else:
                        print(f"    [-] Fallback cut failed for {item['name']}")
                else:
                    print(f"    [-] yt-dlp search/download failed for {item['name']}")
        except Exception as e:
            print(f"    [-] Error {item['name']}: {e}")
        finally:
            if tmp_raw.exists():
                try: tmp_raw.unlink()
                except Exception: pass

    print(f"\n[DONE] Batch 9 Local Encoding Complete! Encoded {len(newly_encoded)}/{len(TARGETS)} titles.")

    # Try uploading to Drive if token is active
    cfg = GoogleDriveHelper.get_stored_config()
    token = cfg.get("token")
    if token and newly_encoded:
        try:
            GoogleDriveClient.test_connection(token)
            print(f"\n[*] Active Google Drive token detected, uploading {len(newly_encoded)} files...")
            remote_files = GoogleDriveClient.list_folder_files(FOLDER_ID, token)
            remote_names = {rf["name"] for rf in remote_files}

            for fpath in newly_encoded:
                if fpath.name in remote_names:
                    continue
                sz_mb = fpath.stat().st_size / (1024 * 1024)
                print(f"    [*] Uploading to Drive: {fpath.name} ({sz_mb:.2f} MB)...")
                try:
                    GoogleDriveClient.upload_file(fpath, FOLDER_ID, token)
                    print(f"    [+] Uploaded: {fpath.name}")
                except Exception as ue:
                    print(f"    [-] Upload error {fpath.name}: {ue}")

            print("\n[*] Running 1-Click Sync to GitHub...")
            sres = GoogleDriveHelper.one_click_sync(FOLDER_ID, progress_cb=print)
            print(f"✅ Sync complete! Total games: {sres['totalGames']}, variants: {sres['totalVariants']}")
        except Exception as te:
            print(f"[*] Note: Google Drive token is expired or unavailable ({te}). Files remain safely saved in {OUTPUT_DIR}.")

if __name__ == "__main__":
    main()
