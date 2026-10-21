import json
from pathlib import Path

def analyze(path_str):
    p = Path(path_str)
    if not p.exists():
        print(f"File not found: {path_str}")
        return
    data = json.loads(p.read_text(encoding="utf-8"))
    games = data.get("games", [])
    total_variants = sum(len(g.get("variants", [])) for g in games)
    
    print(f"\n==========================================")
    print(f"Каталог: {p.name}")
    print(f"Игр в каталоге: {len(games)}")
    print(f"Всего фонов/вариантов: {total_variants}")
    print(f"==========================================")
    
    by_source = {}
    by_author = {}
    
    for g in games:
        for v in g.get("variants", []):
            auth = v.get("author", "Не указан")
            name = v.get("name", "")
            url = v.get("videoUrl", "")
            
            by_author[auth] = by_author.get(auth, 0) + 1
            
            src = "Прямая заливка / Harvester"
            if "MoeWalls" in auth or "moewalls" in name.lower() or "moewalls" in url:
                src = "MoeWalls (Живые обои)"
            elif "SteamGridDB" in auth or "steamgriddb" in name.lower():
                src = "SteamGridDB (Анимированные сетки)"
            elif "Wallpaper Engine" in auth or "workshop" in auth.lower() or "Steam Workshop" in auth:
                src = "Steam Workshop / Wallpaper Engine"
            elif "4IFIR" in auth:
                src = "4IFIR Community"
            elif "H3H" in auth or "Official" in auth:
                src = "H3H / Официальные"
            by_source[src] = by_source.get(src, 0) + 1
            
    print("\nРазбивка по источникам:")
    for s, count in sorted(by_source.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {s}: {count} фонов")
        
    print("\nТоп авторов / тегов:")
    for a, count in sorted(by_author.items(), key=lambda x: x[1], reverse=True)[:8]:
        print(f"  • {a}: {count} фонов")

analyze("catalog/data/catalog.json")
analyze("catalog/data/catalog_after_dark.json")

# Check harvest logs
print("\n==========================================")
print("Логи автоматического парсера (Video Harvest Logs):")
print("==========================================")
for log_file in ["catalog/data/video_harvest_log_main.json", "catalog/data/video_harvest_log_after_dark.json"]:
    lp = Path(log_file)
    if lp.exists():
        data = json.loads(lp.read_text(encoding="utf-8"))
        print(f"  • {lp.name}: {len(data)} успешно обработанных записей")
