import urllib.request
import urllib.parse
import json

print("=== 1. Testing Steam Points Shop API ===")
game = "Witcher 3"
url = f"https://store.steampowered.com/api/storesearch/?term={urllib.parse.quote(game)}&l=english&cc=US"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
        print("Steam Store Search items:", len(data.get("items", [])))
        if data.get("items"):
            first = data["items"][0]
            appid = first["id"]
            name = first["name"]
            print(f"Found game: {name} (appid: {appid})")
            
            # Query Steam Points Shop for this appid
            points_url = f"https://api.steampowered.com/ILoyaltyRewardsService/QueryRewardItems/v1/?appids[0]={appid}&count=50"
            req2 = urllib.request.Request(points_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req2, timeout=10) as resp2:
                pdata = json.loads(resp2.read().decode())
                defs = pdata.get("response", {}).get("definitions", [])
                print(f"Points shop definitions found: {len(defs)}")
                for d in defs[:5]:
                    cdata = d.get("community_item_data", {})
                    cname = cdata.get("item_title", "")
                    itype = d.get("community_item_class", 0)
                    murl = cdata.get("item_movie_mp4", "") or cdata.get("item_movie_webm", "")
                    img = cdata.get("item_image_large", "") or cdata.get("item_image_small", "")
                    if murl:
                        print(f"  - [{itype}] {cname}: movie=https://cdn.akamai.steamstatic.com/steamcommunity/public/images/items/{appid}/{murl}")
                    elif img:
                        print(f"  - [{itype}] {cname}: img=https://cdn.akamai.steamstatic.com/steamcommunity/public/images/items/{appid}/{img}")
except Exception as e:
    print("Steam error:", e)

print("\n=== 2. Testing Tenor API ===")
tenor_url = f"https://tenor.googleapis.com/v2/search?q={urllib.parse.quote(game + ' game loop')}&key=LIVDSRZULELA&limit=5"
try:
    req = urllib.request.Request(tenor_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        tdata = json.loads(resp.read().decode())
        results = tdata.get("results", [])
        print("Tenor results:", len(results))
        for r in results[:3]:
            title = r.get("title") or r.get("content_description", "")
            media = r.get("media_formats", {})
            mp4_url = media.get("tinymp4", {}).get("url") or media.get("mp4", {}).get("url")
            gif_url = media.get("tinygif", {}).get("url") or media.get("gif", {}).get("url")
            print(f"  - {title[:30]}: mp4={mp4_url[:40]}... gif={gif_url[:40]}...")
except Exception as e:
    print("Tenor error:", e)

print("\n=== 3. Testing GIPHY Search ===")
# Giphy public web search or key
giphy_url = f"https://api.giphy.com/v1/gifs/search?api_key=3eFLGCrvKoHdOpWh6mTaZDDdGqqOdtjy&q={urllib.parse.quote(game + ' game')}&limit=5"
try:
    req = urllib.request.Request(giphy_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        gdata = json.loads(resp.read().decode())
        gresults = gdata.get("data", [])
        print("Giphy results:", len(gresults))
        for g in gresults[:3]:
            title = g.get("title", "")
            images = g.get("images", {})
            mp4_url = images.get("original", {}).get("mp4") or images.get("downsized_small", {}).get("mp4")
            gif_url = images.get("fixed_height", {}).get("url")
            print(f"  - {title[:30]}: mp4={mp4_url[:40] if mp4_url else 'None'}... gif={gif_url[:40]}...")
except Exception as e:
    print("Giphy error:", e)
