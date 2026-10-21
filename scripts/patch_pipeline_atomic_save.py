with open('scripts/auto_harvest_pipeline.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''            if tid in catalog_games:
                existing_game = catalog_games[tid]
                existing_vars = existing_game.setdefault("variants", [])
                # Avoid duplicates
                if not any(v.get("url") == dl_url for v in existing_vars):
                    existing_vars.append(variant_obj)
            else:
                new_game = {
                    "titleId": tid,
                    "title": raw_title,
                    "publisher": entry.get("publisher", "Unknown"),
                    "variants": [variant_obj]
                }
                catalog_games[tid] = new_game
                cat_data.setdefault("games", []).append(new_game)

            harvested_this_batch += 1
            print(f"  🎉 [{harvested_this_batch}/{batch_size}] Added to catalog: '{clean_title}'")

            # Incrementally save catalog to disk so no progress is ever lost
            try:
                cat_data["totalGames"] = len(cat_data.get("games", []))
                cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in cat_data.get("games", []))
                cat_data["lastUpdated"] = datetime.now(timezone.utc).isoformat()
                with open(CATALOG_PATH, "w", encoding="utf-8") as f:
                    json.dump(cat_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                pass

            # Check if batch limit reached
            if harvested_this_batch >= batch_size:
                break

        # Safely re-read catalog from disk and merge so external additions from H3H-Studio are never lost
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

replacement = '''            # Atomically save to catalog on disk without losing any existing variants
            cat_data = atomic_save_game_to_catalog(tid, raw_title, entry.get("publisher", "Unknown"), variant_obj)
            catalog_games = {g["titleId"].upper(): g for g in cat_data.get("games", [])}

            harvested_this_batch += 1
            print(f"  🎉 [{harvested_this_batch}/{batch_size}] Added to catalog: '{clean_title}'")

            # Check if batch limit reached
            if harvested_this_batch >= batch_size:
                break'''

content_norm = content.replace('\r\n', '\n')
target_norm = target.replace('\r\n', '\n')
replacement_norm = replacement.replace('\r\n', '\n')

if target_norm in content_norm:
    new_content = content_norm.replace(target_norm, replacement_norm)
    with open('scripts/auto_harvest_pipeline.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('SUCCESS: auto_harvest_pipeline.py updated!')
else:
    print('Target not matched.')
