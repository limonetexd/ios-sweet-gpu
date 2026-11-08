#!/bin/bash
# Copy the Metal payload into the root image, flash it, boot a test image, pull its log.
#   tools/metal-flash-test.sh ROOT.raw BOOT.img TAG [WAIT_SECONDS]
# Needs the user's yes for flashing userdata. Keep the original .simg as rollback.
set -eu
raw=$1; img=$2; tag=$3; wait=${4:-320}
repo=$(cd "$(dirname "$0")/.." && pwd)
pay=${METAL_WORK:-$HOME/Developer/ios-sweet-work/metal-build}/pay
dir=$(cd "$(dirname "$raw")" && pwd)
mnt=$dir/m
mkdir -p "$mnt"
hdiutil attach -noverify -nobrowse -imagekey diskimage-class=CRawDiskImage -mountpoint "$mnt" "$raw" > /dev/null
rsync -rl --chmod=Du=rwx,Dgo=rx,Fu=rwx,Fgo=rx "$pay/" "$mnt/"
sync
hdiutil detach "$mnt" > /dev/null
python3 -I "$repo/tools/raw2simg.py" "$raw" "$dir/$tag.simg"
case "$(fastboot getvar product 2>&1 | head -1)" in *sweet*) ;; *) echo "not sweet" >&2; exit 2;; esac
fastboot -S 512M flash userdata "$dir/$tag.simg" 2>&1 | tail -1
fastboot reboot recovery 2>&1 | tail -1
s=
for _ in $(seq 1 40); do s=$(adb get-state 2>/dev/null) && [ -n "$s" ] && break; sleep 3; done
[ -n "$s" ] || { echo "recovery adb did not come up" >&2; exit 3; }
adb reboot bootloader
for _ in $(seq 1 30); do [ -n "$(fastboot devices 2>/dev/null)" ] && break; sleep 2; done
rm -f "$dir/$tag.simg"
exec bash "$repo/tools/sweet-boot-test.sh" "$img" "$tag" "$wait"
