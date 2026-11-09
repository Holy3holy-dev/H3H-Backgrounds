import json
import subprocess

def check_catalog_authors():
    print("=== АНАЛИЗ ЗАГРУЗОК ИЗ TELEGRAM БОТА ===")
    
    # 1. Check Git commits via TG Bot
    res = subprocess.run(
        ["git", "log", "--all", "--grep=via TG Bot", "--format=%h|%ad|%s"],
        capture_output=True, text=True, encoding="utf-8"
    )
    commits = res.stdout.strip().splitlines()
    print(f"\n[+] Всего коммитов через Telegram-бота: {len(commits)}")
    for c in commits:
        parts = c.split("|", 2)
        if len(parts) == 3:
            h, d, msg = parts
            print(f"  • [{d[:16]}] {msg}")

    # 2. Check catalog entries with author info
    for cname, p in [('Standard Catalog', 'catalog/data/catalog.json'), ('After Dark Catalog', 'catalog/data/catalog_after_dark.json')]:
        cat = json.load(open(p, encoding='utf-8'))
        games = cat.get('games', []) if isinstance(cat, dict) else cat
        tg_uploads = []
        for g in games:
            for v in g.get('variants', []):
                author = v.get('author', '')
                if author.startswith('@') or 'tg' in v.get('notes', '').lower() or author in ['extimka', 'HolyL0rd', 'Secondchancetomourn']:
                    tg_uploads.append((g.get('titleId'), g.get('title'), v.get('name'), author, v.get('url')))
        print(f"\n=== {cname}: найдено вариантов от пользователей: {len(tg_uploads)} ===")
        for tid, title, vname, author, url in tg_uploads:
            print(f"  • Автор: @{author.lstrip('@')}")
            print(f"    Игра: {title} (ID: {tid})")
            print(f"    Название фона: '{vname}'")
            print(f"    Ссылка: {url[:60]}...")

if __name__ == "__main__":
    check_catalog_authors()
