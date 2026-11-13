with open("scripts/expand_new_switch_titles.py", "r", encoding="utf-8") as f:
    code = f.read()

target = """        # Refresh token right before upload
        gdrive_token = get_gdrive_token() or gdrive_token
        print(f"  [*] Uploading {out_mp4.name} ({out_mp4.stat().st_size / 1024 / 1024:.2f} MB) to Google Drive...")
        try:
            up_res = GoogleDriveClient.upload_file(out_mp4, GDRIVE_FOLDER_ID, gdrive_token)
            file_id = up_res.get("fileId")
            direct_url = up_res.get("directUrl") or f"https://drive.google.com/uc?export=download&id={file_id}"
            preview_url = up_res.get("previewUrl") or f"https://drive.google.com/thumbnail?id={file_id}&sz=w640"
        except Exception as e:
            print(f"  [-] Upload error: {e}")
            continue

        sha256_hex = compute_sha256(out_mp4)
        size_bytes = out_mp4.stat().st_size
        has_aud = check_has_audio(out_mp4)
        var_id = f"v_{hashlib.md5(f'{tid}_{source_url}'.encode()).hexdigest()[:8]}"

        new_variant = {
            "id": var_id,
            "name": var_name[:48],
            "style": style,
            "version": "1.0",
            "url": direct_url,
            "previewUrl": preview_url,
            "sizeBytes": size_bytes,
            "sha256": sha256_hex,
            "durationSec": 24.0,
            "author": author,
            "codec": "h264",
            "width": 1280,
            "height": 720,
            "fps": 30.0,
            "hasAudio": has_aud,
            "notes": f"Switch 720p 30fps H264 | {var_name[:40]}"
        }"""

replacement = """        # Generate 256x256 HQ Video Icon from the encoded video (Lanczos + Unsharp)
        out_icon = P720_DIR / f"{tid}_icon_hq.mp4"
        icon_ok = False
        try:
            cmd = [
                "ffmpeg", "-y", "-ss", "2", "-i", str(out_mp4), "-t", "5",
                "-vf", "crop=ih:ih:(iw-ih)/2:0,scale=256:256:flags=lanczos,unsharp=3:3:0.8:3:3:0.0",
                "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.0",
                "-pix_fmt", "yuv420p", "-b:v", "1200k", "-maxrate", "1500k", "-bufsize", "2000k",
                "-an", "-movflags", "+faststart", str(out_icon)
            ]
            r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
            icon_ok = (r.returncode == 0 and out_icon.exists() and out_icon.stat().st_size > 10000)
            if icon_ok:
                print(f"  [+] Generated 256x256 HQ Video Icon ({out_icon.stat().st_size / 1024:.1f} KB)")
        except Exception as ie:
            print(f"  [-] Icon gen error: {ie}")
            icon_ok = False

        # Refresh token right before upload
        gdrive_token = get_gdrive_token() or gdrive_token
        print(f"  [*] Uploading {out_mp4.name} ({out_mp4.stat().st_size / 1024 / 1024:.2f} MB) to Google Drive...")
        try:
            up_res = GoogleDriveClient.upload_file(out_mp4, GDRIVE_FOLDER_ID, gdrive_token)
            file_id = up_res.get("fileId")
            direct_url = up_res.get("directUrl") or f"https://drive.google.com/uc?export=download&id={file_id}"
            preview_url = up_res.get("previewUrl") or f"https://drive.google.com/thumbnail?id={file_id}&sz=w640"
        except Exception as e:
            print(f"  [-] Upload error: {e}")
            continue

        icon_url = None
        icon_size = 0
        if icon_ok:
            try:
                print(f"  [*] Uploading Video Icon {out_icon.name} to Google Drive...")
                up_icon = GoogleDriveClient.upload_file(out_icon, GDRIVE_FOLDER_ID, gdrive_token)
                icon_file_id = up_icon.get("fileId")
                icon_url = up_icon.get("directUrl") or f"https://drive.google.com/uc?export=download&id={icon_file_id}"
                icon_size = out_icon.stat().st_size
                print(f"  [+] Uploaded Video Icon: {icon_file_id}")
            except Exception as e:
                print(f"  [-] Icon upload error: {e}")
            try:
                out_icon.unlink()
            except Exception:
                pass

        sha256_hex = compute_sha256(out_mp4)
        size_bytes = out_mp4.stat().st_size
        has_aud = check_has_audio(out_mp4)
        var_id = f"v_{hashlib.md5(f'{tid}_{source_url}'.encode()).hexdigest()[:8]}"

        new_variant = {
            "id": var_id,
            "name": var_name[:48],
            "style": style,
            "version": "1.0",
            "url": direct_url,
            "previewUrl": preview_url,
            "sizeBytes": size_bytes,
            "sha256": sha256_hex,
            "durationSec": 24.0,
            "author": author,
            "codec": "h264",
            "width": 1280,
            "height": 720,
            "fps": 30.0,
            "hasAudio": has_aud,
            "notes": f"Switch 720p 30fps H264 | {var_name[:40]}"
        }

        if icon_url:
            new_variant["hasIcon"] = True
            new_variant["iconUrl"] = icon_url
            new_variant["iconSizeBytes"] = icon_size
            new_variant["iconCodec"] = "h264"
            new_variant["iconWidth"] = 256
            new_variant["iconHeight"] = 256"""

if target in code:
    code = code.replace(target, replacement)
    with open("scripts/expand_new_switch_titles.py", "w", encoding="utf-8") as f:
        f.write(code)
    print("[+] Successfully patched expand_new_switch_titles.py for HQ video icons!")
else:
    print("[-] Target block not found in expand_new_switch_titles.py")
