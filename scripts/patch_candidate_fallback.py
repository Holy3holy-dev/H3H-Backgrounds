from pathlib import Path

p = Path("scripts/auto_harvest_pipeline.py")
text = p.read_text(encoding="utf-8")

old_block = '''            # Look for animated Heroes first (wide 16:9), then animated Grids
            heroes = client.get_animated_heroes(game_id)
            art_url = None
            art_type = None

            if heroes:
                art_url = heroes[0]["url"]
                art_type = "hero"
                print(f"  [+] Found animated Hero ({len(heroes)} available)")
            else:
                grids = client.get_animated_grids(game_id)
                if grids:
                    art_url = grids[0]["url"]
                    art_type = "grid"
                    print(f"  [+] Found animated Grid ({len(grids)} available)")

            if not art_url:
                print(f"  [-] No animated Hero or Grid found on SGDB for '{game_name}'")
                log_data["items"][tid] = {
                    "titleId": tid,
                    "gameTitle": raw_title,
                    "sgdbGameId": game_id,
                    "sgdbName": game_name,
                    "status": "no_animated_art",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                save_harvest_log(log_data)
                continue

            # Convert to 4IFIR MP4 (1280x720, 30fps, H.264, -an, <=10MB)
            safe_name = re.sub(r'[^0-9A-Za-z_-]', '_', clean_title)[:40]
            out_file = OUTPUT_DIR / f"{tid}_{safe_name}.mp4"

            print(f"  [*] Downloading & converting to 4IFIR 720p 30fps MP4...")
            ok = client.download_and_convert(art_url, out_file)
            if not ok or not out_file.exists() or out_file.stat().st_size < 1000:
                print(f"  [-] Conversion failed for {art_url}")
                continue

            file_size = out_file.stat().st_size
            print(f"  [✓] Converted: {out_file.name} ({file_size} bytes)")'''

new_block = '''            # Collect animated candidate artworks (heroes first, then grids)
            candidates = []
            try:
                for h in client.get_animated_heroes(game_id):
                    u = h.get("url")
                    if u:
                        candidates.append(("hero", u))
                for g in client.get_animated_grids(game_id):
                    u = g.get("url")
                    if u:
                        candidates.append(("grid", u))
            except Exception as e:
                print(f"  [-] Error querying assets for '{game_name}': {e}")

            if not candidates:
                print(f"  [-] No animated Hero or Grid found on SGDB for '{game_name}'")
                log_data["items"][tid] = {
                    "titleId": tid,
                    "gameTitle": raw_title,
                    "sgdbGameId": game_id,
                    "sgdbName": game_name,
                    "status": "no_animated_art",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                save_harvest_log(log_data)
                continue

            safe_name = re.sub(r'[^0-9A-Za-z_-]', '_', clean_title)[:40]
            out_file = OUTPUT_DIR / f"{tid}_{safe_name}.mp4"

            converted_art_type = None
            used_art_url = None

            print(f"  [*] Downloading & converting ({len(candidates)} candidates available)...")
            for art_type, art_url in candidates:
                try:
                    ok = client.download_and_convert(art_url, out_file)
                    if ok and out_file.exists() and out_file.stat().st_size >= 1000:
                        converted_art_type = art_type
                        used_art_url = art_url
                        break
                    else:
                        print(f"  [-] Candidate {art_url[:60]}... failed or returned error, trying next...")
                except Exception as ce:
                    print(f"  [-] Error on {art_url[:60]}...: {ce}, trying next...")

            if not converted_art_type or not out_file.exists() or out_file.stat().st_size < 1000:
                print(f"  [-] All artwork candidates failed for '{game_name}'")
                log_data["items"][tid] = {
                    "titleId": tid,
                    "gameTitle": raw_title,
                    "sgdbGameId": game_id,
                    "sgdbName": game_name,
                    "status": "no_animated_art",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                save_harvest_log(log_data)
                continue

            art_type = converted_art_type
            art_url = used_art_url
            file_size = out_file.stat().st_size
            print(f"  [✓] Converted ({art_type}): {out_file.name} ({file_size} bytes)")'''

assert old_block in text, "old_block not found in auto_harvest_pipeline.py"
text = text.replace(old_block, new_block)
p.write_text(text, encoding="utf-8")
print("Candidate fallback and error resilience successfully applied to auto_harvest_pipeline.py!")
