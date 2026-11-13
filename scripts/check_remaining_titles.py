import json

with open("studio/h3h_studio/data/switch_titles_db.json", "r", encoding="utf-8") as f:
    switch_db = json.load(f)

with open("catalog/data/catalog.json", "r", encoding="utf-8") as f:
    cat = json.load(f)

cat_tids = {g["titleId"].upper() for g in cat.get("games", []) if "titleId" in g}

if isinstance(switch_db, dict):
    all_switch_tids = {k.upper() for k in switch_db.keys()}
elif isinstance(switch_db, list):
    all_switch_tids = {item.get("titleId", item.get("id", "")).upper() for item in switch_db}
else:
    all_switch_tids = set()

already_in_catalog = len(all_switch_tids.intersection(cat_tids))
remaining = len(all_switch_tids) - already_in_catalog

print(f"Total Titles in Switch DB: {len(all_switch_tids)}")
print(f"Already covered in Catalog: {already_in_catalog}")
print(f"Remaining Switch games to cover: {remaining}")
