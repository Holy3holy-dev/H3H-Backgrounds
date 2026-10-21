"""
Upload Batch 9 (46 files) to Google Drive and sync catalog.json to GitHub.
"""

import os
import sys
import json
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.google_drive import GoogleDriveClient, GoogleDriveHelper
from h3h_studio.core.github_publisher import GitHubPublisher

TOKEN = "ya29.a0AX07CmuycNHtflqEeffh6XtbRgDmkTxLMoFcfPfk7XbXeAhJYE0voc0R6FT8cKBJCb14bSwIIrkDiH6q4TVHqB2RlS_FJ1NDxvQR8aNUc6akfxSEW4l29zPbik7WjPDVBonvWDuczIavEbNQcCgCvMRKqSZBDArZbTCVsMqVn-9GrR43xyb7FzkVvTKUrksapAs8G3kaCgYKAbASARISFQHGX2Mit3ABcTJRFKxY6VHf_HLbow0206"
FOLDER_ID = "1hI1klJ6t2ymVoBwGA6IzY79QMjp5dTJC"
LOCAL_DIR = Path(r"e:\videofon\downloaded_official_backgrounds")

def get_existing_drive_files():
    headers = {"Authorization": f"Bearer {TOKEN}"}
    page_token = None
    drive_files = {}
    while True:
        url = f"https://www.googleapis.com/drive/v3/files?q='{FOLDER_ID}'+in+parents+and+trashed=false&pageSize=1000&fields=nextPageToken,files(id,name,size)"
        if page_token:
            url += f"&pageToken={page_token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for f in data.get('files', []):
                drive_files[f['name']] = f['id']
            page_token = data.get('nextPageToken')
            if not page_token:
                break
    return drive_files

def main():
    print("=== Step 1: Querying existing files in Google Drive folder ===")
    drive_files = get_existing_drive_files()
    print(f"Existing files on Drive: {len(drive_files)}")

    local_mp4s = [f for f in LOCAL_DIR.iterdir() if f.suffix == ".mp4"]
    to_upload = [f for f in local_mp4s if f.name not in drive_files]
    print(f"Local files to upload: {len(to_upload)}")

    uploaded_count = 0
    for idx, filepath in enumerate(to_upload, 1):
        print(f"\n[{idx}/{len(to_upload)}] Uploading {filepath.name} ({filepath.stat().st_size} bytes)...")
        try:
            res = GoogleDriveClient.upload_file(
                file_path=filepath,
                folder_id=FOLDER_ID,
                token=TOKEN
            )
            print(f"  -> Uploaded successfully! ID: {res.get('id')}")
            uploaded_count += 1
        except Exception as e:
            print(f"  -> Upload ERROR: {e}")
            time.sleep(2)

    print(f"\n=== Step 2: Running One-Click Catalog Sync (Google Drive -> catalog.json) ===")
    token, _ = GitHubPublisher.get_stored_credentials()
    sync_res = GoogleDriveHelper.one_click_sync(
        folder_id=FOLDER_ID,
        drive_token=TOKEN,
        github_token=token,
        repo_full_name="Holy3holy-dev/H3H-Backgrounds",
        commit_message=f"feat(catalog): sync Batch 9 backgrounds to catalog ({uploaded_count} new files)"
    )
    print("Sync Result:", sync_res)

if __name__ == "__main__":
    main()
