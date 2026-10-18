#!/bin/sh
# Build toolchain for Tenkaichi3Decomp (Windows target), after source/port/release/Dockerfile.
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq --no-install-recommends ca-certificates curl gnupg build-essential binutils python3 cmake \
    ninja-build pkg-config git p7zip-full zip unzip clang-22 llvm-22 libclang-22-dev python3-clang-22 glslang-tools \
    mingw-w64 > /tmp/apt.log 2>&1 || { tail -20 /tmp/apt.log; exit 1; }
ln -sf /usr/bin/clang-22 /usr/local/bin/clang
ln -sf /usr/bin/llc-22 /usr/local/bin/llc
update-alternatives --set x86_64-w64-mingw32-gcc /usr/bin/x86_64-w64-mingw32-gcc-posix
update-alternatives --set x86_64-w64-mingw32-g++ /usr/bin/x86_64-w64-mingw32-g++-posix
mkdir -p /opt/sdl3-mingw
curl -fsSL -o /tmp/sdl-mingw.tar.gz https://github.com/libsdl-org/SDL/releases/download/release-3.4.12/SDL3-devel-3.4.12-mingw.tar.gz
tar -xzf /tmp/sdl-mingw.tar.gz -C /opt/sdl3-mingw
ls /opt/sdl3-mingw/SDL3-3.4.12/x86_64-w64-mingw32
clang --version | head -1
x86_64-w64-mingw32-gcc --version | head -1
python3 -c 'import clang.cindex; print("python clang ok")'
glslangValidator --version | head -1
