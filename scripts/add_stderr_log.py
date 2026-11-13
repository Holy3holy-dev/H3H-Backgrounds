with open("scripts/generate_batch_hq_icons.py", "r", encoding="utf-8") as f:
    text = f.read()

old_res = "res = subprocess.run(cmd, capture_output=True, text=True)"
new_res = """res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"    [!] FFmpeg error (code {res.returncode}):\\n" + "\\n".join(res.stderr.splitlines()[-8:]))"""

text = text.replace(old_res, new_res)

with open("scripts/generate_batch_hq_icons.py", "w", encoding="utf-8") as f:
    f.write(text)

print("[+] Added stderr logging!")
