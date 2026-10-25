"""Вбудований словник і завантаження власного словника з файлу."""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

_WORD_RE = re.compile(r"^[a-z]{2,12}$")
MIN_CUSTOM_WORDS = 50


class WordlistError(ValueError):
    pass


def builtin_words() -> tuple[str, ...]:
    text = resources.files("passgen").joinpath("data/words.txt").read_text(encoding="utf-8")
    return normalize(text.split())


def normalize(words) -> tuple[str, ...]:
    """Малі латинські літери, 2–12 символів, без повторів, у відсортованому порядку."""
    return tuple(sorted({w.strip().lower() for w in words if _WORD_RE.match(w.strip().lower())}))


def load_file(path: str | Path) -> tuple[str, ...]:
    """Слова з текстового файлу: по одному або через пробіли. Інші рядки ігноруються."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise WordlistError(f"Не вдалося прочитати файл словника: {e}") from e
    words = normalize(text.split())
    if len(words) < MIN_CUSTOM_WORDS:
        raise WordlistError(
            f"У словнику {len(words)} придатних слів, потрібно щонайменше {MIN_CUSTOM_WORDS}. "
            "Слово має складатися з 2–12 латинських літер."
        )
    return words
