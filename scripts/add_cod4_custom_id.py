import sys
sys.path.insert(0, 'studio')
import os
import json
import urllib.request
import subprocess
from pathlib import Path
from h3h_studio.core.google_drive import GoogleDriveHelper
from h3h_studio.core.github_publisher import GitHubPublisher

USER_TID = "01B7F96B70C31000"
ALT_TID = "0100C0D400000000"

# Step 1: Base variant
var1 = {
    "id": "cod4-mw-classic",
    "name": "Call of Duty 4 MW: Intro & Action",
    "style": "Cinematic",
    "version": "1.0",
    "url": "https://drive.google.com/uc?export=download&id=1de2HUBh5hsAdld-pfjTRLjzO3lqvq7gL",
    "previewUrl": "https://drive.google.com/thumbnail?id=1de2HUBh5hsAdld-pfjTRLjzO3lqvq7gL&sz=w640",
    "sizeBytes": 0,
    "sha256": "",
    "durationSec": 20.0,
    "author": "Holy3holy-dev",
    "codec": "h264",
    "width": 1280,
    "height": 720,
    "fps": 30.0,
    "hasAudio": False,
    "notes": "Classic CoD4 Modern Warfare Video Background"
}

variants = [var1]

# Step 2: Try fetching and converting animated webp from SteamGridDB
try:
    webp_url = "https://cdn2.steamgriddb.com/grid/6f2cabb88cadfe2076966e1fdc7025df.webp"
    req = urllib.request.Request(webp_url, headers={"User-Agent": "Mozilla/5.0"})
    temp_webp = Path("temp_cod4.webp")
    temp_mp4 = Path("temp_cod4.mp4")
    
    with urllib.request.urlopen(req) as resp:
        temp_webp.write_bytes(resp.read())
    
    print("[+] Downloaded CoD4 animated webp from SteamGridDB")
    cmd = [
        "ffmpeg", "-y", "-i", str(temp_webp),
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,fps=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
        "-an", str(temp_mp4)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and temp_mp4.exists():
        print(f"[+] Converted to MP4: {temp_mp4.stat().st_size} bytes")
        drive = GoogleDriveHelper()
        if drive.is_authenticated():
            remote_name = f"{USER_TID}_Call_of_Duty_4_Animated_Hero.mp4"
            print(f"[*] Uploading {remote_name} to Google Drive...")
            file_id = drive.upload_file(str(temp_mp4), remote_name)
            if file_id:
                print(f"[+] Uploaded to Drive: file_id = {file_id}")
                var2 = {
                    "id": "cod4-mw-hero",
                    "name": "Call of Duty 4 MW: Animated Hero",
                    "style": "Animated Art",
                    "version": "1.0",
                    "url": f"https://drive.google.com/uc?export=download&id={file_id}",
                    "previewUrl": f"https://drive.google.com/thumbnail?id={file_id}&sz=w640",
                    "sizeBytes": temp_mp4.stat().st_size,
                    "sha256": "",
                    "durationSec": 15.0,
                    "author": "SteamGridDB / Holy3holy-dev",
                    "codec": "h264",
                    "width": 1280,
                    "height": 720,
                    "fps": 30.0,
                    "hasAudio": False,
                    "notes": "SteamGridDB Animated Hero Grid"
                }
                variants.append(var2)
    # Cleanup local temp
    if temp_webp.exists(): temp_webp.unlink()
    if temp_mp4.exists(): temp_mp4.unlink()
except Exception as e:
    print(f"[-] Note on SGDB variant: {e}")

# Step 3: Add to catalog.json
cat_path = Path("catalog/data/catalog.json")
with open(cat_path, "r", encoding="utf-8") as f:
    cat = json.load(f)

for tid in [USER_TID, ALT_TID]:
    existing = next((g for g in cat["games"] if g["titleId"].upper() == tid.upper()), None)
    if existing:
        existing["title"] = "Call of Duty 4: Modern Warfare"
        existing["publisher"] = "Activision"
        existing["variants"] = list(variants)
        print(f"[+] Updated existing entry for {tid} with {len(variants)} variants")
    else:
        new_g = {
            "titleId": tid,
            "title": "Call of Duty 4: Modern Warfare",
            "publisher": "Activision",
            "variants": list(variants)
        }
        cat["games"].append(new_g)
        print(f"[+] Added new entry for {tid} with {len(variants)} variants")

cat["totalGames"] = len(cat["games"])
cat["totalVariants"] = sum(len(g.get("variants", [])) for g in cat["games"])

with open(cat_path, "w", encoding="utf-8") as f:
    json.dump(cat, f, indent=2, ensure_ascii=False)

print(f"[+] Catalog updated: {cat['totalGames']} games, {cat['totalVariants']} variants")

# Also copy to romfs
romfs_cat = Path("downloader/romfs/catalog.json")
romfs_cat.write_text(cat_path.read_text(encoding="utf-8"), encoding="utf-8")
print("[+] Synchronized to downloader/romfs/catalog.json")

# Step 4: Sync to GitHub
token, _ = GitHubPublisher.get_stored_credentials()
if token:
    print("[*] Syncing catalog.json to GitHub...")
    GoogleDriveHelper.sync_catalog_to_github(cat_path, token=token, progress_cb=print)
    print("[+] GitHub sync complete!")
