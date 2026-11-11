#!/bin/bash
# Build the Metal path on macOS from pinned sources. Nothing lands in git.
#
#   tools/metal-build.sh [all|host|ios|driver|test|payload]    (default all)
#
# Donor: oosexgang/hackios-xnu-userland (MIT), Mesa 25.0.7 (MIT).
# Our changes to the donor: userland/metal/*.patch, applied in name order.
#
# METAL_WORK   work directory (default ~/Developer/ios-sweet-work/metal-build)
#
# Outputs in $METAL_WORK:
#   host/build/.../air2nir, ir3_compiler   shader compiler for this Mac
#   ios/build/.../libredwoodair.dylib      shader runtime for iOS 16 arm64
#   obj/RedwoodMetal                       Metal plug-in
#   obj/metaltest, obj/default.metallib    on-device Metal self-test (userland/metaltest)
#   pay/                                   files to copy into the phone's root, at these paths
#
# Needs: Xcode with the iPhoneOS SDK, Homebrew bison and gpatch.
set -euo pipefail

DONOR_URL=https://github.com/oosexgang/hackios-xnu-userland.git
DONOR_SHA=a79ff0772a3454fd1ef127e181e5b3bce6c9ce18
MESA=25.0.7
MESA_SHA=592272df3cf01e85e7db300c449df5061092574d099da275d19e97ef0510f8a6
PREFIX=/redwood         # the donor's install prefix on the phone

REPO=$(cd "$(dirname "$0")/.." && pwd)
W=${METAL_WORK:-$HOME/Developer/ios-sweet-work/metal-build}
STAGE=${1:-all}
mkdir -p "$W/shim"
cd "$W"

tools() {
	printf '#!/bin/sh\nexec shasum -a 256 "$@"\n' > shim/sha256sum
	chmod +x shim/sha256sum
	ln -sf "$(brew --prefix gpatch)/bin/gpatch" shim/patch
	if [ ! -x venv/bin/meson ]; then
		python3 -m venv venv
		venv/bin/pip -q install meson mako pyyaml packaging
	fi
	export PATH="$W/shim:$(brew --prefix bison)/bin:$W/venv/bin:$PATH"
}

donor() {
	if [ ! -d donor/.git ]; then
		mkdir -p donor
		git -C donor init -q .
		git -C donor remote add origin "$DONOR_URL"
		git -C donor fetch -q --depth 1 origin "$DONOR_SHA"
		git -C donor -c advice.detachedHead=false checkout -q FETCH_HEAD
		for p in "$REPO"/userland/metal/*.patch; do
			[ -f "$p" ] || continue
			git -C donor apply "$p"
		done
	fi
	if [ ! -f mesa-$MESA.tar.xz ]; then
		curl -fsSL -o mesa-$MESA.tar.xz https://archive.mesa3d.org/mesa-$MESA.tar.xz
	fi
	echo "$MESA_SHA  mesa-$MESA.tar.xz" | shasum -a 256 -c --quiet
}

# unpack DIR PATCH...: fresh Mesa with the donor's patches and sources
unpack() {
	local dir=$1 p
	shift
	rm -rf "$dir"
	mkdir -p "$dir"
	tar xJf mesa-$MESA.tar.xz -C "$dir"
	for p in "$@"; do
		patch -s --no-backup-if-mismatch -d "$dir/mesa-$MESA" -p1 < "$p"
	done
	cp -r donor/tools/mesa/redwood-drm "$dir/mesa-$MESA/src/redwood-drm"
	rm -rf "$dir/mesa-$MESA/src/compiler/air"
	cp -r donor/tools/mesa/air "$dir/mesa-$MESA/src/compiler/air"
}

MESON_COMMON=(--wrap-mode=nofallback -Dplatforms= -Dgallium-drivers=softpipe,freedreno
	-Dfreedreno-kmds=msm -Dvulkan-drivers= -Dglx=disabled -Degl=disabled -Dgbm=disabled
	-Dllvm=disabled -Dopengl=true -Dgles2=enabled -Dshader-cache=disabled -Dvalgrind=disabled
	-Dlibunwind=disabled -Dglvnd=disabled -Dvideo-codecs= -Dtools= -Dgallium-vdpau=disabled
	-Dgallium-va=disabled -Dgallium-xa=disabled -Dlmsensors=disabled -Dzstd=disabled
	-Dxmlconfig=disabled -Dexpat=disabled)

host() {
	unpack host donor/tools/mesa/air-*.patch donor/tools/mesa/ir3-*.patch donor/tools/mesa/freedreno-darwin.patch
	meson setup host/build host/mesa-$MESA --buildtype=debugoptimized "${MESON_COMMON[@]}" \
		-Dbuild-tests=true > host/meson.log
	ninja -C host/build src/compiler/air/air2nir src/gallium/drivers/freedreno/ir3_compiler > host/ninja.log
	echo "host: $W/host/build/src/gallium/drivers/freedreno/ir3_compiler"
}

ios() {
	local sdk clang cxx
	sdk=$(xcrun --sdk iphoneos --show-sdk-path)
	clang=$(xcrun --sdk iphoneos -f clang)
	cxx=$(xcrun --sdk iphoneos -f clang++)
	unpack ios donor/tools/mesa/*.patch
	cat > ios/cross.ini <<-INI
		[binaries]
		c = ['$clang', '-target', 'arm64-apple-ios16.0', '-isysroot', '$sdk']
		cpp = ['$cxx', '-target', 'arm64-apple-ios16.0', '-isysroot', '$sdk']
		objc = ['$clang', '-target', 'arm64-apple-ios16.0', '-isysroot', '$sdk']
		ar = '$(xcrun -f ar)'
		ranlib = '$(xcrun -f ranlib)'
		strip = '$(xcrun -f strip)'
		pkg-config = 'false'

		[host_machine]
		system = 'darwin'
		subsystem = 'ios'
		cpu_family = 'aarch64'
		cpu = 'arm64'
		endian = 'little'

		[properties]
		needs_exe_wrapper = true
	INI
	meson setup ios/build ios/mesa-$MESA --cross-file ios/cross.ini --prefix=$PREFIX --libdir=lib \
		--buildtype=release -Db_ndebug=true "${MESON_COMMON[@]}" -Dosmesa=true -Dshared-glapi=enabled \
		-Dgles1=disabled -Dbuild-tests=false > ios/meson.log
	ninja -C ios/build src/gallium/drivers/freedreno/libredwoodair.dylib > ios/ninja.log
	echo "ios: $W/ios/build/src/gallium/drivers/freedreno/libredwoodair.dylib"
}

driver() {
	local sdk
	sdk=$(xcrun --sdk iphoneos --show-sdk-path)
	rm -rf src obj
	mkdir -p src obj
	cp donor/userland/src/redwoodmetal.m donor/userland/src/redwooddrawable.m donor/userland/src/redwood_drawable.h src/
	xcrun --sdk iphoneos clang -target arm64-apple-ios16.0 -isysroot "$sdk" -O1 -Isrc -bundle \
		-framework Foundation -framework IOKit -framework Metal -lobjc \
		-o obj/RedwoodMetal src/redwoodmetal.m src/redwooddrawable.m 2> obj/clang.log
	echo "driver: $W/obj/RedwoodMetal"
}

test() {
	local sdk src=$REPO/userland/metaltest
	sdk=$(xcrun --sdk iphoneos --show-sdk-path)
	mkdir -p obj
	xcrun --sdk iphoneos clang -target arm64-apple-ios16.0 -isysroot "$sdk" -O1 -fobjc-arc -Wall -Wextra \
		-framework Foundation -framework Metal -framework IOSurface \
		-o obj/metaltest "$src/metaltest.m" 2> obj/metaltest-clang.log
	codesign -f -s - obj/metaltest
	echo "test: $W/obj/metaltest"
	rm -f obj/default.metallib
	if xcrun -sdk iphoneos metal -c -mios-version-min=16.0 -o obj/metaltest.air "$src/shaders.metal" 2> obj/metaltest-metal.log &&
		xcrun -sdk iphoneos metallib -o obj/default.metallib obj/metaltest.air 2>> obj/metaltest-metal.log; then
		echo "test: $W/obj/default.metallib"
	else
		rm -f obj/default.metallib
		echo "test: no metallib (Metal Toolchain missing? see $W/obj/metaltest-metal.log); tests 07-11,14 will FAIL/SKIP" >&2
	fi
}

payload() {
	local air=ios/build/src/gallium/drivers/freedreno/libredwoodair.dylib
	local b=pay/System/Library/Extensions/RedwoodMetal.bundle
	rm -rf pay
	mkdir -p pay$PREFIX/lib "$b"
	cp "$air" pay$PREFIX/lib/libredwoodair.dylib
	xcrun strip -x pay$PREFIX/lib/libredwoodair.dylib
	install_name_tool -id $PREFIX/lib/libredwoodair.dylib pay$PREFIX/lib/libredwoodair.dylib 2>/dev/null
	cp obj/RedwoodMetal "$b/RedwoodMetal"
	cp donor/userland/src/metal_plugin.plist "$b/Info.plist"
	codesign -f -s - pay$PREFIX/lib/libredwoodair.dylib
	codesign -f -s - "$b"
	if [ -f obj/metaltest ]; then
		mkdir -p pay$PREFIX/bin
		cp obj/metaltest pay$PREFIX/bin/metaltest
		codesign -f -s - pay$PREFIX/bin/metaltest
	fi
	if [ -f obj/default.metallib ]; then
		mkdir -p pay$PREFIX/share/metaltest
		cp obj/default.metallib pay$PREFIX/share/metaltest/default.metallib
	fi
	(cd pay && find . -type f | sort | xargs shasum -a 256)
}

tools
donor
case "$STAGE" in
all) host; ios; driver; test; payload ;;
host | ios | driver | test | payload) "$STAGE" ;;
*) echo "unknown stage $STAGE" >&2; exit 2 ;;
esac
