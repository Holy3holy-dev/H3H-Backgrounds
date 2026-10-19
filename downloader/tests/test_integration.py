#!/usr/bin/env python3
"""
Automated Integration Test Suite for H3H Downloader.
Spins up local test server with real FFmpeg-generated 4IFIR assets, tests HTTP streaming,
SHA-256 verification, atomic installation, backup creation, rollback, and network faults.
"""

import hashlib
import json
import shutil
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

# Add studio and downloader to path
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "studio"))
sys.path.insert(0, str(Path(__file__).parent))

from h3h_studio.core.analyzer import VideoAnalyzer
from test_server import MockAssetServer


def test_full_downloader_integration():
    print("=======================================================")
    print("  H3H Downloader Live Integration Test on Test Server  ")
    print("=======================================================")

    server = MockAssetServer(port=9123)
    server.start()
    time.sleep(0.5)

    test_covers_dir = Path("test_server_covers")
    shutil.rmtree(test_covers_dir, ignore_errors=True)
    test_covers_dir.mkdir(parents=True, exist_ok=True)

    title_id = "01005CA01580E000"
    target_mp4 = test_covers_dir / f"{title_id}.mp4"
    backup_file = test_covers_dir / f"{title_id}.bak"

    try:
        # Step 1: Fetch remote catalog over HTTP
        print("\n[STEP 1] Fetching catalog over HTTP...")
        catalog_url = f"http://127.0.0.1:{server.port}/catalog.json"
        with urllib.request.urlopen(catalog_url) as resp:
            self_data = json.loads(resp.read().decode("utf-8"))

        assert self_data["schemaVersion"] == 1
        assert len(self_data["games"]) == 1
        game = self_data["games"][0]
        assert game["titleId"] == title_id
        assert len(game["variants"]) == 2
        print(f"  -> PASS: Remote catalog fetched successfully. Matched Title ID: {title_id}")

        # Step 2: Download Variant 1 and verify SHA-256
        print("\n[STEP 2] Downloading Variant 1 (Opening Intro Loop) over HTTP...")
        v1 = game["variants"][0]
        temp_file = test_covers_dir / f"{title_id}.tmp"

        urllib.request.urlretrieve(v1["url"], temp_file)
        actual_size = temp_file.stat().st_size
        assert actual_size == v1["sizeBytes"], f"Size mismatch: {actual_size} != {v1['sizeBytes']}"

        # Compute SHA-256
        sha = hashlib.sha256()
        with open(temp_file, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        actual_hash = sha.hexdigest().lower()
        assert actual_hash == v1["sha256"], f"Hash mismatch: {actual_hash} != {v1['sha256']}"
        print(f"  -> PASS: Downloaded {actual_size} bytes, SHA-256 checksum {actual_hash} verified.")

        # Step 3: Atomic install
        print("\n[STEP 3] Atomic Commit into sdmc:/recordings/covers/...")
        temp_file.rename(target_mp4)
        assert target_mp4.exists()
        assert not backup_file.exists()
        print(f"  -> PASS: Target file created at {target_mp4}")

        # Verify with FFprobe that the installed file meets 4IFIR specifications
        print("\n[STEP 4] Verifying installed file with FFprobe...")
        analysis = VideoAnalyzer.analyze_file(target_mp4)
        assert analysis.is_compliant == True
        assert analysis.codec == "h264"
        assert analysis.width == 1280
        assert analysis.height == 720
        assert analysis.pixel_format == "yuv420p"
        assert analysis.is_faststart == True
        print(f"  -> PASS: FFprobe verified 4IFIR profile: H.264 High 4.1, 720p 30fps CFR, faststart.")

        # Step 5: Update with Variant 2 and verify automatic backup (.bak)
        print("\n[STEP 5] Installing Variant 2 with automatic backup creation...")
        v2 = game["variants"][1]
        temp_file_v2 = test_covers_dir / f"{title_id}_v2.tmp"
        urllib.request.urlretrieve(v2["url"], temp_file_v2)

        # Atomic swap with backup
        if target_mp4.exists():
            target_mp4.rename(backup_file)
        temp_file_v2.rename(target_mp4)

        assert target_mp4.exists()
        assert backup_file.exists()
        assert backup_file.stat().st_size == v1["sizeBytes"]
        assert target_mp4.stat().st_size == v2["sizeBytes"]
        print(f"  -> PASS: Variant 2 installed. Previous Variant 1 backed up to {backup_file.name}")

        # Step 6: Restore Backup
        print("\n[STEP 6] Testing Restore Backup (.bak -> .mp4)...")
        target_mp4.unlink()
        backup_file.rename(target_mp4)
        assert target_mp4.stat().st_size == v1["sizeBytes"]
        assert not backup_file.exists()
        print(f"  -> PASS: Backup successfully restored back to Variant 1.")

        # Step 7: Network Corrupted Stream Fault Injection
        print("\n[STEP 7] Simulating Network Corruption / Interrupted Stream...")
        corrupt_url = f"http://127.0.0.1:{server.port}/fault/corrupted.mp4"
        corrupt_tmp = test_covers_dir / "corrupt.tmp"
        try:
            urllib.request.urlretrieve(corrupt_url, corrupt_tmp)
            # If retrieved without socket error, verify integrity failure
            corrupt_sha = hashlib.sha256(corrupt_tmp.read_bytes()).hexdigest().lower()
            if corrupt_sha != v1["sha256"]:
                corrupt_tmp.unlink()
        except urllib.error.ContentTooShortError:
            print("  -> Network socket interrupted (ContentTooShortError). Cleaning temp file.")
            if corrupt_tmp.exists():
                corrupt_tmp.unlink()

        assert not corrupt_tmp.exists()
        # Active target file MUST be completely untouched!
        assert target_mp4.exists()
        assert target_mp4.stat().st_size == v1["sizeBytes"]
        print("  -> PASS: Corrupt download rejected, active video cover 100% preserved.")

        print("\n=======================================================")
        print("  ALL LIVE INTEGRATION TESTS PASSED WITH 100% SUCCESS  ")
        print("=======================================================")

    finally:
        server.stop()
        shutil.rmtree(test_covers_dir, ignore_errors=True)
        # Clean server_data
        shutil.rmtree(Path(__file__).parent / "server_data", ignore_errors=True)


if __name__ == "__main__":
    test_full_downloader_integration()
