#!/usr/bin/env python3
"""Summarise a pulled XNU console ring (logs/xnu-TAG.txt) into the numbers HakiOS decisions use.

  tools/sweet-fps-summary.py LOG [LOG ...]        text table, one column per log
  tools/sweet-fps-summary.py --json LOG [...]     the same as JSON (for diffing)
  tools/sweet-fps-summary.py --selftest           check the parser on literal lines

What it reads (the ring interleaves threads, so every pattern is searched anywhere in a line):
  SWEET FPS:        swaps and presents a second (patch 0097)
  redwood-gl: frame the GL frame split, sampled by eagl (1 in 20 after frame 40)
  RedwoodGPU:       submissions, KB pushed out of the cache a submission, us a submission
  RedwoodGPU: the GPU worked / N waits of: submission latency and waits (patch 0139 onwards; rows
                    and JSON keys appear only when a log has them). "worked" runs from the ring write
                    to the first look that finds the submission done (0083), so it includes queueing
                    and time nobody looked. It is NOT GPU execution time. Older logs carry the phrase
                    inside one long line with wrong numbers, and those are deliberately not read.
  SWEET FREEZE / CRASH / SWEET FB: modes published / panic lines

"active" seconds = swaps > 0. "normal" seconds = active and the longest swap gap <= 100 ms (drops
freeze and respring seconds). The A/B rule used so far: compare the "normal" swaps/s average and
p90 and the GL frame p50/p95 of two runs of the same length with the same swipes.
Pure Python 3, no dependencies.
"""
import json
import re
import os
import statistics
import sys
import tempfile

FPS = re.compile(r'SWEET FPS: (\d+) swaps in (\d+) ms \((\d+) ms longest, (\d+) late\), (\d+) presents '
                 r'\((\d+) us average, (\d+) us longest, (\d+) waited for the GPU\)')
GL = re.compile(r'redwood-gl: frame (\d+): .*?; (\d+) us \((\d+) handing on, (\d+) waiting, (\d+) copying out\), '
                r'(\d+) before it')   # the ring cuts lines at ~256 characters: the tail is often gone
SUB = re.compile(r'RedwoodGPU: (\d+) submissions in (\d+) ms: (\d+) command buffers and (\d+) buffers named, '
                 r'(\d+) KB out of the cache in (\d+) us a submission')
# 0139 lines. Each number must be followed by its own text, so a line cut by the ring inside a number
# is not read as a smaller number.
WORKED = re.compile(r'RedwoodGPU: the GPU worked (\d+) us on each of (\d+) \(')
WORKED_HEAD = re.compile(r'RedwoodGPU: the GPU worked')
HIST = re.compile(r'(\d+) under 0\.1 ms, (\d+) under 0\.25, (\d+) under 0\.5, (\d+) under 1, (\d+) under 2, '
                  r'(\d+) under 4, (\d+) longer')
WAITS = re.compile(r'RedwoodGPU: (\d+) waits of (\d+) us, (\d+) over before')
WAITS_HEAD = re.compile(r'RedwoodGPU: \d+ waits of')
MODES = re.compile(r'SWEET FB: modes published: (\d+x\d+) at (\d+) Hz')
CANVAS = re.compile(r'SWEET FB: device tree canvas (\d+x\d+): (\d+x\d+) frames')
CRASH = re.compile(r'CRASH (\S+?)\[\d+\] sig (\d+)')
SHOTS = re.compile(r'SWEET SHOT (\d+) begin')


HIST_NAMES = ('under_0.1ms', 'under_0.25ms', 'under_0.5ms', 'under_1ms', 'under_2ms', 'under_4ms', 'longer')


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
    latency_lines = latency_n = latency_us = cut = 0
    hist = [0] * 7
    hist_lines = 0
    wait_lines = wait_n = wait_us = wait_over = 0
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
        worked_found = 0
        for m in WORKED.finditer(line):
            worked_found += 1
            latency_lines += 1
            n = int(m.group(2))
            latency_n += n
            latency_us += n * int(m.group(1))
            h = HIST.match(line, m.end())
            if h:
                hist_lines += 1
                hist = [a + int(b) for a, b in zip(hist, h.groups())]
            else:
                cut += 1
        cut += len(WORKED_HEAD.findall(line)) - worked_found
        waits_found = 0
        for m in WAITS.finditer(line):
            waits_found += 1
            wait_lines += 1
            n = int(m.group(1))
            wait_n += n
            wait_us += n * int(m.group(2))
            wait_over += int(m.group(3))
        cut += len(WAITS_HEAD.findall(line)) - waits_found
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
    result = {
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
    if latency_lines or wait_lines or cut:
        result['gpu_stats'] = {
            'latency_lines': latency_lines,
            'latency_submissions': latency_n,
            'latency_us_mean': round(latency_us / latency_n) if latency_n else None,
            'histogram_lines': hist_lines,
            'histogram': dict(zip(HIST_NAMES, hist)),
            'wait_lines': wait_lines,
            'waits': wait_n,
            'wait_us_mean': round(wait_us / wait_n) if wait_n else None,
            'waits_already_over': wait_over,
            'lines_cut': cut,
        }
    return result


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
    if any('gpu_stats' in r for r in results):
        def gs(key):
            return lambda r: r.get('gpu_stats', {}).get(key)
        def histogram(r):
            h = r.get('gpu_stats', {}).get('histogram')
            return '/'.join(str(v) for v in h.values()) if h else None
        rows += [
            ('Submit-to-seen-done us (mean)', gs('latency_us_mean')),
            ('GPU timed submissions', gs('latency_submissions')),
            ('Seen-done <.1/.25/.5/1/2/4/+ ms', histogram),
            ('Seen-done lines / with histogram', lambda r: '%s / %s' % (r['gpu_stats']['latency_lines'],
                                                                       r['gpu_stats']['histogram_lines'])
             if 'gpu_stats' in r else None),
            ('GPU waits', gs('waits')),
            ('GPU wait us (mean)', gs('wait_us_mean')),
            ('GPU waits already over', gs('waits_already_over')),
            ('GPU stat lines cut', gs('lines_cut')),
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


def selftest():
    full = ('RedwoodGPU: the GPU worked 812 us on each of 1204 (0 under 0.1 ms, 2 under 0.25, 40 under 0.5, '
            '1100 under 1, 60 under 2, 2 under 4, 0 longer; 977 ms in all)')
    # a long interleaved prefix puts the ring's 256-character cut inside the histogram
    second = ('RedwoodGPU: the GPU worked 1000 us on each of 400 (10 under 0.1 ms, 20 under 0.25, 30 under 0.5, '
              '40 under 1, 100 under 2, 100 under 4, 100 longer; 400 ms in all)')
    at_256 = ('x' * 200 + second)[:256]
    lines = [
        full,
        at_256,
        'RedwoodGPU: the GPU worked 1000 us on each of 4',      # cut inside the count: not read as 4
        'RedwoodGPU: 12 waits of 320 us, 0 over before they began; 60 IOSurfaces taken as buffers in 210 us each; '
        '900 buffers, 120 MB',
        'RedwoodGPU: 8 waits of 100 us, 3 over before they began',
        'RedwoodGPU: 12 waits of 3',                            # cut inside the time: not read as 3 us
        # before 0139: all on one line, numbers wrong, must be ignored
        'RedwoodGPU: 5 submissions in 5001 ms: 5 command buffers and 9 buffers named, 9 KB out of the cache in 9 us '
        'a submission; the GPU worked 7 us on each of 5 (0 under 0.1 ms, 0 under 0.25, 0 under 0.5, 5 under 1, '
        '0 under 2, 0 under 4, 0 longer; 0 ms in all); 99 waits of 99 us, 9 over before they began',
    ]
    if len(at_256) != 256 or HIST.search(at_256):
        print('selftest failed: the 256-character fixture does not cut the histogram', file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as d:
        withstats = os.path.join(d, 'a.txt')
        without = os.path.join(d, 'b.txt')
        with open(withstats, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        with open(without, 'w') as f:
            f.write(lines[-1] + '\nSWEET FB: modes published: 1080x2400 at 60 Hz\n')
        got = summarise(withstats).get('gpu_stats')
        old = summarise(without)
    want = {
        'latency_lines': 2, 'latency_submissions': 1604, 'latency_us_mean': 859, 'histogram_lines': 1,
        'histogram': dict(zip(HIST_NAMES, (0, 2, 40, 1100, 60, 2, 0))),
        'wait_lines': 2, 'waits': 20, 'wait_us_mean': 232, 'waits_already_over': 3, 'lines_cut': 3,
    }
    if got != want:
        print('selftest failed: parsed %r, wanted %r' % (got, want), file=sys.stderr)
        return 1
    if 'gpu_stats' in old:
        print('selftest failed: a pre-0139 log produced gpu_stats', file=sys.stderr)
        return 1
    print('selftest ok')
    return 0


def main(argv):
    if '--selftest' in argv:
        return selftest()
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
