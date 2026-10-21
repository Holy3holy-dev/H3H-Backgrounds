from pathlib import Path

p = Path("scripts/auto_harvest_pipeline.py")
text = p.read_text(encoding="utf-8")

helper_def = '''import subprocess

def check_has_audio(file_path: Path) -> bool:
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-select_streams", "a", str(file_path)],
            capture_output=True, text=True, timeout=5
        )
        return "codec_type=audio" in res.stdout
    except Exception:
        return False
'''

if "def check_has_audio" not in text:
    text = helper_def + "\n" + text

text = text.replace('"hasAudio": False,', '"hasAudio": check_has_audio(out_file),')
p.write_text(text, encoding="utf-8")
print("[+] Patched auto_harvest_pipeline.py with dynamic audio detection!")
