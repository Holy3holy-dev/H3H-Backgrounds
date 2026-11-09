import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "studio")

from PySide6.QtWidgets import QApplication
from studio.h3h_studio.ui.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)
win = MainWindow()
win.resize(1020, 1100)

# Simulate user loading video
test_vid = Path("tmp/4ifir_video_icons_sample/recordings/covers/010090F012916000.mp4")
win.express_view._load_video(test_vid)

win.show()
app.processEvents()

pix = win.grab()
out_path = Path("tmp/studio_with_video_loaded.png")
pix.save(str(out_path))
print(f"[+] Rendered with video loaded to {out_path}")

app.quit()
