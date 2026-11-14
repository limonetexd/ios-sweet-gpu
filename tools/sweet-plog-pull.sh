#!/bin/sh
# Read the shim probe log (shim/plog.c) from a phone booted into OrangeFox
# recovery (fastboot boot recovery/recovery.img; adb root shell).
#   tools/sweet-plog-pull.sh [-s SERIAL] OUT.txt
# Only reads: the 32 blocks (4 KiB) just before the 1025-block XNU console ring.
# Header block: magic "SWPR"/"OBE1", sequence, text length, reason at +16;
# then up to 31 blocks of the shim's console text (shim/console.c con_text).
set -eu

ADB="adb"
if [ "${1:-}" = "-s" ]; then
	shift
	SERIAL=${1:?Error: -s requires a device serial}
	shift
	ADB="adb -s $SERIAL"
fi

out=${1:?usage: sweet-plog-pull.sh [-s SERIAL] OUT.txt}
command -v adb >/dev/null 2>&1 || { echo "Error: adb not found in PATH" >&2; exit 1; }

dev=$($ADB shell 'for d in /dev/block/by-name/userdata /dev/block/bootdevice/by-name/userdata; do [ -e $d ] && readlink -f $d && break; done' 2>/dev/null | tr -d '\r')
[ -n "$dev" ] || { echo "userdata block device not found on connected device" >&2; exit 1; }
bytes=$($ADB shell blockdev --getsize64 "$dev" | tr -d '\r')
skip=$((bytes / 4096 - 1025 - 32))
[ "$skip" -ge 0 ] || { echo "userdata is too small for the scratch area" >&2; exit 1; }
$ADB exec-out "dd if=$dev bs=4096 skip=$skip count=32 2>/dev/null" > "$out.bin"
python3 - "$out.bin" "$out" <<'PY'
import struct, sys

bin_path, out_path = sys.argv[1], sys.argv[2]
with open(bin_path, "rb") as f:
    raw = f.read()
hdr = raw[:4096]
if len(hdr) < 4096:
    sys.exit(f"{bin_path}: short read ({len(hdr)} bytes)")
magic0, magic1, seq, length = struct.unpack_from("<4I", hdr, 0)
if (magic0, magic1) != (0x52505753, 0x3145424F):
    sys.exit(f"{bin_path}: no probe log (magic {magic0:08x} {magic1:08x})")
reason = hdr[16:16 + 256].split(b"\0", 1)[0].decode("ascii", "replace")
text = raw[4096:4096 + length].decode("ascii", "replace")
with open(out_path, "w") as f:
    f.write(text)
print(f"probe log seq {seq}, {length} bytes, last step {reason!r} -> {out_path}", file=sys.stderr)
PY
rm -f "$out.bin"
