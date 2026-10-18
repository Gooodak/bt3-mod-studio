#!/bin/sh
# Builds the Windows program of Tenkaichi3Decomp in /root/bt3 (after source/port/release/inside.sh, Windows part).
set -e
if [ ! -d /root/bt3/.git ]; then
    git clone -q https://github.com/z3xox/Tenkaichi3Decomp.git /root/bt3
fi
cd /root/bt3
git log -1 --format='%h %s'
export BT3_SKELETON=1 BT3_CC=win64 BT3_SDL3=/opt/sdl3-mingw/SDL3-3.4.12/x86_64-w64-mingw32
mkdir -p port/build
start=$(date +%s)
python3 port/tools/undefined.py > port/build/compile_win64.txt 2>&1 || { tail -20 port/build/compile_win64.txt; exit 1; }
if grep -q "^FAILED" port/build/compile_win64.txt; then grep "^FAILED" port/build/compile_win64.txt | head -20; exit 1; fi
echo "compiled in $(( $(date +%s) - start )) s"
python3 port/tools/link.py > port/build/link_win64.txt 2>&1 || { tail -30 port/build/link_win64.txt; exit 1; }
tail -5 port/build/link_win64.txt
echo "built in $(( $(date +%s) - start )) s"
ls -la port/build/*.exe 2>/dev/null || find port/build -maxdepth 2 -name "*.exe" | head
