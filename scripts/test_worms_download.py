import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import json

with open("catalog/data/catalog.json", "r", encoding="utf-8") as f:
    cat = json.load(f)

for g in cat.get("games", []):
    if g.get("titleId", "").upper() == "01001AE005166000":
        print("Worms variants:", len(g.get("variants", [])))
        var_url = g["variants"][0]["url"]
        print("URL:", var_url)
        dest = Path("tmp/batch_hq_icons/worms_full.mp4")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(var_url, stream=True, timeout=15) as r:
            with open(dest, "wb") as f_out:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f_out.write(chunk)
        print("Full downloaded size:", dest.stat().st_size)
        break
