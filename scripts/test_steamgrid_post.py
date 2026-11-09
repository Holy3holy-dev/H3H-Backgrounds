import urllib.request
import json

print("=== 1. Testing GET /api/public/game/5253818 (Zelda BOTW) ===")
# Zelda BOTW ID on SteamGridDB is often 5253818 or similar, let's find ID for Breath of the Wild first:
auto_url = "https://www.steamgriddb.com/api/public/search/autocomplete?term=Breath%20of%20the%20Wild"
req = urllib.request.Request(auto_url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    first = data.get("data", [])[0]
    gid = first.get("id")
    print(f"Game: {first.get('name')} (ID: {gid})")

game_url = f"https://www.steamgriddb.com/api/public/game/{gid}"
req = urllib.request.Request(game_url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as resp:
    g_info = json.loads(resp.read().decode())
    print("Game info keys:", list(g_info.keys()))

print("\n=== 2. Testing POST /api/public/search/assets for icons/animated ===")
search_url = "https://www.steamgriddb.com/api/public/search/assets"
payload = {
    "game_id": gid,
    "asset_type": "icon",
    "page": 1,
    "limit": 20
}
req = urllib.request.Request(
    search_url,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Content-Type": "application/json"
    },
    method="POST"
)
try:
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        items = res.get("data", [])
        print(f"Icons found: {len(items)}")
        for it in items[:5]:
            mime = it.get("mime", "")
            anim = (mime in ["image/webp", "image/apng", "image/gif"]) or it.get("animated")
            print(f"  - Icon ID: {it.get('id')}, anim={anim}, mime={mime}, url={it.get('url')}, thumb={it.get('thumb')}")
except Exception as e:
    print("Search assets err:", e)

# Also test asset_type="grid" (animated square or 600x900)
payload["asset_type"] = "grid"
req = urllib.request.Request(
    search_url,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Content-Type": "application/json"
    },
    method="POST"
)
try:
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        items = res.get("data", [])
        print(f"\nGrids found: {len(items)}")
        for it in items[:5]:
            mime = it.get("mime", "")
            anim = (mime in ["image/webp", "image/apng", "image/gif"]) or it.get("animated")
            print(f"  - Grid ID: {it.get('id')}, anim={anim}, mime={mime}, url={it.get('url')}")
except Exception as e:
    print("Grid search err:", e)
