"""Збирає застосунок для поточної ОС і пакує його в release/.

    python scripts/build.py

Windows: Passgen-<версія>-windows-<arch>.exe (один файл)
macOS:   Passgen-<версія>-macos-<arch>.dmg   (Passgen.app)
Linux:   Passgen-<версія>-linux-<arch>.tar.gz, а також .AppImage,
         якщо в PATH є appimagetool або задано змінну APPIMAGETOOL.

Потрібні: pip install -e .[build]
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
RELEASE = ROOT / "release"
ICON = ROOT / "src" / "passgen" / "data" / "icon.png"
NAME = "Passgen"
# модулі Qt, які застосунку не потрібні, але потрапляють у збірку через плагіни
EXCLUDES = ["PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtNetwork", "PySide6.QtOpenGL", "tkinter"]
BUNDLE_ID = "io.github.mykhailoshchavinskyi.passgen"

DESKTOP_ENTRY = """[Desktop Entry]
Type=Application
Name=Passgen
Comment=Генератор парольних фраз
Exec=Passgen
Icon=passgen
Categories=Utility;Security;
Terminal=false
"""

APPRUN = """#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/passgen/Passgen" "$@"
"""


def version() -> str:
    sys.path.insert(0, str(ROOT / "src"))
    from passgen import __version__

    return __version__


def arch() -> str:
    m = platform.machine().lower()
    return {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64"}.get(m, m)


def run(*cmd: str) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def pyinstaller(onefile: bool) -> None:
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed",
        "--name", NAME,
        "--icon", str(ICON),
        "--collect-data", "passgen",
        "--distpath", str(DIST),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
    ]  # fmt: skip
    for module in EXCLUDES:
        args += ["--exclude-module", module]
    if onefile:
        args.append("--onefile")
    if sys.platform == "darwin":
        args += ["--osx-bundle-identifier", BUNDLE_ID]
    run(*args, str(ROOT / "packaging" / "launcher.py"))


def build_windows(stem: str) -> list[Path]:
    pyinstaller(onefile=True)
    out = RELEASE / f"{stem}.exe"
    shutil.copy2(DIST / f"{NAME}.exe", out)
    return [out]


def build_macos(stem: str) -> list[Path]:
    pyinstaller(onefile=False)
    out = RELEASE / f"{stem}.dmg"
    run("hdiutil", "create", "-volname", NAME, "-srcfolder", str(DIST / f"{NAME}.app"),
        "-ov", "-format", "UDZO", str(out))  # fmt: skip
    return [out]


def build_linux(stem: str) -> list[Path]:
    pyinstaller(onefile=False)
    app_dir = DIST / NAME
    tarball = RELEASE / f"{stem}.tar.gz"
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(app_dir, arcname=NAME)
    outputs = [tarball]

    tool = os.environ.get("APPIMAGETOOL") or shutil.which("appimagetool")
    if not tool:
        print("appimagetool не знайдено, AppImage пропущено")
        return outputs
    appdir = DIST / f"{NAME}.AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    shutil.copytree(app_dir, appdir / "usr" / "lib" / "passgen")
    (appdir / "AppRun").write_text(APPRUN)
    (appdir / "AppRun").chmod(0o755)
    (appdir / "passgen.desktop").write_text(DESKTOP_ENTRY, encoding="utf-8")
    shutil.copy2(ICON, appdir / "passgen.png")
    image = RELEASE / f"{stem}.AppImage"
    env = {**os.environ, "ARCH": platform.machine()}
    cmd = [tool, "--appimage-extract-and-run", "--no-appstream", str(appdir), str(image)]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT, env=env)
    outputs.append(image)
    return outputs


def _utf8_output() -> None:
    """Українські повідомлення не мають падати, якщо консоль у cp1252 (Windows, CI, `> файл`)."""
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if encoding != "utf8" and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main() -> int:
    _utf8_output()
    RELEASE.mkdir(exist_ok=True)
    os_name = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    stem = f"{NAME}-{version()}-{os_name}-{arch()}"
    builder = {"windows": build_windows, "macos": build_macos, "linux": build_linux}[os_name]
    for path in builder(stem):
        print(f"готово: {path.relative_to(ROOT)} ({path.stat().st_size / 1e6:.1f} МБ)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
