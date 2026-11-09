import sys
import subprocess
from pathlib import Path

sys.path.insert(0, "studio")
from h3h_studio.core.github_publisher import GitHubPublisher

gh_token, _ = GitHubPublisher.get_stored_credentials()
if not gh_token:
    print("[-] No GitHub token!")
    sys.exit(1)

repo_name = "Holy3holy-dev/H3H-Backgrounds"
repo_url = f"https://x-access-token:{gh_token}@github.com/{repo_name}.git"

print("[*] Pushing 'main' to GitHub...")
res1 = subprocess.run(["git", "push", repo_url, "main"], capture_output=True, text=True)
print("Main push result:", res1.stdout, res1.stderr)

if res1.returncode == 0:
    print("[+] Main branch successfully pushed!")
    sys.exit(0)
else:
    print("[!] Push failed!")
    sys.exit(1)
