import json
from pathlib import Path

def print_stats(path: Path, name: str):
    if not path.exists():
        print(f"[{name}] File not found: {path}")
        return
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    games = data.get("games", [])
    total_games = len(games)
    total_variants = sum(len(g.get("variants", [])) for g in games)
    games_with_icons = sum(1 for g in games if any(v.get("hasIcon") or v.get("iconUrl") for v in g.get("variants", [])))
    total_icons = sum(sum(1 for v in g.get("variants", []) if v.get("hasIcon") or v.get("iconUrl")) for g in games)
    print(f"=== {name} ===")
    print(f"Игр в каталоге: {total_games}")
    print(f"Всего видеофонов 720p: {total_variants}")
    print(f"Игр с Ultra-HQ видеоиконками 256x256: {games_with_icons}")
    print(f"Всего вариантов видеоиконок: {total_icons}")
    print(f"Дата обновления: {data.get('updatedAt')}\n")

print_stats(Path("catalog/data/catalog.json"), "MAIN CATALOG")
print_stats(Path("catalog/data/catalog_after_dark.json"), "AFTER DARK CATALOG")
