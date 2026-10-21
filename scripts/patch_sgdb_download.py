from pathlib import Path

p = Path("studio/h3h_studio/core/steamgriddb.py")
text = p.read_text(encoding="utf-8")

old_snippet = '''        try:
            req = urllib.request.Request(art_url, headers={"User-Agent": "H3H-Studio/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                with open(tmp_in_path, "wb") as f:
                    f.write(resp.read())

            if not tmp_in_path.exists() or tmp_in_path.stat().st_size < 1000:
                logger.error("Downloaded asset is empty or too small: %s", art_url)
                return False'''

new_snippet = '''        try:
            req = urllib.request.Request(art_url, headers={"User-Agent": "H3H-Studio/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    with open(tmp_in_path, "wb") as f:
                        f.write(resp.read())
            except urllib.error.HTTPError as he:
                logger.warning("HTTP error downloading %s: %s", art_url, he)
                return False
            except Exception as e:
                logger.warning("Network error downloading %s: %s", art_url, e)
                return False

            if not tmp_in_path.exists() or tmp_in_path.stat().st_size < 1000:
                logger.error("Downloaded asset is empty or too small: %s", art_url)
                return False'''

assert old_snippet in text, "old_snippet not found in steamgriddb.py"
text = text.replace(old_snippet, new_snippet)
p.write_text(text, encoding="utf-8")
print("download_and_convert now catches HTTP and network errors safely!")
