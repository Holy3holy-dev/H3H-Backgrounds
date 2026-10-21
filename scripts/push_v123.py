import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path("studio").resolve()))
from h3h_studio.core.github_publisher import GitHubPublisher

def main():
    token, _ = GitHubPublisher.get_stored_credentials()
    if not token:
        print("ERROR: GitHub token not found.")
        return 1

    repo_url = f"https://x-access-token:{token}@github.com/Holy3holy-dev/H3H-Backgrounds.git"

    # Git add modified files
    subprocess.run(["git", "add", "downloader/", "version.json", "scripts/apply_v123_input_fix.py", "scripts/create_release_v123.py"], check=True)
    
    commit_res = subprocess.run(["git", "commit", "-m", "fix(input): eliminate duplicate joystick dispatch, map ZL/ZR tabs, debounce preview transitions, bump v1.2.3"], capture_output=True, text=True)
    print("Commit output:", commit_res.stdout, commit_res.stderr)

    print("Pushing to main...")
    push_res = subprocess.run(["git", "push", repo_url, "main"], capture_output=True, text=True)
    print("Push output:", push_res.stdout, push_res.stderr)

if __name__ == "__main__":
    main()
