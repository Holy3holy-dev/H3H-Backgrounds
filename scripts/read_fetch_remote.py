with open("downloader/src/ui/app.cpp", "r", encoding="utf-8") as f:
    lines = f.readlines()

found = False
for idx, l in enumerate(lines):
    if "fetchRemoteCatalog" in l:
        print(f"L{idx+1}: {l.strip()}")
        start = max(0, idx - 5)
        end = min(len(lines), idx + 80)
        for i in range(start, end):
            print(f"{i+1:4d}: {lines[i]}", end="")
        break
