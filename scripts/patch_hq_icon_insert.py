with open("scripts/expand_new_switch_titles.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for idx, line in enumerate(lines):
    if line.strip() == "# Refresh token right before upload":
        icon_block = """        # Generate 256x256 HQ Video Icon from encoded 720p video
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

"""
        new_lines.append(icon_block)
        new_lines.append(line)
    elif "var_id = f\"v_{hashlib.md5(f'{tid}_{source_url}'.encode()).hexdigest()[:8]}\"" in line:
        upload_icon_block = """        icon_url = None
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

"""
        new_lines.append(upload_icon_block)
        new_lines.append(line)
    elif line.strip() == '"notes": f"Switch 720p 30fps H264 | {var_name[:40]}"':
        new_lines.append(line)
        prop_block = """        }

        if icon_url:
            new_variant["hasIcon"] = True
            new_variant["iconUrl"] = icon_url
            new_variant["iconSizeBytes"] = icon_size
            new_variant["iconCodec"] = "h264"
            new_variant["iconWidth"] = 256
            new_variant["iconHeight"] = 256"""
        # Note: the closing brace is on next line, so we handle it accordingly
    else:
        new_lines.append(line)

with open("scripts/expand_new_switch_titles.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("[+] Successfully inserted HQ video icon generation into expand_new_switch_titles.py!")
