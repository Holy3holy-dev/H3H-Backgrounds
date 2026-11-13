import urllib.request
import json

url = "https://raw.githubusercontent.com/Holy3holy-dev/H3H-Backgrounds/main/catalog/data/catalog.json"
print("Fetching from:", url)

req = urllib.request.Request(
    url, 
    headers={'User-Agent': 'Mozilla/5.0'}
)

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read().decode('utf-8')
        print(f"Downloaded {len(content)} bytes")
        
        # Test JSON parsing
        try:
            data = json.loads(content)
            print("JSON valid! Root keys:", list(data.keys()) if isinstance(data, dict) else type(data))
            if isinstance(data, dict) and "games" in data:
                print(f"Total games: {len(data['games'])}")
                
                # Check for any invalid title IDs or duplicate title IDs
                seen = set()
                dups = []
                invalids = []
                for idx, g in enumerate(data["games"]):
                    tid = g.get("titleId", "")
                    if len(tid) != 16 or not all(c in "0123456789abcdefABCDEF" for c in tid):
                        invalids.append((idx, tid, g.get("title")))
                    norm = tid.upper()
                    if norm in seen:
                        dups.append((idx, norm, g.get("title")))
                    seen.add(norm)
                
                print("Invalids:", len(invalids), invalids[:5])
                print("Duplicates:", len(dups), dups[:5])
        except Exception as je:
            print("JSON parse error:", je)
except Exception as e:
    print("Download error:", e)
