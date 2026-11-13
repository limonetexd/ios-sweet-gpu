#!/usr/bin/env python3
"""Name the `prof:` lines of patch 0014 (boot-arg sweetmetal_prof=1) from a kernel log.

  tools/sweet-prof-symbols.py logs/xnu-TAG.txt [--proc backboardd] [--top N]

The plug-in prints cumulative tables every 60 s; the LAST print of the process is used.
Offsets in libredwoodair.dylib and RedwoodMetal are named with `atos` against the unstripped
host copies ($METAL_WORK/ios/build/.../libredwoodair.dylib, $METAL_WORK/obj/RedwoodMetal),
which must be the build that is on the phone. Other images keep the nearest exported name
the phone printed.

Three tables: leaf (where the pc was), ours (innermost frame in our two images), api (the
library entry the plug-in called). Shares are of all samples; a sample is one millisecond of
wall time of the replaying thread, on a processor or blocked.
"""
import os
import re
import subprocess
import sys

W = os.environ.get("METAL_WORK", os.path.expanduser("~/Developer/ios-sweet-work/metal-build"))
FILES = {
    "libredwoodair.dylib": f"{W}/ios/build/src/gallium/drivers/freedreno/libredwoodair.dylib",
    "RedwoodMetal": f"{W}/obj/RedwoodMetal",
}
HEAD = re.compile(r"prof: (\d+) samples \(running (\d+), waiting (\d+)\), (.*)$")
ROW = re.compile(r"prof: (leaf|ours|api) (\d+) (\S+)\+0x([0-9a-f]+) (.*)$")
NONE = re.compile(r"prof: (ours|api) (\d+) \(none\)")


def atos(image, offsets):
    path = FILES.get(image)
    if not path or not os.path.exists(path) or not offsets:
        return {}
    base = 0x100000000
    r = subprocess.run(["atos", "-o", path, "-arch", "arm64", "-l", hex(base)] +
                       [hex(base + o) for o in offsets], capture_output=True, text=True)
    names = r.stdout.splitlines()
    return {o: re.sub(r" \(in [^)]*\)", "", n) for o, n in zip(offsets, names)}


def main():
    args = sys.argv[1:]
    proc, top = "backboardd", 30
    if "--proc" in args:
        proc = args[args.index("--proc") + 1]
    if "--top" in args:
        top = int(args[args.index("--top") + 1])
    prints, cur = [], None
    with open(args[0], errors="replace") as f:
        for line in f:
            if "prof:" not in line or f"redwoodmetal[{proc} " not in line:
                continue
            line = line.rstrip("\n")
            h = HEAD.search(line)
            if h:
                cur = {"head": h, "rows": [], "none": {}}
                prints.append(cur)
                continue
            if cur is None:
                continue
            r = ROW.search(line)
            if r:
                cur["rows"].append((r.group(1), int(r.group(2)), r.group(3), int(r.group(4), 16), r.group(5)))
                continue
            n = NONE.search(line)
            if n:
                cur["none"][n.group(1)] = int(n.group(2))
    if not prints:
        print(f"no prof: print for {proc}")
        return 1
    last = prints[-1]
    h = last["head"]
    total = int(h.group(1)) or 1
    print(f"{proc}: {len(prints)} prints; last: {total} samples, running {h.group(2)} "
          f"({100 * int(h.group(2)) / total:.0f} %), waiting {h.group(3)}; {h.group(4)}")
    wanted = {}
    for _, _, image, off, _ in last["rows"]:
        wanted.setdefault(image, set()).add(off)
    named = {image: atos(image, sorted(offs)) for image, offs in wanted.items()}
    for table in ("api", "ours", "leaf"):
        rows = [r for r in last["rows"] if r[0] == table]
        merged = {}
        for _, count, image, off, sym in rows:
            name = named.get(image, {}).get(off)
            if name:
                key = (image, re.sub(r" \+ \d+$", "", name))   # same function, any offset
            else:
                key = (image, re.sub(r"\+0x[0-9a-f]+$", "", sym))
            merged[key] = merged.get(key, 0) + count
        shown = sum(merged.values())
        print(f"-- {table}: {shown} of {total} samples in the rows printed"
              + (f", {last['none'][table]} with no frame of ours" if table in last["none"] else ""))
        for (image, name), count in sorted(merged.items(), key=lambda kv: -kv[1])[:top]:
            print(f"   {100 * count / total:5.1f} %  {count:7d}  {image}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
