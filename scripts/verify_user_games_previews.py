import json
import urllib.request
import subprocess
from pathlib import Path

cat = json.load(open('catalog/data/catalog.json', encoding='utf-8'))
games_to_check = [
    '0100965017338000', # Super Mario Party Jamboree
    '01007820196A6000', # Red Dead Redemption
    '0100A5C00D162000', # Cuphead
    '01007EF00011E000', # Zelda BotW
    '0100F2C0115B6000', # Zelda TotK
    '01006FD0080B2000', # Overcooked 2
    '0100633007D48000', # Hollow Knight
]

games_map = {g['titleId']: g for g in cat['games']}

for tid in games_to_check:
    g = games_map.get(tid)
    if not g:
        print(f"[-] {tid}: NOT FOUND in catalog!")
        continue
    variants = g.get('variants', [])
    print(f"\n========================================================")
    print(f"Game: {g.get('title')} ({tid}) [Variants: {len(variants)}]")
    for idx, v in enumerate(variants):
        vid_url = v.get('url', '')
        thumb_url = v.get('previewUrl', '')
        print(f"  Variant {idx+1}: {v.get('name')} (ID: {v.get('id')})")
        print(f"    Expected size: {v.get('sizeBytes')} bytes, duration: {v.get('durationSec')}s")
        
        # Test Thumb URL
        if thumb_url:
            try:
                req = urllib.request.Request(thumb_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as r:
                    t_bytes = r.read(1024)
                    print(f"    [✓] Thumb: HTTP {r.status}, type: {r.headers.get('Content-Type')}, valid JPG header: {t_bytes[:2] == b'\\xff\\xd8'}")
            except Exception as e:
                print(f"    [!] Thumb FAILED: {e}")
        else:
            print("    [-] No previewUrl specified!")

        # Test Video URL
        if vid_url:
            try:
                req = urllib.request.Request(vid_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as r:
                    v_header = r.read(4096)
                    # Check for ftyp / mp4 box
                    is_mp4 = b'ftyp' in v_header[:64]
                    print(f"    [✓] Video: HTTP {r.status}, type: {r.headers.get('Content-Type')}, valid MP4 ftyp: {is_mp4}")
            except Exception as e:
                print(f"    [!] Video URL FAILED: {e}")
        else:
            print("    [-] No video url specified!")
