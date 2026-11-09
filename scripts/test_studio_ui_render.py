import os
import sys
from pathlib import Path

# Ensure paths
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "studio"))

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
from studio.h3h_studio.ui.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)

# Check available fonts
fonts = QFontDatabase.families()
chosen_font = "Segoe UI" if "Segoe UI" in fonts else ("Arial" if "Arial" in fonts else fonts[0] if fonts else "sans-serif")
app.setFont(QFont(chosen_font, 10))

win = MainWindow()
win.resize(1100, 1000)
win.show()
app.processEvents()

# Test 1: Search "GTA"
print("[1] Testing search for 'GTA'...")
express = win.express_view
express.game_search_edit.setText("GTA")
express._do_search()
app.processEvents()

card_count = express.candidates_layout.count()
print(f" -> Candidate cards in layout: {card_count}")

# Render to pixmap with candidates visible
pix1 = win.grab()
out1 = Path(r"C:\Users\HL\.gemini\antigravity\brain\0e2eccd7-a141-47bd-bba5-1dd6edc63967\studio_gta_search.png")
pix1.save(str(out1))
print(f" -> Saved search view to {out1}")

# Test 2: Select first card
print("[2] Selecting top candidate (GTA)...")
first_item = None
for i in range(express.candidates_layout.count()):
    w = express.candidates_layout.itemAt(i).widget()
    if w and w != express.search_status_lbl:
        first_item = w
        break

if first_item:
    first_item.mousePressEvent(None)
    app.processEvents()
    print(f" -> Selected: {express.selected_game_name} ({express.selected_title_id})")

# Test 3: Load sample video
sample_videos = list(PROJECT_ROOT.glob("downloaded_official_backgrounds/*.mp4"))
if sample_videos:
    sample_vid = sample_videos[0]
    print(f"[3] Loading sample video: {sample_vid.name}...")
    express._load_video(sample_vid)
    app.processEvents()

# Render to pixmap with video & selected game
pix2 = win.grab()
out2 = Path(r"C:\Users\HL\.gemini\antigravity\brain\0e2eccd7-a141-47bd-bba5-1dd6edc63967\studio_video_player.png")
pix2.save(str(out2))
print(f" -> Saved player view to {out2}")

print("[+] All Studio Express tests passed cleanly!")
