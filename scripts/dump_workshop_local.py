import os
import json
from pathlib import Path

root = Path(r"E:\SteamLibrary\steamapps\workshop\content\431960")
items = []

for d in root.iterdir():
    if not d.is_dir():
        continue
    p = d / "project.json"
    if not p.exists():
        continue
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        title = data.get("title", "")
        rating = data.get("contentrating", "")
        tags = data.get("tags", [])
        vids = [f.name for f in d.iterdir() if f.suffix.lower() in [".mp4", ".webm"]]
        items.append({
            "id": d.name,
            "title": title,
            "rating": rating,
            "tags": tags,
            "has_video": len(vids) > 0,
            "vid_name": vids[0] if vids else None
        })
    except Exception:
        pass

print(f"Total workshop items found: {len(items)}")
items_with_vid = [i for i in items if i["has_video"]]
print(f"Items with video: {len(items_with_vid)}")

# Output summary by title
with open("tmp_workshop_scan.txt", "w", encoding="utf-8") as f:
    for i in items:
        f.write(f"[{i['id']}] Rating: {i['rating']} | Vid: {i['vid_name']} | Title: {i['title']} | Tags: {','.join(i['tags'])}\n")

print("Saved report to tmp_workshop_scan.txt")
