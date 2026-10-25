"""Алгоритм генерації парольних фраз.

Фраза складається з N частин, з'єднаних роздільником. Кожна частина — слово зі
словника, блок цифр і блок спецсимволів, переставлені у випадковому порядку.

Генератор вибирає рівномірно серед усіх фраз, що вкладаються в max_len: спочатку
динамічним програмуванням рахує, скільки фраз існує для кожного розподілу
довжин частин, і вибирає довжини з відповідними вагами. Алгоритм перенесено з
початкового passgen.py; додано параметри та коректну вагу для порожніх блоків.
"""

from __future__ import annotations

import math
import secrets
import string
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from enum import Enum

from passgen.wordlist import builtin_words, normalize

DIGITS = "0123456789"
ALLOWED_SYMBOLS = string.punctuation
MAX_ATTEMPTS = 1000

WORDS_RANGE = (1, 6)
MAX_LEN_RANGE = (1, 128)
DIGITS_RANGE = (0, 6)
SYMBOLS_RANGE = (0, 4)
SEPARATOR_MAX = 3


class ConfigError(ValueError):
    """Неможливі або некоректні параметри. Текст повідомлення показується користувачу."""


class Case(str, Enum):
    CAPITALIZE = "capitalize"
    LOWER = "lower"
    UPPER = "upper"

    def apply(self, word: str) -> str:
        if self is Case.UPPER:
            return word.upper()
        if self is Case.LOWER:
            return word.lower()
        return word.capitalize()


@dataclass(frozen=True)
class Config:
    words: int = 3
    max_len: int = 26
    digits_min: int = 2
    digits_max: int = 3
    symbols_min: int = 1
    symbols_max: int = 2
    symbol_set: str = "!@#$&?"
    separator: str = "_"
    case: Case = Case.CAPITALIZE
    unique_words: bool = True


@dataclass(frozen=True)
class Segment:
    word: str
    # (вид, текст) у порядку появи; вид: "word", "digits" або "symbols"
    parts: tuple[tuple[str, str], ...]
    # скільки різних частин має точно такий самий шаблон
    # (та сама довжина слова, к-сть цифр і символів, той самий порядок)
    pattern_count: int

    @property
    def text(self) -> str:
        return "".join(t for _, t in self.parts)


@dataclass(frozen=True)
class Passphrase:
    text: str
    bits: float
    segments: tuple[Segment, ...] = field(repr=False)
    separator: str = field(repr=False)

    def __str__(self) -> str:
        return self.text

    def __len__(self) -> int:
        return len(self.text)

    def tokens(self) -> Iterator[tuple[str, str]]:
        """Фраза як послідовність (вид, текст), включно з роздільниками ("separator")."""
        for i, seg in enumerate(self.segments):
            if i and self.separator:
                yield "separator", self.separator
            for kind, text in seg.parts:
                if text:
                    yield kind, text


def unique_symbols(symbols: str) -> str:
    return "".join(dict.fromkeys(symbols))


def _check_range(name: str, value: int, bounds: tuple[int, int]) -> None:
    lo, hi = bounds
    if not lo <= value <= hi:
        raise ConfigError(f"{name}: допустимо від {lo} до {hi}, вказано {value}.")


def validate(config: Config) -> None:
    """Перевіряє параметри, що не залежать від словника."""
    _check_range("Кількість слів", config.words, WORDS_RANGE)
    _check_range("Максимальна довжина", config.max_len, MAX_LEN_RANGE)
    _check_range("Мінімум цифр", config.digits_min, DIGITS_RANGE)
    _check_range("Максимум цифр", config.digits_max, DIGITS_RANGE)
    _check_range("Мінімум символів", config.symbols_min, SYMBOLS_RANGE)
    _check_range("Максимум символів", config.symbols_max, SYMBOLS_RANGE)
    if config.digits_min > config.digits_max:
        raise ConfigError("Мінімум цифр більший за максимум.")
    if config.symbols_min > config.symbols_max:
        raise ConfigError("Мінімум символів більший за максимум.")
    bad = sorted(set(config.symbol_set) - set(ALLOWED_SYMBOLS))
    if bad:
        raise ConfigError(
            f"Недопустимі спецсимволи: {' '.join(bad)}. "
            "Можна використовувати лише розділові знаки ASCII, наприклад !@#$%&?*"
        )
    if config.symbols_max > 0 and not config.symbol_set:
        raise ConfigError("Вкажіть хоча б один спецсимвол або встановіть максимум символів 0.")
    if len(config.separator) > SEPARATOR_MAX:
        raise ConfigError(f"Роздільник може мати не більше {SEPARATOR_MAX} символів.")
    if any(not ch.isprintable() or ch.isspace() for ch in config.separator):
        raise ConfigError("Роздільник не може містити пробіли чи службові символи.")


class Generator:
    """Генератор фраз для фіксованих параметрів і словника.

    randbelow можна підмінити в тестах; за замовчуванням secrets.randbelow (CSPRNG).
    """

    def __init__(
        self,
        config: Config | None = None,
        words: Iterable[str] | None = None,
        randbelow: Callable[[int], int] = secrets.randbelow,
    ) -> None:
        self.config = config = config or Config()
        validate(config)
        self._randbelow = randbelow
        self._symbols = unique_symbols(config.symbol_set)

        words = builtin_words() if words is None else normalize(words)
        if not words:
            raise ConfigError("Словник порожній.")
        if config.unique_words and len(words) < config.words:
            raise ConfigError(
                f"У словнику {len(words)} слів, а потрібно {config.words} різних слів."
            )
        self.wordlist_size = len(words)

        by_len: dict[int, list[str]] = defaultdict(list)
        for w in words:
            by_len[len(w)].append(w)
        self._by_len = {n: tuple(ws) for n, ws in sorted(by_len.items())}

        # тип частини: (довжина слова, к-сть цифр, к-сть символів)
        self._types: list[tuple[tuple[int, int, int], int, int]] = []
        for n, ws in self._by_len.items():
            for nd in range(config.digits_min, config.digits_max + 1):
                for ns in range(config.symbols_min, config.symbols_max + 1):
                    count = len(ws) * len(DIGITS) ** nd * len(self._symbols) ** ns
                    if count == 0:
                        continue
                    # різних порядків блоків: 3! = 6, але порожній блок не дає нових
                    orders = math.factorial(1 + (nd > 0) + (ns > 0))
                    self._types.append(((n, nd, ns), count, count * orders))

        self._by_seglen: dict[int, int] = defaultdict(int)
        for t, _, weight in self._types:
            self._by_seglen[sum(t)] += weight
        self._memo: dict[tuple[int, int], int] = {}

        sep = len(config.separator) * (config.words - 1)
        self._budget = config.max_len - sep
        self.min_length = config.words * min(self._by_seglen) + sep
        self.max_length = min(config.max_len, config.words * max(self._by_seglen) + sep)
        if config.max_len < self.min_length:
            raise ConfigError(
                f"Максимальна довжина замала: з цими параметрами потрібно "
                f"щонайменше {self.min_length} символів."
            )

    def _ways(self, budget: int, k: int) -> int:
        """Кількість способів заповнити k частин, не перевищуючи budget символів."""
        if k == 0:
            return 1
        key = (budget, k)
        if key not in self._memo:
            self._memo[key] = sum(
                w * self._ways(budget - sl, k - 1)
                for sl, w in self._by_seglen.items()
                if sl <= budget
            )
        return self._memo[key]

    def _weighted_choice(self, options: Sequence[tuple[object, int]]):
        r = self._randbelow(sum(w for _, w in options))
        for value, w in options:
            r -= w
            if r < 0:
                return value
        raise AssertionError("unreachable")

    def _choice(self, seq: Sequence):
        return seq[self._randbelow(len(seq))]

    def _shuffle(self, items: list) -> None:
        for i in range(len(items) - 1, 0, -1):
            j = self._randbelow(i + 1)
            items[i], items[j] = items[j], items[i]

    def _segment(self, seg_len: int) -> Segment:
        (n, nd, ns), count, _ = self._weighted_choice(
            [(t, t[2]) for t in self._types if sum(t[0]) == seg_len]
        )
        word = self._choice(self._by_len[n])
        parts = [
            ("word", self.config.case.apply(word)),
            ("digits", "".join(self._choice(DIGITS) for _ in range(nd))),
            ("symbols", "".join(self._choice(self._symbols) for _ in range(ns))),
        ]
        self._shuffle(parts)
        return Segment(word, tuple(parts), count)

    def generate(self) -> Passphrase:
        """Одна фраза, рівномірно вибрана серед усіх, що вкладаються в max_len."""
        cfg = self.config
        for _ in range(MAX_ATTEMPTS):
            budget = self._budget
            segs = []
            for k in range(cfg.words, 0, -1):
                opts = [
                    (sl, w * self._ways(budget - sl, k - 1))
                    for sl, w in self._by_seglen.items()
                    if sl <= budget
                ]
                sl = self._weighted_choice([o for o in opts if o[1] > 0])
                segs.append(self._segment(sl))
                budget -= sl
            if cfg.unique_words and len({s.word for s in segs}) != len(segs):
                continue
            return Passphrase(
                text=cfg.separator.join(s.text for s in segs),
                bits=sum(math.log2(s.pattern_count) for s in segs),
                segments=tuple(segs),
                separator=cfg.separator,
            )
        raise ConfigError("Не вдалося підібрати фразу без повторів слів. Збільште словник.")

    def generate_many(self, count: int) -> list[Passphrase]:
        return [self.generate() for _ in range(count)]

    def entropy_bits(self) -> float:
        """Приблизна стійкість (біт) за умови, що зловмисник знає правила."""
        total = self._ways(self._budget, self.config.words)
        return math.log2(total) if total else 0.0


def strength_label(bits: float) -> str:
    if bits >= 80:
        return "Дуже стійкий"
    if bits >= 60:
        return "Стійкий"
    if bits >= 45:
        return "Середній"
    return "Слабкий"
