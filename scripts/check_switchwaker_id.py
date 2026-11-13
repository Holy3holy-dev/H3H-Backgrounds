import json

target = "01FF575748440000"

for p in ["catalog/data/catalog.json", "downloader/romfs/catalog.json"]:
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    found = False
    for g in data.get("games", []):
        if g.get("titleId", "").upper() == target:
            print(f"FOUND {target} in {p}: {g.get('title')}")
            found = True
            break
    if not found:
        print(f"NOT FOUND {target} in {p}!")
