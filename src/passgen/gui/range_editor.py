"""Поле «до N / рівно N / від N до M» для довжини пароля і кількості літер у слові."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSpinBox, QWidget

UPTO, EXACT, RANGE = "upto", "exact", "range"
MODE_LABELS = {UPTO: "до", EXACT: "рівно", RANGE: "від"}


class RangeEditor(QWidget):
    """Режим і одне чи два числа.

    «до N»: лише верхня межа (нижня — найменше допустиме значення);
    «рівно N»: обидві межі однакові; «від N до M»: діапазон.
    """

    changed = Signal()

    def __init__(self, lo: int, hi: int, modes: tuple[str, ...], tooltip: str = "") -> None:
        super().__init__()
        self._floor = lo
        self._busy = False
        self._prev_mode = modes[0]

        self.mode = QComboBox()
        for m in modes:
            self.mode.addItem(MODE_LABELS[m], m)
        self.mode.setToolTip(tooltip)
        self.low, self.high = QSpinBox(), QSpinBox()
        for spin in (self.low, self.high):
            spin.setRange(lo, hi)
        self._to = QLabel("до")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        for w in (self.mode, self.low, self._to, self.high):
            lay.addWidget(w)
        lay.addStretch()

        self.mode.currentIndexChanged.connect(self._on_mode)
        self.low.valueChanged.connect(self._on_low)
        self.high.valueChanged.connect(self._on_high)
        self._sync_visibility()

    # ---------- стан ----------

    def current_mode(self) -> str:
        return self.mode.currentData()

    def values(self) -> tuple[int, int]:
        mode = self.current_mode()
        if mode == UPTO:
            return self._floor, self.high.value()
        if mode == EXACT:
            return self.low.value(), self.low.value()
        return self.low.value(), self.high.value()

    def set_values(self, lo: int, hi: int, mode: str | None = None) -> None:
        """Без сигналу changed. Режим за замовчуванням виводиться зі значень."""
        if mode is None:
            if lo == hi and self.mode.findData(EXACT) >= 0:
                mode = EXACT
            elif lo <= self._floor and self.mode.findData(UPTO) >= 0:
                mode = UPTO
            else:
                mode = RANGE
        self._busy = True
        self.mode.setCurrentIndex(self.mode.findData(mode))
        self.high.setValue(self.high.maximum())
        self.low.setValue(lo if mode != UPTO else self.low.minimum())
        self.high.setValue(hi)
        self._busy = False
        self._sync_visibility()

    def set_minimum(self, value: int) -> None:
        """Найменше значення, яке можна вибрати (наприклад, мінімально можлива довжина)."""
        self.low.setMinimum(value)
        self.high.setMinimum(value)

    # ---------- реакція на зміни ----------

    def _sync_visibility(self) -> None:
        mode = self._prev_mode = self.current_mode()
        self.low.setVisible(mode != UPTO)
        self._to.setVisible(mode == RANGE)
        self.high.setVisible(mode != EXACT)

    def _on_mode(self) -> None:
        if self._busy:
            return
        self._busy = True
        mode, prev = self.current_mode(), self._prev_mode
        if mode == EXACT:
            # «рівно» беремо з поля, яке було видно: у режимі «до» це верхня межа
            value = self.high.value() if prev == UPTO else self.low.value()
            self.low.setValue(value)
            self.high.setValue(value)
        elif mode == RANGE and prev == UPTO:
            # з «до N» у «від … до N»: нижню межу ставимо на мінімум
            self.low.setValue(self.low.minimum())
        elif mode == RANGE and self.low.value() > self.high.value():
            self.high.setValue(self.low.value())
        self._busy = False
        self._sync_visibility()
        self.changed.emit()

    def _on_low(self, value: int) -> None:
        if self._busy:
            return
        self._busy = True
        if self.current_mode() == EXACT or value > self.high.value():
            self.high.setValue(value)
        self._busy = False
        self.changed.emit()

    def _on_high(self, value: int) -> None:
        if self._busy:
            return
        self._busy = True
        if value < self.low.value():
            self.low.setValue(value)
        self._busy = False
        self.changed.emit()
