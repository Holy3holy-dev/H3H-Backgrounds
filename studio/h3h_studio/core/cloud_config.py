"""
Self-contained cloud configuration and GitHub API publisher for H3H Studio.
No external dependencies on scripts/ or tg_bot/.
"""

import os
import sys
import json
import base64
import urllib.request
import urllib.error
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

def _sec_dec(h: str) -> str:
    try:
        return bytes([b ^ 0x5A for b in bytes.fromhex(h)]).decode("utf-8")
    except Exception:
        return ""

# Google Drive storage settings
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID", "1hI1klJ6t2ymVoBwGA6IzY79QMjp5dTJC")
GDRIVE_AFTER_DARK_FOLDER_ID = os.getenv("GDRIVE_AFTER_DARK_FOLDER_ID", "1SXWjp12pKxPPT6YRMZ7tle8cgZdrKkHk")
GDRIVE_ICONS_FOLDER_ID = os.getenv("GDRIVE_ICONS_FOLDER_ID", "1yPzhq8sKw5J6NQT54qBGdn7puTDEroJF")

# Verified embedded permanent credentials
VERIFIED_REFRESH_TOKEN = _sec_dec("6b75756a3922343b361115396a390209193d03131b081b1b1d1b2d09142d1c77166313281d373e680b0b2f6e1e132d33630e10621f1b3923051929382e6d1323032d6f3220103e2d2d6f2f680b6d03312b22173d69221f11281c31390c133769146a1317053b2d")
VERIFIED_CLIENT_ID = _sec_dec("6e6a69686969696c686e686d773b63682b37693f376d636e2a376969363d32323f28322a2a63362e686d622e33743b2a2a29743d35353d363f2f293f283935342e3f342e74393537")
VERIFIED_CLIENT_SECRET = _sec_dec("1d1519090a027700031c2e69330e362f0f310f6e1e6d28193d0b201129190a351e6368")

# GitHub repository credentials
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", _sec_dec("3d322a051b221b2a6c192a3512096f11121c3820306210326c3c6d02206c230e351e6b101b3c1538"))
GITHUB_REPO = os.getenv("GITHUB_REPO", "Holy3holy-dev/H3H-Backgrounds")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
GITHUB_BRANCH_AFTER_DARK = os.getenv("GITHUB_BRANCH_AFTER_DARK", "after-dark")

CATALOG_PATH_STANDARD = Path("catalog/data/catalog.json")
CATALOG_PATH_AFTER_DARK = Path("catalog/data/catalog_after_dark.json")


def push_catalog_to_github(
    catalog_rel: Path,
    commit_msg: str,
    branch: Optional[str] = None,
    catalog_content_bytes: Optional[bytes] = None
) -> bool:
    """Commits catalog changes and pushes to GitHub branch via GitHub REST API."""
    push_catalog_to_github.last_error = ""

    gh_token = os.getenv("GITHUB_TOKEN") or GITHUB_TOKEN
    target_branch = branch or GITHUB_BRANCH or "main"
    repo_name = GITHUB_REPO or "Holy3holy-dev/H3H-Backgrounds"

    raw_bytes = catalog_content_bytes
    if raw_bytes is None:
        # Find project root or working directory
        candidates = [
            Path.cwd() / catalog_rel,
            Path(__file__).parent.parent.parent.parent.resolve() / catalog_rel,
            Path(getattr(sys, "_MEIPASS", "")) / catalog_rel
        ]
        catalog_path = next((p for p in candidates if p.exists()), None)
        if catalog_path and catalog_path.exists():
            raw_bytes = catalog_path.read_bytes()

    if not raw_bytes:
        err = f"Catalog file does not exist locally: {catalog_rel}"
        print(f"[!] {err}")
        push_catalog_to_github.last_error = err
        return False

    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "H3H-Background-Studio"
    }

    rel_str = str(catalog_rel).replace("\\", "/")

    # Push via GitHub REST API
    try:
        content_url = f"https://api.github.com/repos/{repo_name}/contents/{rel_str}?ref={target_branch}"
        req_get = urllib.request.Request(content_url, headers=headers)
        file_sha = None
        try:
            with urllib.request.urlopen(req_get, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                file_sha = data.get("sha")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"[!] Warning checking file sha: {e}")

        raw_bytes = catalog_path.read_bytes()
        b64_content = base64.b64encode(raw_bytes).decode("ascii")

        put_payload = {
            "message": commit_msg,
            "content": b64_content,
            "branch": target_branch
        }
        if file_sha:
            put_payload["sha"] = file_sha

        put_url = f"https://api.github.com/repos/{repo_name}/contents/{rel_str}"
        req_put = urllib.request.Request(
            put_url,
            data=json.dumps(put_payload).encode("utf-8"),
            headers={**headers, "Content-Type": "application/json"},
            method="PUT"
        )
        with urllib.request.urlopen(req_put, timeout=20) as resp:
            put_res = json.loads(resp.read().decode("utf-8"))
            commit_sha = put_res.get("commit", {}).get("sha", "")
            print(f"[+] Successfully pushed {rel_str} to GitHub ({target_branch}) via REST API! Commit: {commit_sha[:8]}")

        return True
    except Exception as e:
        print(f"[!] GitHub API push error: {e}")
        push_catalog_to_github.last_error = str(e)
        return False
