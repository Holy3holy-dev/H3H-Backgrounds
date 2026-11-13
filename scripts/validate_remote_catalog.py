import requests
import json

url = "https://raw.githubusercontent.com/Holy3holy-dev/H3H-Backgrounds/main/catalog/data/catalog.json"
print("[*] Fetching remote catalog from GitHub:", url)
r = requests.get(url, timeout=15)
print("HTTP status:", r.status_code, "Length:", len(r.text))

try:
    data = r.json()
    print("[+] JSON is syntactically valid!")
except Exception as e:
    print("[-] JSON syntax error:", e)
    exit(1)

schema_ver = data.get("schemaVersion")
print("schemaVersion:", schema_ver)
if schema_ver != 1:
    print("[-] ERROR: schemaVersion != 1")

games = data.get("games")
print("games count:", len(games) if isinstance(games, list) else "NOT A LIST")

seen_tids = set()
errors = []

for idx, g in enumerate(games):
    tid = g.get("titleId", "")
    title = g.get("title", "")
    if len(tid) != 16:
        errors.append(f"Game #{idx}: Title ID length != 16: '{tid}' ({title})")
        continue
    if not all(c in "0123456789ABCDEFabcdef" for c in tid):
        errors.append(f"Game #{idx}: Title ID not hex: '{tid}' ({title})")
        continue
    norm_tid = tid.upper()
    if norm_tid in seen_tids:
        errors.append(f"Game #{idx}: Duplicate Title ID: '{norm_tid}' ({title})")
        continue
    seen_tids.add(norm_tid)

    for v_idx, v in enumerate(g.get("variants", [])):
        u = v.get("url", "")
        if u and not u.startswith("https://"):
            errors.append(f"Game #{idx} '{title}' var #{v_idx}: URL not https: '{u}'")
        iu = v.get("iconUrl", "")
        if iu and not iu.startswith("https://"):
            errors.append(f"Game #{idx} '{title}' var #{v_idx}: iconUrl not https: '{iu}'")

print(f"[*] Total validation errors: {len(errors)}")
for err in errors[:15]:
    print("  ->", err)
