import json

with open("catalog/data/catalog.json", "r", encoding="utf-8") as f:
    data = json.load(f)

games = data.get("games", data) if isinstance(data, dict) else data

print(f"Total games in catalog: {len(games)}")

for g in games:
    gid = str(g.get("titleId", g.get("title_id", ""))).upper()
    name = g.get("name", g.get("title", ""))
    if gid == "01CAA550FBC40000" or "wind waker" in name.lower() or "01CAA550FBC40000" in str(g):
        print("--- MATCH ---")
        print(f"Title ID: {gid}")
        print(f"Name: {name}")
        print(f"Keys: {list(g.keys())}")
        print(f"Video URL: {g.get('videoUrl', g.get('video_url', ''))}")
        print(f"Icon URL: {g.get('iconUrl', g.get('icon_url', ''))}")
        print(f"Aliases / Extra: {json.dumps(g, ensure_ascii=False, indent=2)}")
