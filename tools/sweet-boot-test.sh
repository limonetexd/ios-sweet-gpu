#!/bin/bash
# RAM-boot a test image, wait for it to return to fastboot, pull its kernel log.
#   tools/sweet-boot-test.sh IMAGE TAG [WAIT_SECONDS]      log -> logs/xnu-TAG.txt
# The image must carry sweetgpu_reboot=N. Needs OrangeFox installed in recovery.
# Exit 3: the phone did not come back; the user must hold Power+Vol-down.
set -u
img=${1:?image}; tag=${2:?tag}; wait=${3:-300}
cd "$(dirname "$0")/.."
rg -a -q 'sweetgpu_reboot=[0-9]' "$img" || { echo "no sweetgpu_reboot in $img" >&2; exit 2; }
case "$(fastboot getvar product 2>&1 | head -1)" in *sweet*) ;; *) echo "phone is not sweet in fastboot" >&2; exit 2;; esac
shasum -a 256 "$img" | cut -c1-16
t0=$(date +%s)
fastboot boot "$img" 2>&1 | tail -1
sleep 20
back=
while [ $(( $(date +%s) - t0 )) -lt "$wait" ]; do
	[ -n "$(fastboot devices 2>/dev/null)" ] && { back=1; break; }
	sleep 4
done
[ -n "$back" ] || { echo "NOT back after $wait s" >&2; exit 3; }
echo "back in fastboot after $(( $(date +%s) - t0 )) s"
fastboot reboot recovery 2>&1 | tail -1
s=
for _ in $(seq 1 40); do s=$(adb get-state 2>/dev/null) && [ -n "$s" ] && break; sleep 3; done
[ -n "$s" ] || { echo "recovery adb did not come up" >&2; exit 3; }
sleep 3
bash tools/sweet-log-pull.sh "logs/xnu-$tag.txt" 2>&1 | tail -1
rm -f "logs/xnu-$tag.txt.bin"
adb reboot bootloader
for _ in $(seq 1 30); do [ -n "$(fastboot devices 2>/dev/null)" ] && { echo "fastboot ok"; exit 0; }; sleep 2; done
echo "did not return to fastboot from recovery" >&2
exit 3
