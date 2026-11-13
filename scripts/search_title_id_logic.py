import os
import glob

cpp_files = glob.glob("downloader/src/**/*.cpp", recursive=True) + glob.glob("downloader/include/**/*.hpp", recursive=True)

for path in cpp_files:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
        if "titleId" in content or "title_id" in content or "0100" in content or "formatTitleId" in content:
            print(f"File: {path}")
            lines = content.splitlines()
            for idx, l in enumerate(lines):
                if any(k in l for k in ["titleId", "title_id", "0100", "toUpper", "01"]):
                    if len(l.strip()) < 120 and "include" not in l:
                        print(f"  L{idx+1}: {l.strip()}")
