import json
import urllib.request
import sys

API_KEY = "4200e73768d97fa592e9d9b7eed012fb"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "User-Agent": "H3H-Studio/1.0"
}

def search_game(term):
    enc = urllib.parse.quote(term)
    url = f"https://www.steamgriddb.com/api/v2/search/autocomplete/{enc}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def get_heroes(game_id, animated=True):
    param = "?types=animated" if animated else ""
    url = f"https://www.steamgriddb.com/api/v2/heroes/game/{game_id}{param}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def main():
    import urllib.parse
    test_games = ["The Witcher 3", "Hollow Knight", "Persona 5 Royal", "Doom Eternal", "Dead Cells"]
    for tg in test_games:
        print(f"\n[*] Searching: {tg}...")
        res = search_game(tg)
        if res.get("success") and res.get("data"):
            first = res["data"][0]
            gid = first["id"]
            name = first["name"]
            print(f"  -> Found: {name} (ID: {gid})")
            heroes = get_heroes(gid, animated=True)
            h_data = heroes.get("data", [])
            print(f"  -> Animated Heroes available: {len(h_data)}")
            for h in h_data[:2]:
                print(f"     [Hero] {h.get('url')} | {h.get('mime')} | {h.get('width')}x{h.get('height')}")
        else:
            print("  -> No results")

if __name__ == "__main__":
    main()
