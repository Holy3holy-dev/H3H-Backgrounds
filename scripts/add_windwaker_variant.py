import requests, subprocess, json, time, os, shutil
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "studio"))

from tg_bot.bot import get_gdrive_auth
from tg_bot.config import GDRIVE_FOLDER_ID
from h3h_studio.core.google_drive import GoogleDriveClient

tmp_dir = PROJECT_ROOT / "tmp"
tmp_dir.mkdir(parents=True, exist_ok=True)

# 1. Download webm
webm_url = "https://moewalls.com/wp-content/uploads/preview/2023/the-legend-of-zelda-the-wind-waker-pixel-preview.webm"
raw_webm = tmp_dir / "windwaker_pixel.webm"
out_mp4 = tmp_dir / "01CAA550FBC40000_pixel.mp4"

print("[*] Downloading Wind Waker Pixel Wallpaper...")
r = requests.get(webm_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
raw_webm.write_bytes(r.content)
print(f"[+] Downloaded {raw_webm.stat().st_size} bytes")

# 2. Encode to 720p 30fps Switch MP4
print("[*] Encoding to 1280x720 30fps Switch MP4...")
cmd = [
    "ffmpeg", "-y", "-nostdin",
    "-stream_loop", "-1",
    "-i", str(raw_webm),
    "-t", "15",
    "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=30",
    "-c:v", "libx264",
    "-preset", "fast",
    "-crf", "19",
    "-pix_fmt", "yuv420p",
    "-an",
    "-movflags", "+faststart",
    str(out_mp4)
]
subprocess.run(cmd, check=True)
print(f"[+] Encoded MP4 size: {out_mp4.stat().st_size} bytes")

# 3. Upload to Google Drive
token, _ = get_gdrive_auth("standard")
print("[*] Uploading to Google Drive...")
upload_res = GoogleDriveClient.upload_file(out_mp4, GDRIVE_FOLDER_ID, token)
direct_url = upload_res.get("directUrl")
print(f"[SUCCESS] Uploaded: {direct_url}")

# 4. Save metadata to a temporary json
res_data = {
    "directUrl": direct_url,
    "sizeBytes": out_mp4.stat().st_size
}
(tmp_dir / "windwaker_upload.json").write_text(json.dumps(res_data))
print("[+] Done!")
