from pathlib import Path

p = Path("studio/h3h_studio/ui/express_tab.py")
content = p.read_text(encoding="utf-8")

# Adjust viewport and icon size to be slightly more compact and perfectly proportional
content = content.replace("self.video_viewport_frame.setFixedSize(426, 240)", "self.video_viewport_frame.setFixedSize(392, 220)")
content = content.replace("self.icon_preview_lbl.setFixedSize(220, 220)", "self.icon_preview_lbl.setFixedSize(196, 196)")

# Also update _update_icon_crop_preview to scale to 196x196
content = content.replace("self.icon_preview_lbl.setPixmap(\n            cropped.scaled(240, 240, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)\n        )", "self.icon_preview_lbl.setPixmap(\n            cropped.scaled(196, 196, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)\n        )")

p.write_text(content, encoding="utf-8")
print("[+] Refined dimensions in express_tab.py!")
