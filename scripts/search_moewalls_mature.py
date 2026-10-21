import urllib.request
import urllib.parse
import re
import json

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

queries = [
    'pyra', 'mythra', 'xenoblade',
    'yennefer', 'witcher',
    'persona', 'ann takamaki',
    'fate', 'scathach', 'saber',
    'power chainsaw', 'makima',
    'sugar nikke', 'bunny girl',
    'blue archive swimsuit',
    'a2 nier'
]

results = {}

for q in queries:
    url = f"https://moewalls.com/?s={urllib.parse.quote(q)}"
    req = urllib.request.Request(url, headers=headers)
    try:
        html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')
        articles = re.findall(r'<article[^>]*>.*?<a href="([^"]+)"[^>]*rel="bookmark">(.*?)</a>', html, re.DOTALL)
        clean = []
        for u, t in articles:
            title = re.sub('<[^<]+?>', '', t).strip()
            clean.append({'title': title, 'page_url': u})
        results[q] = clean
        print(f"[{q}] -> {len(clean)} found")
    except Exception as e:
        print(f"[{q}] -> Error: {e}")

with open('tmp_moewalls_search.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print("Saved to tmp_moewalls_search.json")
