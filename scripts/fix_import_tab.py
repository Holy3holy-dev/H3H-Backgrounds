from pathlib import Path

p = Path("studio/h3h_studio/ui/express_tab.py")
code = p.read_text(encoding="utf-8")

code = code.replace(
    "from PySide6.QtCore import Qt, QThread, Signal, QSettings, QTimer\n",
    "from PySide6.QtCore import Qt, QThread, Signal, QSettings, QTimer, QStringListModel\n"
)
code = code.replace(
    "    QCompleter, QStringListModel\n",
    "    QCompleter\n"
)

p.write_text(code, encoding="utf-8")
print("[+] Fixed QStringListModel import")
