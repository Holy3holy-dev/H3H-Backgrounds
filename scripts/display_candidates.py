import json
from pathlib import Path

data = json.loads(Path("tmp/icon_showcase/candidates.json").read_text(encoding="utf-8"))
for item in data:
    g = item["game"]
    total = item["total_found"]
    print(f"\n=== {g} ({total} found) ===")
    for c in item["candidates"]:
        src = c.get("source_label")
        title = c.get("title")
        fmt = c.get("format")
        url = c.get("url")[:65]
        thumb = c.get("thumb_url")
        print(f"  * [{src}] {title} ({fmt})")
        print(f"    URL: {url}...")
        print(f"    Thumb: {thumb[:65]}...")
