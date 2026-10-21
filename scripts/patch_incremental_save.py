from pathlib import Path

p = Path("scripts/auto_harvest_pipeline.py")
text = p.read_text(encoding="utf-8")

old_str = '''            harvested_this_batch += 1
            print(f"  🎉 [{harvested_this_batch}/{batch_size}] Added to catalog: '{clean_title}'")'''

new_str = '''            harvested_this_batch += 1
            print(f"  🎉 [{harvested_this_batch}/{batch_size}] Added to catalog: '{clean_title}'")

            # Incrementally save catalog to disk so no progress is ever lost
            try:
                cat_data["totalGames"] = len(cat_data.get("games", []))
                cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in cat_data.get("games", []))
                cat_data["lastUpdated"] = datetime.now(timezone.utc).isoformat()
                with open(CATALOG_PATH, "w", encoding="utf-8") as f:
                    json.dump(cat_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                pass'''

assert old_str in text, "old_str not found in auto_harvest_pipeline.py"
text = text.replace(old_str, new_str)
p.write_text(text, encoding="utf-8")
print("Incremental catalog saving successfully added!")
