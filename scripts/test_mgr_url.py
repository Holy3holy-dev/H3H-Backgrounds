import urllib.request
import re

url = "https://moewalls.com/games/cyborg-ninja-raiden-metal-gear-rising-revengeance-live-wallpaper/"
headers = {'User-Agent': 'Mozilla/5.0'}
html = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=10).read().decode('utf-8', errors='ignore')

# Find download links or video tag
videos = re.findall(r'<source[^>]*src="([^"]+\.mp4)"', html)
if not videos:
    videos = re.findall(r'href="([^"]+\.mp4)"', html)
if not videos:
    videos = re.findall(r'data-src="([^"]+\.mp4)"', html)

print("Found video links:", videos)
