import sys
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from .ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("H3H Background Studio")
    app.setOrganizationName("H3H")
    app.setFont(QFont("Segoe UI", 10))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
