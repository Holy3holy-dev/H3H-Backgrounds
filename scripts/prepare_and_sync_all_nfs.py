import sys
import subprocess
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.analyzer import VideoAnalyzer
from h3h_studio.core.google_drive import GoogleDriveClient, GoogleDriveHelper
from h3h_studio.core.github_publisher import GitHubPublisher

OUTPUT_DIR = Path(r"e:\videofon\downloaded_official_backgrounds")
FOLDER_ID = "1hI1klJ6t2ymVoBwGA6IzY79QMjp5dTJC"
cfg = GoogleDriveHelper.get_stored_config()
TOKEN = cfg.get("token")

# Step 1: Download & encode NFS Underground 1
nfsu1_target = OUTPUT_DIR / "0100554731000000_NFS_Underground_1.mp4"
if not nfsu1_target.exists():
    print("[*] Downloading NFS Underground 1 intro...")
    tmp = OUTPUT_DIR / "raw_nfsu1.mp4"
    dl_cmd = [
        "C:/Users/HL/AppData/Local/Python/bin/python.exe", "-m", "yt_dlp",
        "-f", "bestvideo[height<=1080][ext=mp4]/best[ext=mp4]/best",
        "--download-sections", "*00:15-00:35",
        "--force-keyframes-at-cuts",
        "-o", str(tmp),
        "https://www.youtube.com/watch?v=SYufqpWTW7M"
    ]
    subprocess.run(dl_cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if not (tmp.exists() and tmp.stat().st_size > 10000):
        # Fallback full dl
        dl_fb = [
            "C:/Users/HL/AppData/Local/Python/bin/python.exe", "-m", "yt_dlp",
            "-f", "bestvideo[height<=1080][ext=mp4]/best[ext=mp4]/best",
            "-o", str(tmp),
            "https://www.youtube.com/watch?v=SYufqpWTW7M"
        ]
        subprocess.run(dl_fb, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if tmp.exists() and tmp.stat().st_size > 10000:
            cmd = [
                "ffmpeg", "-y", "-ss", "15", "-to", "35", "-i", str(tmp),
                "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-profile:v", "high", "-level", "4.1",
                "-crf", "20", "-maxrate", "3500k", "-bufsize", "7000k",
                "-an", str(nfsu1_target)
            ]
            subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    else:
        cmd = [
            "ffmpeg", "-y", "-i", str(tmp),
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-profile:v", "high", "-level", "4.1",
            "-crf", "20", "-maxrate", "3500k", "-bufsize", "7000k",
            "-an", str(nfsu1_target)
        ]
        subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)

    if tmp.exists():
        try: tmp.unlink()
        except: pass

print(f"[+] NFS Underground 1 ready: {nfsu1_target.exists()} ({nfsu1_target.stat().st_size if nfsu1_target.exists() else 0} bytes)")

# Step 2: Upload to Google Drive
nfsu1_gdrive_id = None
if nfsu1_target.exists() and TOKEN:
    print("[*] Uploading NFS Underground 1 to Google Drive...")
    try:
        ures = GoogleDriveClient.upload_file(nfsu1_target, FOLDER_ID, TOKEN)
        nfsu1_gdrive_id = ures.get("id")
        print(f"[+] Uploaded to Drive: ID {nfsu1_gdrive_id}")
    except Exception as e:
        print(f"[-] Drive upload error: {e}")

# Step 3: Load catalog and link all NFS IDs
cat_path = Path("catalog/data/catalog.json")
with open(cat_path, "r", encoding="utf-8") as f:
    cat = json.load(f)

# Find variant URLs for NFSU2, MW, Carbon
url_ug2 = None
url_mw = None
url_carb = None
url_ug1 = f"https://drive.google.com/uc?export=download&id={nfsu1_gdrive_id}" if nfsu1_gdrive_id else None

for g in cat.get("games", []):
    for v in g.get("variants", []):
        vname = v.get("name", "").lower()
        if "underground 2" in vname:
            url_ug2 = v.get("url")
        elif "most wanted" in vname:
            url_mw = v.get("url")
        elif "carbon" in vname:
            url_carb = v.get("url")

print(f"Found URLs: UG1={url_ug1}, UG2={url_ug2}, MW={url_mw}, Carbon={url_carb}")

# Rename existing unnamed games
RENAME_MAP = {
    "0100C0D400000000": "Call of Duty 4: Modern Warfare",
    "0100366014020000": "Grand Theft Auto: Vice City",
    "0100434152420000": "Need for Speed: Carbon (CARB)",
    "0100554732000000": "Need for Speed: Underground 2 (UG2)",
    "01004D5700000000": "Need for Speed: Most Wanted 2005 (MW)",
    "01004E46534D0000": "Need for Speed: Most Wanted (2005)",
    "0100B61019056000": "Vampire Survivors",
    "01005A4F4F540000": "The Legend of Zelda: Ocarina of Time",
    "01000670068D0000": "Terraria",
    "0100000000000001": "Need for Speed: Most Wanted (Homebrew Port)",
    "0100000000000005": "Need for Speed: Carbon (Homebrew Port)"
}

for g in cat.get("games", []):
    tid = g.get("titleId", "").upper()
    if tid in RENAME_MAP:
        g["title"] = RENAME_MAP[tid]

# Now ensure alias entries exist for all common homebrew IDs for NFS!
def ensure_game(tid, title, variant_name, url):
    if not url:
        return
    existing = [g for g in cat.get("games", []) if g.get("titleId", "").upper() == tid.upper()]
    if existing:
        g = existing[0]
        g["title"] = title
        if not g.get("variants"):
            g["variants"].append({
                "id": "var-standard",
                "name": variant_name,
                "style": "Animated Art",
                "version": "1.0",
                "url": url,
                "previewUrl": url.replace("uc?export=download&id=", "thumbnail?id=") + "&sz=w640",
                "sizeBytes": 5000000,
                "sha256": "",
                "durationSec": 20.0,
                "author": "Holy3holy-dev",
                "codec": "h264",
                "width": 1280,
                "height": 720,
                "fps": 30.0,
                "hasAudio": False
            })
    else:
        cat["games"].append({
            "titleId": tid,
            "title": title,
            "publisher": "EA / Homebrew",
            "variants": [{
                "id": "var-standard",
                "name": variant_name,
                "style": "Animated Art",
                "version": "1.0",
                "url": url,
                "previewUrl": url.replace("uc?export=download&id=", "thumbnail?id=") + "&sz=w640",
                "sizeBytes": 5000000,
                "sha256": "",
                "durationSec": 20.0,
                "author": "Holy3holy-dev",
                "codec": "h264",
                "width": 1280,
                "height": 720,
                "fps": 30.0,
                "hasAudio": False
            }]
        })
        print(f"[+] Added alias game: {tid} -> {title}")

# Underground 1
ensure_game("0100554731000000", "Need for Speed: Underground (UG1)", "NFS Underground 1 Intro", url_ug1 or url_ug2)
ensure_game("0100000000000002", "Need for Speed: Underground (Homebrew)", "NFS Underground 1 Intro", url_ug1 or url_ug2)
ensure_game("01004E4653550000", "Need for Speed: Underground (NFSU)", "NFS Underground 1 Intro", url_ug1 or url_ug2)

# Underground 2
ensure_game("0100554732000000", "Need for Speed: Underground 2 (UG2)", "NFS Underground 2", url_ug2)
ensure_game("0100000000000003", "Need for Speed: Underground 2 (Homebrew)", "NFS Underground 2", url_ug2)

# Most Wanted
ensure_game("01004D5700000000", "Need for Speed: Most Wanted (MW)", "NFS Most Wanted", url_mw)
ensure_game("01004E46534D0000", "Need for Speed: Most Wanted (2005)", "NFS Most Wanted", url_mw)
ensure_game("0100000000000004", "Need for Speed: Most Wanted (Homebrew)", "NFS Most Wanted", url_mw)
ensure_game("0100000000000001", "Need for Speed: Most Wanted (Homebrew Port)", "NFS Most Wanted", url_mw)

# Carbon
ensure_game("0100434152420000", "Need for Speed: Carbon (CARB)", "NFS Carbon", url_carb)
ensure_game("0100000000000000", "Need for Speed: Carbon (antoxa2584x)", "NFS Carbon", url_carb)

# Save updated catalog
cat["totalGames"] = len(cat["games"])
cat["totalVariants"] = sum(len(g.get("variants", [])) for g in cat["games"])

with open(cat_path, "w", encoding="utf-8") as f:
    json.dump(cat, f, ensure_ascii=False, indent=2)

print(f"\n[OK] Catalog updated: {cat['totalGames']} games, {cat['totalVariants']} variants")

# Push to GitHub
gh_token, _ = GitHubPublisher.get_stored_credentials()
print(f"[*] Pushing to GitHub (token {gh_token[:6]}...)...")
GoogleDriveHelper.sync_catalog_to_github(
    catalog_path=cat_path,
    token=gh_token,
    progress_cb=print
)
print("✅ Successfully updated and synced with GitHub!")
