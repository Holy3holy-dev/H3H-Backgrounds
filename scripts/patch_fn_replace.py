with open("scripts/generate_batch_hq_icons.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
for idx, line in enumerate(lines):
    if line.startswith("def download_video_chunk"):
        fn = """def download_full_video(url: str, dest_path: Path) -> bool:
    try:
        import requests
        with requests.get(url, stream=True, timeout=25) as r:
            if r.status_code == 200:
                with open(dest_path, "wb") as f_out:
                    for chunk in r.iter_content(chunk_size=512*1024):
                        if chunk:
                            f_out.write(chunk)
                return dest_path.exists() and dest_path.stat().st_size >= 100000
    except Exception as e:
        print(f"    [!] Video download failed: {e}")
    return False

"""
        new_lines.append(fn)
        skip = True
    elif skip and line.startswith("def transcode_hq_video_icon"):
        skip = False
        new_lines.append(line)
    elif not skip:
        new_lines.append(line)

with open("scripts/generate_batch_hq_icons.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("[+] Successfully replaced download function!")
