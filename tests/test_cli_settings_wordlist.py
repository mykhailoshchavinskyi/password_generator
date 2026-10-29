import json
import os
import re
import subprocess
import sys

import pytest

from passgen import settings
from passgen.cli import main
from passgen.core import Case, Config
from passgen.wordlist import MIN_CUSTOM_WORDS, WordlistError, builtin_words, load_file

# ---------- CLI ----------


def test_cli_plain(capsys):
    assert main(["-n", "4", "--plain"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 4
    assert all(len(line) <= 26 for line in lines)


def test_cli_table_and_options(capsys):
    main(
        [
            "-n",
            "2",
            "--words",
            "2",
            "--digits",
            "1-1",
            "--symbols",
            "1",
            "--sep",
            "-",
            "--case",
            "upper",
            "--max-len",
            "30",
        ]
    )
    out = capsys.readouterr().out
    assert "Парольна фраза" in out
    assert "Стійкість генератора загалом" in out
    assert "Словник: 9904 слова" in out


def test_cli_rejects_impossible_length(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--max-len", "5"])
    assert e.value.code == 2
    assert "Максимальна довжина замала" in capsys.readouterr().err


def test_cli_rejects_bad_range():
    with pytest.raises(SystemExit):
        main(["--digits", "a-b"])


def test_cli_custom_wordlist(tmp_path, capsys):
    path = tmp_path / "w.txt"
    path.write_text("\n".join(f"w{chr(97 + i % 26)}{chr(97 + i // 26)}" for i in range(60)))
    main(["-n", "3", "--plain", "--wordlist", str(path)])
    assert len(capsys.readouterr().out.splitlines()) == 3


# ---------- словник ----------


def test_builtin_wordlist_clean():
    words = builtin_words()
    assert len(words) == 9904
    assert len(set(words)) == len(words)
    assert {len(w) for w in words} == set(range(3, 10))
    # стоп-слова прибрано і з власного списку, і з EFF
    for removed in ("piss", "lynch", "fascist", "berlin", "batman", "trump", "twitter"):
        assert removed not in words


def test_load_file_normalizes(tmp_path):
    path = tmp_path / "w.txt"
    good = [f"word{chr(97 + i % 26)}{chr(97 + i // 26)}" for i in range(MIN_CUSTOM_WORDS)]
    path.write_text(" ".join(w.upper() for w in good) + "\nbad1 x ąb " + good[0], "utf-8")
    assert load_file(path) == tuple(sorted(good))


def test_load_file_errors(tmp_path):
    with pytest.raises(WordlistError, match="прочитати"):
        load_file(tmp_path / "missing.txt")
    small = tmp_path / "s.txt"
    small.write_text("one two three")
    with pytest.raises(WordlistError, match="щонайменше"):
        load_file(small)


# ---------- налаштування ----------


def test_settings_roundtrip(tmp_path):
    path = tmp_path / "s.json"
    s = settings.AppSettings(
        config=Config(words=4, max_len=40, case=Case.UPPER, separator="-"),
        clipboard_clear_seconds=0,
        always_on_top=True,
        wordlist_path="/x/words.txt",
        settings_open=False,
    )
    settings.save(s, path)
    assert settings.load(path) == s


def test_settings_missing_or_broken(tmp_path):
    assert settings.load(tmp_path / "none.json") == settings.AppSettings()
    broken = tmp_path / "b.json"
    broken.write_text("{not json")
    assert settings.load(broken) == settings.AppSettings()


def test_settings_bad_values_fall_back(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(
        json.dumps(
            {
                "config": {"words": "три", "max_len": 30, "case": "weird"},
                "clipboard_clear_seconds": 9999,
                "always_on_top": "yes",
            }
        )
    )
    s = settings.load(path)
    assert s.config == Config(max_len=30)
    assert s.clipboard_clear_seconds == 30
    assert s.always_on_top is False


def test_settings_invalid_combination_resets_config(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"config": {"digits_min": 5, "digits_max": 1}}))
    assert settings.load(path).config == Config()


def test_config_dir_override(tmp_path, monkeypatch):
    monkeypatch.setenv("PASSGEN_CONFIG_DIR", str(tmp_path))
    assert settings.settings_path() == tmp_path / "settings.json"


def test_cli_survives_non_utf8_console():
    # Windows із перенаправленим виводом: stdout у cp1252
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    out = subprocess.run(
        [sys.executable, "-m", "passgen.cli", "-n", "1"], capture_output=True, env=env
    )
    assert out.returncode == 0, out.stderr.decode("utf-8", "replace")
    assert "Парольна фраза" in out.stdout.decode("utf-8")


@pytest.mark.parametrize(("arg", "lo", "hi"), [("5", 5, 5), ("4-6", 4, 6)])
def test_cli_word_len(capsys, arg, lo, hi):
    main(["-n", "20", "--plain", "--word-len", arg, "--max-len", "40", "--case", "lower"])
    for line in capsys.readouterr().out.splitlines():
        words = re.findall(r"[a-z]+", line)
        assert len(words) == 3
        assert all(lo <= len(w) <= hi for w in words)


def test_settings_roundtrip_word_len(tmp_path):
    path = tmp_path / "s.json"
    s = settings.AppSettings(config=Config(word_len_min=4, word_len_max=4, max_len=30))
    settings.save(s, path)
    assert settings.load(path).config.word_len_min == 4


def test_old_settings_without_word_len(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"config": {"words": 4, "max_len": 40}}))
    cfg = settings.load(path).config
    assert (cfg.words, cfg.word_len_min, cfg.word_len_max) == (4, 2, 12)


@pytest.mark.parametrize(("arg", "lo", "hi"), [("20", 20, 20), ("18-24", 18, 24)])
def test_cli_length(capsys, arg, lo, hi):
    main(["-n", "30", "--plain", "--length", arg])
    for line in capsys.readouterr().out.splitlines():
        assert lo <= len(line) <= hi


def test_cli_length_with_fixed_words(capsys):
    main(["-n", "20", "--plain", "--length", "24", "--words", "3", "--case", "lower"])
    for line in capsys.readouterr().out.splitlines():
        assert len(line) == 24
        assert len(re.findall(r"[a-z]+", line)) == 3


def test_cli_impossible_length(capsys):
    with pytest.raises(SystemExit):
        main(["--length", "13", "--word-len", "7", "--digits", "3", "--symbols", "2"])
    assert "Найближчі можливі довжини" in capsys.readouterr().err


def test_cli_grouped(capsys):
    main(["-n", "50", "--plain", "--grouped", "--case", "lower", "--sep", "_"])
    for line in capsys.readouterr().out.splitlines():
        for part in line.split("_"):
            assert len(re.findall(r"[a-z]+|\d+|[^a-z\d]+", part)) == 3


def test_settings_roundtrip_length_and_scatter(tmp_path):
    path = tmp_path / "s.json"
    cfg = Config(min_len=20, max_len=24, auto_words=True, scatter=False)
    settings.save(settings.AppSettings(config=cfg), path)
    assert settings.load(path).config == cfg


def test_old_settings_get_new_defaults(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"config": {"words": 3, "max_len": 26}}))
    cfg = settings.load(path).config
    assert (cfg.min_len, cfg.auto_words, cfg.scatter) == (1, False, True)


def test_cli_random_case_and_leet(capsys):
    main(["-n", "30", "--plain", "--case", "random", "--leet", "--grouped", "--sep", "_"])
    for line in capsys.readouterr().out.splitlines():
        for part in line.split("_"):
            word = max(re.findall(r"[A-Za-z][A-Za-z@310$7]*[A-Za-z]|[A-Za-z]+", part), key=len)
            assert sum(c.isupper() for c in word) == 1


def test_settings_roundtrip_case_random_leet(tmp_path):
    path = tmp_path / "s.json"
    cfg = Config(case=Case.RANDOM, leet=True)
    settings.save(settings.AppSettings(config=cfg), path)
    assert settings.load(path).config == cfg
