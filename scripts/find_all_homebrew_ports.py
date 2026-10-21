import json
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('studio/h3h_studio/data/switch_titles_db.json', 'r', encoding='utf-8') as f:
    db = json.load(f)

keywords = [
    'need for speed', 'nfs', 'underground', 'most wanted', 'carbon',
    'max payne', 'gta', 'half-life', 'fallout', 'diablo', 'mario 64',
    'zelda', 'sonic', 'tomb raider', 'heroes of might', 'simpsons',
    'bloodborne', 'god of war', 'silent hill', 'postal', 'openlara',
    'openmw', 'morrowind', 'xash', 'devilution', 'am2r'
]

print("=== Matching Titles in Database ===")
for x in db:
    t = x.get('title', '').lower()
    for kw in keywords:
        if kw in t:
            print(f"[{x.get('titleId')}] {x.get('title')} ({x.get('format')}) by {x.get('publisher')}")
            break
