"""Makes the tool's release zip: builds "BT3 Mod Studio.exe" in a fresh copy of the repository (the committed
code; the tool in this folder may be running, its exe can't be replaced) and zips the exe, its "runtime" folder and
the guides in a folder "bt3-mod-studio/" -> D:\\Tenkaichi3Decomp-windows-x64\\releases\\BT3-Mod-Studio-windows.zip.
    py -I tools/release_tool.py          (commit first; then: gh release create vX.Y.Z <zip> -R Gooodak/bt3-mod-studio)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.dirname(ROOT), "releases", "BT3-Mod-Studio-windows.zip")
NAME = "BT3 Mod Studio"


def main():
    if subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
                      capture_output=True, text=True).stdout.strip():
        print("uncommitted changes: commit first (the build is made from the committed code)")
        return 1
    work = tempfile.mkdtemp(prefix="bt3ms_release_")
    try:
        clone = os.path.join(work, "src")
        subprocess.run(["git", "clone", "-q", "--no-hardlinks", ROOT, clone], check=True)
        if subprocess.run([sys.executable, "-I", os.path.join(clone, "tools", "build_exe.py")], cwd=clone).returncode:
            print("FAILED: build")
            return 1
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        tmp_zip = OUT + ".part"
        with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(os.path.join(clone, NAME + ".exe"), f"bt3-mod-studio/{NAME}.exe")
            for name in ("LISEZMOI.md", "GUIDE.md"):
                z.write(os.path.join(clone, name), f"bt3-mod-studio/{name}")
            for folder, _dirs, files in os.walk(os.path.join(clone, "runtime")):
                for f in files:
                    full = os.path.join(folder, f)
                    z.write(full, "bt3-mod-studio/" + os.path.relpath(full, clone).replace("\\", "/"))
        os.replace(tmp_zip, OUT)
        print("zip:", OUT, os.path.getsize(OUT), "bytes")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
