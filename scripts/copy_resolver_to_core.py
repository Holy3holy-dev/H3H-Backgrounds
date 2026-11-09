import sys
import shutil
from pathlib import Path

src = Path("scripts/title_id_resolver.py")
dst = Path("studio/h3h_studio/core/title_id_resolver.py")

content = src.read_text(encoding="utf-8")

# Add sys import if missing
if "import sys" not in content:
    content = "import sys\n" + content

# Improve db_path resolution to work inside PyInstaller
target = """        # Also load all official Switch titles and homebrews from database
        db_path = self.catalog_path.parent.parent.parent / "studio" / "h3h_studio" / "data" / "switch_titles_db.json"
        if not db_path.exists():
            db_path = Path("studio/h3h_studio/data/switch_titles_db.json")
        if db_path.exists():"""

replacement = """        # Also load all official Switch titles and homebrews from database
        db_candidates = [
            Path(__file__).parent.parent / "data" / "switch_titles_db.json",
            Path(getattr(sys, "_MEIPASS", "")) / "h3h_studio" / "data" / "switch_titles_db.json",
            Path("studio/h3h_studio/data/switch_titles_db.json"),
            self.catalog_path.parent.parent.parent / "studio" / "h3h_studio" / "data" / "switch_titles_db.json"
        ]
        db_path = next((p for p in db_candidates if p.exists()), None)
        if db_path and db_path.exists():"""

if target in content:
    content = content.replace(target, replacement, 1)

dst.write_text(content, encoding="utf-8")
print(f"Created {dst} successfully!")
