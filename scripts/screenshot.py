"""Знімки вікна для документації: docs/images/*.png.

Запуск: QT_QPA_PLATFORM=offscreen python scripts/screenshot.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shiboken6  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from passgen.gui.main_window import MainWindow  # noqa: E402
from passgen.settings import AppSettings  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "images"


def shoot(window: MainWindow, name: str) -> None:
    for _ in range(3):
        QApplication.processEvents()
    path = OUT / name
    window.grab().save(str(path))
    print(f"saved {path}")


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    OUT.mkdir(parents=True, exist_ok=True)

    window = MainWindow(AppSettings())
    window.resize(460, 10)
    window.show()
    shoot(window, "main-window.png")

    window.toggle.setChecked(False)
    shoot(window, "compact.png")

    window.toggle.setChecked(True)
    window.symbol_set_edit.setText("!a")
    shoot(window, "error.png")
    window.close()
    # як і в passgen.gui.app: вікно знищуємо раніше за QApplication,
    # інакше PySide під час виходу падає з segfault
    shiboken6.delete(window)
    return 0


if __name__ == "__main__":
    sys.exit(main())
