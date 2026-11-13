import urllib.request
import json

urls = [
    "https://raw.githubusercontent.com/Holy3holy-dev/H3H-Backgrounds/main/catalog/data/catalog.json",
    "https://cdn.jsdelivr.net/gh/Holy3holy-dev/H3H-Backgrounds@main/catalog/data/catalog.json",
    "https://fastly.jsdelivr.net/gh/Holy3holy-dev/H3H-Backgrounds@main/catalog/data/catalog.json"
]

for u in urls:
    print(f"\nTesting URL: {u}")
    req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            print(f"Status: {resp.status}, Size: {len(data)} bytes")
            # Try parsing
            try:
                j = json.loads(data.decode('utf-8'))
                print("JSON OK! Games:", len(j.get("games", [])))
            except Exception as je:
                print("JSON ERROR:", je)
                print("First 200 chars:", data[:200])
    except Exception as e:
        print("HTTP ERROR:", e)
