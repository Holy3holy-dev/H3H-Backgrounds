import json
import copy
from datetime import datetime, timezone

def update_catalog_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    games = data.get("games", [])
    
    # Check if 01FF575748440000 already exists
    exists_switchwaker = any(g.get("titleId", "").upper() == "01FF575748440000" for g in games)
    
    # Find 01CAA550FBC40000
    src_game = None
    for g in games:
        if g.get("titleId", "").upper() == "01CAA550FBC40000":
            src_game = g
            # Fix any replacement chars
            for v in g.get("variants", []):
                v["name"] = v.get("name", "").replace("\ufffd", "★")
            break
            
    if not src_game:
        print(f"[-] Source 01CAA550FBC40000 not found in {filepath}!")
        return False
        
    if not exists_switchwaker:
        # Clone for SwitchWakerHD (01FF575748440000)
        sw_game = copy.deepcopy(src_game)
        sw_game["titleId"] = "01FF575748440000"
        sw_game["title"] = "The Legend of Zelda: The Wind Waker HD"
        sw_game["publisher"] = "Nintendo / SwitchWakerHD"
        
        # Adjust variant IDs so they are distinct
        for idx, v in enumerate(sw_game.get("variants", [])):
            v["id"] = f"var-sw-{idx+1}"
            v["name"] = v.get("name", "").replace("\ufffd", "★")
            
        games.append(sw_game)
        print(f"[+] Added SwitchWakerHD (01FF575748440000) to {filepath}")
    else:
        print(f"[*] 01FF575748440000 already present in {filepath}")
        
    data["totalGames"] = len(games)
    data["totalVariants"] = sum(len(g.get("variants", [])) for g in games)
    data["updatedAt"] = datetime.now(timezone.utc).isoformat()
    data["lastUpdated"] = data["updatedAt"]
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] Saved {filepath} (Total games: {data['totalGames']})")
    return True

update_catalog_file("catalog/data/catalog.json")
update_catalog_file("downloader/romfs/catalog.json")
