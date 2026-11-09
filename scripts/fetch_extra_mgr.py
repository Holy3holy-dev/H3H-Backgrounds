import sys
import os
import re
import uuid
import json
import urllib.request
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "studio")

from tg_bot.bot import get_gdrive_auth, transcode_to_switch_720p, append_variant_to_catalog, push_catalog_to_github
from h3h_studio.core.google_drive import GoogleDriveClient

page_url = "https://moewalls.com/games/raiden-girl-metal-gear-live-wallpaper/"
req = urllib.request.Request(page_url, headers={"User-Agent": "Mozilla/5.0"})

with urllib.request.urlopen(req, timeout=15) as resp:
    html = resp.read().decode("utf-8")

matches = re.findall(r'<source\s+src="([^"]+\.webm)"', html)
if not matches:
    matches = re.findall(r'<source\s+src="([^"]+\.mp4)"', html)

if not matches:
    print("[!] No video stream found on page")
    sys.exit(0)

video_url = matches[0]
if video_url.startswith("/"):
    video_url = f"https://moewalls.com{video_url}"
print(f"[*] Found video stream: {video_url}")

tmp_dir = Path("tmp/mgr_harvest")
tmp_dir.mkdir(parents=True, exist_ok=True)

raw_file = tmp_dir / "raiden_girl_raw.webm"
req_vid = urllib.request.Request(video_url, headers={"User-Agent": "Mozilla/5.0", "Referer": page_url})

print("[*] Downloading video...")
with urllib.request.urlopen(req_vid, timeout=30) as r, open(raw_file, "wb") as f:
    f.write(r.read())

print(f"[+] Downloaded raw video ({raw_file.stat().st_size} bytes)")

out_mp4 = tmp_dir / "05988A343C507000_raiden_girl.mp4"
out_thumb = tmp_dir / "05988A343C507000_raiden_girl.jpg"

print("[*] Transcoding to Switch 720p 30fps H264...")
transcode_to_switch_720p(raw_file, out_mp4, out_thumb, codec="h264")
print(f"[+] Transcoded Switch video ({out_mp4.stat().st_size} bytes)")

access_tok, folder_id = get_gdrive_auth("standard")
print("[*] Uploading to Google Drive...")
upload_res = GoogleDriveClient.upload_file(
    file_path=out_mp4,
    folder_id=folder_id,
    token=access_tok
)

direct_url = upload_res.get("directUrl")
preview_url = upload_res.get("previewUrl")
file_size = upload_res.get("size", out_mp4.stat().st_size)
print(f"[+] Uploaded to Google Drive! URL: {direct_url}")

# Register in catalog.json for 05988A343C507000
cat_main_rel = Path("catalog/data/catalog.json")
cat_ad_rel = Path("catalog/data/catalog_after_dark.json")

new_var_main = append_variant_to_catalog(
    catalog_rel=cat_main_rel,
    title_id="05988A343C507000",
    game_name="Metal Gear Rising: Revengeance",
    variant_name="Raiden Cybernetic Katana (Rule of Nature)",
    author="@MoeWalls",
    category="standard",
    direct_url=direct_url,
    preview_url=preview_url,
    file_size=file_size,
    codec="h264"
)

new_var_ad = append_variant_to_catalog(
    catalog_rel=cat_ad_rel,
    title_id="05988A343C507000",
    game_name="Metal Gear Rising: Revengeance",
    variant_name="Raiden Cybernetic Katana (Rule of Nature)",
    author="@MoeWalls",
    category="after_dark",
    direct_url=direct_url,
    preview_url=preview_url,
    file_size=file_size,
    codec="h264"
)

print("[+] Successfully added 6th variant to both catalogs!")
