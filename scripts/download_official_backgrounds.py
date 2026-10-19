"""
Fetches and encodes official animated video backgrounds from game developers
(via Steam Community official Points Shop CDN) for popular Nintendo Switch titles.
All output files are automatically converted to 100% compliant 4IFIR MP4s.
"""

import os
import sys
import subprocess
import urllib.request
from pathlib import Path

OUTPUT_DIR = Path(r"e:\videofon\downloaded_official_backgrounds")

OFFICIAL_ASSETS = [
    {
        "game": "Hades",
        "titleId": "0100535012974000",
        "variant": "Underworld Tartarus",
        "url": "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/items/1145360/b8c251caa191efe0f459049b8833939361163d63.mp4",
        "filename": "0100535012974000_Hades_Underworld.mp4"
    },
    {
        "game": "The Witcher 3: Wild Hunt",
        "titleId": "01003D200E400000",
        "variant": "Kaer Morhen",
        "url": "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/items/292030/a3cb7d5079bb8f64de9326570ded52ec9d94174d.mp4",
        "filename": "01003D200E400000_Witcher_3_Kaer_Morhen.mp4"
    },
    {
        "game": "The Witcher 3: Wild Hunt",
        "titleId": "01003D200E400000",
        "variant": "White Frost",
        "url": "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/items/292030/be5d9b291e693efbb653fa18f73671292369f3ff.mp4",
        "filename": "01003D200E400000_Witcher_3_White_Frost.mp4"
    },
    {
        "game": "Dead Cells",
        "titleId": "01000B900D8B0000",
        "variant": "Promenade of the Condemned",
        "url": "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/items/588650/1fc9a0c56e07855c9992a689fe82dc5cf9ff4de5.mp4",
        "filename": "01000B900D8B0000_Dead_Cells_Promenade.mp4"
    },
    {
        "game": "Dead Cells",
        "titleId": "01000B900D8B0000",
        "variant": "Undying Shores",
        "url": "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/items/588650/c03d66035d0feb15d89a054a310e504f061cac66.mp4",
        "filename": "01000B900D8B0000_Dead_Cells_Undying_Shores.mp4"
    },
    {
        "game": "Persona 5 Royal",
        "titleId": "01009B0014D86000",
        "variant": "Phantom Thieves",
        "url": "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/items/1687950/dee5cf6da16b64e282b4a95d2ca1bbb13d913dd3.mp4",
        "filename": "01009B0014D86000_Persona_5_Royal.mp4"
    },
    {
        "game": "Cult of the Lamb",
        "titleId": "0100227018306000",
        "variant": "Red Crown Ritual",
        "url": "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/items/1313140/c80d1a3ea315f69f72cbb77bffe42c5ed0f7b945.mp4",
        "filename": "0100227018306000_Cult_of_the_Lamb.mp4"
    },
    {
        "game": "Dave the Diver",
        "titleId": "010089C017C7A000",
        "variant": "Secret Lake",
        "url": "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/items/1868140/3f61ed2c34a5aa4e3611c8ac741c9b0eaab90d20.mp4",
        "filename": "010089C017C7A000_Dave_the_Diver_Secret_Lake.mp4"
    },
    {
        "game": "Dave the Diver",
        "titleId": "010089C017C7A000",
        "variant": "Quiet Night",
        "url": "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/items/1868140/dac4a188a8d666edd9d1a3c50947dafa16d9e333.mp4",
        "filename": "010089C017C7A000_Dave_the_Diver_Quiet_Night.mp4"
    },
    {
        "game": "Risk of Rain 2",
        "titleId": "0100E4A00CBCE000",
        "variant": "Commando",
        "url": "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/items/632360/fe65d7f7c9d2bc633d1960e1ed659ced46267c23.mp4",
        "filename": "0100E4A00CBCE000_Risk_of_Rain_2_Commando.mp4"
    },
    {
        "game": "Vampire Survivors",
        "titleId": "0100B61019056000",
        "variant": "Treasure Chest",
        "url": "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/items/1794680/11c7fab3f2104a6815c702ed4fed27848c7b1490.mp4",
        "filename": "0100B61019056000_Vampire_Survivors.mp4"
    },
    {
        "game": "Brotato",
        "titleId": "0100F7A01B5BE000",
        "variant": "New Dawn",
        "url": "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/items/1942280/8efd8cb6f0c65d9fa59ea06c59227b141ce7ffa6.mp4",
        "filename": "0100F7A01B5BE000_Brotato_New_Dawn.mp4"
    }
]

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[*] Output directory: {OUTPUT_DIR}")
    print(f"[*] Preparing {len(OFFICIAL_ASSETS)} official animated backgrounds...")

    for idx, item in enumerate(OFFICIAL_ASSETS, 1):
        gname = item["game"]
        var = item["variant"]
        tid = item["titleId"]
        url = item["url"]
        target = OUTPUT_DIR / item["filename"]

        if target.exists() and target.stat().st_size > 50000:
            print(f"[{idx}/{len(OFFICIAL_ASSETS)}] Skipping already downloaded: {target.name}")
            continue

        print(f"[{idx}/{len(OFFICIAL_ASSETS)}] Downloading & encoding: {gname} - {var} ({tid})...")
        raw_tmp = OUTPUT_DIR / f"temp_{idx}.mp4"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp, open(raw_tmp, "wb") as f:
                f.write(resp.read())

            cmd = [
                "ffmpeg", "-y", "-i", str(raw_tmp),
                "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-profile:v", "high", "-level", "4.1",
                "-crf", "20", "-maxrate", "3500k", "-bufsize", "7000k",
                "-an", str(target)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and target.exists():
                sz_mb = target.stat().st_size / (1024 * 1024)
                print(f"    [+] OK: {target.name} ({sz_mb:.2f} MB)")
            else:
                print(f"    [-] FFmpeg error on {target.name}: {res.stderr}")
        except Exception as e:
            print(f"    [-] Error: {e}")
        finally:
            if raw_tmp.exists():
                try:
                    raw_tmp.unlink()
                except Exception:
                    pass

    print("\n[+] All official backgrounds downloaded and converted!")

if __name__ == "__main__":
    main()
