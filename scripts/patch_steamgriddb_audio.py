from pathlib import Path

p = Path("studio/h3h_studio/core/steamgriddb.py")
text = p.read_text(encoding="utf-8")

old_part = '-an", str(output_mp4_path)'
new_part = '-map", "0:v:0", "-map", "0:a?", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", str(output_mp4_path)'

if old_part in text:
    text = text.replace(old_part, new_part)
    p.write_text(text, encoding="utf-8")
    print("[+] Patched steamgriddb.py with audio preserving flags!")
else:
    print("[-] Old part not found in steamgriddb.py")
