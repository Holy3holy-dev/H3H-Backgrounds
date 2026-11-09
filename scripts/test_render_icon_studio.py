import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from studio.h3h_studio.ui.express_tab import ExpressTab

w = ExpressTab()
w.resize(1180, 850)
w.show()

# Find a test video
test_vid = None
for p in [Path("tmp/test_generated_icon.mp4"), Path("tmp/mgr_harvest/0100C81014168000_mgr1.mp4")]:
    if p.exists():
        test_vid = p
        break

if not test_vid:
    for p in Path(".").glob("**/*.mp4"):
        test_vid = p
        break

if test_vid:
    print(f"[*] Loading test video: {test_vid}")
    w._load_video(test_vid.resolve())

# Select GTA 5
w._select_game({
    "titleId": "0100B00B51230000",
    "title": "Grand Theft Auto V",
    "publisher": "Rockstar Games",
    "genre": "Open World / Action",
    "isHomebrew": True
})

out_png = Path("tmp/studio_with_icon_player.png")
out_png.parent.mkdir(parents=True, exist_ok=True)

def capture():
    pix = w.grab()
    pix.save(str(out_png))
    print(f"[+] Screenshot captured: {out_png} ({pix.width()}x{pix.height()})")
    app.quit()

QTimer.singleShot(1500, capture)
app.exec()
