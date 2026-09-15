"""Build the release bundle with PyInstaller.

    python build.py 1.0.0

Produces dist/AndroidContextDeploy/ and an archive next to it:
AndroidContextDeploy-v1.0.0-windows.zip or -linux.tar.gz.

onedir, not onefile: it starts instantly (nothing to unpack). The files a
company edits -- deploy.json, banner.txt, locales/ -- are copied next to the
executable rather than bundled, so changing them never needs a rebuild. adb
comes from the adbutils package; there is no adb binary in this repository.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "AndroidContextDeploy"
NEXT_TO_EXE = ["deploy.json", "banner.txt", "locales", "scrcpy_server", "LICENSE"]


def main(version: str) -> Path:
    version = version.lstrip("v")
    dist = ROOT / "dist"
    subprocess.run([
        sys.executable, "-m", "PyInstaller", str(ROOT / "main.py"),
        "--name", NAME, "--onedir", "--windowed", "--noconfirm", "--clean",
        "--paths", str(ROOT / "src"),
        "--distpath", str(dist), "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build"),
        "--collect-data", "customtkinter",   # CTk themes
        "--collect-binaries", "av",          # ffmpeg libraries for the Mirror
        "--collect-data", "adbutils",        # the bundled adb
        "--exclude-module", "pytest",
    ], check=True)

    app_dir = dist / NAME
    for item in NEXT_TO_EXE:
        source = ROOT / item
        if source.is_dir():
            shutil.copytree(source, app_dir / item, dirs_exist_ok=True)
        else:
            shutil.copy2(source, app_dir / item)

    windows = sys.platform == "win32"
    archive = shutil.make_archive(
        str(dist / f"{NAME}-v{version}-{'windows' if windows else 'linux'}"),
        "zip" if windows else "gztar", root_dir=dist, base_dir=NAME)
    print(f"OK: {archive}")
    return Path(archive)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "0.0.0-dev")
