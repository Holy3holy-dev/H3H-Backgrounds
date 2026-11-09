"""Upgrades tg_bot/bot.py to v1.3.6-cloud with robust background network stats syncer."""
from pathlib import Path

p = Path("tg_bot/bot.py")
text = p.read_text(encoding="utf-8")

# Bump version string
text = text.replace("v1.3.5-cloud", "v1.3.6-cloud")

# Replace get_catalog_stats implementation with background thread + cached memory stats
old_section = text[text.index("_last_remote_sync = 0.0"):text.index("@bot.message_handler(commands=[\"status\", \"ping\"]")]

new_section = """_cached_stats = {}
_stats_lock = threading.Lock()

def _refresh_stats_from_network():
    global _cached_stats
    stats_tmp = {}
    try:
        raw_std = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/catalog/data/catalog.json?t={int(time.time())}"
        req = urllib.request.Request(raw_std, headers={"User-Agent": "H3H-Bot-Sync/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
            std_games = len(data.get("games", []))
            std_vars = sum(len(g.get("variants", [])) for g in data.get("games", []))
            std_icons = 0
            std_icon_titles = []
            for g in data.get("games", []):
                icons_in_g = sum(1 for v in g.get("variants", []) if v.get("hasIcon") or v.get("iconUrl") or "icon" in v.get("style", "").lower())
                if icons_in_g > 0:
                    std_icons += icons_in_g
                    std_icon_titles.append({
                        "titleId": g.get("titleId", ""),
                        "title": g.get("title", ""),
                        "iconsCount": icons_in_g
                    })
            stats_tmp["std_games"] = std_games
            stats_tmp["std_vars"] = std_vars
            stats_tmp["std_icons"] = std_icons
            stats_tmp["std_icon_games"] = len(std_icon_titles)
            stats_tmp["std_icon_titles"] = std_icon_titles
    except Exception as e:
        pass

    try:
        raw_ad = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/catalog/data/catalog_after_dark.json?t={int(time.time())}"
        req = urllib.request.Request(raw_ad, headers={"User-Agent": "H3H-Bot-Sync/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
            stats_tmp["ad_games"] = len(data.get("games", []))
            stats_tmp["ad_vars"] = sum(len(g.get("variants", [])) for g in data.get("games", []))
            stats_tmp["ad_icons"] = sum(sum(1 for v in g.get("variants", []) if v.get("hasIcon") or v.get("iconUrl")) for g in data.get("games", []))
    except Exception as e:
        pass

    if stats_tmp.get("std_games"):
        with _stats_lock:
            stats_tmp["total_icons"] = stats_tmp.get("std_icons", 0) + stats_tmp.get("ad_icons", 0)
            stats_tmp["resolver_db"] = len(resolver.games)
            _cached_stats.update(stats_tmp)

def _background_stats_syncer():
    time.sleep(3)  # brief delay after boot
    _refresh_stats_from_network()
    while True:
        time.sleep(90)  # every 90s
        _refresh_stats_from_network()

threading.Thread(target=_background_stats_syncer, daemon=True).start()

def get_catalog_stats() -> dict:
    with _stats_lock:
        if _cached_stats and _cached_stats.get("std_games"):
            return dict(_cached_stats)

    # Local fallback
    std_games = 0
    std_vars = 0
    std_icons = 0
    std_icon_titles = []
    ad_games = 0
    ad_vars = 0
    ad_icons = 0
    try:
        p_std = PROJECT_ROOT / CATALOG_PATH_STANDARD
        if p_std.exists():
            data = json.loads(p_std.read_text(encoding="utf-8"))
            std_games = len(data.get("games", []))
            std_vars = sum(len(g.get("variants", [])) for g in data.get("games", []))
            for g in data.get("games", []):
                icons_in_g = sum(1 for v in g.get("variants", []) if v.get("hasIcon") or v.get("iconUrl") or "icon" in v.get("style", "").lower())
                if icons_in_g > 0:
                    std_icons += icons_in_g
                    std_icon_titles.append({
                        "titleId": g.get("titleId", ""),
                        "title": g.get("title", ""),
                        "iconsCount": icons_in_g
                    })
    except Exception:
        pass
    try:
        p_ad = PROJECT_ROOT / CATALOG_PATH_AFTER_DARK
        if p_ad.exists():
            data = json.loads(p_ad.read_text(encoding="utf-8"))
            ad_games = len(data.get("games", []))
            ad_vars = sum(len(g.get("variants", [])) for g in data.get("games", []))
            ad_icons = sum(sum(1 for v in g.get("variants", []) if v.get("hasIcon") or v.get("iconUrl")) for g in data.get("games", []))
    except Exception:
        pass
    return {
        "std_games": std_games,
        "std_vars": std_vars,
        "std_icons": std_icons,
        "std_icon_games": len(std_icon_titles),
        "std_icon_titles": std_icon_titles,
        "ad_games": ad_games,
        "ad_vars": ad_vars,
        "ad_icons": ad_icons,
        "total_icons": std_icons + ad_icons,
        "resolver_db": len(resolver.games)
    }

"""

text = text[:text.index("_last_remote_sync = 0.0")] + new_section + text[text.index("@bot.message_handler(commands=[\"status\", \"ping\"]"):]
p.write_text(text, encoding="utf-8")
print("[+] Upgraded tg_bot/bot.py to v1.3.6-cloud with background stats syncer thread!")
