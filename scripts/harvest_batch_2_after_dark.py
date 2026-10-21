import os
import sys
import json
import time
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, 'studio')
from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient
from h3h_studio.core.github_publisher import GitHubPublisher

DRIVE_STAGE = Path(r"H:\h3h_stage")
RAW_DIR = DRIVE_STAGE / "raw"
P720_DIR = DRIVE_STAGE / "720p"
THUMB_DIR = DRIVE_STAGE / "thumbs"

AFTER_DARK_FOLDER_ID = "1SXWjp12pKxPPT6YRMZ7tle8cgZdrKkHk"

DRIVE_IDS = {
    "xenoblade-mythra-starry": "1qt1VVz9U54o7wxAynDHClo16Zc7L-u7l",
    "p5r-ann-summer": "1tyALI2P2Bw1L25qCFcah2CjdZZ8ZXSim",
    "p5r-kasumi-blossom": "1oi8qjjXKuFIsLLAjQLkWCQEbthYNgZgt",
    "nier-2b-a2-rain": "17LF9LrdfUIV50r57X48G_G7vW11h9yJx",
    "nier-a2-water": "1pfzQvW-4SnR1nbDK76XSvps1rp_O85eL",
    "witcher-yennefer-geralt": "1Lgzaj2v6hjMhM9TYqgxvEqX-HYK_KAu1",
    "nikke-sugar-bunny": "1tAUHQPZmiPYC041IVeqwMY3Vr0LAmns9",
    "ba-akane-bunny": "1Lur7-pq-DVQc4DJxzUSlBzwu7Vn5kbxI",
    "ba-makoto-swimsuit": "1_umnNL2gwk4Wv58HbxNj7xeb8T40KfTJ",
    "bunny-mai-sakurajima": "1S-PJsbabg16ljJPlLZE3Wnye0SXmo0aR",
    "fate-scathach-lancer": "18cFG8au-s3CHEywJAscShhGbRHAcWg5s",
    "fate-saber-lilies": "1m0ZPIOEyoWHd-ekDZNONPp8H9YaOGWJ3",
    "chainsaw-power-blood": "1mcPq4EUJAmjexkcb4OG6gQBsQ6kzzNqA"
}

TARGETS = [
    # Xenoblade Chronicles 2 (0100E95004038000)
    {
        "tid": "0100E95004038000",
        "game_title": "Xenoblade Chronicles 2",
        "publisher": "Nintendo / Monolith Soft",
        "var_id": "xenoblade-mythra-starry",
        "name": "Mythra: Full Moon Starry Night",
        "style": "Ecchi / Mature",
    },
    # Persona 5 Royal (010091200CDA4000)
    {
        "tid": "010091200CDA4000",
        "game_title": "Persona 5 Royal",
        "publisher": "ATLUS / SEGA",
        "var_id": "p5r-ann-summer",
        "name": "Ann Takamaki: Summer Vacation",
        "style": "Ecchi / Mature",
    },
    {
        "tid": "010091200CDA4000",
        "game_title": "Persona 5 Royal",
        "publisher": "ATLUS / SEGA",
        "var_id": "p5r-kasumi-blossom",
        "name": "Kasumi Yoshizawa: Violet Blossom",
        "style": "Ecchi / Mature",
    },
    # NieR:Automata (01005C000B2AE000)
    {
        "tid": "01005C000B2AE000",
        "game_title": "NieR:Automata The End of YoRHa Edition",
        "publisher": "Square Enix",
        "var_id": "nier-2b-a2-rain",
        "name": "2B & A2: In the Rain",
        "style": "Ecchi / Mature",
    },
    {
        "tid": "01005C000B2AE000",
        "game_title": "NieR:Automata The End of YoRHa Edition",
        "publisher": "Square Enix",
        "var_id": "nier-a2-water",
        "name": "A2: Lying on the Water",
        "style": "Ecchi / Mature",
    },
    # The Witcher 3 (0100E8B00BDC6000)
    {
        "tid": "0100E8B00BDC6000",
        "game_title": "The Witcher 3: Wild Hunt - Complete Edition",
        "publisher": "CD PROJEKT RED",
        "var_id": "witcher-yennefer-geralt",
        "name": "Yennefer & Geralt: Midnight Embrace",
        "style": "Ecchi / Mature",
    },
    # ★ Коллекция After Dark (Свободный выбор) (0000000000000000)
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "nikke-sugar-bunny",
        "name": "Sugar: Killer Rabbit Bunny Suit (NIKKE)",
        "style": "Ecchi / Mature",
    },
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "ba-akane-bunny",
        "name": "Akane: Bunny Girl (Blue Archive)",
        "style": "Ecchi / Mature",
    },
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "ba-makoto-swimsuit",
        "name": "Makoto: Summer Swimsuit (Blue Archive)",
        "style": "Ecchi / Mature",
    },
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "bunny-mai-sakurajima",
        "name": "Mai Sakurajima: Bunny Girl Senpai",
        "style": "Ecchi / Mature",
    },
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "fate-scathach-lancer",
        "name": "Scathach: Crimson Lancer (Fate)",
        "style": "Ecchi / Mature",
    },
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "fate-saber-lilies",
        "name": "Saber: White Lilies (Fate)",
        "style": "Ecchi / Mature",
    },
    {
        "tid": "0000000000000000",
        "game_title": "★ Коллекция After Dark (Свободный выбор)",
        "publisher": "H3H Studio",
        "var_id": "chainsaw-power-blood",
        "name": "Power: Blood Fiend (Chainsaw Man)",
        "style": "Ecchi / Mature",
    }
]

def calculate_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()

def get_duration(filepath):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(filepath)]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return round(float(res.stdout.strip()), 2)
    except Exception:
        return 15.0

def process_item(item, token):
    var_id = item['var_id']
    name = item['name']
    out_mp4 = P720_DIR / f"{var_id}.mp4"
    thumb_path = THUMB_DIR / f"{var_id}.jpg"
    
    file_id = DRIVE_IDS.get(var_id)
    if not file_id:
        print(f"[*] Uploading to Google Drive folder 'H3H-AfterDark'...")
        up_res = GoogleDriveClient.upload_file(out_mp4, AFTER_DARK_FOLDER_ID, token)
        file_id = up_res.get('id')
    
    # Ensure public access
    GoogleDriveClient.make_public(file_id, token)

    sha = calculate_sha256(out_mp4)
    duration = get_duration(out_mp4)
    size_bytes = out_mp4.stat().st_size

    direct_url = GoogleDriveHelper.to_direct_download_url(file_id)
    preview_url = GoogleDriveHelper.to_preview_url(file_id)

    return {
        "id": var_id,
        "name": name,
        "style": item["style"],
        "version": "1.0",
        "url": direct_url,
        "previewUrl": preview_url,
        "sizeBytes": size_bytes,
        "sha256": sha,
        "durationSec": duration,
        "author": "Community (After Dark)",
        "codec": "h264",
        "width": 1280,
        "height": 720,
        "fps": 30.0,
        "hasAudio": False,
        "notes": f"Switch 720p 30fps | {item.get('name')}"
    }

def main():
    print("==================================================")
    print("H3H After Dark: Batch 2 Catalog Registrar & Sync")
    print("==================================================")
    
    gdrive_cfg = GoogleDriveHelper.get_stored_config()
    refresh_tok = gdrive_cfg.get("refresh_token")
    token = GoogleDriveHelper.refresh_access_token(refresh_tok)

    catalog_path = Path("catalog/data/catalog_after_dark.json")
    with open(catalog_path, 'r', encoding='utf-8') as f:
        catalog = json.load(f)

    games_map = {g['titleId']: g for g in catalog.get('games', [])}

    success_count = 0
    for target in TARGETS:
        try:
            var_dict = process_item(target, token)
            tid = target['tid']
            if tid not in games_map:
                game_entry = {
                    "titleId": tid,
                    "title": target["game_title"],
                    "publisher": target["publisher"],
                    "iconUrl": f"https://raw.githubusercontent.com/Langegen/switch-game-collection/main/covers/{tid}.jpg" if tid != "0000000000000000" else "",
                    "variants": []
                }
                catalog["games"].append(game_entry)
                games_map[tid] = game_entry

            curr_variants = games_map[tid].setdefault("variants", [])
            existing_idx = next((i for i, v in enumerate(curr_variants) if v["id"] == var_dict["id"]), -1)
            if existing_idx >= 0:
                curr_variants[existing_idx] = var_dict
            else:
                curr_variants.append(var_dict)
            success_count += 1
            print(f"[+] Added: {target['name']} -> {tid}")
        except Exception as e:
            print(f"[!] Error processing {target['name']}: {e}")

    # Update metadata
    catalog["updatedAt"] = datetime.now(timezone.utc).isoformat()
    catalog["totalGames"] = len(catalog["games"])
    catalog["totalVariants"] = sum(len(g.get("variants", [])) for g in catalog["games"])

    with open(catalog_path, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"\n[+] Successfully registered {success_count} variants in catalog_after_dark.json!")
    print(f"[*] Total games: {catalog['totalGames']} | Total variants: {catalog['totalVariants']}")

    # Sync to GitHub on both after-dark and main
    gh_token, _ = GitHubPublisher.get_stored_credentials()
    repo_url = f"https://x-access-token:{gh_token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"
    
    subprocess.run(["git", "add", "catalog/data/catalog_after_dark.json"], check=True)
    subprocess.run(["git", "commit", "-m", f"feat(after-dark): batch 2 populate {success_count} mature themes (Xenoblade/Persona/NieR/Witcher/NIKKE)"], check=True)
    subprocess.run(["git", "push", repo_url, "main:after-dark"], check=True)
    subprocess.run(["git", "push", repo_url, "main"], check=True)
    print("\n[SUCCESS] Catalog pushed to both after-dark and main branches!")

if __name__ == "__main__":
    sys.exit(main())
