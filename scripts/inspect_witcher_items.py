import sys
import json
import re
import urllib.request
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.animated_icons_fetcher import AnimatedIconsFetcher

# Let's inspect Witcher 3 Steam Points avatars specifically!
store_url = "https://store.steampowered.com/api/storesearch/?term=Witcher%203&l=english&cc=US"
req = urllib.request.Request(store_url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    appid = data["items"][0]["id"]

points_url = f"https://api.steampowered.com/ILoyaltyRewardsService/QueryRewardItems/v1/?appids[0]={appid}&count=50"
req = urllib.request.Request(points_url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req) as resp:
    pdata = json.loads(resp.read().decode())
    defs = pdata.get("response", {}).get("definitions", [])
    print(f"Total Witcher definitions: {len(defs)}")
    for d in defs:
        cdata = d.get("community_item_data", {})
        title = cdata.get("item_title", "")
        itype = d.get("community_item_class", 0) # 13=mini-profile, 14=animated avatar, 15=avatar frame
        murl = cdata.get("item_movie_mp4", "")
        img = cdata.get("item_image_large", "")
        print(f"Class {itype}: '{title}' mp4={bool(murl)} img={bool(img)}")
