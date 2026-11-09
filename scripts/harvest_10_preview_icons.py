import sys
import json
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.animated_icons_fetcher import AnimatedIconsFetcher

TOP_GAMES = [
    ("The Witcher 3", "0100E6700C40C000"),
    ("The Legend of Zelda Breath of the Wild", "01007EF00011E000"),
    ("Cyberpunk 2077", "01000A10041EA000"),
    ("Hollow Knight", "01006BB00C6F0000"),
    ("Hades", "0100535012974000"),
    ("Super Mario Odyssey", "0100000000010000"),
    ("Metroid Dread", "010093801237C000"),
    ("NieR Automata", "0100573014B40000"),
    ("Dead Cells", "0100646009F0E000"),
    ("DOOM Eternal", "0100CF5010EE8000")
]

preview_dir = Path("tmp/icon_showcase")
preview_dir.mkdir(parents=True, exist_ok=True)

findings = []

for gname, tid in TOP_GAMES:
    print(f"\n[*] Searching animations for: {gname} [{tid}]")
    res = AnimatedIconsFetcher.search_all(gname)
    print(f"    Found {len(res)} candidate animations")
    
    # Filter or pick the best 2-3 candidates
    best = []
    # Prefer Steam Points or high quality SteamGridDB
    for it in res:
        # Avoid huge non-square items if possible, or pick top
        best.append(it)
        if len(best) >= 3:
            break
            
    findings.append({
        "game": gname,
        "title_id": tid,
        "total_found": len(res),
        "candidates": best
    })

out_json = preview_dir / "candidates.json"
out_json.write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n[+] Saved candidates to {out_json}")
