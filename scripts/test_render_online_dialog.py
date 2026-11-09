import sys
from pathlib import Path

sys.path.insert(0, str(Path("studio").resolve()))
from PySide6.QtWidgets import QApplication
from h3h_studio.ui.online_icons_dialog import OnlineIconsDialog

app = QApplication(sys.argv)
dlg = OnlineIconsDialog(initial_query="Hades")
dlg.show()

# Render screenshot to tmp/online_icons_dialog.png
Path("tmp").mkdir(parents=True, exist_ok=True)
pix = dlg.grab()
pix.save("tmp/online_icons_dialog.png")
print("Screenshot saved: tmp/online_icons_dialog.png")
app.quit()
