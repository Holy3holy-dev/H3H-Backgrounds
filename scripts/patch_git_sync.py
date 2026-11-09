import os

path = "scripts/generate_batch_hq_icons.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

needle = '        # Commit and push to git\n        subprocess.run(["git", "add", "catalog/data/catalog.json"], check=False)'
replacement = '        # Sync with upstream to avoid parallel conflicts\n        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=False)\n        # Commit and push to git\n        subprocess.run(["git", "add", "catalog/data/catalog.json"], check=False)'

if needle in text:
    text = text.replace(needle, replacement)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("[+] Git rebase sync added successfully")
else:
    print("[-] Needle not found")
