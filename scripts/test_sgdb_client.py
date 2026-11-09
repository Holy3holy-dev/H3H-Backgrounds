import sys
from pathlib import Path

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.steamgriddb import SteamGridDBClient

client = SteamGridDBClient()
for test_game in ["Breath of the Wild", "Hollow Knight", "Witcher 3", "Cyberpunk 2077"]:
    games = client.search_game(test_game)
    if not games:
        continue
    g = games[0]
    gid = g["id"]
    gname = g["name"]
    print(f"\nGame: {gname} (ID: {gid})")
    
    # Check icons:
    url_icons = f"https://www.steamgriddb.com/api/v2/icons/game/{gid}?types=animated"
    data_icons = client._fetch_json_with_retry(url_icons)
    icons = data_icons.get("data", []) if data_icons else []
    print(f"  - Animated Icons: {len(icons)}")
    for ic in icons[:2]:
        print(f"    * Icon ({ic.get('mime')}): {ic.get('url')}")

    # Check grids:
    grids = client.get_animated_grids(gid)
    print(f"  - Animated Grids: {len(grids)}")
    for gr in grids[:2]:
        print(f"    * Grid ({gr.get('mime')}): {gr.get('url')}")
