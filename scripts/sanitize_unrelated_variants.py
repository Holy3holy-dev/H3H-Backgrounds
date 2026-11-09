"""
Sanitize catalog from unrelated PC moba/anime cross-tags (League of Legends, Valorant, Dota, etc.)
that were mistakenly matched to Switch titles by legacy substring searches.
"""

import json
from pathlib import Path

CAT_PATH = Path("catalog/data/catalog.json")

def is_bad_variant(game_title: str, var_name: str) -> bool:
    g_low = game_title.lower()
    v_low = var_name.lower()
    
    # Legit Naruto games keep their variants
    if "naruto" in g_low and ("naruto" in v_low or "boruto" in v_low):
        return False
        
    # Bad terms from other games
    bad_tags = [
        "league of legends", "valorant", "dota 2", "one punch man",
        "saitama", "obito kamui", "rick and morty", "jett valorant",
        "six paths naruto"
    ]
    
    for tag in bad_tags:
        if tag in v_low:
            return True
            
    # Game-specific false positives
    if "portal" in g_low and not any(k in v_low for k in ["portal 2", "portal companion", "glados", "chell", "aperture", "valve"]):
        if any(k in v_low for k in ["minecraft", "saitama", "garou", "naruto", "rick and morty", "world behind the door", "payback"]):
            return True
            
    return False

def main():
    if not CAT_PATH.exists():
        print("Catalog not found.")
        return
        
    cat = json.loads(CAT_PATH.read_text(encoding="utf-8"))
    removed_count = 0
    
    for g in cat.get("games", []):
        g_title = g.get("title", "")
        clean_vars = []
        for v in g.get("variants", []):
            v_name = v.get("name", "")
            if is_bad_variant(g_title, v_name):
                print(f"[-] Removing unrelated variant '{v_name}' from game '{g_title}' [{g.get('titleId')}]")
                removed_count += 1
            else:
                clean_vars.append(v)
        g["variants"] = clean_vars
        
    print(f"\n[*] Total unrelated variants removed: {removed_count}")
    if removed_count > 0:
        cat["totalVariants"] = sum(len(g.get("variants", [])) for g in cat.get("games", []))
        CAT_PATH.write_text(json.dumps(cat, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[+] Catalog updated and saved! New total variants: {cat['totalVariants']}")

if __name__ == "__main__":
    main()
