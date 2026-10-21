import urllib.request
import re

headers = {'User-Agent': 'Mozilla/5.0'}

queries = [
    'ecchi', 'waifu', 'genshin', 'nier', 'tifa', 'cyberpunk', 'senran', 'honkai', 'nikke', 'stellar blade', 'dead or alive', 'azur lane', 'bikini', 'swimsuit', 'bunny'
]

for q in queries:
    url = f"https://moewalls.com/?s={urllib.parse.quote(q)}"
    req = urllib.request.Request(url, headers=headers)
    try:
        html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
        articles = re.findall(r'<article[^>]*>.*?<a href="([^"]+)"[^>]*rel="bookmark">(.*?)</a>', html, re.DOTALL)
        clean = []
        for u, t in articles:
            title = re.sub('<[^<]+?>', '', t).strip()
            clean.append((title, u))
        print(f"[{q}] -> {len(clean)} results")
        for t, u in clean[:3]:
            print(f"   {t} ({u})")
    except Exception as e:
        print(f"[{q}] -> Error: {e}")
