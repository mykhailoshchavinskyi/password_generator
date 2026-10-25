"""Точка входу десктопного застосунку."""

from __future__ import annotations

import os
import sys
from importlib import resources

import shiboken6
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from passgen import __version__, settings
from passgen.gui.main_window import MainWindow


def app_icon() -> QIcon:
    path = resources.files("passgen").joinpath("data/icon.png")
    return QIcon(str(path)) if path.is_file() else QIcon()


def main(argv: list[str] | None = None) -> int:
    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("Passgen")
    app.setApplicationDisplayName("Passgen")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Passgen")
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())

    smoke_test = bool(os.environ.get("PASSGEN_SMOKE_TEST"))
    if smoke_test:
        # перевірка зібраного файлу в CI: вікно відкривається, генерує фразу і закривається
        window = MainWindow()
        QTimer.singleShot(300, window.close)
    else:
        window = MainWindow(settings.load(), save=settings.save)
    window.show()
    code = app.exec()
    if smoke_test and window.phrase is None:
        code = 3
    # Вікно знищуємо раніше за QApplication, інакше PySide під час виходу
    # може вдруге видалити вже знищені віджети і завершитися аварійно.
    shiboken6.delete(window)
    return code


if __name__ == "__main__":
    sys.exit(main())
