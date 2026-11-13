import json
import re

def is_valid_title_id(tid):
    if len(tid) != 16:
        return False
    for c in tid:
        if c not in "0123456789abcdefABCDEF":
            return False
    return True

with open("catalog/data/catalog.json", "r", encoding="utf-8") as f:
    data = json.load(f)

if not isinstance(data, dict) or "games" not in data or not isinstance(data["games"], list):
    print("FATAL: Root is not dict with 'games' list!")
    exit(1)

parsed_index = {}
errors = []

for idx, j_game in enumerate(data["games"]):
    if not isinstance(j_game, dict):
        errors.append(f"Game index {idx} is not an object")
        continue
    
    raw_tid = j_game.get("titleId", "")
    if not is_valid_title_id(raw_tid):
        errors.append(f"Invalid Title ID at idx {idx}: '{raw_tid}' (Game: {j_game.get('title', 'Unknown')})")
        continue
    
    norm_tid = raw_tid.upper()
    if norm_tid in parsed_index:
        prev_idx = parsed_index[norm_tid]
        errors.append(f"Duplicate Title ID {norm_tid}: idx {idx} ('{j_game.get('title')}') vs idx {prev_idx} ('{data['games'][prev_idx].get('title')}')")
    else:
        parsed_index[norm_tid] = idx
    
    variants = j_game.get("variants", [])
    if isinstance(variants, list):
        for v_idx, v in enumerate(variants):
            if not isinstance(v, dict):
                errors.append(f"Game {norm_tid} variant {v_idx} is not dict")
                continue
            url = v.get("url", "")
            icon_url = v.get("iconUrl", "")
            if url and not url.startswith("https://"):
                errors.append(f"Game {norm_tid} variant {v_idx} insecure url: '{url}'")
            if icon_url and not icon_url.startswith("https://"):
                errors.append(f"Game {norm_tid} variant {v_idx} insecure iconUrl: '{icon_url}'")

print(f"Total games: {len(data['games'])}")
print(f"Total errors found: {len(errors)}")
for e in errors[:50]:
    print("  ERROR:", e)
