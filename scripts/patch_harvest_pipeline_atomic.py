from pathlib import Path
import re

path = Path(r"e:\videofon\scripts\auto_harvest_pipeline.py")
text = path.read_text(encoding="utf-8")

# Helper definition
helper_def = '''def safe_write_json(path: Path, data: Any) -> None:
    """Atomically writes JSON to disk via a temporary file with retry for Windows file locking."""
    path = Path(path).resolve()
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    text_data = json.dumps(data, ensure_ascii=False, indent=2)
    
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(text_data)
        f.flush()

    for attempt in range(5):
        try:
            os.replace(tmp_path, path)
            return
        except OSError:
            if attempt == 4:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text_data)
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
                return
            time.sleep(0.15)
'''

# Replace save_harvest_log
old_save_re = re.compile(
    r'def save_harvest_log\(log_data: Dict\[str, Any\]\) -> None:\s+'
    r'log_data\["lastUpdated"\] = datetime\.now\(timezone\.utc\)\.isoformat\(\)\s+'
    r'log_data\["totalHarvested"\] = sum\(1 for v in log_data\.get\("items", \{\}\)\.values\(\) if v\.get\("status"\) == "published"\)\s+'
    r'with open\(LOG_PATH, "w", encoding="utf-8"\) as f:\s+'
    r'json\.dump\(log_data, f, ensure_ascii=False, indent=2\)',
    re.MULTILINE
)

new_save = helper_def + '\n\ndef save_harvest_log(log_data: Dict[str, Any]) -> None:\n' \
    '    log_data["lastUpdated"] = datetime.now(timezone.utc).isoformat()\n' \
    '    log_data["totalHarvested"] = sum(1 for v in log_data.get("items", {}).values() if v.get("status") == "published")\n' \
    '    safe_write_json(LOG_PATH, log_data)\n'

text, count = old_save_re.subn(new_save, text)
print(f"Replaced save_harvest_log: {count}")

# Replace atomic_save_game_to_catalog saving
old_cat_re = re.compile(
    r'with open\(CATALOG_PATH, "w", encoding="utf-8"\) as f:\s+'
    r'json\.dump\(cat_data, f, ensure_ascii=False, indent=2\)'
)
new_cat = 'safe_write_json(CATALOG_PATH, cat_data)'
text, count2 = old_cat_re.subn(new_cat, text)
print(f"Replaced catalog save: {count2}")

# Fix imports order at top
old_top_re = re.compile(
    r'import subprocess\s+'
    r'def check_has_audio\(file_path: Path\) -> bool:.*?'
    r'return False\s+',
    re.DOTALL
)
# Match everything up to studio import
full_top_re = re.compile(
    r'import subprocess.*?sys\.path\.insert\(0, str\(\(ROOT_DIR / "studio"\)\.resolve\(\)\)\)',
    re.DOTALL
)

new_full_top = '''import os
import sys
import json
import time
import re
import argparse
import tempfile
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

def check_has_audio(file_path: Path) -> bool:
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-select_streams", "a", str(file_path)],
            capture_output=True, text=True, timeout=5
        )
        return "codec_type=audio" in res.stdout
    except Exception:
        return False

"""
H3H-Backgrounds: Automated SteamGridDB Harvester Pipeline
Downloads, converts to 4IFIR 720p 30fps MP4, uploads to Google Drive in batches of 50,
logs everything into catalog/data/steamgriddb_harvest_log.json,
and pushes live catalog updates to GitHub.
"""

# Ensure studio is on path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str((ROOT_DIR / "studio").resolve()))'''

text, count3 = full_top_re.subn(new_full_top, text)
print(f"Replaced top imports: {count3}")

path.write_text(text, encoding="utf-8")
print("Done writing patched file!")
