#!/usr/bin/env python3
"""
Test HTTP server for H3H Downloader integration testing.
Serves verified 4IFIR MP4 assets, catalog JSON, and simulates network fault scenarios.
"""

import hashlib
import http.server
import json
import socketserver
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional


class TestServerHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=str(directory), **kwargs)

    def do_GET(self):
        # Simulate network faults on specific paths
        if self.path == "/fault/corrupted.mp4":
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", "1000")
            self.end_headers()
            # Send incomplete/garbage bytes
            self.wfile.write(b"CORRUPTED_GARBAGE_BYTES_SIMULATING_NETWORK_CUT")
            return
        elif self.path == "/fault/404.mp4":
            self.send_error(404, "File Not Found")
            return

        return super().do_GET()


class MockAssetServer:
    def __init__(self, port: int = 8999):
        self.port = port
        self.server_dir = Path(__file__).parent / "server_data"
        self.videos_dir = self.server_dir / "videos"
        self.httpd: Optional[socketserver.TCPServer] = None
        self.thread: Optional[threading.Thread] = None

    def setup_sample_assets(self):
        """Generates real, 100% compliant 4IFIR sample video assets using FFmpeg."""
        self.videos_dir.mkdir(parents=True, exist_ok=True)

        sample_mp4 = self.videos_dir / "01005CA01580E000_sample.mp4"
        if not sample_mp4.exists():
            print("[*] Generating real 4IFIR test video with FFmpeg...")
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "testsrc=duration=2:size=1280x720:rate=30",
                "-c:v", "libx264", "-profile:v", "high", "-level", "4.1",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-an",
                str(sample_mp4)
            ]
            subprocess.run(cmd, check=True, capture_output=True)

        sample_v2_mp4 = self.videos_dir / "01005CA01580E000_action.mp4"
        if not sample_v2_mp4.exists():
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "smptebars=duration=2:size=1280x720:rate=30",
                "-c:v", "libx264", "-profile:v", "high", "-level", "4.1",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-an",
                str(sample_v2_mp4)
            ]
            subprocess.run(cmd, check=True, capture_output=True)

        # Compute accurate SHA-256 and byte sizes
        def get_sha256(p: Path) -> str:
            sha = hashlib.sha256()
            with open(p, "rb") as f:
                while c := f.read(65536):
                    sha.update(c)
            return sha.hexdigest().lower()

        sha1 = get_sha256(sample_mp4)
        size1 = sample_mp4.stat().st_size
        sha2 = get_sha256(sample_v2_mp4)
        size2 = sample_v2_mp4.stat().st_size

        # Create catalog pointing to this local server
        catalog = {
            "schemaVersion": 1,
            "updatedAt": "2026-10-19T04:00:00Z",
            "totalGames": 1,
            "totalVariants": 2,
            "games": [
                {
                    "titleId": "01005CA01580E000",
                    "title": "Teenage Mutant Ninja Turtles: Shredder's Revenge",
                    "publisher": "Dotemu",
                    "variants": [
                        {
                            "id": "shredders-intro-loop",
                            "name": "Opening Intro Loop",
                            "style": "Animated Art",
                            "version": "1.0",
                            "url": f"http://127.0.0.1:{self.port}/videos/01005CA01580E000_sample.mp4",
                            "previewUrl": f"http://127.0.0.1:{self.port}/videos/01005CA01580E000_sample.mp4",
                            "sizeBytes": size1,
                            "sha256": sha1,
                            "durationSec": 2.0,
                            "author": "H3H_Team",
                            "codec": "h264",
                            "width": 1280,
                            "height": 720,
                            "fps": 30.0,
                            "hasAudio": False
                        },
                        {
                            "id": "shredders-action-loop",
                            "name": "Action Combat Loop",
                            "style": "Gameplay",
                            "version": "1.1",
                            "url": f"http://127.0.0.1:{self.port}/videos/01005CA01580E000_action.mp4",
                            "previewUrl": f"http://127.0.0.1:{self.port}/videos/01005CA01580E000_action.mp4",
                            "sizeBytes": size2,
                            "sha256": sha2,
                            "durationSec": 2.0,
                            "author": "H3H_Team",
                            "codec": "h264",
                            "width": 1280,
                            "height": 720,
                            "fps": 30.0,
                            "hasAudio": False
                        }
                    ]
                }
            ]
        }

        with open(self.server_dir / "catalog.json", "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2)

    def start(self):
        self.setup_sample_assets()

        handler = lambda *args, **kwargs: TestServerHandler(*args, directory=self.server_dir, **kwargs)
        # Allow socket reuse to prevent port-in-use errors
        socketserver.TCPServer.allow_reuse_address = True
        self.httpd = socketserver.TCPServer(("127.0.0.1", self.port), handler)

        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        print(f"[+] Test HTTP server started on http://127.0.0.1:{self.port}")

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            print("[*] Test HTTP server stopped.")


if __name__ == "__main__":
    server = MockAssetServer()
    server.start()
    try:
        input("Server running. Press Enter to stop...\n")
    finally:
        server.stop()
