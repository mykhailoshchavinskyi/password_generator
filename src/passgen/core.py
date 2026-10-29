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
WORD_LEN_RANGE = (2, 12)  # як і обмеження на слова у власному словнику
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
    # за замовчуванням без обмеження: увесь допустимий діапазон
    word_len_min: int = WORD_LEN_RANGE[0]
    word_len_max: int = WORD_LEN_RANGE[1]
    max_len: int = 26
    # нижня межа довжини всієї фрази; 1 — без нижньої межі («до max_len»)
    min_len: int = 1
    # True: кількість слів (1–6) підбирається автоматично під потрібну довжину
    auto_words: bool = False
    digits_min: int = 2
    digits_max: int = 3
    symbols_min: int = 1
    symbols_max: int = 2
    symbol_set: str = "!@#$&?"
    separator: str = "_"
    case: Case = Case.CAPITALIZE
    unique_words: bool = True
    # True: кожна цифра й кожен символ стоять окремо у випадковому місці частини
    # (групи теж можливі); False: цифри й символи завжди йдуть суцільними блоками
    scatter: bool = True


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


def letters(n: int) -> str:
    """1 літера, 3 літери, 5 літер, 12 літер."""
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} літера"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} літери"
    return f"{n} літер"


def _genitive(n: int, one: str, many: str) -> str:
    """Після «до»: до 21 літери / символу, до 24 літер / символів."""
    return f"{n} {one if n % 10 == 1 and n % 100 != 11 else many}"


def word_len_text(config: Config) -> str:
    """«рівно 5 літер» або «від 4 до 6 літер» — для повідомлень користувачу."""
    lo, hi = config.word_len_min, config.word_len_max
    return f"рівно {letters(lo)}" if lo == hi else f"від {lo} до {_genitive(hi, 'літери', 'літер')}"


def symbols_count(n: int) -> str:
    """1 символ, 3 символи, 26 символів."""
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} символ"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} символи"
    return f"{n} символів"


def length_text(config: Config) -> str:
    """«рівно 20 символів», «від 18 до 24 символів» або «до 26 символів»."""
    lo, hi = config.min_len, config.max_len
    upto = _genitive(hi, "символу", "символів")
    if lo == hi:
        return f"рівно {symbols_count(lo)}"
    if lo > 1:
        return f"від {lo} до {upto}"
    return f"до {upto}"


def unique_symbols(symbols: str) -> str:
    return "".join(dict.fromkeys(symbols))


def _check_range(name: str, value: int, bounds: tuple[int, int]) -> None:
    lo, hi = bounds
    if not lo <= value <= hi:
        raise ConfigError(f"{name}: допустимо від {lo} до {hi}, вказано {value}.")


def validate(config: Config) -> None:
    """Перевіряє параметри, що не залежать від словника."""
    _check_range("Кількість слів", config.words, WORDS_RANGE)
    _check_range("Мінімум літер у слові", config.word_len_min, WORD_LEN_RANGE)
    _check_range("Максимум літер у слові", config.word_len_max, WORD_LEN_RANGE)
    if config.word_len_min > config.word_len_max:
        raise ConfigError("Мінімум літер у слові більший за максимум.")
    _check_range("Максимальна довжина", config.max_len, MAX_LEN_RANGE)
    _check_range("Мінімальна довжина", config.min_len, MAX_LEN_RANGE)
    if config.min_len > config.max_len:
        raise ConfigError("Мінімальна довжина пароля більша за максимальну.")
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


def arrangements(nd: int, ns: int, scatter: bool) -> int:
    """Скільки різних розташувань слова, nd цифр і ns символів у частині.

    Групами: перестановки непорожніх блоків (3! = 6, з одним порожнім блоком 2, з двома 1).
    Окремо: позиції слова, цифр і символів серед 1 + nd + ns місць.
    """
    if scatter:
        return math.factorial(1 + nd + ns) // (math.factorial(nd) * math.factorial(ns))
    return math.factorial(1 + (nd > 0) + (ns > 0))


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
        self.wordlist_size = len(words)
        words = tuple(w for w in words if config.word_len_min <= len(w) <= config.word_len_max)
        if not words:
            raise ConfigError(f"У словнику немає слів довжиною {word_len_text(config)}.")
        self.word_counts = (
            tuple(range(WORDS_RANGE[0], WORDS_RANGE[1] + 1))
            if config.auto_words
            else (config.words,)
        )
        if config.unique_words:
            # слова у фразі не повторюються, тож слів має вистачити
            self.word_counts = tuple(k for k in self.word_counts if k <= len(words))
            if not self.word_counts:
                raise ConfigError(
                    f"Слів довжиною {word_len_text(config)} у словнику лише {len(words)}, "
                    f"а потрібно {config.words} різних."
                )
        self.usable_words = len(words)

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
                    orders = arrangements(nd, ns, config.scatter)
                    self._types.append(((n, nd, ns), count, count * orders))

        self._by_seglen: dict[int, int] = defaultdict(int)
        for t, _, weight in self._types:
            self._by_seglen[sum(t)] += weight
        self._memo: dict[tuple[int, int], int] = {}
        self._min_seg, self._max_seg = min(self._by_seglen), max(self._by_seglen)

        # для кожної можливої кількості слів k — скільки фраз потрібної довжини
        weights = [(k, self._ways(k)) for k in self.word_counts]
        self._k_weights = [(k, w) for k, w in weights if w > 0]
        reachable = self._reachable_lengths()
        self.min_length, self.max_length = min(reachable), max(reachable)
        if not self._k_weights:
            raise ConfigError(self._length_error(reachable))

    def _sep_len(self, k: int) -> int:
        return len(self.config.separator) * (k - 1)

    def _seg_bounds(self, k: int, lo: int, hi: int) -> range:
        """Суми довжин частин (без роздільників) для фраз з k слів довжиною від lo до hi."""
        sep = self._sep_len(k)
        return range(max(lo - sep, k * self._min_seg), min(hi - sep, k * self._max_seg) + 1)

    def _exact(self, total: int, k: int) -> int:
        """Скільки способів заповнити k частин рівно total символами (з вагами типів)."""
        if k == 0:
            return 1 if total == 0 else 0
        if not k * self._min_seg <= total <= k * self._max_seg:
            return 0
        key = (total, k)
        if key not in self._memo:
            self._memo[key] = sum(
                w * self._exact(total - sl, k - 1)
                for sl, w in self._by_seglen.items()
                if sl <= total
            )
        return self._memo[key]

    def _ways(self, k: int) -> int:
        """Скільки фраз з k слів мають довжину в межах min_len..max_len."""
        cfg = self.config
        return sum(self._exact(t, k) for t in self._seg_bounds(k, cfg.min_len, cfg.max_len))

    def _reachable_lengths(self) -> list[int]:
        """Усі довжини фраз, можливі з цими налаштуваннями без обмеження довжини."""
        lengths = {
            t + self._sep_len(k)
            for k in self.word_counts
            for t in self._seg_bounds(k, 1, 10 * MAX_LEN_RANGE[1])
            if self._exact(t, k)
        }
        return sorted(lengths)

    def _length_error(self, reachable: list[int]) -> str:
        cfg = self.config
        if cfg.min_len <= 1 and not cfg.auto_words:
            return (
                f"Максимальна довжина замала: з цими параметрами потрібно "
                f"щонайменше {symbols_count(self.min_length)}."
            )

        def distance(n: int) -> int:
            return (
                0
                if cfg.min_len <= n <= cfg.max_len
                else min(abs(n - cfg.min_len), abs(n - cfg.max_len))
            )

        closest = sorted(sorted(reachable, key=lambda n: (distance(n), n))[:3])
        return (
            f"Пароль довжиною {length_text(cfg)} з цими налаштуваннями неможливий. "
            f"Найближчі можливі довжини: {', '.join(map(str, closest))}."
        )

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
        digits = [self._choice(DIGITS) for _ in range(nd)]
        symbols = [self._choice(self._symbols) for _ in range(ns)]
        if self.config.scatter:
            # кожна цифра й символ — окремий елемент; рівномірна перестановка всіх
            # елементів дає рівномірний вибір серед arrangements(nd, ns) розташувань
            parts = [("word", self.config.case.apply(word))]
            parts += [("digits", d) for d in digits] + [("symbols", c) for c in symbols]
        else:
            parts = [
                ("word", self.config.case.apply(word)),
                ("digits", "".join(digits)),
                ("symbols", "".join(symbols)),
            ]
        self._shuffle(parts)
        return Segment(word, tuple(p for p in parts if p[1]), count)

    def generate(self) -> Passphrase:
        """Одна фраза, рівномірно вибрана серед усіх, що відповідають налаштуванням."""
        cfg = self.config
        for _ in range(MAX_ATTEMPTS):
            k = self._weighted_choice(self._k_weights)
            bounds = self._seg_bounds(k, cfg.min_len, cfg.max_len)
            remaining = self._weighted_choice([(t, self._exact(t, k)) for t in bounds])
            segs = []
            for j in range(k, 0, -1):
                opts = [
                    (sl, w * self._exact(remaining - sl, j - 1))
                    for sl, w in self._by_seglen.items()
                    if sl <= remaining
                ]
                sl = self._weighted_choice([o for o in opts if o[1] > 0])
                segs.append(self._segment(sl))
                remaining -= sl
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
        total = sum(w for _, w in self._k_weights)
        return math.log2(total) if total else 0.0


def strength_label(bits: float) -> str:
    if bits >= 80:
        return "Дуже стійкий"
    if bits >= 60:
        return "Стійкий"
    if bits >= 45:
        return "Середній"
    return "Слабкий"
