import json

cat = json.load(open('catalog/data/catalog.json', encoding='utf-8'))
codecs = {}
resolutions = {}
sizes = []
zero_sizes = []
for g in cat['games']:
    for v in g.get('variants', []):
        c = v.get('codec', 'unknown')
        codecs[c] = codecs.get(c, 0) + 1
        res = f"{v.get('width', 0)}x{v.get('height', 0)}"
        resolutions[res] = resolutions.get(res, 0) + 1
        sz = v.get('sizeBytes', 0)
        sizes.append((sz, g['title'], v['name'], v.get('url', '')))
        if sz == 0:
            zero_sizes.append((g['title'], v['name'], v.get('url', '')))

print('Codecs distribution:', codecs)
print('Resolutions distribution:', resolutions)
print(f'Total variants with 0 sizeBytes: {len(zero_sizes)}')
sizes.sort(reverse=True)
print('\nTop 10 largest files:')
for s in sizes[:10]:
    print(f'  {s[0]} bytes ({s[0]/(1024*1024):.1f} MB): {s[1]} - {s[2]} | {s[3]}')

print('\nTop 5 zero or smallest files:')
for s in sizes[-5:]:
    print(f'  {s[0]} bytes: {s[1]} - {s[2]} | {s[3]}')
