import json
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('catalog/data/catalog.json', 'r', encoding='utf-8') as f:
    cat = json.load(f)

games = cat.get('games', [])
variants_count = sum(len(g.get('variants', [])) for g in games)
print(f"Total Games in Catalog: {len(games)}")
print(f"Total Variants in Catalog: {variants_count}")

sample_checks = [
    '01004D4F4F4E0000', '0100434849410000', '0100505053530000', '01004D4742410000',
    '0100464C59430000', '010000000000100C', '010000000000100A', '0100414D32520000',
    '0100534849500000', '0100325348490000', '01004F504D570000', '01004C4152410000',
    '0100475441340000', '0100435942450000', '0100454C444E0000', '010046414C4C3300'
]

print("\nSample Check of Games:")
for g in games:
    if g.get('titleId') in sample_checks:
        v = g.get('variants', [{}])[0]
        url = v.get('url', '')
        print(f"  [{g.get('titleId')}] {g.get('title')} | {v.get('name')} | {url[:45]}...")
