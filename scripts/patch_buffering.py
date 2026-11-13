with open("scripts/generate_batch_hq_icons.py", "r", encoding="utf-8") as f:
    text = f.read()

target = "import subprocess"
replacement = "import subprocess\n\nsys.stdout.reconfigure(encoding='utf-8', line_buffering=True)\nsys.stderr.reconfigure(encoding='utf-8', line_buffering=True)"

if "line_buffering=True" not in text:
    text = text.replace(target, replacement, 1)
    with open("scripts/generate_batch_hq_icons.py", "w", encoding="utf-8") as f:
        f.write(text)
    print("Added line buffering!")
