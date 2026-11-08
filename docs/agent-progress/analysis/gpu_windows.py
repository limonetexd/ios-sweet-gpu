#!/usr/bin/env python3
"""GPU occupancy, present readiness and frame-cost tables from pulled kernel rings.

Usage: python3 docs/agent-progress/analysis/gpu_windows.py LOG [LOG ...]

Prints two Markdown tables. All figures use "active" seconds (SWEET FPS swaps > 0).

Ring occupied %: the share of once-a-second samples at which the newest submission was unfinished
for >= 1 ms ("GPU N ms pending", 0097). The fence word is read directly, so unlike the 0139 "worked"
latency it does not depend on anyone looking. N truncates to whole ms, so a newest submission under
1 ms old reads as 0. The figure is therefore a LOWER bound; "upper" adds submissions/s * 1 ms
(Markov bound on a submission in the last ms). It means work outstanding on the ring, not shader
execution time.

Stale %: stale / (presents + stale), the share of vsync ticks with a new frame waiting at which the
GPU was not done with that frame's surfaces (drawn(), 0095). Repeats (0112) are excluded, and one
frame can be stale on several ticks.

Late %: swaps whose gap from the previous swap exceeded 20 ms (0097c). It is not "missed a vsync".

Profile: the last line of the longest-lived backboardd. Its counters are cumulative. "in GL
calls" excludes glFlush and "outside" contains it (donor eagl.c:407,1028), so add them to get frame time
but do not add the per-call figures to "in GL calls". Per-call timers are process-wide.
Host-only. Pure Python 3.
"""
import math
import re
import sys

FPS = re.compile(r'SWEET FPS: (\d+) swaps in (\d+) ms \((\d+) ms longest, (\d+) late\), (\d+) presents '
                 r'\((\d+) us average, (\d+) us longest, (\d+) waited for the GPU\), vsync timer (\d+) ms longest; '
                 r'GPU (\d+) ms pending \(fence (\d+)\)')
PROFILE = re.compile(r'redwood-gl: profile: (\d+) us a frame in GL calls, (\d+) outside them; '
                     r'frames ended on big cores (\d+), little (\d+); most time: ([^\n]*)')
CALL = re.compile(r'(gl[A-Za-z0-9]+) (\d+)(?=,| us)')


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - s) / d), min(1.0, (c + s) / d)


def analyse(path):
    active = []
    segments = []
    last_fence = None
    for line in open(path, errors='replace'):
        for m in FPS.finditer(line):
            swaps, win, longest, late, presents, _, _, stale, _, pending, fence = [int(x) for x in m.groups()]
            delta = None if last_fence is None or fence < last_fence else fence - last_fence
            last_fence = fence
            if swaps > 0:
                active.append((swaps, win, longest, late, presents, stale, pending, delta))
        for m in PROFILE.finditer(line):
            frames = int(m.group(3)) + int(m.group(4))
            if not segments or frames < segments[-1]['frames']:
                segments.append({'frames': 0, 'calls': {}})
            seg = segments[-1]
            seg['frames'] = frames
            seg['gl'], seg['outside'] = int(m.group(1)), int(m.group(2))
            for name, us in CALL.findall(m.group(5)):
                seg['calls'][name] = (int(us), frames)
    return active, (max(segments, key=lambda s: s['frames']) if segments else None)


def row(path):
    active, seg = analyse(path)
    name = path.split('/')[-1].replace('.txt', '')
    n = len(active)
    if not n:
        return ('| %s | 0 | - | - | - | - | - | - | - | - |' % name), None
    normal = [r for r in active if r[2] <= 100]
    swaps = sum(r[0] for r in active)
    ms = sum(r[1] for r in active)
    rate = swaps / ms * 1000
    timed = [r for r in active if r[7] is not None and 900 <= r[1] <= 1100]
    subs = sum(r[7] for r in timed)
    sub_rate = subs / sum(r[1] for r in timed) * 1000 if timed else 0.0
    sub_swap = subs / sum(r[0] for r in timed) if timed else 0.0
    late = sum(r[3] for r in active)
    late_n = sum(r[3] for r in normal)
    swaps_n = sum(r[0] for r in normal)
    stale = sum(r[5] for r in active)
    presents = sum(r[4] for r in active)
    k = sum(1 for r in active if r[6] >= 1)
    k_n = sum(1 for r in normal if r[6] >= 1)
    u = k / n
    lo, hi = wilson(k, n)
    upper = min(1.0, u + sub_rate / 1000)
    a = ('| %s | %d / %d | %.1f | %.1f | %.2f | %.1f / %s | %.1f | %d/%d = %.0f%% (%.0f-%.0f); normal %d/%d | %.0f%% | %.1f-%.1f |'
         % (name, n, len(normal), rate, sub_rate, sub_swap, 100 * late / swaps,
            ('%.1f' % (100 * late_n / swaps_n)) if swaps_n else '-',
            100 * stale / max(1, stale + presents), k, n, 100 * u, 100 * lo, 100 * hi, k_n, len(normal), 100 * upper,
            1000 * u / rate, 1000 * upper / rate))
    b = None
    if seg:
        f = seg['frames']
        c = [('%.1f' % (seg['calls'][x][0] / seg['calls'][x][1] / 1000)) if x in seg['calls'] else '-'
             for x in ('glFlush', 'glTexImage2D', 'glDeleteTextures')]
        b = '| %s | %d | %.1f | %.1f | %s | %s | %s |' % (name, f, seg['gl'] / 1000, seg['outside'] / 1000, c[0], c[1], c[2])
    return a, b


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    rows = [row(p) for p in argv]
    print('| Run | Active / normal s | Swaps/s | Subs/s | Subs/swap | Late % active / normal | Stale % | '
          'Ring occupied, active (95% CI) | Upper | ms occupied per swap |')
    print('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |')
    for a, _ in rows:
        print(a)
    print()
    print('| Run | Frames | "in GL calls" ms | "outside" ms | glFlush ms/frame | glTexImage2D | glDeleteTextures |')
    print('| --- | --- | --- | --- | --- | --- | --- |')
    for _, b in rows:
        if b:
            print(b)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
