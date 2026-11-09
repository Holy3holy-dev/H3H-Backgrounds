import requests, re

url2 = "https://moewalls.com/pixel-art/the-legend-of-zelda-the-wind-waker-pixel-live-wallpaper/"
html = requests.get(url2, headers={"User-Agent": "Mozilla/5.0"}).text
links = re.findall(r'href="([^"]+)"', html) + re.findall(r'src="([^"]+)"', html)
for l in set(links):
    if any(ext in l.lower() for ext in [".mp4", ".webm", ".mkv", "drive", "mega"]):
        print("Media Link:", l)
