import sys
sys.path.insert(0, 'studio')
import json
from pathlib import Path
from h3h_studio.core.google_drive import GoogleDriveHelper
from h3h_studio.core.github_publisher import GitHubPublisher

CAT_PATH = Path('catalog/data/catalog.json')
with open(CAT_PATH, 'r', encoding='utf-8') as f:
    cat = json.load(f)

ALL_MW_VARIANTS = [
    {
        'id': 'var-mw-intro',
        'name': 'NFS MW: BMW M3 GTR Intro',
        'style': 'Cinematic',
        'version': '1.0',
        'url': 'https://drive.google.com/uc?export=download&id=1FsdxfgiWtZn5FZULpVsGXxmBMcK4IE4_',
        'previewUrl': 'https://drive.google.com/thumbnail?id=1FsdxfgiWtZn5FZULpVsGXxmBMcK4IE4_&sz=w640',
        'sizeBytes': 0,
        'sha256': '',
        'durationSec': 20.0,
        'author': 'Holy3holy-dev',
        'codec': 'h264',
        'width': 1280,
        'height': 720,
        'fps': 30.0,
        'hasAudio': False,
        'notes': 'Classic M3 GTR Cutscene Intro'
    },
    {
        'id': 'var-mw-blacklist',
        'name': 'NFS MW: Blacklist Pursuit',
        'style': 'Cinematic',
        'version': '1.0',
        'url': 'https://drive.google.com/uc?export=download&id=1vkXU_2eWSjAVAlYEYIZGFBMKINUUsAM-',
        'previewUrl': 'https://drive.google.com/thumbnail?id=1vkXU_2eWSjAVAlYEYIZGFBMKINUUsAM-&sz=w640',
        'sizeBytes': 0,
        'sha256': '',
        'durationSec': 20.0,
        'author': 'Holy3holy-dev',
        'codec': 'h264',
        'width': 1280,
        'height': 720,
        'fps': 30.0,
        'hasAudio': False,
        'notes': 'Rockport Blacklist Pursuit'
    },
    {
        'id': 'var-mw-highway',
        'name': 'NFS MW: Rockport Highway',
        'style': 'Gameplay',
        'version': '1.0',
        'url': 'https://drive.google.com/uc?export=download&id=185FEVgKFc4lp9sxh3Xz0Dqh-YKDytjnJ',
        'previewUrl': 'https://drive.google.com/thumbnail?id=185FEVgKFc4lp9sxh3Xz0Dqh-YKDytjnJ&sz=w640',
        'sizeBytes': 0,
        'sha256': '',
        'durationSec': 20.0,
        'author': 'Holy3holy-dev',
        'codec': 'h264',
        'width': 1280,
        'height': 720,
        'fps': 30.0,
        'hasAudio': False,
        'notes': 'High Speed Police Evade'
    },
    {
        'id': 'var-mw-chase',
        'name': 'NFS MW: Police Chase Action',
        'style': 'Action',
        'version': '1.0',
        'url': 'https://drive.google.com/uc?export=download&id=1PhhoQiuu8b9edT_EMAhVl6jrT7E0LU1s',
        'previewUrl': 'https://drive.google.com/thumbnail?id=1PhhoQiuu8b9edT_EMAhVl6jrT7E0LU1s&sz=w640',
        'sizeBytes': 0,
        'sha256': '',
        'durationSec': 20.0,
        'author': 'Holy3holy-dev',
        'codec': 'h264',
        'width': 1280,
        'height': 720,
        'fps': 30.0,
        'hasAudio': False,
        'notes': 'Heat Level 5 Police Pursuit'
    },
    {
        'id': 'var-mw-sgdb1',
        'name': 'NFS MW: Animated Artwork Hero',
        'style': 'Animated Art',
        'version': '1.0',
        'url': 'https://drive.google.com/uc?export=download&id=1dhnmAAjKPO_Wi41oh8Uo2NB5TCj_QMl8',
        'previewUrl': 'https://drive.google.com/thumbnail?id=1dhnmAAjKPO_Wi41oh8Uo2NB5TCj_QMl8&sz=w640',
        'sizeBytes': 0,
        'sha256': '',
        'durationSec': 20.0,
        'author': 'Holy3holy-dev',
        'codec': 'h264',
        'width': 1280,
        'height': 720,
        'fps': 30.0,
        'hasAudio': False,
        'notes': 'SteamGridDB Animated Hero Art'
    },
    {
        'id': 'var-mw-sgdb2',
        'name': 'NFS MW: City Skyline Neon',
        'style': 'Animated Art',
        'version': '1.0',
        'url': 'https://drive.google.com/uc?export=download&id=17Udt88Xnxflfjo8AmEdh5BtZk6beEQhz',
        'previewUrl': 'https://drive.google.com/thumbnail?id=17Udt88Xnxflfjo8AmEdh5BtZk6beEQhz&sz=w640',
        'sizeBytes': 0,
        'sha256': '',
        'durationSec': 20.0,
        'author': 'Holy3holy-dev',
        'codec': 'h264',
        'width': 1280,
        'height': 720,
        'fps': 30.0,
        'hasAudio': False,
        'notes': 'SteamGridDB City Skyline Neon'
    }
]

ALL_MW_TIDS = [
    '03DB18EF71F2C000',
    '01004E46534D0000',
    '01004D5700000000',
    '0100000000000001',
    '0100000000000004'
]

games_by_id = {g['titleId'].upper(): g for g in cat['games']}
for tid in ALL_MW_TIDS:
    if tid in games_by_id:
        games_by_id[tid]['title'] = 'Need for Speed: Most Wanted'
        games_by_id[tid]['variants'] = list(ALL_MW_VARIANTS)
    else:
        new_g = {
            'titleId': tid,
            'title': 'Need for Speed: Most Wanted',
            'publisher': 'Electronic Arts',
            'variants': list(ALL_MW_VARIANTS)
        }
        cat['games'].append(new_g)
        games_by_id[tid] = new_g

cat['totalGames'] = len(cat['games'])
cat['totalVariants'] = sum(len(g.get('variants', [])) for g in cat['games'])

with open(CAT_PATH, 'w', encoding='utf-8') as f:
    json.dump(cat, f, indent=2, ensure_ascii=False)

print(f"Catalog updated: {cat['totalGames']} games, {cat['totalVariants']} variants.")
gh_token, _ = GitHubPublisher.get_stored_credentials()
if gh_token:
    print('Syncing to GitHub...')
    GoogleDriveHelper.sync_catalog_to_github(CAT_PATH, token=gh_token, progress_cb=print)
    print('Sync complete!')
