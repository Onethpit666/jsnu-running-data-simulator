"""Run from any working directory. Console remains visible for errors and shutdown."""
from pathlib import Path
import subprocess
import sys


def main():
    base = Path(__file__).resolve().parent
    command = [sys.executable, "-m", "PyInstaller", str(base / "app.py"),
               "--name=KeepRunStudio", "--onefile", "--console", "--clean", "--noconfirm",
               "--distpath=" + str(base / "dist"), "--workpath=" + str(base / "build"),
               "--specpath=" + str(base),
               "--add-data=" + str(base / "static") + ";static",
               "--add-data=" + str(base / "templates") + ";templates"]
    subprocess.run(command, cwd=base, check=True)
    print("EXE:", base / "dist" / "KeepRunStudio.exe")


if __name__ == "__main__":
    main()
