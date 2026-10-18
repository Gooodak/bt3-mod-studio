#!/bin/sh
# The release zip of BT3 Mod Studio's edition of the port (branch etendu of the Windows clone D:\...\source), without
# the test kit and without any game data (package.py strips the program's data tables, as for z3xox's releases).
# Written to D:\Tenkaichi3Decomp-windows-x64\releases\.
set -e
SRC=/mnt/d/Tenkaichi3Decomp-windows-x64/source
OUT=/mnt/d/Tenkaichi3Decomp-windows-x64/releases
cd /root/bt3
git fetch -q "$SRC" +etendu:refs/remotes/win/etendu
if [ ! -d /root/bt3-release ]; then
    git worktree add -q -f /root/bt3-release win/etendu
fi
cd /root/bt3-release
git checkout -q -f --detach win/etendu
git clean -q -fd port/src src include
export BT3_SKELETON=1 BT3_CC=win64 BT3_SDL3=/opt/sdl3-mingw/SDL3-3.4.12/x86_64-w64-mingw32
start=$(date +%s)
mkdir -p port/build
python3 port/tools/undefined.py > port/build/compile_win64.txt 2>&1 || { tail -30 port/build/compile_win64.txt; exit 1; }
if grep -q "^FAILED" port/build/compile_win64.txt; then grep -A15 "^FAILED" port/build/compile_win64.txt | head -60; exit 1; fi
python3 port/tools/link.py > port/build/link_win64.txt 2>&1 || { tail -30 port/build/link_win64.txt; exit 1; }
tail -1 port/build/link_win64.txt
sh port/setup/build.sh win > port/build/setup_win64.txt 2>&1 || { tail -30 port/build/setup_win64.txt; exit 1; }
python3 port/tools/package.py > port/build/package_win64.txt 2>&1 || { tail -30 port/build/package_win64.txt; exit 1; }
tail -3 port/build/package_win64.txt
mkdir -p $OUT
v=$(git describe --tags --always win/etendu)
cp port/build/Tenkaichi3Decomp-windows-x64.zip "$OUT/Tenkaichi3Decomp-etendu-$v-windows-x64.zip"
ls -la "$OUT"
echo "release built in $(( $(date +%s) - start )) s ($v)"
