"""Збереження налаштувань у JSON у теці конфігурації користувача."""

from __future__ import annotations

import contextlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

from passgen.core import Case, Config, ConfigError, validate

CLIPBOARD_CLEAR_RANGE = (0, 300)  # 0 — не очищати


def config_dir() -> Path:
    if override := os.environ.get("PASSGEN_CONFIG_DIR"):
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "passgen"


def settings_path() -> Path:
    return config_dir() / "settings.json"


@dataclass
class AppSettings:
    config: Config = field(default_factory=Config)
    clipboard_clear_seconds: int = 30
    always_on_top: bool = False
    wordlist_path: str | None = None
    settings_open: bool = True

    def to_dict(self) -> dict:
        d = asdict(self)
        d["config"]["case"] = self.config.case.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> AppSettings:
        """Невідомі ключі ігноруються, некоректні значення замінюються стандартними."""
        s = cls()
        if not isinstance(data, dict):
            return s
        cfg = data.get("config")
        if isinstance(cfg, dict):
            s.config = _config_from_dict(cfg)
        lo, hi = CLIPBOARD_CLEAR_RANGE
        secs = data.get("clipboard_clear_seconds")
        if isinstance(secs, int) and not isinstance(secs, bool) and lo <= secs <= hi:
            s.clipboard_clear_seconds = secs
        if isinstance(data.get("always_on_top"), bool):
            s.always_on_top = data["always_on_top"]
        if isinstance(data.get("settings_open"), bool):
            s.settings_open = data["settings_open"]
        path = data.get("wordlist_path")
        if isinstance(path, str) and path:
            s.wordlist_path = path
        return s


def _config_from_dict(data: dict) -> Config:
    """Поля неправильного типу пропускаються; якщо разом параметри некоректні — стандартні."""
    default = Config()
    values = {}
    for f in fields(Config):
        if f.name not in data:
            continue
        value = data[f.name]
        if f.name == "case":
            with contextlib.suppress(ValueError):
                values[f.name] = Case(value)
        elif type(value) is type(getattr(default, f.name)):
            values[f.name] = value
    cfg = replace(default, **values)
    try:
        validate(cfg)
    except ConfigError:
        return default
    return cfg


def load(path: Path | None = None) -> AppSettings:
    path = path or settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return AppSettings()
    return AppSettings.from_dict(data)


def save(settings: AppSettings, path: Path | None = None) -> None:
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
