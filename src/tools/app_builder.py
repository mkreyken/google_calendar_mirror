import os
import subprocess
from pathlib import Path

from src.util.filesystem import project_root

APP_NAME = "ICCalendarApp"
ENTRY = "src/services/launcher.py"


def remove_dir(path: Path) -> None:
    if path.exists() and path.is_dir():
        subprocess.run(
            ["cmd", "/c", "rmdir", "/s", "/q", str(path)],
            shell=True
        )


def build_exe() -> None:
    root = project_root(installed=False)  # your helper that returns the real project root
    remove_dir(root / "build")
    os.chdir(root)  # CRITICAL: run PyInstaller from project root

    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        f"--name={APP_NAME}",
        "--paths=src",
        ENTRY,
    ]

    subprocess.run(cmd, check=True)
    print(f"EXE built at {root / 'dist' / (APP_NAME + '.exe')}")


if __name__ == "__main__":
    build_exe()
