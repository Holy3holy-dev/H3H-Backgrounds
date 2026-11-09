import sys
import json
import subprocess
from pathlib import Path

sys.path.append('.')
from tg_bot.config import GITHUB_TOKEN, GITHUB_REPO

CAT_MAIN_PATH = Path("catalog/data/catalog.json")
CAT_AD_PATH = Path("catalog/data/catalog_after_dark.json")

# 1. Fix names in main catalog
cat_main = json.loads(CAT_MAIN_PATH.read_text(encoding="utf-8"))
for g in cat_main.get("games", []):
    tid = g.get("titleId", "").upper()
    if tid == "01009C701A35E000":
        g["title"] = "Super Mario 3D World + Bowser's Fury"
        g["publisher"] = "Nintendo"
    elif tid == "010067300059A000":
        g["title"] = "Donkey Kong Country: Tropical Freeze"
        g["publisher"] = "Nintendo"

CAT_MAIN_PATH.write_text(json.dumps(cat_main, indent=2, ensure_ascii=False), encoding="utf-8")
print("[+] Fixed titles in catalog.json")

# 2. Extract the 4 user variants from main
user_tids = ["01003DC0144B6000", "010032E00E6E2000", "01009C701A35E000", "010067300059A000"]
user_games = {}
for g in cat_main.get("games", []):
    tid = g.get("titleId", "").upper()
    if tid in user_tids:
        # find the variant by @Secondchancetomourn
        sc_variants = [v for v in g.get("variants", []) if "secondchancetomourn" in v.get("author", "").lower()]
        if sc_variants:
            user_games[tid] = {
                "titleId": tid,
                "title": g.get("title"),
                "publisher": g.get("publisher", "Nintendo"),
                "variants": sc_variants
            }

print(f"[+] Found {len(user_games)} games from @Secondchancetomourn to sync to After Dark:")
for tid, g in user_games.items():
    print(f"  - {g['title']} ({tid})")

# 3. Add to catalog_after_dark.json
cat_ad = json.loads(CAT_AD_PATH.read_text(encoding="utf-8"))
ad_games_map = {g.get("titleId", "").upper(): g for g in cat_ad.get("games", [])}

added_count = 0
for tid, g_data in user_games.items():
    if tid not in ad_games_map:
        new_entry = {
            "titleId": tid,
            "title": g_data["title"],
            "publisher": g_data["publisher"],
            "variants": list(g_data["variants"])
        }
        cat_ad["games"].append(new_entry)
        ad_games_map[tid] = new_entry
        added_count += 1
    else:
        existing_urls = {v.get("url") for v in ad_games_map[tid].get("variants", [])}
        for v in g_data["variants"]:
            if v.get("url") not in existing_urls:
                ad_games_map[tid]["variants"].append(v)
                added_count += 1

cat_ad["updatedAt"] = "2026-10-23T15:45:00.000000Z"
cat_ad["totalGames"] = len(cat_ad["games"])
cat_ad["totalVariants"] = sum(len(g.get("variants", [])) for g in cat_ad["games"])

CAT_AD_PATH.write_text(json.dumps(cat_ad, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"[+] Updated catalog_after_dark.json (total games: {cat_ad['totalGames']}, variants: {cat_ad['totalVariants']})")

# 4. Push catalog_after_dark.json directly to after-dark branch on GitHub
token = GITHUB_TOKEN
if token:
    repo_url = f"https://x-access-token:{token}@github.com/{GITHUB_REPO}.git"
    print("[*] Pushing updated catalog_after_dark.json to origin/after-dark...")
    
    # Commit on a temporary detached tree or stash
    subprocess.run(["git", "add", "catalog/data/catalog_after_dark.json"], check=True)
    subprocess.run(["git", "commit", "-m", "feat(after-dark): sync user-uploaded community themes from @Secondchancetomourn"], check=False)
    
    res = subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/after-dark"], capture_output=True, text=True)
    print("Push stdout:", res.stdout)
    print("Push stderr:", res.stderr)
    if res.returncode == 0:
        print("[SUCCESS] Successfully pushed to origin/after-dark!")
    else:
        print("[!] Git push error code:", res.returncode)
