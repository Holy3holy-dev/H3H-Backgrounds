import urllib.request
import re

url = "https://www.steamgriddb.com/static/assets/233e475efea66025d29a.js"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
content = urllib.request.urlopen(req).read().decode("utf-8", errors="ignore")

for endpoint in ["/api/public/game/", "/api/public/search/assets"]:
    idx = 0
    while True:
        idx = content.find(endpoint, idx)
        if idx == -1:
            break
        snippet = content[max(0, idx - 100):min(len(content), idx + 200)]
        print(f"=== {endpoint} ===")
        print(snippet)
        print()
        idx += len(endpoint)
