import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.github_publisher import GitHubPublisher
from h3h_studio.core.google_drive import GoogleDriveHelper

cat_path = Path("catalog/data/catalog.json")
with open(cat_path, "r", encoding="utf-8") as f:
    cat = json.load(f)

# The user's exact Title IDs from the photo:
# Need for Speed Underground 1: 05DDE5B45EF3E000
# Need for Speed Most Wanted: 03DB18EF71F2C000

# Get existing URLs for NFSU1 and NFSMW
url_ug1 = "https://drive.google.com/uc?export=download&id=14dK76hI0buCZ5pvSFwdG9nRJEzj4DW3o"
url_mw = "https://drive.google.com/uc?export=download&id=1FsdxfgiWtZn5FZULpVsGXxmBMcK4IE4_"

# Verify from catalog
for g in cat.get("games", []):
    for v in g.get("variants", []):
        vname = v.get("name", "").lower()
        if "underground 1" in vname or "underground" in vname:
            if v.get("url"): url_ug1 = v.get("url")
        elif "most wanted" in vname:
            if v.get("url"): url_mw = v.get("url")

print(f"Using URLs:\n  UG1: {url_ug1}\n  MW: {url_mw}")

def add_or_update(tid, title, var_name, url):
    for g in cat.get("games", []):
        if g.get("titleId", "").upper() == tid.upper():
            g["title"] = title
            g["variants"] = [{
                "id": "var-standard",
                "name": var_name,
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
            print(f"[UPDATED] {tid} -> {title}")
            return
    
    # Add new
    cat["games"].append({
        "titleId": tid.upper(),
        "title": title,
        "publisher": "Electronic Arts",
        "variants": [{
            "id": "var-standard",
            "name": var_name,
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
    print(f"[ADDED] {tid} -> {title}")

# Add user's exact Title IDs
add_or_update("05DDE5B45EF3E000", "Need for Speed Underground 1", "NFS Underground 1 Intro", url_ug1)
add_or_update("03DB18EF71F2C000", "Need for Speed Most Wanted", "NFS Most Wanted", url_mw)

cat["totalGames"] = len(cat["games"])
cat["totalVariants"] = sum(len(g.get("variants", [])) for g in cat["games"])

with open(cat_path, "w", encoding="utf-8") as f:
    json.dump(cat, f, ensure_ascii=False, indent=2)

print(f"\n[OK] Catalog updated: {cat['totalGames']} games, {cat['totalVariants']} variants")

# Push to GitHub immediately
gh_token, _ = GitHubPublisher.get_stored_credentials()
print(f"[*] Pushing to GitHub (token {gh_token[:6]}...)...")
GoogleDriveHelper.sync_catalog_to_github(
    catalog_path=cat_path,
    token=gh_token,
    progress_cb=print
)
print("✅ Successfully updated catalog on GitHub with user's exact Title IDs!")
