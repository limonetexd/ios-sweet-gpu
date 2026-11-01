#!/bin/bash
# Build the GPU user space for sweet on a Mac (GitHub Actions: .github/workflows/userland.yml):
# Mesa 25.0.7 freedreno + softpipe as libOSMesa (ios-topaz userland/mesa, from vcvkk
# darwin-redwood / HackiOS), the OpenGL ES library behind EAGLContext (eagl.c +
# gl_osmesa.c), the backboardd loader (topaz_inject.c), the backboardd wrapper
# (bbd_wrap.c) and gl_test (HackiOS: a triangle drawn with OSMesa, read back).
#
#   userland/build-gpu.sh DONOR_DIR OUT_DIR
#
# DONOR_DIR holds the pinned clones topaz/ (MakrSas/ios-topaz) and hackios/
# (oosexgang/hackios-xnu-kernel). Installed on the phone under /topaz/lib (the paths
# compiled into topaz_inject.c and bbd_wrap.c); see tools/sweet-gpu-userland.py.
set -euo pipefail
D=$(cd "$1" && pwd)
mkdir -p "$2"
OUT=$(cd "$2" && pwd)
T=$D/topaz/userland
H=$D/hackios/userland
SDK=$(xcrun --sdk iphoneos --show-sdk-path)
MACSDK=$(xcrun --sdk macosx --show-sdk-path)
CLANG=$(xcrun --sdk iphoneos -f clang)

# Mesa: mk-mesa-mac.sh expects to sit in userland/ (patches and redwood-drm in userland/mesa/).
cp "$T/mesa/mk-mesa-mac.sh" "$T/mk-mesa-mac.sh"
mkdir -p "$T/build-mesa"
PATH=/opt/homebrew/opt/bison/bin:$PATH bash "$T/mk-mesa-mac.sh" || {
	tail -50 "$T/build-mesa/meson-setup.log" 2>/dev/null || true
	tail -80 "$T/build-mesa/ninja.log" 2>/dev/null || true
	exit 1
}
M=$T/build-mesa/out

# iOS SDKs ship IOKit without headers: use the macOS SDK's (the user-space API is the same).
INC=$OUT/.inc
mkdir -p "$INC"
rm -rf "$INC/IOKit"
cp -R "$MACSDK/System/Library/Frameworks/IOKit.framework/Headers" "$INC/IOKit"
CC=("$CLANG" -target arm64-apple-ios16.0 -isysroot "$SDK" -O1 -I"$INC" -Wno-deprecated-declarations)

python3 "$H/mkeagl.py" "$H/src/eagl_slots.txt" "$M/gl.xml" "$M/exported-gl.txt" "$T/gpu/eagl.c" > "$INC/eagl_gen.h"
"${CC[@]}" -dynamiclib -install_name /topaz/lib/libtopaz-gl.dylib -I"$T/gpu" \
	-framework CoreFoundation -framework IOKit -framework IOSurface -lobjc "$M/libOSMesa.8.dylib" \
	-o "$OUT/libtopaz-gl.dylib" "$T/gpu/eagl.c" "$T/gpu/gl_osmesa.c"
"${CC[@]}" -dynamiclib -install_name /topaz/lib/libtopaz-inject.dylib \
	-framework CoreFoundation -framework IOKit -lobjc -o "$OUT/libtopaz-inject.dylib" "$T/gpu/topaz_inject.c"
"${CC[@]}" -o "$OUT/backboardd" "$T/gpu/bbd_wrap.c"
if [ -f "$H/src/gl_test.c" ]; then
	"${CC[@]}" -I"$H/src" -framework CoreFoundation -framework IOKit "$M/libOSMesa.8.dylib" \
		-o "$OUT/gl_test" "$H/src/gl_test.c" || echo "gl_test: not built"
fi
cp "$M/libOSMesa.8.dylib" "$OUT/"
for f in "$OUT"/*.dylib "$OUT"/backboardd "$OUT"/gl_test; do
	[ -f "$f" ] && codesign -f -s - "$f"
done
rm -rf "$INC"
(cd "$OUT" && shasum -a 256 * > SHA256SUMS && ls -l)
