import os
import sys
import json
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.google_drive import GoogleDriveClient

TOKEN = ""
FOLDER_ID = "1hI1klJ6t2ymVoBwGA6IzY79QMjp5dTJC"
LOCAL_DIR = Path(r"H:\H3H_Backgrounds") if Path(r"H:\H3H_Backgrounds").exists() else Path(r"e:\videofon\downloaded_official_backgrounds")

def main():
    headers = {"Authorization": f"Bearer {TOKEN}"}
    page_token = None
    drive_names = set()
    while True:
        url = f"https://www.googleapis.com/drive/v3/files?q='{FOLDER_ID}'+in+parents+and+trashed=false&pageSize=1000&fields=nextPageToken,files(name)"
        if page_token:
            url += f"&pageToken={page_token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for f in data.get('files', []):
                drive_names.add(f['name'])
            page_token = data.get('nextPageToken')
            if not page_token:
                break

    local_files = [f for f in LOCAL_DIR.iterdir() if f.suffix == ".mp4"]
    unuploaded = [f for f in local_files if f.name not in drive_names]

    print(f"Total unuploaded MP4s: {len(unuploaded)}")

    for idx, p in enumerate(unuploaded, 1):
        print(f"[{idx}/{len(unuploaded)}] Uploading {p.name} ({p.stat().st_size} bytes)...", flush=True)
        try:
            res = GoogleDriveClient.upload_file(p, FOLDER_ID, TOKEN)
            print(f"  -> Uploaded! Drive ID: {res.get('id')}", flush=True)
        except Exception as e:
            print(f"  -> Error: {e}", flush=True)

    print("Done uploading!")

if __name__ == "__main__":
    main()
