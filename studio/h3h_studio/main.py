import sys
from PySide6.QtWidgets import QApplication
from .ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("H3H Background Studio")
    app.setOrganizationName("H3H")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
