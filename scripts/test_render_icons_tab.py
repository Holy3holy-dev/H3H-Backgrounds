import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

# Setup paths
sys.path.insert(0, str(Path("studio").resolve()))

from h3h_studio.ui.main_window import MainWindow

def test_render():
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.resize(1260, 920)
    win.show()

    # Switch to the new Icons tab (index 1)
    win.tabs.setCurrentIndex(1)
    app.processEvents()

    # Save screenshot of the Icons tab
    out_img = Path("tmp/studio_icons_tab.png")
    out_img.parent.mkdir(parents=True, exist_ok=True)
    pix = win.grab()
    pix.save(str(out_img))
    print(f"[+] Screenshot saved to {out_img} (Size: {pix.width()}x{pix.height()})")

    win.close()
    app.quit()

if __name__ == "__main__":
    test_render()
