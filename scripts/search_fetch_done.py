with open("downloader/src/ui/app.cpp", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, l in enumerate(lines):
    if "m_catalogFetchDone" in l:
        print(f"L{idx+1}: {l.strip()}")
        start = max(0, idx - 5)
        end = min(len(lines), idx + 40)
        for i in range(start, end):
            print(f"{i+1:4d}: {lines[i]}", end="")
        print("="*50)
