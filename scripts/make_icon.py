"""Малює іконку застосунку в src/passgen/data/icon.png.

Запуск: QT_QPA_PLATFORM=offscreen python scripts/make_icon.py
PyInstaller сам перетворює PNG на .ico/.icns (потрібен Pillow).
"""

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath

SIZE = 1024
OUT = Path(__file__).resolve().parents[1] / "src" / "passgen" / "data" / "icon.png"


def main() -> None:
    _app = QGuiApplication([])
    img = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    m = SIZE * 0.06
    bg = QPainterPath()
    bg.addRoundedRect(QRectF(m, m, SIZE - 2 * m, SIZE - 2 * m), SIZE * 0.2, SIZE * 0.2)
    p.fillPath(bg, QColor("#0d6670"))

    # три блоки частини фрази: слово, цифри, символи — і роздільник під ними
    bar_h = SIZE * 0.13
    y = SIZE * 0.36
    x = SIZE * 0.185
    for width, color in ((0.30, "#ffffff"), (0.13, "#9fc0ff"), (0.13, "#ffb184")):
        r = QPainterPath()
        r.addRoundedRect(QRectF(x, y, SIZE * width, bar_h), bar_h * 0.3, bar_h * 0.3)
        p.fillPath(r, QColor(color))
        x += SIZE * width + SIZE * 0.035
    sep = QPainterPath()
    sep.addRoundedRect(QRectF(SIZE * 0.185, SIZE * 0.6, SIZE * 0.63, SIZE * 0.045), 12, 12)
    p.fillPath(sep, QColor(255, 255, 255, 110))
    p.end()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(OUT))
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
