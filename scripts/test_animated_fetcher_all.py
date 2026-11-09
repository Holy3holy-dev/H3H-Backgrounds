import json
import re
import urllib.request
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any, Optional

class AnimatedIconsFetcher:
    STEAMGRID_KEY = "4200e73768d97fa592e9d9b7eed012fb"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    @classmethod
    def search_steamgriddb(cls, game_name: str) -> List[Dict[str, Any]]:
        results = []
        try:
            # 1. Autocomplete game id
            term = urllib.parse.quote(game_name.strip(), safe='')
            auto_url = f"https://www.steamgriddb.com/api/v2/search/autocomplete/{term}"
            req = urllib.request.Request(auto_url, headers={
                "Authorization": f"Bearer {cls.STEAMGRID_KEY}",
                "User-Agent": cls.USER_AGENT
            })
            with urllib.request.urlopen(req, timeout=12) as resp:
                gdata = json.loads(resp.read().decode())
                games = gdata.get("data", [])
                if not games:
                    return []
                gid = games[0]["id"]
                matched_name = games[0].get("name", game_name)

            # 2. Fetch animated icons
            url_icons = f"https://www.steamgriddb.com/api/v2/icons/game/{gid}?types=animated"
            req = urllib.request.Request(url_icons, headers={
                "Authorization": f"Bearer {cls.STEAMGRID_KEY}",
                "User-Agent": cls.USER_AGENT
            })
            with urllib.request.urlopen(req, timeout=12) as resp:
                idata = json.loads(resp.read().decode())
                for item in idata.get("data", []):
                    results.append({
                        "title": f"{matched_name} (Иконка)",
                        "source": "steamgriddb",
                        "source_label": "SteamGridDB Icon",
                        "url": item.get("url"),
                        "thumb_url": item.get("thumb") or item.get("url"),
                        "format": item.get("mime", "").split("/")[-1] or "webp",
                        "width": item.get("width", 512),
                        "height": item.get("height", 512),
                    })

            # 3. Fetch animated grids (square or motion covers)
            url_grids = f"https://www.steamgriddb.com/api/v2/grids/game/{gid}?types=animated"
            req = urllib.request.Request(url_grids, headers={
                "Authorization": f"Bearer {cls.STEAMGRID_KEY}",
                "User-Agent": cls.USER_AGENT
            })
            with urllib.request.urlopen(req, timeout=12) as resp:
                gdata = json.loads(resp.read().decode())
                for item in gdata.get("data", []):
                    results.append({
                        "title": f"{matched_name} (Арт {item.get('width')}x{item.get('height')})",
                        "source": "steamgriddb",
                        "source_label": "SteamGridDB Grid",
                        "url": item.get("url"),
                        "thumb_url": item.get("thumb") or item.get("url"),
                        "format": item.get("mime", "").split("/")[-1] or "webp",
                        "width": item.get("width", 600),
                        "height": item.get("height", 900),
                    })

        except Exception as e:
            print(f"[-] SteamGridDB search error: {e}")

        return results

    @classmethod
    def search_steam_points(cls, game_name: str) -> List[Dict[str, Any]]:
        results = []
        try:
            # 1. Search Steam Store for App ID
            store_url = f"https://store.steampowered.com/api/storesearch/?term={urllib.parse.quote(game_name)}&l=english&cc=US"
            req = urllib.request.Request(store_url, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req, timeout=12) as resp:
                sdata = json.loads(resp.read().decode())
                items = sdata.get("items", [])
                if not items:
                    return []
                appid = items[0]["id"]
                appname = items[0]["name"]

            # 2. Query Loyalty Rewards
            points_url = f"https://api.steampowered.com/ILoyaltyRewardsService/QueryRewardItems/v1/?appids[0]={appid}&count=50"
            req = urllib.request.Request(points_url, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req, timeout=12) as resp:
                pdata = json.loads(resp.read().decode())
                defs = pdata.get("response", {}).get("definitions", [])
                for d in defs:
                    cdata = d.get("community_item_data", {})
                    title = cdata.get("item_title", "Steam Animated")
                    murl = cdata.get("item_movie_mp4", "") or cdata.get("item_movie_webm", "")
                    img = cdata.get("item_image_large", "") or cdata.get("item_image_small", "")
                    
                    if murl:
                        full_murl = f"https://cdn.akamai.steamstatic.com/steamcommunity/public/images/items/{appid}/{murl}"
                        full_thumb = f"https://cdn.akamai.steamstatic.com/steamcommunity/public/images/items/{appid}/{img}" if img else full_murl
                        results.append({
                            "title": f"{appname} — {title}",
                            "source": "steam_points",
                            "source_label": "Steam Points Shop",
                            "url": full_murl,
                            "thumb_url": full_thumb,
                            "format": "mp4",
                            "width": 300,
                            "height": 300,
                        })
        except Exception as e:
            print(f"[-] Steam Points search error: {e}")

        return results

    @classmethod
    def search_tenor(cls, game_name: str) -> List[Dict[str, Any]]:
        results = []
        try:
            clean_term = re.sub(r"[^\w\s]", "", game_name).strip().replace(" ", "-").lower()
            url = f"https://tenor.com/search/{clean_term}-gifs"
            req = urllib.request.Request(url, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                mp4s = list(set(re.findall(r"https://media\.tenor\.com/[^\s\"\'<>]+\.mp4", html)))
                gifs = list(set(re.findall(r"https://media\.tenor\.com/[^\s\"\'<>]+\.gif", html)))

                # Match pairs or add mp4s
                for i, m in enumerate(mp4s[:15]):
                    thumb = gifs[i] if i < len(gifs) else m
                    name_part = m.split("/")[-1].replace(".mp4", "").replace("-", " ").capitalize()
                    results.append({
                        "title": f"{game_name} — {name_part[:30]}",
                        "source": "tenor",
                        "source_label": "Tenor Loop",
                        "url": m,
                        "thumb_url": thumb,
                        "format": "mp4",
                        "width": 256,
                        "height": 256,
                    })
        except Exception as e:
            print(f"[-] Tenor search error: {e}")

        return results

    @classmethod
    def search_all(cls, game_name: str) -> List[Dict[str, Any]]:
        all_results = []
        all_results.extend(cls.search_steam_points(game_name))
        all_results.extend(cls.search_steamgriddb(game_name))
        all_results.extend(cls.search_tenor(game_name))
        return all_results

if __name__ == "__main__":
    for query in ["Witcher 3", "Cyberpunk", "Hades"]:
        print(f"\n==================== SEARCHING: {query} ====================")
        res = AnimatedIconsFetcher.search_all(query)
        print(f"Total results for {query}: {len(res)}")
        by_src = {}
        for r in res:
            by_src[r['source_label']] = by_src.get(r['source_label'], 0) + 1
        print("Breakdown by source:", by_src)
        for r in res[:4]:
            print(f"  [{r['source_label']}] {r['title']} ({r['format']}) -> {r['url'][:60]}...")
