"""Кольори частин фрази та шкали стійкості для світлої й темної теми."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Colors:
    word: str
    digits: str
    symbols: str
    separator: str
    accent: str
    good: str
    warn: str
    bad: str
    muted: str


LIGHT = Colors(
    word="#15202b",
    digits="#2c5bc7",
    symbols="#b04a14",
    separator="#9aa6b3",
    accent="#0d6670",
    good="#1f7a43",
    warn="#a86a00",
    bad="#b3261e",
    muted="#566373",
)
DARK = Colors(
    word="#e4eaf0",
    digits="#8eacff",
    symbols="#f2955f",
    separator="#5f6e7d",
    accent="#4fc0c9",
    good="#5cc98a",
    warn="#e2ad48",
    bad="#f07a70",
    muted="#94a2b1",
)


def current() -> Colors:
    window = QApplication.palette().color(QPalette.ColorRole.Window)
    return DARK if window.lightness() < 128 else LIGHT


def strength_color(bits: float, c: Colors) -> str:
    if bits >= 60:
        return c.good
    if bits >= 45:
        return c.warn
    return c.bad
