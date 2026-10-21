import sys
sys.path.insert(0, 'studio')
import json
import urllib.request
import subprocess
from pathlib import Path
from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient
from h3h_studio.core.github_publisher import GitHubPublisher

USER_TID = "01B7F96B70C31000"
ALT_TID = "0100C0D400000000"

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

# Download and convert animated webp
webp_url = "https://cdn2.steamgriddb.com/grid/6f2cabb88cadfe2076966e1fdc7025df.webp"
temp_webp = Path("temp_cod4.webp")
temp_mp4 = Path("temp_cod4.mp4")

try:
    req = urllib.request.Request(webp_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        temp_webp.write_bytes(resp.read())
    print("[+] Downloaded CoD4 webp")

    cmd = [
        "ffmpeg", "-y", "-i", str(temp_webp),
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,fps=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
        "-an", str(temp_mp4)
    ]
    subprocess.run(cmd, check=True)
    print(f"[+] Converted to MP4: {temp_mp4.stat().st_size} bytes")

    cfg = GoogleDriveHelper.get_stored_config()
    tok_res = GoogleDriveHelper.refresh_access_token(cfg.get('refresh_token'))
    access_token = tok_res[0]
    folder_id = cfg.get('folder_id')

    print("[*] Uploading to Google Drive...")
    up_res = GoogleDriveClient.upload_file(temp_mp4, folder_id, access_token)
    file_id = up_res.get('id')
    print(f"[+] Uploaded to Drive: ID = {file_id}")

    var2 = {
        "id": "cod4-mw-hero",
        "name": "Call of Duty 4 MW: Animated Hero Art",
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
except Exception as e:
    print(f"[-] SGDB error: {e}")
finally:
    if temp_webp.exists(): temp_webp.unlink()
    if temp_mp4.exists(): temp_mp4.unlink()

# Update catalog.json
cat_path = Path("catalog/data/catalog.json")
cat = json.loads(cat_path.read_text(encoding="utf-8"))

for tid in [USER_TID, ALT_TID]:
    existing = next((g for g in cat["games"] if g["titleId"].upper() == tid.upper()), None)
    if existing:
        existing["title"] = "Call of Duty 4: Modern Warfare"
        existing["publisher"] = "Activision"
        existing["variants"] = list(variants)
        print(f"[+] Updated {tid} with {len(variants)} variants")
    else:
        new_g = {
            "titleId": tid,
            "title": "Call of Duty 4: Modern Warfare",
            "publisher": "Activision",
            "variants": list(variants)
        }
        cat["games"].append(new_g)
        print(f"[+] Added {tid} with {len(variants)} variants")

cat["totalGames"] = len(cat["games"])
cat["totalVariants"] = sum(len(g.get("variants", [])) for g in cat["games"])

cat_path.write_text(json.dumps(cat, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"[+] Saved catalog.json: {cat['totalGames']} games, {cat['totalVariants']} variants")

# Sync to GitHub
gh_token, _ = GitHubPublisher.get_stored_credentials()
if gh_token:
    print("[*] Syncing to GitHub...")
    GoogleDriveHelper.sync_catalog_to_github(cat_path, token=gh_token, progress_cb=print)
    print("[+] Done syncing to GitHub!")
