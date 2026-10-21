from pathlib import Path

p = Path("downloader/src/ui/app.cpp")
text = p.read_text(encoding="utf-8").replace("\r\n", "\n")

closing_ns = """} // namespace ui
} // namespace h3h"""

# Find closing_ns and move it to the very end of the file
idx = text.rfind(closing_ns)
if idx != -1:
    before = text[:idx]
    after = text[idx + len(closing_ns):]
    text = before + after + "\n\n} // namespace ui\n} // namespace h3h\n"
    p.write_text(text, encoding="utf-8")
    print("[+] Successfully moved namespace closing braces to end of file!")
else:
    print("[-] closing_ns not found")
