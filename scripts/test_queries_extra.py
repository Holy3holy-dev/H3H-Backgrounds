import urllib.request
import re

headers = {'User-Agent': 'Mozilla/5.0'}
for q in ['purah', 'zelda', 'dead or alive', 'senran', 'genshin', 'makima']:
    url = f"https://moewalls.com/?s={urllib.parse.quote(q)}"
    req = urllib.request.Request(url, headers=headers)
    html = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')
    articles = re.findall(r'<article[^>]*>.*?<a href="([^"]+)"[^>]*rel="bookmark">(.*?)</a>', html, re.DOTALL)
    print(f"Query '{q}': {len(articles)} found")
    for u, t in articles[:3]:
        print(f"  - {re.sub('<[^<]+?>', '', t).strip()}: {u}")
