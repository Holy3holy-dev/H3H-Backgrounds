import json

for filepath in ["catalog/data/catalog.json", "downloader/romfs/catalog.json"]:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"\n--- Checking {filepath} ---")
    games = data.get("games", [])
    for idx, g in enumerate(games):
        title = g.get("title", "")
        tid = g.get("titleId", "")
        # Check if title has strange chars or surrogates
        for c in title:
            if ord(c) > 0xFFFF:
                print(f"Game {idx} [{tid}] has 4-byte unicode (emoji/surrogate): {ord(c):04X} in title: {repr(title)}")
                break
        for v in g.get("variants", []):
            vname = v.get("name", "")
            for c in vname:
                if ord(c) > 0xFFFF:
                    print(f"Game {idx} [{tid}] variant {v.get('id')} has 4-byte unicode: {ord(c):04X} in variant name: {repr(vname)}")
                    break
