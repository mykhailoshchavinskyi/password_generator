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


def kinds(seg):
    """Слово, усі цифри й усі символи частини, незалежно від того, розкидані вони чи ні."""
    out = {"word": "", "digits": "", "symbols": ""}
    for kind, text in seg.parts:
        out[kind] += text
    return out


@pytest.mark.parametrize("scatter", [False, True])
@pytest.mark.parametrize("seed", range(5))
def test_default_phrase_follows_rules(seed, scatter):
    gen = Generator(Config(scatter=scatter), randbelow=seeded(seed))
    for _ in range(200):
        p = gen.generate()
        assert len(p.text) <= 26
        assert len(p.segments) == 3
        assert len({s.word for s in p.segments}) == 3
        assert p.text == "_".join(s.text for s in p.segments)
        for seg in p.segments:
            k = kinds(seg)
            assert k["word"] == seg.word.capitalize()
            assert seg.word.capitalize() in seg.text
            assert 2 <= len(k["digits"]) <= 3 and k["digits"].isdigit()
            assert 1 <= len(k["symbols"]) <= 2
            assert set(k["symbols"]) <= set("!@#$&?")
            if not scatter:
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
    # оригінал ставить цифри й символи лише групами
    cfg = Config(words=words_count, max_len=max_len, scatter=False)
    gen = Generator(cfg, words=ref.WORDS)
    assert gen.entropy_bits() == pytest.approx(ref.entropy_bits(max_len), abs=1e-9)


def test_default_entropy_with_builtin_wordlist():
    gen = Generator()
    assert gen.wordlist_size == 9904
    # розкидання додає розташувань: ~90.6 біт проти ~82.9 для груп
    assert 90 < gen.entropy_bits() < 91.5
    assert 82 < Generator(Config(scatter=False)).entropy_bits() < 84


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
        == Generator(Config(word_len_min=3, word_len_max=9)).entropy_bits()
    )


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (Config(word_len_min=6, word_len_max=4), "Мінімум літер у слові більший"),
        (Config(word_len_min=1), "Мінімум літер у слові"),
        (Config(word_len_max=13), "Максимум літер у слові"),
        (Config(word_len_min=10, word_len_max=12), "немає слів довжиною від 10 до 12 літер"),
        (Config(word_len_min=11, word_len_max=11), "немає слів довжиною рівно 11 літер"),
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


# ---------- розкидання цифр і символів ----------


def test_arrangements_counts():
    from passgen.core import arrangements

    assert arrangements(1, 1, scatter=False) == arrangements(1, 1, scatter=True) == 6
    assert arrangements(2, 1, scatter=False) == 6
    assert arrangements(2, 1, scatter=True) == 12  # 4! / (2!·1!)
    assert arrangements(2, 2, scatter=True) == 30  # 5! / (2!·2!)
    assert arrangements(0, 2, scatter=True) == 3
    assert arrangements(0, 2, scatter=False) == 2


def test_scatter_uniform_and_splits_symbols():
    # слово «ab» і 2 символи з «!?»: 3 розташування · 4 набори символів = 12 фраз
    cfg = Config(
        words=1,
        max_len=10,
        digits_min=0,
        digits_max=0,
        symbols_min=2,
        symbols_max=2,
        symbol_set="!?",
    )
    gen = Generator(cfg, ["ab"], randbelow=seeded(11))
    assert 2 ** gen.entropy_bits() == pytest.approx(12)
    n = 12_000
    counts = Counter(gen.generate().text for _ in range(n))
    assert len(counts) == 12
    assert "!Ab?" in counts and "?Ab!" in counts  # символи по обидва боки слова
    for c in counts.values():
        assert c / n == pytest.approx(1 / 12, abs=0.015)


def test_scatter_mixes_digits_and_symbols():
    # 2 цифри й 1 символ: 4!/(2!·1!) = 12 розташувань · 100 · 2 = 2400 фраз
    cfg = Config(
        words=1,
        max_len=10,
        digits_min=2,
        digits_max=2,
        symbols_min=1,
        symbols_max=1,
        symbol_set="!?",
    )
    gen = Generator(cfg, ["ab"], randbelow=seeded(12))
    assert 2 ** gen.entropy_bits() == pytest.approx(2400)
    shapes = Counter(
        re.sub(r"\d", "9", re.sub(r"[!?]", "!", gen.generate().text)) for _ in range(6000)
    )
    assert len(shapes) == 12
    assert "9Ab!9" in shapes and "9!Ab9" in shapes  # цифри розділено


def test_grouped_mode_keeps_blocks():
    cfg = Config(scatter=False, digits_min=2, digits_max=3, max_len=40)
    gen = Generator(cfg, randbelow=seeded(13))
    for _ in range(200):
        for seg in gen.generate().segments:
            assert len(split_parts(seg.text)) == 3


# ---------- довжина пароля: рівно / від–до, автоматична кількість слів ----------


def test_exact_length_count_is_exact():
    # частини 4 («ab»+1+1) або 5 («cde»+1+1) символів; рівно 8 → лише 2 частини по 4
    cfg = Config(
        min_len=8,
        max_len=8,
        auto_words=True,
        separator="",
        unique_words=False,
        digits_min=1,
        digits_max=1,
        symbols_min=1,
        symbols_max=1,
        symbol_set="!",
    )
    gen = Generator(cfg, ["ab", "cde"], randbelow=seeded(14))
    assert 2 ** gen.entropy_bits() == pytest.approx((1 * 10 * 1 * 6) ** 2)
    assert all(len(gen.generate()) == 8 for _ in range(300))


def test_length_range_is_uniform():
    # від 8 до 9: 4+4 (3600 фраз) і 4+5, 5+4 (по 3600) → довжина 9 удвічі частіша
    cfg = Config(
        min_len=8,
        max_len=9,
        auto_words=True,
        separator="",
        unique_words=False,
        digits_min=1,
        digits_max=1,
        symbols_min=1,
        symbols_max=1,
        symbol_set="!",
    )
    gen = Generator(cfg, ["ab", "cde"], randbelow=seeded(15))
    assert 2 ** gen.entropy_bits() == pytest.approx(3 * 3600)
    n = 9000
    lengths = Counter(len(gen.generate()) for _ in range(n))
    assert set(lengths) == {8, 9}
    assert lengths[9] / n == pytest.approx(2 / 3, abs=0.02)


@pytest.mark.parametrize(("length", "words"), [(12, {1}), (20, {2, 3}), (33, {3, 4}), (40, {4, 5})])
def test_exact_length_with_builtin_words(length, words):
    # кількість слів підбирається під довжину; при рівномірному виборі серед усіх фраз
    # переважає та кількість слів, що дає найбільше варіантів
    gen = Generator(
        Config(min_len=length, max_len=length, auto_words=True), randbelow=seeded(length)
    )
    seen = set()
    for _ in range(300):
        p = gen.generate()
        assert len(p) == length
        seen.add(len(p.segments))
    assert seen <= words


def test_fixed_words_with_exact_length():
    gen = Generator(Config(words=3, min_len=24, max_len=24), randbelow=seeded(16))
    for _ in range(200):
        p = gen.generate()
        assert len(p) == 24 and len(p.segments) == 3


def test_max_only_mode_matches_previous_behaviour():
    # «до N» (min_len=1) — та сама кількість фраз, що й раніше
    ref = load_reference()
    ref.WORDS_COUNT = 3
    gen = Generator(Config(max_len=26, scatter=False), words=ref.WORDS)
    assert gen.entropy_bits() == pytest.approx(ref.entropy_bits(26), abs=1e-9)


def test_impossible_exact_length_suggests_closest():
    cfg = Config(
        min_len=13,
        max_len=13,
        auto_words=True,
        word_len_min=7,
        word_len_max=7,
        digits_min=3,
        digits_max=3,
        symbols_min=2,
        symbols_max=2,
    )
    with pytest.raises(ConfigError, match=r"рівно 13 символів .*Найближчі можливі довжини: 12, 25"):
        Generator(cfg)


def test_min_len_above_max_len():
    with pytest.raises(ConfigError, match="Мінімальна довжина пароля більша"):
        Generator(Config(min_len=30, max_len=20))


def test_auto_words_respects_unique_words():
    cfg = Config(
        min_len=8,
        max_len=30,
        auto_words=True,
        digits_min=1,
        digits_max=1,
        symbols_min=1,
        symbols_max=1,
        symbol_set="!",
    )
    gen = Generator(cfg, ["ab", "cd"], randbelow=seeded(17))
    assert gen.word_counts == (1, 2)
    for _ in range(100):
        p = gen.generate()
        assert len({s.word for s in p.segments}) == len(p.segments)


def test_length_text():
    from passgen.core import length_text

    assert length_text(Config(min_len=20, max_len=20)) == "рівно 20 символів"
    assert length_text(Config(min_len=18, max_len=24)) == "від 18 до 24 символів"
    assert length_text(Config(max_len=22)) == "до 22 символів"
    assert length_text(Config(min_len=21, max_len=21)) == "рівно 21 символ"
    assert length_text(Config(max_len=21)) == "до 21 символу"


def test_words_count():
    from passgen.core import words_count

    assert [words_count(n) for n in (1, 3, 5, 11, 21, 3495, 9904)] == [
        "1 слово",
        "3 слова",
        "5 слів",
        "11 слів",
        "21 слово",
        "3495 слів",
        "9904 слова",
    ]


def test_word_len_text_genitive():
    from passgen.core import word_len_text

    assert word_len_text(Config(word_len_min=2, word_len_max=4)) == "від 2 до 4 літер"
    assert word_len_text(Config(word_len_min=3, word_len_max=3)) == "рівно 3 літери"


# ---------- велика літера у випадковому місці та leet ----------


def test_spellings_counts():
    from passgen.core import spellings

    assert spellings("seat", Case.CAPITALIZE, leet=False) == 1
    assert spellings("seat", Case.RANDOM, leet=False) == 4
    # внутрішні «e», «a» замінні: 2^2 = 4
    assert spellings("seat", Case.CAPITALIZE, leet=True) == 4
    # велика на s/t: 2·4, на e/a: 2·2 → 12
    assert spellings("seat", Case.RANDOM, leet=True) == 12
    # перша й остання літери не замінюються
    assert spellings("sat", Case.LOWER, leet=True) == 2
    assert spellings("dry", Case.LOWER, leet=True) == 1


def test_random_case_and_leet_are_uniform_and_exact():
    cfg = Config(
        words=1,
        max_len=10,
        digits_min=0,
        digits_max=0,
        symbols_min=0,
        symbols_max=0,
        case=Case.RANDOM,
        leet=True,
    )
    gen = Generator(cfg, ["seat"], randbelow=seeded(21))
    assert 2 ** gen.entropy_bits() == pytest.approx(12)
    n = 12_000
    counts = Counter(gen.generate().text for _ in range(n))
    assert set(counts) == {
        "Seat",
        "S3at",
        "Se@t",
        "S3@t",
        "seaT",
        "s3aT",
        "se@T",
        "s3@T",
        "sEat",
        "sE@t",
        "seAt",
        "s3At",
    }
    for c in counts.values():
        assert c / n == pytest.approx(1 / 12, abs=0.015)


def test_leet_count_is_exact_with_prefix_words():
    # «car7» могло б бути і «cart» з t→7, і «car» + цифра 7, але кінцеві літери
    # не замінюються, тож усі 80 фраз різні: (2 + 2) · 10 · 2 розташування
    cfg = Config(
        words=1,
        max_len=10,
        digits_min=1,
        digits_max=1,
        symbols_min=0,
        symbols_max=0,
        symbol_set="",
        leet=True,
    )
    gen = Generator(cfg, ["car", "cart"], randbelow=seeded(22))
    assert 2 ** gen.entropy_bits() == pytest.approx(80)
    assert len({gen.generate().text for _ in range(8000)}) == 80


@pytest.mark.parametrize("case", [Case.CAPITALIZE, Case.RANDOM, Case.UPPER])
def test_leet_and_case_decode_back_to_word(case):
    from passgen.core import LEET

    back = {v: k for k, v in LEET.items()}
    gen = Generator(Config(case=case, leet=True, max_len=40), randbelow=seeded(23))
    for _ in range(300):
        for seg in gen.generate().segments:
            written = kinds(seg)["word"]
            assert written[0].isalpha() and written[-1].isalpha()
            assert "".join(back.get(c, c) for c in written).lower() == seg.word
            if case is Case.RANDOM:
                assert sum(c.isupper() for c in written) == 1


def test_random_case_and_leet_add_entropy():
    base = Generator().entropy_bits()
    both = Generator(Config(case=Case.RANDOM, leet=True)).entropy_bits()
    assert both - base > 6


# ---------- без схожих символів ----------


def no_similar(text):
    return not set(text) & set("01|") and not ("I" in text and "l" in text)


@pytest.mark.parametrize("case", list(Case))
@pytest.mark.parametrize("leet", [False, True])
def test_avoid_similar_never_mixes_lookalikes(case, leet):
    cfg = Config(case=case, leet=leet, avoid_similar=True, symbol_set="!@#$|", max_len=40)
    gen = Generator(cfg, randbelow=seeded(31))
    for _ in range(300):
        text = gen.generate().text
        assert no_similar(text), text


def test_without_option_lookalikes_do_appear():
    gen = Generator(Config(max_len=40), randbelow=seeded(32))
    texts = "".join(gen.generate().text for _ in range(300))
    assert "0" in texts and "1" in texts


def test_avoid_similar_spellings():
    from passgen.core import spellings

    # «silo»: внутрішні i, l; leet i→1 вилучено, велика не на «i» → s, l, o
    assert spellings("silo", Case.RANDOM, leet=True, avoid_similar=True) == 3
    assert spellings("silo", Case.RANDOM, leet=True, avoid_similar=False) == 7


def test_avoid_similar_is_exact_and_uniform():
    # 3 написання · 8 цифр · 2 розташування = 48 фраз
    cfg = Config(
        words=1,
        max_len=10,
        digits_min=1,
        digits_max=1,
        symbols_min=0,
        symbols_max=0,
        symbol_set="",
        case=Case.RANDOM,
        leet=True,
        avoid_similar=True,
    )
    gen = Generator(cfg, ["silo"], randbelow=seeded(33))
    assert 2 ** gen.entropy_bits() == pytest.approx(48)
    n = 9600
    counts = Counter(gen.generate().text for _ in range(n))
    assert len(counts) == 48
    assert all(no_similar(t) for t in counts)
    for c in counts.values():
        assert c / n == pytest.approx(1 / 48, abs=0.012)


def test_avoid_similar_drops_words_starting_with_i_only_when_capitalized():
    words = ["into", "lit", "ink"]
    cap = Generator(Config(words=1, max_len=12, avoid_similar=True), words)
    low = Generator(Config(words=1, max_len=12, avoid_similar=True, case=Case.LOWER), words)
    assert cap.usable_words == 1
    assert low.usable_words == 3


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (Config(avoid_similar=True, symbol_set="|"), "набір спецсимволів порожній"),
        (Config(avoid_similar=True, separator="|"), "Роздільник містить схожі символи"),
        (Config(avoid_similar=True, separator="l"), "Роздільник містить схожі символи"),
    ],
)
def test_avoid_similar_errors(config, message):
    with pytest.raises(ConfigError, match=message):
        Generator(config)


def test_avoid_similar_costs_a_little_entropy():
    base = Generator().entropy_bits()
    avoided = Generator(Config(avoid_similar=True)).entropy_bits()
    assert 0 < base - avoided < 4
