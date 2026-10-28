import importlib.util
import random
import re
from collections import Counter
from pathlib import Path

import pytest

from passgen.core import Case, Config, ConfigError, Generator

REFERENCE = Path(__file__).parent / "reference" / "passgen_original.py"
SMALL_WORDS = ["ab", "cd", "efg"]


def seeded(seed=1):
    return random.Random(seed).randrange


def load_reference():
    spec = importlib.util.spec_from_file_location("passgen_original", REFERENCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def split_parts(text):
    return re.findall(r"[A-Za-z]+|\d+|[^A-Za-z\d]+", text)


@pytest.mark.parametrize("seed", range(5))
def test_default_phrase_follows_rules(seed):
    gen = Generator(randbelow=seeded(seed))
    for _ in range(200):
        p = gen.generate()
        assert len(p.text) <= 26
        assert len(p.segments) == 3
        assert len({s.word for s in p.segments}) == 3
        assert p.text == "_".join(s.text for s in p.segments)
        for seg in p.segments:
            kinds = dict(seg.parts)
            assert kinds["word"] == seg.word.capitalize()
            assert 2 <= len(kinds["digits"]) <= 3 and kinds["digits"].isdigit()
            assert 1 <= len(kinds["symbols"]) <= 2
            assert set(kinds["symbols"]) <= set("!@#$&?")
            assert len(split_parts(seg.text)) == 3


def test_tokens_rebuild_text():
    p = Generator(randbelow=seeded()).generate()
    assert "".join(t for _, t in p.tokens()) == p.text
    assert [k for k, _ in p.tokens()].count("separator") == 2


@pytest.mark.parametrize("words_count", [1, 3])
@pytest.mark.parametrize("max_len", [12, 20, 26, 40])
def test_entropy_matches_original_script(words_count, max_len):
    ref = load_reference()
    ref.WORDS_COUNT = words_count
    if max_len < words_count * 6 + words_count - 1:
        pytest.skip("неможлива комбінація для оригіналу")
    gen = Generator(Config(words=words_count, max_len=max_len), words=ref.WORDS)
    assert gen.entropy_bits() == pytest.approx(ref.entropy_bits(max_len), abs=1e-9)


def test_default_entropy_with_builtin_wordlist():
    gen = Generator()
    assert gen.wordlist_size == 3495
    assert 81 < gen.entropy_bits() < 83


def test_uniform_over_all_phrases():
    # 1 слово, по 1 цифрі й символу: (2·10·2 + 1·10·2) · 3! = 360 рівноймовірних фраз
    cfg = Config(
        words=1,
        max_len=10,
        digits_min=1,
        digits_max=1,
        symbols_min=1,
        symbols_max=1,
        symbol_set="!?",
    )
    gen = Generator(cfg, SMALL_WORDS, randbelow=seeded(7))
    assert 2 ** gen.entropy_bits() == pytest.approx(360)
    n = 36_000
    counts = Counter(gen.generate().text for _ in range(n))
    assert len(counts) == 360
    expected = n / 360
    chi2 = sum((c - expected) ** 2 / expected for c in counts.values())
    assert chi2 < 359 + 5 * (2 * 359) ** 0.5


def test_max_len_cut_keeps_uniformity():
    # частини довжиною 4 (слово з 2 літер) і 5 (з 3 літер) мають однакову кількість варіантів,
    # тож при межі 9 допустимі пари (4,4), (4,5), (5,4) рівноймовірні, а (5,5) відсікається
    cfg = Config(
        words=2,
        max_len=9,
        separator="",
        digits_min=1,
        digits_max=1,
        symbols_min=1,
        symbols_max=1,
        symbol_set="!?",
        unique_words=False,
    )
    gen = Generator(cfg, ["ab", "cd", "efg", "hij"], randbelow=seeded(3))
    n = 20_000
    pairs = Counter(tuple(len(s.text) for s in gen.generate().segments) for _ in range(n))
    assert set(pairs) == {(4, 4), (4, 5), (5, 4)}
    for pair in pairs:
        assert pairs[pair] / n == pytest.approx(1 / 3, abs=0.02)


def test_empty_blocks_weighted_correctly():
    # "Ab" або одна цифра до/після слова: 1 + 10·2 = 21 рівноймовірна фраза
    cfg = Config(
        words=1, max_len=10, digits_min=0, digits_max=1, symbols_min=0, symbols_max=0, symbol_set=""
    )
    gen = Generator(cfg, ["ab"], randbelow=seeded(5))
    assert 2 ** gen.entropy_bits() == pytest.approx(21)
    n = 21_000
    counts = Counter(gen.generate().text for _ in range(n))
    assert len(counts) == 21
    assert counts["Ab"] / n == pytest.approx(1 / 21, abs=0.008)


@pytest.mark.parametrize(
    ("case", "check"),
    [(Case.CAPITALIZE, str.istitle), (Case.LOWER, str.islower), (Case.UPPER, str.isupper)],
)
def test_case_modes(case, check):
    p = Generator(Config(case=case), randbelow=seeded()).generate()
    for seg in p.segments:
        assert check(dict(seg.parts)["word"])


def test_custom_separator_and_symbols():
    cfg = Config(words=4, max_len=60, separator="-+", symbol_set="%%^")
    p = Generator(cfg, randbelow=seeded()).generate()
    assert p.text.count("-+") == 3
    for seg in p.segments:
        assert set(dict(seg.parts)["symbols"]) <= {"%", "^"}


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (Config(max_len=10), "Максимальна довжина замала"),
        (Config(words=0), "Кількість слів"),
        (Config(words=7), "Кількість слів"),
        (Config(digits_min=3, digits_max=2), "Мінімум цифр більший"),
        (Config(symbols_min=2, symbols_max=1), "Мінімум символів більший"),
        (Config(symbol_set="!a"), "Недопустимі спецсимволи: a"),
        (Config(symbol_set=""), "хоча б один спецсимвол"),
        (Config(separator="____"), "не більше 3"),
        (Config(separator=" "), "пробіли"),
    ],
)
def test_invalid_config(config, message):
    with pytest.raises(ConfigError, match=message):
        Generator(config)


def test_empty_symbol_set_allowed_without_symbols():
    cfg = Config(symbols_min=0, symbols_max=0, symbol_set="", max_len=40)
    p = Generator(cfg, randbelow=seeded()).generate()
    assert not re.search(r"[^A-Za-z0-9_]", p.text)


def test_unique_words_needs_enough_words():
    with pytest.raises(ConfigError, match="потрібно 3 різних"):
        Generator(Config(words=3, max_len=40), ["ab", "cd"])


@pytest.mark.parametrize(("lo", "hi"), [(5, 5), (4, 6), (3, 3), (7, 7)])
def test_word_length_limits(lo, hi):
    cfg = Config(word_len_min=lo, word_len_max=hi, max_len=40)
    gen = Generator(cfg, randbelow=seeded(lo * 10 + hi))
    for _ in range(200):
        assert all(lo <= len(s.word) <= hi for s in gen.generate().segments)


def test_word_length_entropy_counts_only_matching_words():
    # 2 слова по 2 літери, 1 слово з 3 літер; рівно 2 літери → 2·10·2·3! = 240 фраз
    cfg = Config(
        words=1,
        max_len=10,
        word_len_min=2,
        word_len_max=2,
        digits_min=1,
        digits_max=1,
        symbols_min=1,
        symbols_max=1,
        symbol_set="!?",
    )
    gen = Generator(cfg, SMALL_WORDS)
    assert gen.usable_words == 2
    assert gen.wordlist_size == 3
    assert 2 ** gen.entropy_bits() == pytest.approx(240)


def test_default_word_length_keeps_original_behaviour():
    assert (
        Generator().entropy_bits()
        == Generator(Config(word_len_min=3, word_len_max=7)).entropy_bits()
    )


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (Config(word_len_min=6, word_len_max=4), "Мінімум літер у слові більший"),
        (Config(word_len_min=1), "Мінімум літер у слові"),
        (Config(word_len_max=13), "Максимум літер у слові"),
        (Config(word_len_min=10, word_len_max=12), "немає слів довжиною від 10 до 12 літер"),
        (Config(word_len_min=8, word_len_max=8), "немає слів довжиною рівно 8 літер"),
    ],
)
def test_invalid_word_length(config, message):
    with pytest.raises(ConfigError, match=message):
        Generator(config)


def test_letters_plural():
    from passgen.core import letters

    assert [letters(n) for n in (1, 2, 4, 5, 11, 12, 21)] == [
        "1 літера",
        "2 літери",
        "4 літери",
        "5 літер",
        "11 літер",
        "12 літер",
        "21 літера",
    ]
