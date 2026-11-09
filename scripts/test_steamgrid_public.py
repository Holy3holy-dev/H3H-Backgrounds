import urllib.request
import urllib.parse
import json

print("=== Testing SteamGridDB Public Autocomplete ===")
url = "https://www.steamgriddb.com/api/public/search/autocomplete?term=Zelda"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        print("SteamGridDB public autocomplete status: OK!")
        games = data.get("data", [])
        print("Found games:", len(games))
        for g in games[:5]:
            print(f"  - ID: {g.get('id')}, Name: {g.get('name')}, Types: {g.get('types')}")
            
        if games:
            gid = games[0].get('id')
            # Test getting game icons
            icons_url = f"https://www.steamgriddb.com/api/public/game/{gid}/icons"
            req2 = urllib.request.Request(icons_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req2) as resp2:
                ic_data = json.loads(resp2.read().decode())
                print(f"\nIcons for {games[0].get('name')}:", len(ic_data.get("data", [])))
                for ic in ic_data.get("data", [])[:5]:
                    mime = ic.get("mime")
                    anim = ic.get("animated") or (mime in ["image/webp", "image/apng", "image/gif"])
                    print(f"  - Icon ID: {ic.get('id')}, anim={anim}, mime={mime}, url={ic.get('url')}")
except Exception as e:
    print("SteamGridDB public err:", e)
