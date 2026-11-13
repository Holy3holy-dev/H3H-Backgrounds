import json

def is_valid_title_id(tid):
    if len(tid) != 16:
        return False
    return all(c in "0123456789ABCDEFabcdef" for c in tid)

for path in ["catalog/data/catalog.json", "catalog/data/catalog_after_dark.json"]:
    try:
        data = json.load(open(path, "r", encoding="utf-8"))
    except Exception as e:
        print(f"Error reading {path}: {e}")
        continue

    print(f"=== Checking {path} ===")
    seen = {}
    err_count = 0
    for idx, g in enumerate(data.get("games", [])):
        tid = g.get("titleId", "")
        if not is_valid_title_id(tid):
            print(f"INVALID TitleID at #{idx}: '{tid}' in game '{g.get('title')}'")
            err_count += 1
        norm = tid.upper()
        if norm in seen:
            print(f"DUPLICATE TitleID at #{idx}: '{norm}' (first at #{seen[norm]}) game '{g.get('title')}'")
            err_count += 1
        seen[norm] = idx

        for v_idx, v in enumerate(g.get("variants", [])):
            u = v.get("url", "")
            if u and not u.startswith("https://"):
                print(f"INSECURE variant URL at #{idx} var #{v_idx}: '{u}'")
                err_count += 1
            iu = v.get("iconUrl", "")
            if iu and not iu.startswith("https://"):
                print(f"INSECURE icon URL at #{idx} var #{v_idx}: '{iu}'")
                err_count += 1

    print(f"Result for {path}: {err_count} errors across {len(data.get('games', []))} games.")
