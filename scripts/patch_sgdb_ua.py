from pathlib import Path

p = Path("studio/h3h_studio/core/steamgriddb.py")
t = p.read_text(encoding="utf-8")
t = t.replace('"User-Agent": "H3H-Studio/1.0"', '"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"')
p.write_text(t, encoding="utf-8")
print("Updated steamgriddb.py User-Agent!")
