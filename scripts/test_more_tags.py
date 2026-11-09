import urllib.request
import re

tags = [
    'bikini', 'swimsuit', 'beach', 'bunny', 'maid', 'hot', 'legs', 'dress',
    'gothic', 'elf', 'demon', 'vampire', 'genshin-impact', 'honkai-star-rail',
    'blue-archive', 'cyberpunk', 'overlord', 'konosuba', 'hololive',
    'summer', 'school-uniform', 'flowers', 'rain', 'night', 'water', 'city'
]

headers = {'User-Agent': 'Mozilla/5.0'}
for t in tags:
    url = f'https://moewalls.com/tag/{t}/'
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            articles = re.findall(r'<article[^>]*>.*?<a href="([^"]+)"[^>]*rel="bookmark">(.*?)</a>', html, re.DOTALL)
            print(f'tag:{t} -> {len(articles)} wallpapers on p.1')
    except Exception as e:
        print(f'tag:{t} -> error ({e})')
