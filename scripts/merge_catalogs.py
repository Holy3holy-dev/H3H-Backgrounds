import json
import subprocess
from pathlib import Path

# Get catalog from HEAD
head_cat_bytes = subprocess.run(["git", "show", "HEAD:catalog/data/catalog.json"], capture_output=True, check=True).stdout
head_cat = json.loads(head_cat_bytes.decode('utf-8'))

# Get catalog from origin/main (MERGE_HEAD)
remote_cat_bytes = subprocess.run(["git", "show", "origin/main:catalog/data/catalog.json"], capture_output=True, check=True).stdout
remote_cat = json.loads(remote_cat_bytes.decode('utf-8'))

merged_games = {}

# 1. Add all from remote
for g in remote_cat.get("games", []):
    tid = g.get("titleId")
    merged_games[tid] = {
        "titleId": tid,
        "title": g.get("title"),
        "publisher": g.get("publisher", "Unknown"),
        "variants": list(g.get("variants", []))
    }

# 2. Add/merge from HEAD (including Metal Gear Rising)
for g in head_cat.get("games", []):
    tid = g.get("titleId")
    if tid not in merged_games:
        merged_games[tid] = {
            "titleId": tid,
            "title": g.get("title"),
            "publisher": g.get("publisher", "Unknown"),
            "variants": list(g.get("variants", []))
        }
    else:
        existing_vids = {v.get("id") for v in merged_games[tid]["variants"]}
        for v in g.get("variants", []):
            if v.get("id") not in existing_vids:
                merged_games[tid]["variants"].append(v)
                existing_vids.add(v.get("id"))

result = {
    "schemaVersion": 1,
    "updatedAt": remote_cat.get("updatedAt", ""),
    "games": list(merged_games.values())
}

# Write resolved file
out_p = Path("catalog/data/catalog.json")
out_p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[+] Successfully merged catalog! Total games: {len(result['games'])}")
