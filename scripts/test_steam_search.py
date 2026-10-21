import urllib.request
import urllib.parse
import re

def search_workshop(q, mature=False):
    tags = ["Video"]
    if mature:
        tags.append("Mature")
    params = [("appid", "431960"), ("searchtext", q)]
    for t in tags:
        params.append(("requiredtags[]", t))
    query_str = urllib.parse.urlencode(params)
    url = f"https://steamcommunity.com/workshop/browse/?{query_str}"

    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Cookie": "mature_content=1; birthtime=786240001; lastagecheckage=1-0-1995;"
    })
    html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
    matches = re.findall(r'<a href="https://steamcommunity\.com/sharedfiles/filedetails/\?id=(\d+)"[^>]*><img src="([^"]+)" alt="([^"]*)"', html)
    return [{"id": m[0], "preview": m[1].replace("&amp;", "&"), "title": m[2]} for m in matches]

res = search_workshop("Cyberpunk", mature=True)
print(f"[*] Found {len(res)} Cyberpunk mature video wallpapers:")
for r in res[:5]:
    print(f"  - [{r['id']}] {r['title']}")
