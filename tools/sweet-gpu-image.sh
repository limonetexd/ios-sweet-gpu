#!/bin/bash
# Build an iOS boot image with the GPU brought up by the shim.
# Usage: tools/sweet-gpu-image.sh KERNEL_DIR TAG ["extra boot-args"]
#   KERNEL_DIR holds kernel.development.sweet (CI artifact xnu-kernel); image -> shim/out/shim-boot-TAG.img
# Default boot-args: best config so far (sweetgpu=2 cpus=8, 30 Hz framebuffer copy; SWEETFB_HZ=60
# for the 60 Hz experiment; SWEET_SERIAL=0 by default: the serial console blocks IOLog once its
# buffer fills, serial=3 only for early-boot debugging). Add e.g. "sweetgpu_reboot=600
# sweetgpu_swipe=90" for unattended runs (tools/sweet-probe-loop.ps1).
set -e
K=${1:?kernel dir}; T=${2:?tag}; EXTRA=${3:-}; HZ=${SWEETFB_HZ:-30}; SER=${SWEET_SERIAL:-0}
# 0156: the PM6150 RTC cannot supply wall time (qcom,qpnp-rtc-write = 0), so
# the image carries the host's Unix time; override with SWEET_EPOCH=<seconds>.
EPOCH=${SWEET_EPOCH:-$(date +%s)}
cd "$(dirname "$0")/.."
# SWEET_SCALE=2: 0129's experimental 750x1624 @2x frame (the kernel follows the ADT, 0138)
python3 -I tools/mkadt.py shim/out/sweet-gpupool.adt --highmem --gpupool $([ "${SWEET_SCALE:-3}" = 2 ] && echo --scale2) ${SWEET_WLAN:+--wlan}
B="debug=0xc serial=$SER cpus=8 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=$HZ sweetgpu=2 sweetepoch=$EPOCH $EXTRA"
echo "boot-args: $B"
python3 -I tools/mkpayload.py "$K/kernel.development.sweet" shim/out/sweet-gpupool.adt "shim/out/payload-$T.bin" --cmdline "$B" | tail -2
(cd shim && SHIM_CFLAGS="-DSHIM_GPUPROBE -DSHIM_GPUBOOT $([ "${SWEET_CPUMAX:-0}" = 1 ] && echo -DSHIM_CPUMAX)" ./build.sh "../shim/out/payload-$T.bin" 2>&1 | grep -E 'warning|error' || true)
cp shim/out/shim-boot.img "shim/out/shim-boot-$T.img"
python3 -I tools/unpack_bootv2.py "shim/out/shim-boot-$T.img" "shim/out/check-$T" >/dev/null
cmp "shim/out/check-$T/ramdisk" "shim/out/payload-$T.bin" && echo RAMDISK MATCH
sha256sum "shim/out/shim-boot-$T.img"
