import sys
import os
import json
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

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

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

def process_single(item):
    var_id = item['var_id']
    title = item['title']
    vid_url = item['vid_url']
    
    print(f"\n==================================================")
    print(f"[*] Processing: {title} ({var_id})")
    
    # 1. Download raw
    ext = ".webm" if ".webm" in vid_url else ".mp4"
    raw_path = RAW_DIR / f"{var_id}{ext}"
    if not raw_path.exists() or raw_path.stat().st_size == 0:
        print(f"[*] Downloading raw: {vid_url}")
        req = urllib.request.Request(vid_url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp, open(raw_path, 'wb') as out:
            out.write(resp.read())
        print(f"[+] Downloaded raw: {raw_path.stat().st_size} bytes")
    else:
        print(f"[+] Raw already exists: {raw_path.stat().st_size} bytes")
        
    # 2. Transcode to Switch 720p 30fps H.264
    out_mp4 = P720_DIR / f"{var_id}.mp4"
    print(f"[*] Transcoding to 720p H.264...")
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
    print(f"[+] Transcoded MP4: {out_mp4.stat().st_size} bytes")
    
    # 3. Generate Thumbnail
    thumb_path = THUMB_DIR / f"{var_id}.jpg"
    print(f"[*] Generating poster thumbnail...")
    cmd_thumb = [
        "ffmpeg", "-y", "-ss", "00:00:01", "-i", str(out_mp4),
        "-vframes", "1",
        "-vf", "scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2:color=black",
        str(thumb_path)
    ]
    subprocess.run(cmd_thumb, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[+] Thumbnail created: {thumb_path.stat().st_size} bytes")
    
    # 4. Upload to Google Drive
    print(f"[*] Authenticating with Google Drive...")
    cfg = GoogleDriveHelper.get_stored_config()
    tok_res = GoogleDriveHelper.refresh_access_token(cfg.get('refresh_token'))
    access_token = tok_res if isinstance(tok_res, str) else tok_res[0]
    
    print(f"[*] Uploading 720p video to Google Drive After Dark folder...")
    up_res = GoogleDriveClient.upload_file(out_mp4, AFTER_DARK_FOLDER_ID, access_token)
    file_id = up_res.get('id')
    print(f"[+] Uploaded to Drive: File ID = {file_id}")
    
    # 5. Metadata
    sha = calculate_sha256(out_mp4)
    duration = get_duration(out_mp4)
    size_bytes = out_mp4.stat().st_size
    
    variant = {
        "id": var_id,
        "name": title,
        "style": "Ecchi / Mature",
        "version": "1.0",
        "url": f"https://drive.google.com/uc?export=download&id={file_id}",
        "previewUrl": f"https://drive.google.com/thumbnail?id={file_id}&sz=w640",
        "sizeBytes": size_bytes,
        "sha256": sha,
        "durationSec": duration,
        "author": item.get('author', 'H3H Studio'),
        "codec": "h264",
        "width": 1280,
        "height": 720,
        "fps": 30.0,
        "hasAudio": False,
        "notes": f"{item.get('game_name', 'After Dark')} Video Background"
    }
    print(f"[+] Variant constructed successfully:")
    print(json.dumps(variant, indent=2, ensure_ascii=False))
    return variant

if __name__ == '__main__':
    test_item = {
        "var_id": "nier-2b-yorha-blade",
        "title": "2B: YoRHa No.2 Type B Blade",
        "game_name": "NieR:Automata",
        "title_id": "01005C000B2AE000",
        "vid_url": "https://moewalls.com/wp-content/uploads/preview/2023/2b-nier-automata-preview.webm",
        "author": "MoeWalls / Holy3holy-dev"
    }
    res = process_single(test_item)
