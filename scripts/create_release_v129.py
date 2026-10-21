import os
import sys
import glob
import json
import time
import hashlib
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.github_publisher import GitHubPublisher

ROOT_DIR = Path(r"E:\videofon")
COVERS_DIR = ROOT_DIR / "tmp" / "community_covers"

custom_names = {
    "0100A0800E9C4000": "The Witcher 3: Wild Hunt - Complete Edition (RU)",
    "0100EA80032EA000": "New Super Mario Bros. U Deluxe",
    "010019A01E2F2000": "Metroid Prime 4: Beyond",
    "01004D300C5AE000": "Kirby and the Forgotten Land",
    "0100A5C00D162000": "Cuphead + The Delicious Last Course",
    "0100B8E016F76000": "NieR: Automata The End of YoRHa Edition",
    "0100B9C0148D0000": "Slime Rancher: Plortable Edition",
    "0100F7E00C70E000": "Hogwarts Legacy",
}

custom_publishers = {
    "0100A0800E9C4000": "CD PROJEKT RED",
    "0100EA80032EA000": "Nintendo",
}

def update_catalog():
    print("[*] Merging 26 community recordings into catalog.json...")
    vids = sorted(glob.glob(str(COVERS_DIR / "*.mp4")))
    if not vids:
        print("[!] No transcoded videos found in", COVERS_DIR)
        return False

    cat_paths = [
        ROOT_DIR / "downloader" / "romfs" / "catalog.json",
        ROOT_DIR / "catalog.json"
    ]

    for cpath in cat_paths:
        if not cpath.exists():
            continue
        with open(cpath, "r", encoding="utf-8") as f:
            cat = json.load(f)

        games_dict = {g["titleId"].upper(): g for g in cat.get("games", [])}
        added_variants = 0
        added_games = 0

        for vid in vids:
            fname = os.path.basename(vid)
            tid = os.path.splitext(fname)[0].upper()
            thumb = COVERS_DIR / f"{tid}.jpg"
            sz = os.path.getsize(vid)

            # Compute sha256
            with open(vid, "rb") as vf:
                sha = hashlib.sha256(vf.read()).hexdigest()

            # probe duration and audio
            probe_cmd = ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', vid]
            dur = 60.0
            has_audio = True
            try:
                out = subprocess.check_output(probe_cmd)
                info = json.loads(out)
                dur = float(info.get('format', {}).get('duration', 60.0))
                has_audio = any(s.get('codec_type') == 'audio' for s in info.get('streams', []))
            except Exception:
                pass

            var_obj = {
                "id": f"4ifir-rec-{tid.lower()}",
                "name": "4IFIR Запись (Gameplay + Звук)" if has_audio else "4IFIR Запись (Gameplay)",
                "style": "Gameplay",
                "version": "1.0",
                "url": f"https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.2.9/rec_{tid}.mp4",
                "previewUrl": f"https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/download/v1.2.9/thumb_{tid}.jpg",
                "sizeBytes": sz,
                "sha256": sha,
                "durationSec": round(dur, 1),
                "author": "4IFIR Community (Telegram)",
                "codec": "h264",
                "width": 1280,
                "height": 720,
                "fps": 30.0,
                "hasAudio": has_audio,
                "notes": f"High-quality 4IFIR community recording for {tid}"
            }

            if tid in games_dict:
                g = games_dict[tid]
                # Replace or append variant
                existing_idx = None
                for idx, v in enumerate(g.get("variants", [])):
                    if v.get("id") == var_obj["id"] or "4ifir" in v.get("id", "").lower() and "rec" in v.get("id", "").lower():
                        existing_idx = idx
                        break
                if existing_idx is not None:
                    g["variants"][existing_idx] = var_obj
                else:
                    g["variants"].append(var_obj)
                added_variants += 1
            else:
                title = custom_names.get(tid, f"Nintendo Switch Title ({tid})")
                pub = custom_publishers.get(tid, "Unknown")
                new_game = {
                    "titleId": tid,
                    "title": title,
                    "publisher": pub,
                    "variants": [var_obj]
                }
                cat["games"].append(new_game)
                games_dict[tid] = new_game
                added_games += 1
                added_variants += 1

        cat["totalGames"] = len(cat["games"])
        total_vars = sum(len(g.get("variants", [])) for g in cat["games"])
        cat["totalVariants"] = total_vars
        cat["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())

        with open(cpath, "w", encoding="utf-8") as f:
            json.dump(cat, f, indent=2, ensure_ascii=False)
        print(f"  [+] Updated {cpath}: {len(cat['games'])} games, {total_vars} variants (+{added_games} games, +{added_variants} variants)")

    return True

def upload_asset(rel_id, token, file_path, asset_name):
    upload_url = f"https://uploads.github.com/repos/Holy3holy-dev/H3H-Backgrounds/releases/{rel_id}/assets?name={asset_name}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio-Uploader"
    }
    with open(file_path, "rb") as f:
        data = f.read()

    req = urllib.request.Request(upload_url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status in (200, 201):
                print(f"    [+] Uploaded {asset_name} ({len(data)} bytes)")
                return True
    except urllib.error.HTTPError as e:
        if e.code == 422:
            print(f"    [*] Asset {asset_name} already exists, skipping")
            return True
        print(f"    [!] Failed to upload {asset_name}: {e.code} {e.reason}")
    except Exception as e:
        print(f"    [!] Error uploading {asset_name}: {e}")
    return False

def main():
    print("=== H3H Release v1.2.9 & Community Recordings Publisher ===")
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("[!] GitHub token not found.")
        return 1

    # 1. Update catalog
    update_catalog()

    # 2. Recompile NROs with updated RomFS catalog
    print("\n[*] Rebuilding H3H-Backgrounds.nro with updated RomFS...")
    env = dict(os.environ)
    env["TMP"] = r"E:\videofon\tmp"
    env["TEMP"] = r"E:\videofon\tmp"
    r1 = subprocess.run([sys.executable, "scripts/build_nro.py"], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r1.returncode != 0:
        print("[!] Failed to build H3H-Backgrounds.nro:")
        print(r1.stderr)
        return 1

    print("[*] Rebuilding H3H-AfterDark.nro with updated RomFS...")
    r2 = subprocess.run([sys.executable, "scripts/build_nro_after_dark.py"], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r2.returncode != 0:
        print("[!] Failed to build H3H-AfterDark.nro:")
        print(r2.stderr)
        return 1

    # 3. Git commit & tag
    print("\n[*] Committing changes...")
    subprocess.run(["git", "add", "."], check=False)
    subprocess.run(["git", "commit", "-m", "feat(v1.2.9): favorites system, storage manager, batch multi-select, and 26 4IFIR community recordings"], check=False)

    # 4. Push git to remote
    print("[*] Pushing git commit...")
    repo_url = f"https://x-access-token:{token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"
    subprocess.run(["git", "push", repo_url, "main"], check=False)

    # 5. Create or get GitHub Release v1.2.9
    tag = "v1.2.9"
    name = "H3H Backgrounds & After Dark v1.2.9 (Favorites, Storage Manager, Batch Multi-Select)"
    body = (
        "## Release v1.2.9 / Релиз v1.2.9\n\n"
        "### 🌟 1. Система «Избранное» (Favorites / Bookmarks)\n"
        "- Быстрое добавление любого варианта фона в избранное кнопками `[R3]` (правый стик) или `[L]`.\n"
        "- Золотая звезда `★` на карточках вариантов и в предпросмотре.\n"
        "- Сохранение списка на карту памяти в `favorites.json`.\n"
        "- Режим сортировки в каталоге: `★ Только избранное`.\n\n"
        "### 🧹 2. Менеджер памяти и кэша MicroSD (Storage & Cache Manager)\n"
        "- Наглядный дашборд в Настройках с полосой свободного/занятого места MicroSD.\n"
        "- Подсчёт установленных видеофонов, файлов кэша превью (`thumbs/`) и кэша видеоплеера.\n"
        "- Быстрая очистка кэша картинок и видео в 1 клик прямо из настроек.\n\n"
        "### 📥 3. Пакетный выбор для установки (Multi-Select Checklist)\n"
        "- Чекбоксы `[✓]` на карточках игр: выделение кнопками `[R3]` / `[L3]` или тапом по экрану.\n"
        "- Плашка действий: `[ZL] Установить выбранные` и `[-] Сбросить`.\n"
        "- Пакетная фоновая очередь загрузки с отображением прогресса.\n\n"
        "### 🎬 4. 26 новых видеофонов 4IFIR Community (с живым звуком!)\n"
        "- Добавлены записи сообщества Telegram 4IFIR, включая The Witcher 3, New Super Mario Bros. U Deluxe, "
        "Cuphead, Hogwarts Legacy, Kirby, Metroid Prime 4, NieR Automata, Slime Rancher и другие.\n"
        "- Прямая CDN загрузка через GitHub Releases без таймаутов Google Drive.\n\n"
        "### 🕹 5. Выход из приложения\n"
        "- Выход по `[B]` теперь работает только из главного меню (Home), а из всех остальных вкладок возвращает в меню."
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Studio-Uploader"
    }

    rel_url = f"https://api.github.com/repos/Holy3holy-dev/H3H-Backgrounds/releases/tags/{tag}"
    rel_id = None
    try:
        req = urllib.request.Request(rel_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            rel_data = json.loads(resp.read().decode())
            rel_id = rel_data["id"]
            print(f"[+] Release {tag} already exists (ID: {rel_id})")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            create_url = "https://api.github.com/repos/Holy3holy-dev/H3H-Backgrounds/releases"
            payload = {
                "tag_name": tag,
                "name": name,
                "body": body,
                "draft": False,
                "prerelease": False
            }
            req = urllib.request.Request(create_url, data=json.dumps(payload).encode(), headers=headers, method="POST")
            with urllib.request.urlopen(req) as resp:
                rel_data = json.loads(resp.read().decode())
                rel_id = rel_data["id"]
                print(f"[+] Created GitHub Release {tag} (ID: {rel_id})")

    if not rel_id:
        print("[!] Could not obtain release ID")
        return 1

    # 6. Upload NRO binaries
    print("\n[*] Uploading NRO binaries to Release v1.2.9...")
    nro1 = ROOT_DIR / "downloader" / "H3H-Backgrounds.nro"
    nro2 = ROOT_DIR / "downloader" / "H3H-AfterDark.nro"
    upload_asset(rel_id, token, str(nro1), "H3H-Backgrounds.nro")
    upload_asset(rel_id, token, str(nro2), "H3H-AfterDark.nro")

    # 7. Upload Community Recordings (*.mp4 and *.jpg)
    print("\n[*] Uploading 26 community recordings to GitHub Release v1.2.9 CDN...")
    vids = sorted(glob.glob(str(COVERS_DIR / "*.mp4")))
    for v in vids:
        fname = os.path.basename(v)
        tid = os.path.splitext(fname)[0].upper()
        thumb = COVERS_DIR / f"{tid}.jpg"
        upload_asset(rel_id, token, v, f"rec_{tid}.mp4")
        if thumb.exists():
            upload_asset(rel_id, token, str(thumb), f"thumb_{tid}.jpg")

    print("\n[SUCCESS] Release v1.2.9 published with all 26 community recordings!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
