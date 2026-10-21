import json
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('studio/h3h_studio/data/switch_titles_db.json', 'r', encoding='utf-8') as f:
    db = json.load(f)

print("=== Search in switch_titles_db.json ===")
for item in db:
    title = item.get('title', '')
    if any(k in title.lower() for k in ['need for speed', 'underground', 'most wanted', 'carbon', 'nfs']):
        print(f"  {item.get('titleId')}: {title}")

print("\n=== Search in catalog.json ===")
with open('catalog/data/catalog.json', 'r', encoding='utf-8') as f:
    cat = json.load(f)

for g in cat.get('games', []):
    title = g.get('title', '')
    if any(k in title.lower() for k in ['need for speed', 'underground', 'most wanted', 'carbon', 'nfs']):
        print(f"  {g.get('titleId')}: {title}")
