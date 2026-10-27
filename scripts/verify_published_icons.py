import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tg_bot.bot import get_catalog_stats

def main():
    print("=== Running Catalog & Bot Verification ===")
    stats = get_catalog_stats()
    print(f"[*] H3H Catalog: {stats['std_games']} games ({stats['std_vars']} video variants)")
    print(f"[*] 4IFIR Video Icons: {stats['std_icons']} icons across {stats['std_icon_games']} titles")
    print(f"[*] After Dark: {stats['ad_games']} games ({stats['ad_vars']} video variants)")
    
    # Check top titles sample
    titles = stats.get("std_icon_titles", [])
    print(f"[*] First 5 icon titles:")
    for t in titles[:5]:
        print(f"    - {t['title']} ({t['titleId']}) -> {t['iconsCount']} icon variants")
        
    print(f"[*] Last 5 icon titles:")
    for t in titles[-5:]:
        print(f"    - {t['title']} ({t['titleId']}) -> {t['iconsCount']} icon variants")

    assert stats['std_icons'] > 0, "No icons found in catalog!"
    assert stats['std_icon_games'] >= 100, f"Expected at least 100 icon games, found {stats['std_icon_games']}"
    print("[+] All verification assertions passed!")

if __name__ == "__main__":
    main()
