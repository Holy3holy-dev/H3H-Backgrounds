import json
import sys
from pathlib import Path

sys.path.insert(0, 'studio')
from h3h_studio.core.google_drive import GoogleDriveHelper
from h3h_studio.core.github_publisher import GitHubPublisher

log_path = Path('catalog/data/steamgriddb_harvest_log.json')
cat_path = Path('catalog/data/catalog.json')

log = json.loads(log_path.read_text(encoding='utf-8'))
cat = json.loads(cat_path.read_text(encoding='utf-8'))

cat_games = {g['titleId'].upper(): g for g in cat['games']}
added_count = 0

for tid, item in log['items'].items():
    if item.get('status') != 'published':
        continue
    dl_url = item.get('downloadUrl')
    drive_id = item.get('driveFileId', '')
    if not dl_url or not drive_id:
        continue

    clean_name = item.get('cleanTitle') or item.get('gameTitle') or 'Default'
    v_obj = {
        'id': f'var-{drive_id[:8]}',
        'name': clean_name,
        'style': 'Animated Art',
        'version': '1.0',
        'url': dl_url,
        'previewUrl': f'https://drive.google.com/thumbnail?id={drive_id}&sz=w640',
        'sizeBytes': 0,
        'sha256': '',
        'durationSec': 20.0,
        'author': 'Holy3holy-dev',
        'codec': 'h264',
        'width': 1280,
        'height': 720,
        'fps': 30.0,
        'hasAudio': False,
        'notes': f'SteamGridDB Animated: {clean_name}'
    }

    if tid in cat_games:
        existing_vars = cat_games[tid].setdefault('variants', [])
        if not any(v.get('url') == dl_url for v in existing_vars):
            existing_vars.append(v_obj)
    else:
        new_g = {
            'titleId': tid,
            'title': item.get('gameTitle', 'Unknown Game'),
            'publisher': 'Unknown',
            'variants': [v_obj]
        }
        cat_games[tid] = new_g
        cat['games'].append(new_g)
        added_count += 1

cat['totalGames'] = len(cat['games'])
cat['totalVariants'] = sum(len(g.get('variants', [])) for g in cat['games'])
cat_path.write_text(json.dumps(cat, indent=2, ensure_ascii=False), encoding='utf-8')
print(f'Added {added_count} games from log. Total games now: {cat["totalGames"]}, variants: {cat["totalVariants"]}')

token, _ = GitHubPublisher.get_stored_credentials()
if token:
    GoogleDriveHelper.sync_catalog_to_github(cat_path, token=token, progress_cb=print)
    GoogleDriveHelper.sync_file_to_github(
        log_path,
        repo_path='catalog/data/steamgriddb_harvest_log.json',
        token=token,
        commit_message='feat(catalog): sync batch of harvested backgrounds to catalog',
        progress_cb=print
    )
    print('Catalog and harvest log synced live to GitHub!')
