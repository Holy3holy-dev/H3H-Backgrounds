import subprocess
import json

p = subprocess.Popen(['git', 'show', 'origin/main:catalog/data/catalog.json'], stdout=subprocess.PIPE)
data = json.load(p.stdout)
seen = {}
errors = 0
for idx, g in enumerate(data.get('games', [])):
    tid = g.get('titleId', '')
    if len(tid) != 16 or not all(c in '0123456789ABCDEFabcdef' for c in tid):
        print(f"INVALID TitleID at #{idx}: {tid} - {g.get('title')}")
        errors += 1
    norm = tid.upper()
    if norm in seen:
        print(f"DUPLICATE TitleID at #{idx}: {norm} (first #{seen[norm]}) - {g.get('title')}")
        errors += 1
    seen[norm] = idx
    for vi, v in enumerate(g.get('variants', [])):
        u = v.get('url', '')
        if u and not u.startswith('https://'):
            print(f"INSECURE URL #{idx} #{vi}: {u}")
            errors += 1
        iu = v.get('iconUrl', '')
        if iu and not iu.startswith('https://'):
            print(f"INSECURE ICON URL #{idx} #{vi}: {iu}")
            errors += 1
print(f"Total errors in origin/main: {errors}")
