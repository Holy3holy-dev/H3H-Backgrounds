import sys
import json
import time
from pathlib import Path

sys.path.insert(0, 'studio')
from h3h_studio.core.google_drive import GoogleDriveHelper, GoogleDriveClient

cat_path = Path("catalog/data/catalog_after_dark.json")
cat = json.loads(cat_path.read_text(encoding="utf-8"))

cfg = GoogleDriveHelper.get_stored_config()
tok = GoogleDriveHelper.refresh_access_token(cfg.get('refresh_token'))

all_fids = []
for g in cat.get('games', []):
    for v in g.get('variants', []):
        url = v.get('url', '')
        fid = GoogleDriveHelper.extract_file_id(url)
        if fid:
            all_fids.append((v['id'], fid))

print(f"Checking permissions for {len(all_fids)} files...")
for vid_id, fid in all_fids:
    for attempt in range(1, 4):
        try:
            ok = GoogleDriveClient.make_public(fid, tok)
            print(f"[OK] {vid_id} -> {fid}")
            break
        except Exception as e:
            if attempt == 3:
                print(f"[FAIL] {vid_id} -> {e}")
            else:
                time.sleep(2)
