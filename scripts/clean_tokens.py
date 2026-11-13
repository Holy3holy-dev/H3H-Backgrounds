import re
from pathlib import Path

files = [
    Path("scripts/harvest_all_steamgriddb.py"),
    Path("scripts/harvest_steamgriddb.py"),
    Path("scripts/upload_batch_9.py"),
]

for p in files:
    if p.exists():
        text = p.read_text(encoding="utf-8")
        cleaned = re.sub(r'TOKEN\s*=\s*"ya29\.[^"]+"', 'TOKEN = ""', text)
        p.write_text(cleaned, encoding="utf-8")
        print(f"Cleaned {p}")
