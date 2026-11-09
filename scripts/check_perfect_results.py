import json
from pathlib import Path

data = json.loads(Path("tmp/perfect_10.json").read_text(encoding="utf-8"))
for item in data:
    g = item["game"]
    res = item["results"]
    print(f"\n=== {g} ({len(res)} results) ===")
    for r in res[:3]:
        src = r.get("source_label")
        title = r.get("title")
        fmt = r.get("format")
        url = r.get("url")
        print(f"  * [{src}] {title} ({fmt})")
        print(f"    URL: {url}")
