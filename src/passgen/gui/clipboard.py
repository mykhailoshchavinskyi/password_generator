"""Копіювання в буфер обміну з автоматичним очищенням."""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication

# Підказки менеджерам буфера обміну не зберігати вміст в історії:
# Windows (Win+V), macOS (менеджери на кшталт Maccy), KDE Klipper.
_SECRET_HINTS = {
    'application/x-qt-windows-mime;value="ExcludeClipboardContentFromMonitorProcessing"': b"\0",
    "org.nspasteboard.ConcealedType": b"",
    "x-kde-passwordManagerHint": b"secret",
}


class ClipboardGuard(QObject):
    """Копіює текст і через заданий час очищає буфер, якщо там досі цей текст."""

    remaining_changed = Signal(int)  # секунд до очищення; 0 — очищено або скасовано

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._text: str | None = None
        self._remaining = 0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    def copy(self, text: str, clear_after: int) -> None:
        mime = QMimeData()
        mime.setText(text)
        for fmt, data in _SECRET_HINTS.items():
            mime.setData(fmt, data)
        QGuiApplication.clipboard().setMimeData(mime)
        self._text = text
        self._remaining = clear_after
        if clear_after > 0:
            self._timer.start()
        else:
            self._timer.stop()
        self.remaining_changed.emit(self._remaining)

    def _tick(self) -> None:
        self._remaining -= 1
        if self._remaining <= 0:
            self.clear_now()
        else:
            self.remaining_changed.emit(self._remaining)

    def clear_now(self) -> None:
        """Очищає буфер, лише якщо користувач не скопіював туди щось інше."""
        self._timer.stop()
        if self._text is not None and QGuiApplication.clipboard().text() == self._text:
            QGuiApplication.clipboard().clear()
        self._text = None
        self._remaining = 0
        self.remaining_changed.emit(0)

    @property
    def pending(self) -> bool:
        return self._text is not None and self._timer.isActive()
