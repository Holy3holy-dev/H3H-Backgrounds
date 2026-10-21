import json
import subprocess

# Read remote version of catalog.json
remote_data = subprocess.check_output(["git", "show", "FETCH_HEAD:catalog/data/catalog.json"], text=True, encoding="utf-8")
remote_cat = json.loads(remote_data)

# Read HEAD version of catalog.json
head_data = subprocess.check_output(["git", "show", "HEAD:catalog/data/catalog.json"], text=True, encoding="utf-8")
head_cat = json.loads(head_data)

# Create merged games map by titleId
merged_games = {}
for g in head_cat.get("games", []):
    tid = g.get("titleId", "").upper()
    if tid:
        merged_games[tid] = g

for g in remote_cat.get("games", []):
    tid = g.get("titleId", "").upper()
    if not tid:
        continue
    if tid not in merged_games:
        merged_games[tid] = g
    else:
        # If remote has more variants or it's not NFS MW, merge variants
        if "need for speed" not in g.get("title", "").lower() and "most wanted" not in g.get("title", "").lower():
            existing_vars = {v["id"]: v for v in merged_games[tid].get("variants", [])}
            for v in g.get("variants", []):
                existing_vars[v["id"]] = v
            merged_games[tid]["variants"] = list(existing_vars.values())

final_cat = {
    "schemaVersion": 1,
    "updatedAt": "2026-10-21T00:46:00.000000+00:00",
    "totalGames": len(merged_games),
    "totalVariants": sum(len(g.get("variants", [])) for g in merged_games.values()),
    "games": list(merged_games.values()),
    "lastUpdated": "2026-10-21T00:46:00.000000+00:00"
}

with open("catalog/data/catalog.json", "w", encoding="utf-8") as f:
    json.dump(final_cat, f, indent=2, ensure_ascii=False)

print(f"[+] Conflict resolved cleanly! Total games: {final_cat['totalGames']}, variants: {final_cat['totalVariants']}")
