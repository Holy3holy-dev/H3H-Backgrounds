import urllib.request
import urllib.parse
import re

headers = {'User-Agent': 'Mozilla/5.0'}
for q in ['metal gear rising', 'jetstream sam', 'raiden metal gear', 'senator armstrong']:
    url = f'https://moewalls.com/?s={urllib.parse.quote_plus(q)}'
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode('utf-8')
        links = re.findall(r'<a\s+href="([^"]+)"\s+rel="bookmark">([^<]+)</a>', html)
        if not links:
            links = re.findall(r'<h2 class="entry-title"><a href="([^"]+)">([^<]+)</a>', html)
        print(f"=== Query: {q} (Found {len(links)}) ===")
        for href, title in links[:6]:
            print(f"  {title.strip()} -> {href}")
    except Exception as e:
        print(f"Query {q} error: {e}")
