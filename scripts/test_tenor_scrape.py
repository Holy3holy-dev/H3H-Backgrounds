import urllib.request
import re

url = "https://tenor.com/search/witcher-gifs"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
        mp4s = set(re.findall(r"https://media\.tenor\.com/[^\s\"\'<>]+\.mp4", html))
        gifs = set(re.findall(r"https://media\.tenor\.com/[^\s\"\'<>]+\.gif", html))
        print("Tenor web scrape MP4s:", len(mp4s), "GIFs:", len(gifs))
        for m in list(mp4s)[:3]:
            print("  MP4:", m)
        for g in list(gifs)[:3]:
            print("  GIF:", g)
except Exception as e:
    print("Tenor scrape err:", e)
