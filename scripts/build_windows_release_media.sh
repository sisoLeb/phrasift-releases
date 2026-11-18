#!/usr/bin/env bash
# Build redistributable Windows media tools from their pinned upstream sources.
# Run on Linux with MinGW-w64, make, curl, xz, and NASM.
set -euo pipefail

recipe=$(realpath "${BASH_SOURCE[0]}")
out=$(realpath -m "${1:?Select a new output directory}")
mkdir -p "$out/source"
source_dir="$out/source"
cross=x86_64-w64-mingw32-
ffmpeg_archive=ffmpeg-9.0.2.tar.xz
zlib_archive=zlib-1.4.tar.gz
dav1d_archive=dav1d-1.5.4.tar.xz

cd "$source_dir"
curl -fsSL --retry 3 "https://ffmpeg.org/releases/$ffmpeg_archive" -o "$ffmpeg_archive"
curl -fsSL --retry 3 "https://github.com/madler/zlib/releases/download/v1.4/$zlib_archive" -o "$zlib_archive"
curl -fsSL --retry 3 "https://download.videolan.org/pub/videolan/dav1d/1.5.4/$dav1d_archive" -o "$dav1d_archive"
sha256sum -c <<EOF
8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e  $ffmpeg_archive
02dd159783677a749c04adbdd02b55b8a2bcc7e054f51b76b549199a916ad584  $zlib_archive
686616b7c69eb88d44459391ab25cac13b6647a3b288835c5784e71c1514a5c5  $dav1d_archive
EOF
cp "$recipe" "$source_dir/build_windows_media.sh"

work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
tar -xf "$ffmpeg_archive" -C "$work"
tar -xf "$zlib_archive" -C "$work"
tar -xf "$dav1d_archive" -C "$work"
zlib="$work/zlib-1.4"
ffmpeg="$work/ffmpeg-9.0.2"
jobs=$(getconf _NPROCESSORS_ONLN)
make -C "$zlib" -j"$jobs" -f win32/Makefile.gcc "PREFIX=$cross" libz.a
cat > "$source_dir/mingw-cross.ini" <<EOF
[binaries]
c = '${cross}gcc'
ar = '${cross}ar'
strip = '${cross}strip'
windres = '${cross}windres'
pkg-config = 'pkg-config'
[host_machine]
system = 'windows'
cpu_family = 'x86_64'
cpu = 'x86_64'
endian = 'little'
[properties]
needs_exe_wrapper = true
EOF
meson setup "$work/dav1d-build" "$work/dav1d-1.5.4" \
    --cross-file "$source_dir/mingw-cross.ini" --prefix "$out/install" --libdir lib \
    --buildtype release --default-library static -Denable_tools=false \
    -Denable_tests=false -Denable_examples=false -Denable_docs=false
meson compile -C "$work/dav1d-build" -j "$jobs"
meson install -C "$work/dav1d-build"
cp "$work/dav1d-1.5.4/COPYING" "$source_dir/dav1d-COPYING"
export PKG_CONFIG_LIBDIR="$out/install/lib/pkgconfig"

cd "$ffmpeg"
./configure --prefix="$out/install" --target-os=mingw32 --arch=x86_64 \
    --cross-prefix="$cross" --enable-cross-compile \
    --disable-autodetect --disable-gpl --disable-nonfree --disable-network \
    --disable-doc --disable-debug --disable-ffplay --disable-pthreads \
    --enable-w32threads --enable-shared --disable-static --enable-zlib \
    --enable-mediafoundation --enable-d3d11va --enable-encoder=h264_mf --enable-libdav1d \
    --pkg-config=pkg-config --pkg-config-flags=--static \
    --extra-cflags="-I$zlib -I$out/install/include" \
    --extra-ldflags="-L$zlib -L$out/install/lib -static-libgcc"
cp config.h ffbuild/config.mak "$source_dir/"
cp COPYING.LGPLv2.1 "$source_dir/FFmpeg-COPYING.LGPLv2.1"
cp "$zlib/LICENSE" "$source_dir/zlib-LICENSE"
"${cross}gcc" --version > "$source_dir/compiler.txt"
make -j"$jobs"
make install
mkdir -p "$out/bin"
cp "$out/install/bin/"*.exe "$out/install/bin/"*.dll "$out/bin/"
cd "$out/bin"
sha256sum ./*.exe ./*.dll > "$source_dir/windows-media-sha256.txt"
