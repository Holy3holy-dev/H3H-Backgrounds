import urllib.request
import re
import json

print("Testing SteamGridDB web search...")
url = "https://www.steamgriddb.com/search/autocomplete/zelda"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
try:
    with urllib.request.urlopen(req) as resp:
        print("Autocomplete:", resp.read().decode()[:300])
except Exception as e:
    print("Autocomplete err:", e)

# Test search page
search_url = "https://www.steamgriddb.com/search/grids?term=Zelda"
req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
try:
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode()
        print("Search page status 200, length:", len(html))
        # Find games
        games = re.findall(r'href="/game/(\d+)"[^>]*>([^<]+)</a>', html)
        print("Found games:", len(games))
        for gid, gname in games[:5]:
            print(f"  - {gname.strip()} (ID: {gid})")
except Exception as e:
    print("Search err:", e)
