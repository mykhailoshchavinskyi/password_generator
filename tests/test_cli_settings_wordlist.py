import json

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
    assert "Словник: 3495 слів" in out


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
    assert len(words) == 3495
    assert len(set(words)) == len(words)
    for removed in ("piss", "lynch", "fascist", "berlin", "batman"):
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
