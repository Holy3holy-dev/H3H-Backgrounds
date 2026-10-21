from pathlib import Path

p = Path("scripts/auto_harvest_pipeline.py")
text = p.read_text(encoding="utf-8")

old_code = '''        # Save Catalog to disk
        cat_data["totalGames"] = len(cat_data.get("games", []))
        cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in cat_data.get("games", []))
        cat_data["lastUpdated"] = datetime.now(timezone.utc).isoformat()

        with open(CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(cat_data, f, ensure_ascii=False, indent=2)'''

new_code = '''        # Safely re-read catalog from disk and merge so external additions from H3H-Studio are never lost
        if CATALOG_PATH.exists():
            try:
                with open(CATALOG_PATH, "r", encoding="utf-8") as cf:
                    disk_cat = json.load(cf)
                disk_games = {g["titleId"].upper(): g for g in disk_cat.get("games", [])}
                for g in cat_data.get("games", []):
                    tid = g["titleId"].upper()
                    if tid not in disk_games:
                        disk_games[tid] = g
                        disk_cat.setdefault("games", []).append(g)
                    else:
                        existing_urls = {v.get("url") for v in disk_games[tid].get("variants", [])}
                        for v in g.get("variants", []):
                            if v.get("url") not in existing_urls:
                                disk_games[tid].setdefault("variants", []).append(v)
                                existing_urls.add(v.get("url"))
                cat_data = disk_cat
            except Exception as e:
                print(f"[-] Warning during catalog merge: {e}")

        cat_data["totalGames"] = len(cat_data.get("games", []))
        cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in cat_data.get("games", []))
        cat_data["lastUpdated"] = datetime.now(timezone.utc).isoformat()

        with open(CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(cat_data, f, ensure_ascii=False, indent=2)'''

assert old_code in text, "old_code not found in auto_harvest_pipeline.py"
text = text.replace(old_code, new_code)
p.write_text(text, encoding="utf-8")
print("Safe atomic merge successfully added!")
