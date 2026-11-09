with open('e:/videofon/downloader/src/ui/app.cpp', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'onButtonPress' in line:
        print(f"Line {i+1}: {line}")
        for j in range(max(0, i-2), min(len(lines), i+15)):
            print(f"  {j+1}: {repr(lines[j])}")
