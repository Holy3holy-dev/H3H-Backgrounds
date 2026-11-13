import json

cat = json.load(open('catalog/data/catalog.json', 'r', encoding='utf-8'))
for q in ['01CAA550FBC40000', 'wind waker', 'zelda', 'зельда']:
    matches = []
    for g in cat.get('games', []):
        t = g.get('title', '').lower()
        tid = g.get('titleId', '').lower()
        if q.lower() in t or q.lower() in tid:
            matches.append((g.get('titleId'), g.get('title'), len(g.get('variants', []))))
    print(f'Query "{q}": found {len(matches)} matches')
    for m in matches[:3]:
        print('  ->', m)
