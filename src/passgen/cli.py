"""Консольний інтерфейс, сумісний з початковим passgen.py.

Приклади:
  passgen-cli                 # 10 фраз
  passgen-cli -n 5 --max-len 30
  passgen-cli --words 4 --digits 1-2 --symbols 1-1 --symbol-set '!?' --sep -
"""

from __future__ import annotations

import argparse
import sys

from passgen.core import Case, Config, ConfigError, Generator
from passgen.wordlist import WordlistError, load_file


def _range(text: str) -> tuple[int, int]:
    try:
        lo, _, hi = text.partition("-")
        lo_i = int(lo)
        hi_i = int(hi) if hi else lo_i
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"очікується діапазон на кшталт 2-3, отримано {text!r}"
        ) from None
    return lo_i, hi_i


def _utf8_output() -> None:
    """Українські повідомлення не мають падати, якщо консоль у cp1252 (Windows, CI, `> файл`)."""
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if encoding != "utf8" and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    d = Config()
    ap = argparse.ArgumentParser(prog="passgen-cli", description="Генератор парольних фраз")
    ap.add_argument("-n", "--count", type=int, default=10, help="кількість фраз (10)")
    ap.add_argument("--max-len", type=int, default=d.max_len, help=f"макс. довжина ({d.max_len})")
    ap.add_argument("--words", type=int, default=d.words, help=f"кількість слів ({d.words})")
    ap.add_argument(
        "--digits",
        type=_range,
        default=(d.digits_min, d.digits_max),
        metavar="MIN-MAX",
        help="цифр у частині (2-3)",
    )
    ap.add_argument(
        "--symbols",
        type=_range,
        default=(d.symbols_min, d.symbols_max),
        metavar="MIN-MAX",
        help="спецсимволів у частині (1-2)",
    )
    ap.add_argument(
        "--symbol-set", default=d.symbol_set, help=f"набір спецсимволів ({d.symbol_set})"
    )
    ap.add_argument("--sep", default=d.separator, help=f"роздільник ({d.separator})")
    ap.add_argument(
        "--case",
        choices=[c.value for c in Case],
        default=d.case.value,
        help="регістр слів (capitalize)",
    )
    ap.add_argument("--wordlist", metavar="FILE", help="власний словник (.txt)")
    ap.add_argument("--plain", action="store_true", help="лише фрази, без таблиці")
    return ap


def main(argv: list[str] | None = None) -> int:
    _utf8_output()
    ap = build_parser()
    args = ap.parse_args(argv)
    if not 1 <= args.count <= 10_000:
        ap.error("--count має бути від 1 до 10000")
    config = Config(
        words=args.words,
        max_len=args.max_len,
        digits_min=args.digits[0],
        digits_max=args.digits[1],
        symbols_min=args.symbols[0],
        symbols_max=args.symbols[1],
        symbol_set=args.symbol_set,
        separator=args.sep,
        case=Case(args.case),
    )
    try:
        words = load_file(args.wordlist) if args.wordlist else None
        gen = Generator(config, words)
        phrases = gen.generate_many(args.count)
    except (ConfigError, WordlistError) as e:
        ap.error(str(e))

    if args.plain:
        print("\n".join(p.text for p in phrases))
        return 0

    width = max(config.max_len, len("Парольна фраза")) + 2
    print(f"{'Парольна фраза':<{width}} {'Довж.':>5}  {'Біт':>5}")
    print("-" * (width + 13))
    for p in phrases:
        print(f"{p.text:<{width}} {len(p):>5}  {p.bits:>5.1f}")
    print("-" * (width + 13))
    print("Біт = стійкість, навіть якщо зловмисник знає точний шаблон фрази.")
    print(
        f"Стійкість генератора загалом (знає лише правила): "
        f"~{gen.entropy_bits():.1f} біт. Словник: {gen.wordlist_size} слів."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
