import json
from pathlib import Path

cat_path = Path("catalog/data/catalog.json")
cat_data = json.loads(cat_path.read_text(encoding="utf-8"))

# Find MGR entry
mgr_entry = None
for g in cat_data.get("games", []):
    if g.get("titleId") == "01004D4752000000":
        mgr_entry = g
        break

if mgr_entry:
    print(f"Found MGR entry with {len(mgr_entry.get('variants', []))} variants!")
    
    # Check if 05988A343C507000 already exists
    target_entry = None
    for g in cat_data.get("games", []):
        if g.get("titleId") == "05988A343C507000":
            target_entry = g
            break
            
    if not target_entry:
        import copy
        target_entry = copy.deepcopy(mgr_entry)
        target_entry["titleId"] = "05988A343C507000"
        target_entry["title"] = "Metal Gear Rising: Revengeance"
        target_entry["publisher"] = "Konami / PlatinumGames"
        cat_data["games"].append(target_entry)
        print("Created new entry for 05988A343C507000 with 5 variants!")
    else:
        print("05988A343C507000 already exists, updating variants...")
        target_entry["variants"] = copy.deepcopy(mgr_entry["variants"])
        
    cat_data["totalGames"] = len(cat_data["games"])
    cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in cat_data["games"])
    cat_path.write_text(json.dumps(cat_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"catalog.json updated: {cat_data['totalGames']} games, {cat_data['totalVariants']} variants.")

# Also add to catalog_after_dark.json
ad_path = Path("catalog/data/catalog_after_dark.json")
ad_data = json.loads(ad_path.read_text(encoding="utf-8"))
ad_target = None
for g in ad_data.get("games", []):
    if g.get("titleId") == "05988A343C507000":
        ad_target = g
        break

if not ad_target and mgr_entry:
    import copy
    ad_entry = copy.deepcopy(mgr_entry)
    ad_entry["titleId"] = "05988A343C507000"
    ad_entry["title"] = "Metal Gear Rising: Revengeance"
    ad_entry["publisher"] = "Konami / PlatinumGames"
    ad_data["games"].append(ad_entry)
    ad_data["totalGames"] = len(ad_data["games"])
    ad_data["totalVariants"] = sum(len(g.get("variants", [])) for g in ad_data["games"])
    ad_path.write_text(json.dumps(ad_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"catalog_after_dark.json updated with 05988A343C507000: {ad_data['totalGames']} games, {ad_data['totalVariants']} variants.")
