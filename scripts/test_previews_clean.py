import json
import urllib.request
import subprocess
import sys
from pathlib import Path

# Fix console encoding for windows
sys.stdout.reconfigure(encoding='utf-8')

cat = json.load(open('catalog/data/catalog.json', encoding='utf-8'))
games_to_check = [
    ('Super Mario Party Jamboree', '0100965017338000'),
    ('Red Dead Redemption', '01007820196A6000'),
    ('Cuphead', '0100A5C00D162000'),
    ('Zelda: Breath of the Wild', '01007EF00011E000'),
    ('Zelda: Tears of the Kingdom', '0100F2C0115B6000'),
    ('Overcooked! 2', '01006FD0080B2000'),
    ('Hollow Knight', '0100633007D48000'),
]

games_map = {g['titleId']: g for g in cat['games']}

print("Checking video preview links and files for user games...")
print("=" * 70)

for name, tid in games_to_check:
    g = games_map.get(tid)
    if not g:
        print(f"[-] {name} ({tid}): NOT FOUND in catalog!")
        continue
    variants = g.get('variants', [])
    print(f"\nGame: {name} (TID: {tid}) - {len(variants)} variant(s)")
    for idx, v in enumerate(variants):
        vid_url = v.get('url', '')
        thumb_url = v.get('previewUrl', '')
        v_id = v.get('id')
        v_name = v.get('name')
        print(f"  Variant #{idx+1}: '{v_name}' (ID: {v_id})")

        # 1. Check Thumbnail
        thumb_status = "FAIL"
        if thumb_url:
            try:
                req = urllib.request.Request(thumb_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read(1024)
                    if resp.status == 200 and len(data) > 0:
                        thumb_status = f"OK (HTTP {resp.status}, {resp.headers.get('Content-Type')})"
                    else:
                        thumb_status = f"WARN (HTTP {resp.status})"
            except Exception as e:
                thumb_status = f"ERROR: {e}"
        print(f"    Thumb Preview: {thumb_status}")

        # 2. Check Video Stream
        video_status = "FAIL"
        if vid_url:
            try:
                req = urllib.request.Request(vid_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    chunk = resp.read(65536)
                    if b'ftyp' in chunk[:128] or b'moov' in chunk or resp.status in (200, 302):
                        video_status = f"OK (HTTP {resp.status}, valid MP4 header, len={len(chunk)})"
                    else:
                        video_status = f"WARN (HTTP {resp.status}, len={len(chunk)})"
            except Exception as e:
                video_status = f"ERROR: {e}"
        print(f"    Live Video MP4: {video_status}")

print("\n" + "=" * 70)
print("Preview test completed!")
