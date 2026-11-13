with open("scripts/generate_batch_hq_icons.py", "r", encoding="utf-8") as f:
    text = f.read()

old_chunk_fn = """def download_video_chunk(url: str, dest_path: Path, max_bytes: int = 3500000) -> bool:
    try:
        import requests
        headers = {"Range": f"bytes=0-{max_bytes}"}
        resp = requests.get(url, headers=headers, stream=True, timeout=12)
        if resp.status_code in [200, 206]:
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
            return dest_path.exists() and dest_path.stat().st_size >= 500000
    except Exception as e:
        print(f"    [!] Chunk download failed: {e}")
    return False"""

new_chunk_fn = """def download_full_video(url: str, dest_path: Path) -> bool:
    try:
        import requests
        with requests.get(url, stream=True, timeout=30) as resp:
            if resp.status_code == 200:
                with open(dest_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=512*1024):
                        if chunk:
                            f.write(chunk)
                return dest_path.exists() and dest_path.stat().st_size >= 100000
    except Exception as e:
        print(f"    [!] Video download failed: {e}")
    return False"""

text = text.replace(old_chunk_fn, new_chunk_fn)
text = text.replace("download_video_chunk(var_url, temp_src)", "download_full_video(var_url, temp_src)")

with open("scripts/generate_batch_hq_icons.py", "w", encoding="utf-8") as f:
    f.write(text)

print("[+] Successfully updated video downloader in scripts/generate_batch_hq_icons.py!")
