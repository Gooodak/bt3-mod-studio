"""Builds "BT3 Mod Studio.exe" (Python included: nothing to install for whoever runs it) from studio.py.
Usage: py -I tools/build_exe.py      (needs PyInstaller: py -m pip install --user pyinstaller)

The program is the exe plus its folder "runtime" next to it (PyInstaller's one-folder build). A one-file exe would
unpack Python into a temporary folder at every start (seconds, more with an antivirus): this starts at once.
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import base64

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
NAME = "BT3 Mod Studio"
RUNTIME = "runtime"


def make_icon(path):
    """An .ico of the tool's icon (studio_ui.ball_png) in several sizes, each stored as PNG."""
    import studio_ui
    sizes = [16, 24, 32, 48, 64, 128, 256]
    pngs = [base64.b64decode(studio_ui.ball_png(s)) for s in sizes]
    head = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    dirs = b""
    for s, png in zip(sizes, pngs):
        dirs += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
    with open(path, "wb") as f:
        f.write(head + dirs + b"".join(pngs))
    return path


def main():
    work = os.path.join(tempfile.gettempdir(), "bt3modstudio_build")
    dist = os.path.join(work, "dist")
    shutil.rmtree(dist, ignore_errors=True)
    os.makedirs(work, exist_ok=True)
    icon = make_icon(os.path.join(work, "icon.ico"))
    r = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
                        "--collect-all", "py7zr",  # (the .7z mods of the community: py7zr and its codecs)
                        "--name", NAME, "--contents-directory", RUNTIME, "--icon", icon, "--distpath", dist,
                        "--workpath", os.path.join(work, "work"), "--specpath", work,
                        os.path.join(ROOT, "studio.py")], cwd=ROOT)
    built = os.path.join(dist, NAME)
    if r.returncode != 0 or not os.path.exists(os.path.join(built, NAME + ".exe")):
        print("FAILED")
        return 1
    # the exe and its folder next to the tool's other files (in place of the previous build)
    shutil.rmtree(os.path.join(ROOT, RUNTIME), ignore_errors=True)
    exe = os.path.join(ROOT, NAME + ".exe")
    if os.path.exists(exe):
        os.remove(exe)
    shutil.move(os.path.join(built, RUNTIME), os.path.join(ROOT, RUNTIME))
    shutil.move(os.path.join(built, NAME + ".exe"), exe)
    print("built:", exe, "+", os.path.join(ROOT, RUNTIME))
    return 0


if __name__ == "__main__":
    sys.exit(main())
