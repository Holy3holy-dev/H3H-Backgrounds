import json

with open("catalog/data/catalog.json", "r", encoding="utf-8") as f:
    cat = json.load(f)

for g in cat.get("games", []):
    title = g.get("title", "").lower()
    tid = g.get("titleId", "")
    if "most wanted" in title or "need for speed" in title or "hot pursuit" in title:
        print(f"TitleId: {tid} | Title: {g.get('title')} | Variants count: {len(g.get('variants', []))}")
        for v in g.get("variants", []):
            print(f"   * {v.get('id')} | {v.get('name')} | {v.get('url')}")
