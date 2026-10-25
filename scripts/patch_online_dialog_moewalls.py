from pathlib import Path

p = Path("studio/h3h_studio/ui/online_icons_dialog.py")
text = p.read_text(encoding="utf-8")

old = 'self.source_combo.addItem("🎨 SteamGridDB (Сетки и иконки)", "steamgriddb")\n        self.source_combo.addItem("🌀 Tenor (Гифки)", "tenor")'
new = 'self.source_combo.addItem("🎨 SteamGridDB (Сетки и иконки)", "steamgriddb")\n        self.source_combo.addItem("✨ MoeWalls (Живые обои 1080p)", "moewalls")\n        self.source_combo.addItem("🌀 Tenor (Гифки)", "tenor")'

assert old in text, "old string not found"
text = text.replace(old, new, 1)
p.write_text(text, encoding="utf-8")
print("SUCCESS: online_icons_dialog.py updated with MoeWalls!")
