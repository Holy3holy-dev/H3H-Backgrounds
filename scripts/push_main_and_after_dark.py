import sys
import subprocess
from pathlib import Path

sys.path.insert(0, 'studio')
from h3h_studio.core.github_publisher import GitHubPublisher

gh_token, _ = GitHubPublisher.get_stored_credentials()
if not gh_token:
    print("[-] No GitHub token!")
    sys.exit(1)

repo_name = "Holy3holy-dev/H3H-Backgrounds"
repo_url = f"https://x-access-token:{gh_token}@github.com/{repo_name}.git"

# 1. Push main (bot fixes)
print("[*] Pushing 'main' to GitHub...")
res1 = subprocess.run(["git", "push", repo_url, "main"], capture_output=True, text=True)
print("Main push result:", res1.stdout, res1.stderr)

# 2. Stage catalog_after_dark.json and push to after-dark branch
print("[*] Staging and pushing 'catalog/data/catalog_after_dark.json' to after-dark branch...")
subprocess.run(["git", "add", "catalog/data/catalog_after_dark.json"])
subprocess.run(["git", "commit", "-m", "feat(after-dark): populate 17 verified 18+/Waifu video themes across NieR, FF7, Zelda, and collection"])

res2 = subprocess.run(["git", "push", repo_url, "HEAD:refs/heads/after-dark"], capture_output=True, text=True)
print("After-Dark push result:", res2.stdout, res2.stderr)

if res1.returncode == 0 and res2.returncode == 0:
    print("[+] ALL PUSHES SUCCEEDED!")
    sys.exit(0)
else:
    sys.exit(1)
