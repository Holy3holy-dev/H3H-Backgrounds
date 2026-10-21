import subprocess
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

cmd = [
    'C:/Users/HL/AppData/Local/Python/bin/python.exe', '-m', 'yt_dlp',
    '--dump-json', '--default-search', 'ytsearch3', '--no-playlist',
    'Need for Speed Underground intro 1080p 60fps'
]
p = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
for line in p.stdout.splitlines():
    if line.startswith('{'):
        d = json.loads(line)
        print(f"{d.get('id')} | {d.get('title')} ({d.get('duration')}s)")
