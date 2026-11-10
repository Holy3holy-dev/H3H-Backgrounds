import json
import os
import sys
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "studio"))
sys.path.insert(0, str(PROJECT_ROOT))

from h3h_studio.core.github_publisher import GitHubPublisher
from tg_bot.config import detect_local_proxy

gh_token, _ = GitHubPublisher.get_stored_credentials()
if not gh_token:
    print("[-] GitHub token not found!")
    sys.exit(1)

local_proxy = detect_local_proxy()
repo_url = f"https://x-access-token:{gh_token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"

git_env = os.environ.copy()
git_env["GIT_EDITOR"] = ":"
git_env["GIT_TERMINAL_PROMPT"] = "0"
if local_proxy:
    git_env["http_proxy"] = local_proxy
    git_env["https_proxy"] = local_proxy

files_to_add = [
    ("H3H-Backgrounds.nro", True),
    ("downloader/H3H-Backgrounds.nro", False),
    ("downloader/romfs/catalog.json", False),
    ("catalog/data/catalog.json", False),
    ("catalog/data/catalog.min.json", False),
    ("catalog/data/catalog.min.json.gz", False),
    ("downloader/include/core/config.hpp", False),
    ("downloader/include/core/types.hpp", False),
    ("downloader/include/core/installer.hpp", False),
    ("downloader/include/ui/app.hpp", False),
    ("downloader/src/core/installer.cpp", False),
    ("downloader/src/platform/switch_platform.cpp", False),
    ("downloader/src/ui/app.cpp", False),
    ("scripts/build_min_catalog.py", False),
    ("scripts/generate_batch_hq_icons.py", False),
    ("scripts/commit_and_push_release.py", False),
    ("version.json", False),
]

print("[*] Staging targeted v1.5.0 release files...")
for f, force in files_to_add:
    full_p = PROJECT_ROOT / f
    if full_p.exists():
        cmd = ["git", "add", "-f", f] if force else ["git", "add", f]
        subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)

msg = (
    "feat(release): v1.5.0 unified button contract, glass action sheet [X], "
    "A-Z stick jump, forwarder link, multi-slot rotation & gzipped turbo index [skip render] [skip ci]"
)
print(f"[*] Committing: {msg}")
res = subprocess.run(["git", "commit", "-m", msg], cwd=str(PROJECT_ROOT), env=git_env, capture_output=True, text=True)
print("Commit STDOUT:", res.stdout)
print("Commit STDERR:", res.stderr)

print("[*] Pulling with rebase from main...")
subprocess.run(["git", "pull", "--rebase", repo_url, "main"], cwd=str(PROJECT_ROOT), env=git_env, check=False)

print("[*] Pushing to main...")
res = subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/main"], cwd=str(PROJECT_ROOT), env=git_env, capture_output=True, text=True)
print("Push STDOUT:", res.stdout)
print("Push STDERR:", res.stderr)
print("Exit code:", res.returncode)

if res.returncode != 0:
    print("\n[-] Push failed!")
    sys.exit(1)

print("\n[SUCCESS] Successfully pushed v1.5.0 release to GitHub main!")

# Create or update GitHub Release v1.5.0 and upload H3H-Backgrounds.nro asset
try:
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": local_proxy, "https": local_proxy})
    ) if local_proxy else urllib.request.build_opener()

    ver_data = json.loads((PROJECT_ROOT / "version.json").read_text(encoding="utf-8"))
    body_text = ver_data.get("changelogRu", "") + "\n\n---\n\n" + ver_data.get("changelog", "")
    api_base = "https://api.github.com/repos/Holy3holy-dev/H3H-Backgrounds"
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "H3H-Release-Publisher/1.5.0",
    }

    rel_obj = None
    try:
        req = urllib.request.Request(f"{api_base}/releases/tags/v1.5.0", headers=headers)
        with opener.open(req, timeout=30) as resp:
            rel_obj = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            payload = json.dumps({
                "tag_name": "v1.5.0",
                "target_commitish": "main",
                "name": "H3H Backgrounds v1.5.0 — Unified Controls & Ideas 1–6",
                "body": body_text,
                "draft": False,
                "prerelease": False,
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{api_base}/releases",
                data=payload,
                headers={**headers, "Content-Type": "application/json"},
                method="POST",
            )
            with opener.open(req, timeout=30) as resp:
                rel_obj = json.loads(resp.read().decode("utf-8"))

    if rel_obj and "upload_url" in rel_obj:
        upload_base = rel_obj["upload_url"].split("{")[0]
        nro_bytes = (PROJECT_ROOT / "downloader" / "H3H-Backgrounds.nro").read_bytes()
        up_req = urllib.request.Request(
            f"{upload_base}?name=H3H-Backgrounds.nro",
            data=nro_bytes,
            headers={**headers, "Content-Type": "application/octet-stream"},
            method="POST",
        )
        with opener.open(up_req, timeout=120) as resp:
            print("[+] Uploaded H3H-Backgrounds.nro to GitHub Release v1.5.0!")
except Exception as exc:
    print(f"[!] Note while creating GitHub Release tag (main raw URL is already live): {exc}")
