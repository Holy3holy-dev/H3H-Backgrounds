import json
from pathlib import Path

cat_path = Path("catalog/data/catalog.json")
data = json.loads(cat_path.read_text(encoding="utf-8"))

# 1. Update Super Mario Odyssey (0100000000010000)
for g in data["games"]:
    if g["titleId"] == "0100000000010000":
        g["variants"] = [
            {
                "id": "mario-odyssey-new-donk",
                "name": "New Donk City (Gameplay)",
                "style": "Cinematic Gameplay",
                "version": "1.0",
                "url": "https://drive.google.com/uc?export=download&id=1RSj17SlAuso-7l3BSZEdjColjt-cgGqq",
                "previewUrl": "https://drive.google.com/thumbnail?id=1RSj17SlAuso-7l3BSZEdjColjt-cgGqq&sz=w640",
                "sizeBytes": 6179895,
                "sha256": "",
                "durationSec": 20.0,
                "author": "Holy3holy-dev",
                "codec": "h264",
                "width": 1280,
                "height": 720,
                "fps": 30.0,
                "hasAudio": False,
                "notes": "Google Drive: Super Mario Odyssey New Donk City 720p H.264"
            },
            {
                "id": "super-mario-odyssey",
                "name": "Title Screen",
                "style": "Official Theme",
                "version": "1.0",
                "url": "https://drive.google.com/uc?export=download&id=1MQa9RJbq1xD3PSdZhGakMg7Ha5FDniUR",
                "previewUrl": "https://drive.google.com/thumbnail?id=1MQa9RJbq1xD3PSdZhGakMg7Ha5FDniUR&sz=w640",
                "sizeBytes": 3073003,
                "sha256": "",
                "durationSec": 20.0,
                "author": "Holy3holy-dev",
                "codec": "h264",
                "width": 1280,
                "height": 720,
                "fps": 30.0,
                "hasAudio": False,
                "notes": "Google Drive: 0100000000010000_Super_Mario_Odyssey.mp4"
            }
        ]
        print("[+] Updated Super Mario Odyssey with New Donk City as default Variant 1!")

    elif g["titleId"] == "0100152000022000":
        g["variants"] = [
            {
                "id": "mario-kart-8-deluxe",
                "name": "Rainbow Road",
                "style": "Cinematic Gameplay",
                "version": "1.0",
                "url": "https://drive.google.com/uc?export=download&id=1aZrWpw28vqW1shanjvbQuIrboinSLDCC",
                "previewUrl": "https://drive.google.com/thumbnail?id=1aZrWpw28vqW1shanjvbQuIrboinSLDCC&sz=w640",
                "sizeBytes": 9048143,
                "sha256": "",
                "durationSec": 20.0,
                "author": "Holy3holy-dev",
                "codec": "h264",
                "width": 1280,
                "height": 720,
                "fps": 30.0,
                "hasAudio": False,
                "notes": "Google Drive: 0100152000022000_Mario_Kart_8_Deluxe.mp4"
            },
            {
                "id": "mario-kart-8-king-boo",
                "name": "Twisted Mansion (King Boo)",
                "style": "Action Drift",
                "version": "1.0",
                "url": "https://drive.google.com/uc?export=download&id=1rcCzaeSe3D0KawRUvvFfKkbtfLqLCwc8",
                "previewUrl": "https://drive.google.com/thumbnail?id=1rcCzaeSe3D0KawRUvvFfKkbtfLqLCwc8&sz=w640",
                "sizeBytes": 6070467,
                "sha256": "",
                "durationSec": 20.0,
                "author": "Holy3holy-dev",
                "codec": "h264",
                "width": 1280,
                "height": 720,
                "fps": 30.0,
                "hasAudio": False,
                "notes": "Google Drive: Mario Kart 8 King Boo 720p H.264"
            }
        ]
        print("[+] Updated Mario Kart 8 with Rainbow Road as default Variant 1 and King Boo as Variant 2!")

    else:
        # If game has both a raw TID variant named 'Standard' and an optimized named variant,
        # sort so the optimized named variant comes first
        if len(g["variants"]) > 1:
            raw_indices = [
                i for i, v in enumerate(g["variants"])
                if v.get("notes", "").endswith(g["titleId"] + ".mp4") and v.get("name") == "Standard"
            ]
            if raw_indices and raw_indices[0] == 0:
                # Move non-raw variant to front
                non_raw = [v for i, v in enumerate(g["variants"]) if i not in raw_indices]
                raw = [g["variants"][i] for i in raw_indices]
                if non_raw:
                    g["variants"] = non_raw + raw
                    print(f"[*] Reordered variants for {g['title']}: {g['variants'][0]['name']} is now default Variant 1")

# Update totals
data["totalGames"] = len(data["games"])
data["totalVariants"] = sum(len(g["variants"]) for g in data["games"])
cat_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"[+] Catalog updated! Total games: {data['totalGames']}, total variants: {data['totalVariants']}")
