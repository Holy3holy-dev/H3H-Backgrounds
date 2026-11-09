import sys
import os
import json
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "studio")

from tg_bot.bot import get_gdrive_auth
from tg_bot.config import GDRIVE_ICONS_FOLDER_ID
from h3h_studio.core.google_drive import GoogleDriveClient

tok, root_folder_id = get_gdrive_auth("standard")
icons_folder_id = GDRIVE_ICONS_FOLDER_ID

cover_path = Path("tmp/4ifir_video_icons_sample/recordings/covers/010090F012916000.mp4")
icon_path = Path("tmp/4ifir_video_icons_sample/recordings/icons/010090F012916000.mp4")

print(f"[*] Uploading Ghostrunner Cover ({cover_path.stat().st_size} bytes) to {root_folder_id}...")
cover_res = GoogleDriveClient.upload_file(
    file_path=cover_path,
    folder_id=root_folder_id,
    token=tok
)
cover_url = cover_res.get("directUrl")
cover_preview = cover_res.get("previewUrl")
print(f"[+] Cover uploaded: {cover_url}")

print(f"[*] Uploading Ghostrunner Video Icon ({icon_path.stat().st_size} bytes) to {icons_folder_id}...")
icon_res = GoogleDriveClient.upload_file(
    file_path=icon_path,
    folder_id=icons_folder_id,
    token=tok
)
icon_url = icon_res.get("directUrl")
print(f"[+] Icon uploaded: {icon_url}")

# Register in catalog.json
cat_path = Path("catalog/data/catalog.json")
cat_data = json.loads(cat_path.read_text(encoding="utf-8"))

game_entry = None
for g in cat_data.get("games", []):
    if g.get("titleId") == "010090F012916000":
        game_entry = g
        break

if not game_entry:
    game_entry = {
        "titleId": "010090F012916000",
        "title": "Ghostrunner",
        "publisher": "505 Games",
        "variants": []
    }
    cat_data["games"].append(game_entry)

new_var = {
    "id": "var-gh-010090f0-pack",
    "name": "Ghostrunner Neon Jack (Cover + Video Icon)",
    "style": "4IFIR Dynamic Pack",
    "version": "1.0",
    "url": cover_url,
    "previewUrl": cover_preview,
    "sizeBytes": cover_path.stat().st_size,
    "sha256": "",
    "durationSec": 8.0,
    "author": "@4IFIR",
    "codec": "h264",
    "width": 1280,
    "height": 720,
    "fps": 24.0,
    "hasAudio": True,
    "hasIcon": True,
    "iconUrl": icon_url,
    "iconSizeBytes": icon_path.stat().st_size,
    "iconCodec": "hevc",
    "iconWidth": 256,
    "iconHeight": 256,
    "notes": "Official 4IFIR Dynamic Theme Pack: 720p Video Background + 256x256 HEVC Animated Tile Icon"
}

game_entry["variants"].insert(0, new_var)

cat_data["totalGames"] = len(cat_data["games"])
cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in cat_data["games"])
cat_path.write_text(json.dumps(cat_data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"[+] catalog.json updated! Total games: {cat_data['totalGames']}, variants: {cat_data['totalVariants']}")
