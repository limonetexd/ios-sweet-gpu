#!/usr/bin/env python3
"""Summarise a pulled XNU console ring (logs/xnu-TAG.txt) into the numbers HakiOS decisions use.

  tools/sweet-fps-summary.py LOG [LOG ...]        text table, one column per log
  tools/sweet-fps-summary.py --json LOG [...]     the same as JSON (for diffing)

What it reads (the ring interleaves threads, so every pattern is searched anywhere in a line):
  SWEET FPS:        swaps and presents a second (patch 0097)
  redwood-gl: frame the GL frame split, sampled by eagl (1 in 20 after frame 40)
  RedwoodGPU:       submissions, KB pushed out of the cache a submission, us a submission
  SWEET FREEZE / CRASH / SWEET FB: modes published / panic lines

"active" seconds = swaps > 0. "normal" seconds = active and the longest swap gap <= 100 ms (drops
freeze and respring seconds). The A/B rule used so far: compare the "normal" swaps/s average and
p90 and the GL frame p50/p95 of two runs of the same length with the same swipes.
Pure Python 3, no dependencies.
"""
import json
import re
import statistics
import sys

FPS = re.compile(r'SWEET FPS: (\d+) swaps in (\d+) ms \((\d+) ms longest, (\d+) late\), (\d+) presents '
                 r'\((\d+) us average, (\d+) us longest, (\d+) waited for the GPU\)')
GL = re.compile(r'redwood-gl: frame (\d+): .*?; (\d+) us \((\d+) handing on, (\d+) waiting, (\d+) copying out\), '
                r'(\d+) before it')   # the ring cuts lines at ~256 characters: the tail is often gone
SUB = re.compile(r'RedwoodGPU: (\d+) submissions in (\d+) ms: (\d+) command buffers and (\d+) buffers named, '
                 r'(\d+) KB out of the cache in (\d+) us a submission')
MODES = re.compile(r'SWEET FB: modes published: (\d+x\d+) at (\d+) Hz')
CANVAS = re.compile(r'SWEET FB: device tree canvas (\d+x\d+): (\d+x\d+) frames')
CRASH = re.compile(r'CRASH (\S+?)\[\d+\] sig (\d+)')
SHOTS = re.compile(r'SWEET SHOT (\d+) begin')


def pct(values, p):
    if not values:
        return None
    values = sorted(values)
    k = min(len(values) - 1, max(0, int(round((len(values) - 1) * p / 100.0))))
    return values[k]


def stats(values):
    if not values:
        return {'n': 0}
    return {'n': len(values), 'avg': round(statistics.fmean(values), 2), 'p50': pct(values, 50),
            'p90': pct(values, 90), 'p95': pct(values, 95), 'max': max(values)}


def summarise(path):
    swaps_active, swaps_normal, present_us, waited = [], [], [], []
    gl_total, gl_hand, gl_wait, gl_attach = [], [], [], []
    sub_n = sub_kb = sub_us = 0
    freezes = 0
    crashes = {}
    modes = set()
    canvas = set()
    shots = 0
    panic = 0
    seconds = 0
    for line in open(path, errors='replace'):
        for m in FPS.finditer(line):
            seconds += 1
            swaps, longest = int(m.group(1)), int(m.group(3))
            if swaps > 0:
                swaps_active.append(swaps)
                if longest <= 100:
                    swaps_normal.append(swaps)
                    present_us.append(int(m.group(6)))
                    waited.append(int(m.group(8)))
        for m in GL.finditer(line):
            gl_total.append(int(m.group(2)))
            gl_hand.append(int(m.group(3)))
            gl_wait.append(int(m.group(4)))
            gl_attach.append(int(m.group(6)))
        for m in SUB.finditer(line):
            n = int(m.group(1))
            sub_n += n
            sub_kb += n * int(m.group(5))
            sub_us += n * int(m.group(6))
        if 'SWEET FREEZE:' in line:
            freezes += 1
        for m in CRASH.finditer(line):
            key = '%s sig %s' % (m.group(1), m.group(2))
            crashes[key] = crashes.get(key, 0) + 1
        for m in MODES.finditer(line):
            modes.add('%s@%s' % (m.group(1), m.group(2)))
        for m in CANVAS.finditer(line):
            canvas.add('canvas %s -> %s frames' % (m.group(1), m.group(2)))
        shots += len(SHOTS.findall(line))
        if 'panic(' in line or 'Panicked task' in line or 'Kernel panic' in line:
            panic += 1
    return {
        'log': path,
        'seconds_logged': seconds,
        'swaps_active': stats(swaps_active),
        'swaps_normal': stats(swaps_normal),
        'present_us_avg_normal': stats(present_us),
        'presents_waited_for_gpu_normal': stats(waited),
        'gl_frame_us': stats(gl_total),
        'gl_handing_on_us': stats(gl_hand),
        'gl_waiting_us': stats(gl_wait),
        'gl_attach_us': stats(gl_attach),
        'gpu_submissions': sub_n,
        'kb_out_of_cache_per_submission': round(sub_kb / sub_n) if sub_n else None,
        'us_per_submission': round(sub_us / sub_n) if sub_n else None,
        'freeze_lines': freezes,
        'crashes': crashes,
        'modes': sorted(modes) + sorted(canvas),
        'screenshots': shots,
        'panic_lines': panic,
    }


def show(results):
    rows = [
        ('swaps/s normal avg', lambda r: r['swaps_normal'].get('avg')),
        ('swaps/s normal p50', lambda r: r['swaps_normal'].get('p50')),
        ('swaps/s normal p90', lambda r: r['swaps_normal'].get('p90')),
        ('swaps/s normal max', lambda r: r['swaps_normal'].get('max')),
        ('seconds normal / active', lambda r: '%s / %s' % (r['swaps_normal']['n'], r['swaps_active']['n'])),
        ('present us (avg of avgs)', lambda r: r['present_us_avg_normal'].get('avg')),
        ('GL frame us p50', lambda r: r['gl_frame_us'].get('p50')),
        ('GL frame us p90', lambda r: r['gl_frame_us'].get('p90')),
        ('GL frame us p95', lambda r: r['gl_frame_us'].get('p95')),
        ('  handing on us p50', lambda r: r['gl_handing_on_us'].get('p50')),
        ('  waiting us p50', lambda r: r['gl_waiting_us'].get('p50')),
        ('  attach us p50', lambda r: r['gl_attach_us'].get('p50')),
        ('GL frames sampled', lambda r: r['gl_frame_us']['n']),
        ('KB out of cache / submission', lambda r: r['kb_out_of_cache_per_submission']),
        ('us / submission (cache work)', lambda r: r['us_per_submission']),
        ('GPU submissions', lambda r: r['gpu_submissions']),
        ('SWEET FREEZE lines', lambda r: r['freeze_lines']),
        ('panic lines', lambda r: r['panic_lines']),
        ('screenshots', lambda r: r['screenshots']),
        ('modes', lambda r: ', '.join(r['modes']) or '-'),
        ('crashes', lambda r: ', '.join('%s x%d' % kv for kv in r['crashes'].items()) or '-'),
    ]
    width = max(len(name) for name, _ in rows)
    head = ['%-*s' % (width, '')] + ['%-26s' % r['log'].replace('\\', '/').split('/')[-1][:26] for r in results]
    print('  '.join(head))
    for name, fn in rows:
        cells = []
        for r in results:
            v = fn(r)
            cells.append('%-26s' % ('-' if v is None else v))
        print('  '.join(['%-*s' % (width, name)] + cells))


def main(argv):
    as_json = '--json' in argv
    paths = [a for a in argv if not a.startswith('--')]
    if not paths:
        print(__doc__)
        return 2
    results = [summarise(p) for p in paths]
    if as_json:
        print(json.dumps(results, indent=1))
    else:
        show(results)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
