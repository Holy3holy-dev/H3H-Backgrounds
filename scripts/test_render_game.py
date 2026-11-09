import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "studio")

from PySide6.QtWidgets import QApplication
from studio.h3h_studio.ui.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)
win = MainWindow()
win.resize(1020, 1000)

# Simulate user typing 'Ghostrunner'
win.express_view.game_search_edit.setText("Ghostrunner")

win.show()
app.processEvents()

pix = win.grab()
out_path = Path("tmp/studio_with_game.png")
pix.save(str(out_path))
print(f"[+] Rendered with game to {out_path}")

app.quit()
