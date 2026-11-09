import urllib.request
import re

url = "https://www.steamgriddb.com/static/assets/233e475efea66025d29a.js"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
content = urllib.request.urlopen(req).read().decode("utf-8", errors="ignore")
matches = re.findall(r"/api/public/[^\s\"\'\`\)]+", content)
for m in sorted(list(set(matches))):
    print(m)
