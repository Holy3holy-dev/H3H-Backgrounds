import json
from pathlib import Path

cat_path = Path("catalog/data/catalog.json")
cat = json.loads(cat_path.read_text(encoding="utf-8"))

for g in cat.get("games", []):
    tid = g.get("titleId", "").upper()
    
    # 1. Fix Wind Waker
    if tid == "01CAA550FBC40000":
        g["title"] = "The Legend of Zelda: The Wind Waker HD"
        g["publisher"] = "Nintendo"
        
        # Update existing variant #1
        if g.get("variants"):
            v1 = g["variants"][0]
            v1["name"] = "The Great Sea Intro & Sailing"
            v1["style"] = "Cinematic"
            v1["notes"] = "Submitted via Telegram by @Secondchancetomourn"
            
        # Add variant #2 (Pixel Wallpaper 60fps)
        pixel_var_id = "var-windwaker-pixel"
        has_pixel = any(v.get("id") == pixel_var_id for v in g.get("variants", []))
        if not has_pixel:
            g["variants"].append({
                "id": pixel_var_id,
                "name": "The Great Sea Pixel Art (60fps)",
                "style": "Wallpaper Engine 60fps",
                "version": "1.0",
                "url": "https://drive.google.com/uc?export=download&id=11DdfW_4zMJ8fqqMFgWz-GPva_eD0D0R6",
                "previewUrl": "https://drive.google.com/thumbnail?id=11DdfW_4zMJ8fqqMFgWz-GPva_eD0D0R6&sz=w640",
                "sizeBytes": 1123047,
                "sha256": "",
                "durationSec": 15.0,
                "author": "MoeWalls / Wallpaper Engine",
                "codec": "h264",
                "width": 1280,
                "height": 720,
                "fps": 30.0,
                "hasAudio": False,
                "hasIcon": True,
                "iconUrl": "https://drive.google.com/uc?export=download&id=1BxMmUwbspG5rySvXLALDjgyEByLTI0Tw",
                "iconSizeBytes": 373219,
                "iconCodec": "hevc",
                "iconWidth": 256,
                "iconHeight": 256,
                "notes": "Pixel Animated Ocean Theme from Wallpaper Engine"
            })
            
        # Add standalone 4IFIR icon variant
        icon_var_id = "icon-01caa550fbc40000"
        has_icon_var = any(v.get("id") == icon_var_id for v in g.get("variants", []))
        if not has_icon_var:
            g["variants"].append({
                "id": icon_var_id,
                "name": "4IFIR Иконка: The Legend of Zelda: The Wind Waker HD",
                "style": "4IFIR Dynamic Icon",
                "version": "1.0",
                "url": "https://drive.google.com/uc?export=download&id=1BxMmUwbspG5rySvXLALDjgyEByLTI0Tw",
                "previewUrl": "https://drive.google.com/thumbnail?id=1BxMmUwbspG5rySvXLALDjgyEByLTI0Tw&sz=w256",
                "sizeBytes": 373219,
                "sha256": "",
                "durationSec": 4.0,
                "author": "@Secondchancetomourn / 4IFIR",
                "codec": "hevc",
                "width": 256,
                "height": 256,
                "fps": 30.0,
                "hasAudio": False,
                "hasIcon": True,
                "iconUrl": "https://drive.google.com/uc?export=download&id=1BxMmUwbspG5rySvXLALDjgyEByLTI0Tw",
                "iconSizeBytes": 373219,
                "iconCodec": "hevc",
                "iconWidth": 256,
                "iconHeight": 256,
                "notes": "4IFIR 256x256 Animated Icon (Great Sea Water Logo)"
            })
        print("[+] Wind Waker 01CAA550FBC40000 updated successfully with 2 covers + 1 icon!")

    # 2. Fix Homebrew Menu forwarder
    elif tid == "0104444444444000":
        g["title"] = "Homebrew Menu (hbmenu Forwarder)"
        g["publisher"] = "SwitchBrew"
        print("[+] 0104444444444000 set to Homebrew Menu")

    # 3. Fix Kefir / StarterNX Homebrew Menu forwarder
    elif tid == "03DB12780BD84000":
        g["title"] = "Homebrew Menu (Kefir / StarterNX Forwarder)"
        g["publisher"] = "Team Kefir / SwitchBrew"
        print("[+] 03DB12780BD84000 set to Homebrew Menu (Kefir)")

# Clean out dead 0100F0400E850000 entry (which had 404 dead link)
cat["games"] = [g for g in cat.get("games", []) if g.get("titleId", "").upper() != "0100F0400E850000"]

cat["totalGames"] = len(cat["games"])
cat["totalVariants"] = sum(len(g.get("variants", [])) for g in cat["games"])

cat_path.write_text(json.dumps(cat, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"[+] Total games: {cat['totalGames']}, total variants: {cat['totalVariants']}")
