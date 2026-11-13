#!/usr/bin/env python3
"""Summarise `passlog:` blocks (patch 0013, boot-arg sweetmetal_passlog=1) from a kernel log.

  tools/sweet-passlog-summary.py logs/xnu-TAG.txt [--top N] [--busy DRAWS]

Per process: the open line, totals over all 5 s blocks (command buffers, draws, flushes,
batches by mode, bins), the same per command buffer, and the names by draws. A block is
"busy" when it holds at least --busy draws (default 200); busy blocks are also totalled
alone, because idle blocks (a clock tick, a cursor) dilute the per-command-buffer figures.

The per-name time is the wall time of every command buffer that held the name, so names
that always share a command buffer show the same time: it ranks command buffers, not draws.
"""
import re
import sys
from collections import defaultdict

HEAD = re.compile(
    r"passlog: ([\d.]+) s, (\d+) cbs, (\d+) draws, (\d+) names.*library: (\d+) flushes, (.*)$")
MODES = re.compile(
    r"(\d+) batches: sysmem (\d+), gmem (\d+), nondraw (\d+); bins (\d+) .*max (\d+)")
NAME = re.compile(r"passlog:   (\S+) draws (\d+), in (\d+) cbs, cb time sum ([\d.]+) ms")
PROC = re.compile(r"redwoodmetal\[(\S+) \d+\]")


def main():
    args = sys.argv[1:]
    top, busy = 12, 200
    if "--top" in args:
        top = int(args[args.index("--top") + 1])
    if "--busy" in args:
        busy = int(args[args.index("--busy") + 1])
    path = args[0]
    procs = defaultdict(lambda: {
        "open": None, "blocks": 0, "busy": 0,
        "all": defaultdict(float), "hot": defaultdict(float),
        "names": defaultdict(lambda: [0, 0, 0.0]), "bins_max": 0, "cbtime": 0.0, "hot_cbtime": 0.0})
    cur, cur_busy = None, False
    with open(path, errors="replace") as f:
        for line in f:
            if "passlog:" not in line:
                continue
            m = PROC.search(line)
            if not m:
                continue
            p = procs[m.group(1)]
            if "passlog: open:" in line:
                p["open"] = line.split("passlog: open:", 1)[1].strip()
                continue
            h = HEAD.search(line)
            if h:
                secs, cbs, draws = float(h.group(1)), int(h.group(2)), int(h.group(3))
                flushes = int(h.group(5))
                cur, cur_busy = p, draws >= busy
                p["blocks"] += 1
                p["busy"] += cur_busy
                vals = {"s": secs, "cbs": cbs, "draws": draws, "flushes": flushes}
                mm = MODES.search(h.group(6))
                if mm:
                    vals.update(batches=int(mm.group(1)), sysmem=int(mm.group(2)),
                                gmem=int(mm.group(3)), nondraw=int(mm.group(4)),
                                bins=int(mm.group(5)))
                    p["bins_max"] = max(p["bins_max"], int(mm.group(6)))
                for k, v in vals.items():
                    p["all"][k] += v
                    if cur_busy:
                        p["hot"][k] += v
                continue
            n = NAME.search(line)
            if n and cur is p:
                e = p["names"][n.group(1)]
                e[0] += int(n.group(2))
                e[1] += int(n.group(3))
                e[2] += float(n.group(4))
    for name, p in sorted(procs.items()):
        print(f"== {name}: {p['blocks']} blocks ({p['busy']} with >= {busy} draws)")
        print(f"   open: {p['open']}")
        for label, t in (("all", p["all"]), ("busy", p["hot"])):
            cbs = t["cbs"] or 1
            print(f"   {label:4}: {t['s']:.0f} s, {t['cbs']:.0f} cbs ({t['cbs'] / (t['s'] or 1):.1f}/s), "
                  f"{t['draws']:.0f} draws ({t['draws'] / cbs:.1f}/cb), flushes {t['flushes'] / cbs:.1f}/cb, "
                  f"batches {t['batches'] / cbs:.1f}/cb = sysmem {t['sysmem'] / cbs:.2f} + gmem {t['gmem'] / cbs:.2f} "
                  f"+ nondraw {t['nondraw'] / cbs:.2f}; bins/gmem batch {t['bins'] / (t['gmem'] or 1):.1f}")
        print(f"   bins max (process): {p['bins_max']}")
        rows = sorted(p["names"].items(), key=lambda kv: -kv[1][0])[:top]
        for nm, (draws, cbs, ms) in rows:
            print(f"   {draws:7d} draws  {cbs:5d} cbs  {ms / (cbs or 1):7.1f} ms/cb  {nm}")


if __name__ == "__main__":
    main()
