#!/bin/sh
# Builds BT3 Mod Studio's edition of the port (branch etendu of the Windows clone D:\...\source) with the test kit,
# into the test install (testkit/). The exe it replaces is kept once as bt3-upstream.exe.
set -e
KIT=/mnt/d/Tenkaichi3Decomp-windows-x64/bt3-mod-studio/testkit-src
SRC=/mnt/d/Tenkaichi3Decomp-windows-x64/source
OUT=/mnt/d/Tenkaichi3Decomp-windows-x64/testkit
cd /root/bt3
git fetch -q "$SRC" +etendu:refs/remotes/win/etendu
git checkout -q -f -B testkit-etendu win/etendu
git clean -q -fd port/src src include
python3 $KIT/apply_hooks.py
export BT3_SKELETON=1 BT3_CC=win64 BT3_SDL3=/opt/sdl3-mingw/SDL3-3.4.12/x86_64-w64-mingw32
start=$(date +%s)
python3 port/tools/undefined.py > port/build/compile_win64.txt 2>&1 || { tail -30 port/build/compile_win64.txt; exit 1; }
if grep -q "^FAILED" port/build/compile_win64.txt; then grep -A15 "^FAILED" port/build/compile_win64.txt | head -60; exit 1; fi
grep -i "error" port/build/compile_win64.txt | head -20 || true
python3 port/tools/link.py > port/build/link_win64.txt 2>&1 || { tail -30 port/build/link_win64.txt; exit 1; }
tail -2 port/build/link_win64.txt
[ -f $OUT/bt3-upstream.exe ] || cp $OUT/bt3.exe $OUT/bt3-upstream.exe
cp port/build/bt3.exe port/build/bt3.dat port/build/bt3.exe.mem port/build/bt3.exe.map $OUT/
echo "rebuilt in $(( $(date +%s) - start )) s ($(git describe --tags --always win/etendu))"
