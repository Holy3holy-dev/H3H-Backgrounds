"""
Test render Switch Home overlay dialog with a real game video.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from studio.h3h_studio.ui.switch_preview_dialog import SwitchHomePreviewDialog

app = QApplication.instance() or QApplication(sys.argv)

vid_path = Path("tmp/icon_showcase_v3/1_witcher_mw.mp4")
if not vid_path.exists():
    vid_path = Path("tmp/test_generated_icon.mp4")

dlg = SwitchHomePreviewDialog(video_path=vid_path, start_sec=0.0, dur_sec=6.0)
dlg.show()
app.processEvents()

# Grab dialog image
grabbed = dlg.grab()
out_file = Path("tmp/switch_overlay_preview.png")
grabbed.save(str(out_file))
print("Saved preview to", out_file)
dlg.close()
