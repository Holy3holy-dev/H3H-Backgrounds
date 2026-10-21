import json

cat = json.load(open('catalog/data/catalog.json', encoding='utf-8'))
for g in cat['games']:
    title_lower = g['title'].lower()
    if 'odyssey' in title_lower or 'mario kart' in title_lower:
        print(f"\nGame: {g['title']} (TID: {g.get('titleId')})")
        for i, v in enumerate(g.get('variants', [])):
            print(f"  Variant {i+1}: {v.get('name')} (id: {v.get('id')})")
            print(f"    URL: {v.get('url')}")
            print(f"    Preview: {v.get('previewUrl')}")
            print(f"    Size: {v.get('sizeBytes')} bytes")
