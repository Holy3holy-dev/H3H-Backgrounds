import json
import glob
import os

target_id = "01caa550fbc40000"

print(f"Target Title ID: {target_id.upper()}")

json_files = glob.glob("**/*.json", recursive=True)

for path in json_files:
    if ".git" in path or "node_modules" in path:
        continue
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            if target_id in content.lower():
                print(f"[FOUND ID] in {path}")
            if "wind waker" in content.lower():
                print(f"[FOUND WIND WAKER] in {path}")
    except Exception:
        pass
