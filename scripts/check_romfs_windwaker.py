import json

with open("downloader/romfs/catalog.json", "r", encoding="utf-8") as f:
    romfs_catalog = json.load(f)

print("romfs games count:", len(romfs_catalog.get("games", [])))

target_id = "01CAA550FBC40000"
for g in romfs_catalog.get("games", []):
    tid = g.get("titleId", "").upper()
    title = g.get("title", "")
    if tid == target_id or "wind" in title.lower() or "waker" in title.lower():
        print("FOUND IN ROMFS:")
        print(f"Title ID: {tid}")
        print(f"Title: {title}")
        print(f"Variants count: {len(g.get('variants', []))}")
        for v in g.get("variants", []):
            print(f"  Variant id={v.get('id')}, name={v.get('name')}, url={v.get('url')}")
