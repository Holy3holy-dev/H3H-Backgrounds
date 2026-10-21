import urllib.request
import re

headers = {'User-Agent': 'Mozilla/5.0'}

articles = [
    "https://moewalls.com/anime/2b-in-the-field-of-blue-lilies-nier-automata-live-wallpaper/",
    "https://moewalls.com/games/zelda-ultrahand-tears-of-the-kingdom-live-wallpaper/",
    "https://moewalls.com/games/cereza-bayonetta-live-wallpaper/",
    "https://moewalls.com/anime/makima-controlling-chainsaw-man-y-live-wallpaper/",
    "https://moewalls.com/anime/arlecchino-crimson-moon-genshin-impact-live-wallpaper/",
    "https://moewalls.com/anime/2b-blindfold-nier-automata-live-wallpaper/"
]

for url in articles:
    try:
        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='ignore')
        vids = re.findall(r'<source\s+[^>]*src="([^"]+)"', html)
        posters = re.findall(r'<video[^>]*poster="([^"]+)"', html)
        print(f"Article: {url}")
        print(f"  Vid:    {vids}")
        print(f"  Poster: {posters}")
    except Exception as e:
        print(f"Article: {url} -> ERROR: {e}")
