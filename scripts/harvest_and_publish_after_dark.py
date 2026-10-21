"""
H3H After Dark (18+) Autonomous Harvester & Publisher.
Scrapes, downloads, converts to Switch 720p H.264, uploads to Google Drive 'H3H-AfterDark',
updates catalog_after_dark.json, and pushes to 'after-dark' branch.
"""

import sys
import os
import json
import time
import hashlib
import subprocess
import urllib.request
from pathlib import Path

sys.path.insert(0, 'studio')
from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient

DRIVE_STAGE = Path(r"H:\h3h_stage")
RAW_DIR = DRIVE_STAGE / "raw"
P720_DIR = DRIVE_STAGE / "720p"
THUMB_DIR = DRIVE_STAGE / "thumbs"

RAW_DIR.mkdir(parents=True, exist_ok=True)
P720_DIR.mkdir(parents=True, exist_ok=True)
THUMB_DIR.mkdir(parents=True, exist_ok=True)

AFTER_DARK_FOLDER_ID = "1SXWjp12pKxPPT6YRMZ7tle8cgZdrKkHk"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

TARGETS = [
    # NieR:Automata (01005C000B2AE000)
    {
        "tid": "01005C000B2AE000",
        "game_title": "NieR:Automata The End of YoRHa Edition",
        "publisher": "Square Enix",
        "var_id": "nier-2b-yorha-blade",
        "name": "2B: YoRHa No.2 Type B Blade",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2023/2b-nier-automata-preview.webm",
        "existing_fid": "1MHtkA5yY2K-OxIf50TF7B4q8YFlc34ni"
    },
    {
        "tid": "01005C000B2AE000",
        "game_title": "NieR:Automata The End of YoRHa Edition",
        "publisher": "Square Enix",
        "var_id": "nier-2b-blue-lilies",
        "name": "2B: Field of Blue Lilies",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2026/2b-in-the-field-of-blue-lilies-nier-automata-preview.webm"
    },
    {
        "tid": "01005C000B2AE000",
        "game_title": "NieR:Automata The End of YoRHa Edition",
        "publisher": "Square Enix",
        "var_id": "nier-2b-blindfold",
        "name": "2B: Blindfold & Katana",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2024/2b-blindfold-nier-automata-preview.webm"
    },

    # Final Fantasy VII (0100A5B00BDC6000)
    {
        "tid": "0100A5B00BDC6000",
        "game_title": "Final Fantasy VII",
        "publisher": "Square Enix",
        "var_id": "ff7-tifa-starry-sky",
        "name": "Tifa Lockhart: Starry Sky",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2022/tifa-lockhart-starry-sky-final-fantasy-vii-preview.webm"
    },
    {
        "tid": "0100A5B00BDC6000",
        "game_title": "Final Fantasy VII",
        "publisher": "Square Enix",
        "var_id": "ff7-tifa-flower-field",
        "name": "Tifa Lockhart: Flower Field",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2026/tifa-relaxing-flower-field-final-fantasy-vii-remake-preview.webm"
    },

    # The Legend of Zelda: Tears of the Kingdom (0100F2C0115B6000)
    {
        "tid": "0100F2C0115B6000",
        "game_title": "The Legend of Zelda: Tears of the Kingdom",
        "publisher": "Nintendo",
        "var_id": "zelda-ultrahand-totk",
        "name": "Princess Zelda: Tears of the Kingdom",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2023/zelda-ultrahand-tears-of-the-kingdom-preview.webm"
    },

    # Bayonetta (010076F0049A2000)
    {
        "tid": "010076F0049A2000",
        "game_title": "Bayonetta",
        "publisher": "SEGA / Nintendo",
        "var_id": "bayonetta-cereza-witch",
        "name": "Cereza Bayonetta: Umbra Witch",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2023/cereza-bayonetta-preview.webm"
    },

    # ★ Коллекция After Dark (Свободный выбор) (0000000000000000)
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "cyberpunk-lucy-moon",
        "name": "Lucy: Night City & Moon (Cyberpunk)",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2022/lucy-cyberpunk-edgerunners-1-preview.webm"
    },
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "stellar-blade-eve-sunset",
        "name": "Eve: Nano Suit & Sunset (Stellar Blade)",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2025/eve-stellar-blade-preview.webm"
    },
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "nikke-cinderella-bikini",
        "name": "Cinderella: Summer Bikini (NIKKE)",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2026/cinderella-bikini-goddess-of-victory-nikke-preview.webm"
    },
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "nikke-sakura-summer",
        "name": "Sakura: Summer Bloom Ecchi (NIKKE)",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2026/nikke-sakura-bloom-in-summer-preview.webm"
    },
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "azur-lane-prinz-eugen-bikini",
        "name": "Prinz Eugen: Beach Swimsuit (Azur Lane)",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2022/prinz-eugen-bikini-azur-lane-preview.webm"
    },
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "genshin-raiden-inazuma",
        "name": "Raiden Shogun: Inazuma Throne (Genshin)",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2026/raiden-shogun-throne-room-genshin-impact-preview.webm"
    },
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "genshin-yae-sakura",
        "name": "Yae Miko: Sakura Blossoms (Genshin)",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2026/yae-miko-sakura-cherry-blossoms-genshin-impact-preview.webm"
    },
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "genshin-arlecchino-blood",
        "name": "Arlecchino: Crimson Moon (Genshin)",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2026/arlecchino-crimson-moon-genshin-impact-preview.webm"
    },
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "honkai-kafka-spider",
        "name": "Kafka: Destiny Spider (Honkai)",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2024/kafka-honkai-star-rail-1-preview.webm"
    },
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "chainsaw-makima-hypnotic",
        "name": "Makima: Hypnotic Eyes (Chainsaw Man)",
        "style": "Ecchi / Mature",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2026/makima-controlling-chainsaw-man-preview.webm"
    }
]

def calculate_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def get_duration(filepath):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(filepath)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return round(float(res.stdout.strip()), 2)
    except Exception:
        return 15.0

def process_item(item, token):
    var_id = item['var_id']
    name = item['name']
    vid_url = item['vid_url']
    
    print(f"\n--------------------------------------------------")
    print(f"[*] Processing: {name} ({var_id})")
    
    ext = ".webm" if ".webm" in vid_url else ".mp4"
    raw_path = RAW_DIR / f"{var_id}{ext}"
    out_mp4 = P720_DIR / f"{var_id}.mp4"
    thumb_path = THUMB_DIR / f"{var_id}.jpg"
    
    # 1. Download raw if not present
    if not raw_path.exists() or raw_path.stat().st_size == 0:
        print(f"[*] Downloading raw from {vid_url}...")
        req = urllib.request.Request(vid_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=40) as resp, open(raw_path, 'wb') as f:
            f.write(resp.read())
        print(f"[+] Downloaded: {raw_path.stat().st_size} bytes")
    else:
        print(f"[+] Raw cached: {raw_path.stat().st_size} bytes")

    # 2. Transcode to 720p H.264
    if not out_mp4.exists() or out_mp4.stat().st_size == 0:
        print(f"[*] Transcoding to 720p 30fps H.264...")
        cmd = [
            "ffmpeg", "-y", "-i", str(raw_path),
            "-t", "30",
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,fps=30",
            "-c:v", "libx264", "-preset", "slow", "-crf", "20",
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
            "-b:v", "2500k", "-maxrate", "3000k", "-bufsize", "5000k",
            "-an", "-movflags", "+faststart",
            str(out_mp4)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[+] Transcoded: {out_mp4.stat().st_size} bytes")
    else:
        print(f"[+] MP4 cached: {out_mp4.stat().st_size} bytes")

    # 3. Generate thumbnail
    if not thumb_path.exists() or thumb_path.stat().st_size == 0:
        cmd_thumb = [
            "ffmpeg", "-y", "-ss", "00:00:01", "-i", str(out_mp4),
            "-vframes", "1",
            "-vf", "scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2:color=black",
            str(thumb_path)
        ]
        subprocess.run(cmd_thumb, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 4. Upload to Google Drive if needed
    file_id = item.get("existing_fid")
    if not file_id:
        print(f"[*] Uploading to Google Drive folder 'H3H-AfterDark'...")
        up_res = GoogleDriveClient.upload_file(out_mp4, AFTER_DARK_FOLDER_ID, token)
        file_id = up_res.get('id')
        print(f"[+] Uploaded: Drive ID = {file_id}")
    else:
        print(f"[+] Using existing Drive ID = {file_id}")

    # Ensure public access
    GoogleDriveClient.make_public(file_id, token)

    # 5. Metadata
    sha = calculate_sha256(out_mp4)
    duration = get_duration(out_mp4)
    
    variant = {
        "id": var_id,
        "name": name,
        "style": item.get("style", "Ecchi / Mature"),
        "version": "1.0",
        "url": f"https://drive.google.com/uc?export=download&id={file_id}",
        "previewUrl": f"https://drive.google.com/thumbnail?id={file_id}&sz=w640",
        "sizeBytes": out_mp4.stat().st_size,
        "sha256": sha,
        "durationSec": duration,
        "author": "MoeWalls / Holy3holy-dev",
        "codec": "h264",
        "width": 1280,
        "height": 720,
        "fps": 30.0,
        "hasAudio": False,
        "notes": f"H3H After Dark 18+ Animated Background"
    }
    return variant

def main():
    print("==================================================")
    print("H3H After Dark Autonomous Harvest & Publish")
    print(f"Targeting {len(TARGETS)} verified 18+/Waifu video themes")
    print("==================================================")

    cfg = GoogleDriveHelper.get_stored_config()
    token = GoogleDriveHelper.refresh_access_token(cfg.get('refresh_token'))
    if not token:
        print("[-] Error: Failed to acquire Google Drive access token!")
        return 1

    catalog_path = Path("catalog/data/catalog_after_dark.json")
    if catalog_path.exists():
        cat = json.loads(catalog_path.read_text(encoding="utf-8"))
    else:
        cat = {
            "schemaVersion": 1,
            "name": "H3H After Dark (18+) Official Catalog",
            "updatedAt": "",
            "totalGames": 0,
            "totalVariants": 0,
            "games": []
        }

    # Group targets by title ID
    groups = {}
    for t in TARGETS:
        tid = t['tid']
        if tid not in groups:
            groups[tid] = {
                "titleId": tid,
                "title": t['game_title'],
                "publisher": t['publisher'],
                "items": []
            }
        groups[tid]['items'].append(t)

    processed_count = 0
    for tid, grp in groups.items():
        # Find or create game entry in catalog
        g_entry = next((g for g in cat['games'] if g['titleId'].upper() == tid.upper()), None)
        if not g_entry:
            g_entry = {
                "titleId": tid,
                "title": grp['title'],
                "publisher": grp['publisher'],
                "variants": []
            }
            cat['games'].append(g_entry)
        else:
            g_entry['title'] = grp['title']
            g_entry['publisher'] = grp['publisher']

        for item in grp['items']:
            try:
                # Refresh token periodically if needed
                if processed_count > 0 and processed_count % 5 == 0:
                    token = GoogleDriveHelper.refresh_access_token(cfg.get('refresh_token'))
                
                v = process_item(item, token)
                # Remove if variant with same ID already exists
                g_entry['variants'] = [x for x in g_entry['variants'] if x['id'] != v['id']]
                g_entry['variants'].append(v)
                processed_count += 1

                # Save catalog incrementally
                cat['totalGames'] = len(cat['games'])
                cat['totalVariants'] = sum(len(g['variants']) for g in cat['games'])
                cat['updatedAt'] = datetime.now(timezone.utc).isoformat()
                catalog_path.write_text(json.dumps(cat, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"[+] Saved catalog: {cat['totalVariants']} total variants")
            except Exception as e:
                print(f"[-] ERROR processing {item['var_id']}: {e}")

    print("\n==================================================")
    print(f"HARVEST COMPLETE: {processed_count} variants processed!")
    print(f"Total Games in Catalog: {cat['totalGames']}")
    print(f"Total Variants: {cat['totalVariants']}")
    print("==================================================")
    return 0

if __name__ == '__main__':
    from datetime import datetime, timezone
    sys.exit(main())
