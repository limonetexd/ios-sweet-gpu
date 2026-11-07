#!/usr/bin/env python3
"""check-patch.py: cheap guards for a kernel patch before it is pushed (CI cannot be re-run for free).

  tools/check-patch.py xnu/patches/NNNN-name.patch [more.patch ...]

Exit 0 = nothing found, 1 = problems (printed). Looks only at the lines a patch ADDS:
  * a carriage return anywhere            (CI's `git apply` skips the patch)
  * a C string literal that is not closed on its line - a literal newline inside "..." is what
    broke CI for 0117-0119 (write \\n instead); also an odd number of quotes in an added line
  * a tab-less continuation of an IOLog/printf line longer than 256 characters (IOLog cuts there)
  * hunk header counts that do not match the hunk body (a hand-edited patch)
  * a blank context line without its leading space (also a hand-edit slip)
It is a heuristic (comments and char literals are stripped first), not a compiler: a warning on
a line you know is fine can be ignored, an error exit means look at it.
"""
import re
import sys


def strip_code(line):
    """Remove char literals, escaped characters and comments; keep the string quotes."""
    line = re.sub(r"'(\\.|[^\\'])'", "''", line)
    line = line.replace('\\\\', '').replace('\\"', '')
    line = re.sub(r'/\*.*?\*/', '', line)
    # a // comment starts outside of any string
    out, in_str = [], False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"':
            in_str = not in_str
        if not in_str and line.startswith('//', i):
            break
        out.append(ch)
        i += 1
    return ''.join(out)


def check(path):
    problems = []
    raw = open(path, 'rb').read()
    if b'\r' in raw:
        problems.append((0, 'carriage return in the patch'))
    text = raw.decode('utf-8', errors='replace')
    lines = text.split('\n')
    cur_file = ''
    hunk = None   # [start_line, old_expected, new_expected, old_seen, new_seen]
    in_comment = False
    for no, line in enumerate(lines, 1):
        if line.startswith('+++ '):
            cur_file = line[4:].strip()
            hunk = None
            continue
        if line.startswith('--- ') or line.startswith('diff ') or line.startswith('index '):
            continue
        m = re.match(r'@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@', line)
        if m:
            if hunk and (hunk[1] != hunk[3] or hunk[2] != hunk[4]):
                problems.append((hunk[0], 'hunk counts: header says -%d +%d, body has -%d +%d' % tuple(hunk[1:5])))
            hunk = [no, int(m.group(1) or 1), int(m.group(2) or 1), 0, 0]
            continue
        if hunk is None:
            continue
        if line == '' and no == len(lines):
            continue
        if line.startswith('\\'):
            continue
        tag = line[:1]
        if tag == '+':
            hunk[4] += 1
        elif tag == '-':
            hunk[3] += 1
        elif tag == ' ':
            hunk[3] += 1
            hunk[4] += 1
        elif line == '':
            problems.append((no, 'empty line inside a hunk: a blank context line needs a leading space'))
            hunk[3] += 1
            hunk[4] += 1
        else:
            hunk = None
            continue
        if tag != '+' or not re.search(r'\.(c|cpp|h|hpp|m|mm|S)$', cur_file):
            continue
        body = line[1:]
        code = strip_code(body)
        stripped = body.strip()
        if stripped.startswith('/*') and '*/' not in stripped:
            in_comment = True
            continue
        if in_comment:
            if '*/' in stripped:
                in_comment = False
            continue
        if stripped.startswith('*') or stripped.startswith('//'):
            continue
        if code.count('"') % 2 == 1:
            problems.append((no, 'odd number of quotes: unterminated string literal? ' + body.strip()[:90]))
        if re.search(r'(IOLog|printf|kprintf|panic)\(', body) and len(body.expandtabs(8)) > 256:
            problems.append((no, 'added line longer than 256 characters (IOLog truncates there)'))
    if hunk and (hunk[1] != hunk[3] or hunk[2] != hunk[4]):
        problems.append((hunk[0], 'hunk counts: header says -%d +%d, body has -%d +%d' % tuple(hunk[1:5])))
    return problems


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    bad = 0
    for path in argv:
        problems = check(path)
        for no, msg in problems:
            print('%s:%d: %s' % (path, no, msg))
        bad += len(problems)
        if not problems:
            print('%s: ok' % path)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
