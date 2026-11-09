import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "studio")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtCore import QSize

from studio.h3h_studio.ui.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)
win = MainWindow()
win.resize(1020, 950)
win.show()

# Process events to lay out all widgets
app.processEvents()

# Grab window
pix = win.grab()
out_path = Path("tmp/studio_rendered.png")
pix.save(str(out_path))
print(f"[+] Rendered studio screenshot saved to {out_path} ({out_path.stat().st_size} bytes)")

app.quit()
