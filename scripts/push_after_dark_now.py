import os
import sys
import subprocess
from pathlib import Path

sys.path.append('.')
from tg_bot.config import GITHUB_TOKEN, GITHUB_REPO

token = GITHUB_TOKEN or os.getenv("GITHUB_TOKEN")
if not token:
    # Try reading from config
    token = "github_pat_11BMG34JQ0uN46YjG4R1vG_o2Hq64Nq8YkQ9q6s3..." # check studio
    from h3h_studio.core.github_publisher import GitHubPublisher
    token = GitHubPublisher.get_token()

repo_url = f"https://x-access-token:{token}@github.com/{GITHUB_REPO}.git"

print("[*] Staging catalog_after_dark.json and video_harvest_log_after_dark.json...")
subprocess.run(["git", "add", "catalog/data/catalog_after_dark.json", "catalog/data/video_harvest_log_after_dark.json", "scripts/auto_video_harvester.py"], check=True)
subprocess.run(["git", "commit", "-m", "feat(after-dark): restructure catalog into 88 games and add spicy tags & waifu franchises"], check=False)

print("[*] Pushing to origin after-dark branch...")
res = subprocess.run(["git", "push", "--force", repo_url, "HEAD:refs/heads/after-dark"], capture_output=True, text=True)
print("Push stdout:", res.stdout)
print("Push stderr:", res.stderr)
if res.returncode == 0:
    print("[SUCCESS] Successfully pushed restructured catalog to after-dark branch!")
else:
    print("[!] Push failed code:", res.returncode)
