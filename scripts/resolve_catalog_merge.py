import json
import subprocess
from pathlib import Path

# Get upstream version (:2) and local version (:3)
cat_path = Path("catalog/data/catalog.json")

proc2 = subprocess.run(["git", "show", ":2:catalog/data/catalog.json"], capture_output=True, text=True, encoding="utf-8")
proc3 = subprocess.run(["git", "show", ":3:catalog/data/catalog.json"], capture_output=True, text=True, encoding="utf-8")

cat2 = json.loads(proc2.stdout)
cat3 = json.loads(proc3.stdout)

# Merge
games_map = {}
for g in cat2.get("games", []):
    tid = g.get("titleId", "").upper()
    if tid:
        games_map[tid] = g

for g in cat3.get("games", []):
    tid = g.get("titleId", "").upper()
    if not tid:
        continue
    if tid not in games_map:
        games_map[tid] = g
    else:
        # Merge variants by ID
        existing_vars = {v.get("id"): v for v in games_map[tid].get("variants", [])}
        for v in g.get("variants", []):
            vid = v.get("id")
            if vid not in existing_vars:
                games_map[tid]["variants"].append(v)
                existing_vars[vid] = v
            else:
                # Update variant fields if new one has better info
                existing_vars[vid].update(v)

merged_games = list(games_map.values())
merged_games.sort(key=lambda x: x.get("title", ""))

total_vars = sum(len(g.get("variants", [])) for g in merged_games)

final_cat = {
    "schemaVersion": 1,
    "updatedAt": "2026-10-20T20:00:00.000000+00:00",
    "totalGames": len(merged_games),
    "totalVariants": total_vars,
    "games": merged_games,
    "lastUpdated": "2026-10-20T20:00:00.000000+00:00"
}

with open(cat_path, "w", encoding="utf-8") as f:
    json.dump(final_cat, f, indent=2, ensure_ascii=False)

print(f"[+] Successfully merged catalog: {len(merged_games)} games, {total_vars} variants.")
