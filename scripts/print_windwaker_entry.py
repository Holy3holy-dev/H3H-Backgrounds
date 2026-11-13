import json

with open("catalog/data/catalog.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for g in data.get("games", []):
    if g.get("titleId", "").upper() == "01CAA550FBC40000":
        print(json.dumps(g, indent=2, ensure_ascii=False))
        break
