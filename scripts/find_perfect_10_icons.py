import sys
import json
import re
import urllib.request
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.animated_icons_fetcher import AnimatedIconsFetcher

GAMES = [
    ("Witcher 3 Geralt", "0100E6700C40C000", "The Witcher 3: Wild Hunt"),
    ("Zelda Tears of the Kingdom", "0100F2C0115B6000", "The Legend of Zelda: TotK"),
    ("Super Smash Bros Ultimate", "01006A800016E000", "Super Smash Bros. Ultimate"),
    ("Persona 5 Royal Joker", "01000A10041EA000", "Persona 5 Royal"),
    ("Hollow Knight Knight", "01006BB00C6F0000", "Hollow Knight"),
    ("Hades Zagreus", "0100535012974000", "Hades"),
    ("Mario Odyssey Cappy", "0100000000010000", "Super Mario Odyssey"),
    ("Samus Metroid Dread", "010093801237C000", "Metroid Dread"),
    ("Nier Automata 2B", "0100573014B40000", "NieR: Automata"),
    ("Dead Cells Beheaded", "0100646009F0E000", "Dead Cells")
]

out = []
for query, tid, clean_name in GAMES:
    print(f"Searching: {query}...")
    res = AnimatedIconsFetcher.search_all(query)
    print(f"  Found {len(res)} results for {query}")
    out.append({
        "game": clean_name,
        "query": query,
        "title_id": tid,
        "results": res[:5]
    })

Path("tmp/perfect_10.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print("\n[+] Saved to tmp/perfect_10.json")
