#!/usr/bin/env python3
"""Decode the kernel SWEET SHOT screenshots (patch 0141, roadmap A3) into PNG files.

  tools/sweet-shot.py LOG [--out DIR] [--scale N] [--selftest]

LOG is a pulled XNU console ring (tools/sweet-log-pull.sh). The ring interleaves threads, so the
"SWEET SHOT" fragments are found with a regex search anywhere in a line, not at line start.

Format (A3, the kernel writes it):
  SWEET SHOT n begin WxH rgb565 packbits LEN sum HEX why TEXT t MS
  SWEET SHOT n SEQ4 BASE64          <= 100 base64 characters a line
  SWEET SHOT n end

Chunks are ordered by SEQ4 and joined. The compressed payload is PackBits over 16-bit
little-endian RGB565 words: control c 0..127 copies c+1 literal words, 129..255 repeats the next
word 257-c times, 128 is a no-op. The sum is FNV-1a 32-bit over the raw RGB565 bytes. A differing
sum or a missing chunk is reported but the image is still written; missing chunks stay black.
The output is DIR/shot-N-why.png, optionally nearest-neighbour upscaled by --scale.

Pure Python 3: struct, zlib, base64, re, argparse, os, sys. No PIL.
"""
import argparse
import base64
import os
import re
import struct
import sys
import zlib

BEGIN = re.compile(r'SWEET SHOT (\d+) begin (\d+)x(\d+) rgb565 packbits (\d+) (?:sum )?([0-9A-Fa-f]{8}) why (\S+) t (\d+)',
                   re.IGNORECASE)
CHUNK = re.compile(r'SWEET SHOT (\d+) (\d{4}) ([A-Za-z0-9+/=]+)')

FNV_OFFSET = 0x811c9dc5
FNV_PRIME = 0x01000193


def fnv1a(data):
    """FNV-1a 32-bit, the same loop as the kernel."""
    h = FNV_OFFSET
    for b in data:
        h = ((h ^ b) * FNV_PRIME) & 0xffffffff
    return h


def packbits_encode(words):
    """Python twin of the kernel encoder: PackBits over 16-bit little-endian words."""
    out = bytearray()
    i, n = 0, len(words)
    while i < n:
        run = 1
        while i + run < n and words[i + run] == words[i] and run < 128:
            run += 1
        if run >= 2:
            out.append(257 - run)                       # 255..129
            out += struct.pack('<H', words[i])
            i += run
            continue
        j = i + 1
        while j < n and j - i < 128:
            if j + 1 < n and words[j] == words[j + 1]:
                break                                   # leave the run for the next step
            j += 1
        out.append(j - i - 1)                           # 0..127
        for k in range(i, j):
            out += struct.pack('<H', words[k])
        i = j
    return bytes(out)


def packbits_decode(data, max_words):
    """Inverse of packbits_encode; returns at most max_words words."""
    out = []
    i, n = 0, len(data)
    while i < n and len(out) < max_words:
        c = data[i]
        i += 1
        if c == 128:
            continue
        if c < 128:
            cnt = c + 1
            if i + 2 * cnt > n:                         # truncated line: take what is there
                cnt = (n - i) // 2
            for _ in range(cnt):
                out.append(data[i] | (data[i + 1] << 8))
                i += 2
        else:
            cnt = 257 - c
            if i + 2 > n:
                break
            v = data[i] | (data[i + 1] << 8)
            i += 2
            out.extend([v] * min(cnt, max_words - len(out)))
    return out


def rgb565_to_rgb888(words):
    out = bytearray(len(words) * 3)
    j = 0
    for v in words:
        r5 = (v >> 11) & 31
        g6 = (v >> 5) & 63
        b5 = v & 31
        out[j] = (r5 << 3) | (r5 >> 2)
        out[j + 1] = (g6 << 2) | (g6 >> 4)
        out[j + 2] = (b5 << 3) | (b5 >> 2)
        j += 3
    return bytes(out)


def upscale(rgb, w, h, scale):
    if scale == 1:
        return rgb, w, h
    stride = w * 3
    out = bytearray()
    for y in range(h):
        row = rgb[y * stride:(y + 1) * stride]
        big = bytearray()
        for x in range(w):
            px = row[x * 3:x * 3 + 3]
            big += px * scale
        out += big * scale
    return bytes(out), w * scale, h * scale


def png_bytes(w, h, rgb):
    """Minimal RGB8 PNG writer (one filter-0 row at a time)."""
    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))

    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b''))


def parse_log(text):
    """Return {shot number: {w,h,len,sum,why,seqs:{seq: compressed bytes}}}.

    Both patterns are searched anywhere in a line, so console prefixes and other threads'
    text around a fragment do not matter.
    """
    shots = {}
    for line in text.splitlines():
        m = BEGIN.search(line)
        if m:
            n = int(m.group(1))
            s = shots.setdefault(n, {'w': 0, 'h': 0, 'len': 0, 'sum': None,
                                     'why': 'shot', 'seqs': {}})
            s['w'] = int(m.group(2))
            s['h'] = int(m.group(3))
            s['len'] = int(m.group(4))
            s['sum'] = int(m.group(5), 16)
            s['why'] = m.group(6)
        for m in CHUNK.finditer(line):
            n = int(m.group(1))
            seq = int(m.group(2))
            payload = m.group(3)
            s = shots.setdefault(n, {'w': 0, 'h': 0, 'len': 0, 'sum': None,
                                     'why': 'shot', 'seqs': {}})
            if seq in s['seqs']:
                continue                                # duplicate ring line
            try:
                pad = '=' * ((4 - len(payload) % 4) % 4)
                s['seqs'][seq] = base64.b64decode(payload + pad)
            except Exception:
                print(f'warning: shot {n} seq {seq:04d}: bad base64, chunk skipped',
                      file=sys.stderr)
    return shots


def assemble(shot):
    """Join the chunks by SEQ4; missing chunks become zeros. Returns (blob, missing, first)."""
    seqs = sorted(shot['seqs'])
    if not seqs:
        return b'', 0, 0
    first = 0 if 0 in shot['seqs'] else seqs[0]
    if first != 0:
        print(f'warning: first chunk is SEQ {first:04d} (earlier chunks lost)',
              file=sys.stderr)
    chunk_bytes = max(len(v) for v in shot['seqs'].values()) or 1
    blob = bytearray()
    missing = 0
    for k in range(first, seqs[-1] + 1):
        b = shot['seqs'].get(k)
        if b is None:
            blob += b'\0' * chunk_bytes
            missing += 1
        else:
            blob += b
    return bytes(blob), missing, first


def decode_shot(shot):
    """Decode one shot into (w, h, rgb888, rgb565 words, warnings list)."""
    w, h = shot['w'], shot['h']
    warn = []
    if w <= 0 or h <= 0:
        raise ValueError('no "begin" line (size unknown)')
    blob, missing, _ = assemble(shot)
    if missing:
        warn.append(f'{missing} missing chunk(s), their rows are black')
    # LEN is the compressed size; tolerate a kernel that logs the raw size instead.
    if shot['len'] and len(blob) != shot['len'] and shot['len'] != w * h * 2:
        warn.append(f'compressed data {len(blob)} bytes, begin says LEN {shot["len"]}'
                    ' (ring truncated?)')
    words = packbits_decode(blob, w * h)
    if len(words) < w * h:
        if not missing:
            warn.append(f'only {len(words)} of {w * h} words decoded, padding black')
        words.extend([0] * (w * h - len(words)))
    words = words[:w * h]
    raw = b''.join(struct.pack('<H', v) for v in words)
    got = fnv1a(raw)
    if shot['sum'] is not None and got != shot['sum']:
        warn.append(f'checksum {got:08x} != begin sum {shot["sum"]:08x}')
    return w, h, rgb565_to_rgb888(words), words, warn


def safe_why(why):
    out = re.sub(r'[^A-Za-z0-9._-]', '_', why or 'shot').strip('._-')
    return (out or 'shot')[:32]


def run(log, out_dir, scale):
    with open(log, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    shots = parse_log(text)
    if not shots:
        print(f'no SWEET SHOT in {log}', file=sys.stderr)
        return 1
    os.makedirs(out_dir, exist_ok=True)
    written = 0
    for n in sorted(shots):
        shot = shots[n]
        try:
            w, h, rgb, words, warn = decode_shot(shot)
        except Exception as e:
            print(f'shot {n}: {e}', file=sys.stderr)
            continue
        for msg in warn:
            print(f'warning: shot {n}: {msg}', file=sys.stderr)
        rgb, ow, oh = upscale(rgb, w, h, scale)
        path = os.path.join(out_dir, f'shot-{n}-{safe_why(shot["why"])}.png')
        with open(path, 'wb') as f:
            f.write(png_bytes(ow, oh, rgb))
        print(f'{path}: {w}x{h} -> {ow}x{oh}' + (' (with warnings)' if warn else ''))
        written += 1
    return 0 if written else 1


def selftest():
    """Build a synthetic image, encode it exactly as the kernel does, and decode the log back."""
    w, h = 61, 23
    words = []
    for y in range(h):
        for x in range(w):
            if y < 2:
                words.append(0xf800)                    # red: long repeat run
            elif y < 4:
                words.append(0x001f)
            elif y < 6:
                words.append(0x0000)
            else:
                r = (x * 31) // (w - 1)
                g = (y * 63) // (h - 1)
                b = ((x + y) * 31) // (w + h - 2)
                words.append((r << 11) | (g << 5) | b)

    raw = b''.join(struct.pack('<H', v) for v in words)
    want_sum = fnv1a(raw)
    comp = packbits_encode(words)
    if packbits_decode(comp, w * h) != words:
        print('selftest failed: encoder/decoder round trip', file=sys.stderr)
        return 1

    b64 = base64.b64encode(comp).decode('ascii')
    chunks = [b64[i:i + 100] for i in range(0, len(b64), 100)]
    lines = [
        '[   0.000000] unrelated console line from another thread',
        f'[  12.345678] AppleCLCD: SWEET SHOT 1 begin {w}x{h} rgb565 packbits {len(comp)} '
        f'sum {want_sum:08x} why selftest t 7',
    ]
    # Reverse the order and bury every fragment mid-line: the decoder must sort by SEQ4.
    for seq in reversed(range(len(chunks))):
        lines.append(f'[  12.345679] SWEET SHOT 1 {seq:04d} {chunks[seq]} trailing noise')
    lines.append('[  12.345680] SWEET SHOT 1 end')
    shots = parse_log('\n'.join(lines))
    if list(shots) != [1]:
        print(f'selftest failed: parsed shots {list(shots)}', file=sys.stderr)
        return 1
    got_w, got_h, rgb, got_words, warn = decode_shot(shots[1])
    if (got_w, got_h) != (w, h) or got_words != words or warn:
        print(f'selftest failed: decode mismatch ({got_w}x{got_h}, {len(got_words)} words, '
              f'warnings {warn})', file=sys.stderr)
        return 1
    want_rgb = rgb565_to_rgb888(words)
    if rgb != want_rgb:
        print('selftest failed: RGB888 mismatch', file=sys.stderr)
        return 1
    png = png_bytes(w, h, rgb)
    if png[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack_from('>II', png, 16) != (w, h):
        print('selftest failed: bad PNG header', file=sys.stderr)
        return 1
    # A missing middle chunk must still produce an image (its rows are black).
    shot = shots[1]
    saved = dict(shot['seqs'])
    if len(saved) >= 3:
        del shot['seqs'][1]
        _, _, _, miss_words, miss_warn = decode_shot(shot)
        if not miss_warn or len(miss_words) != w * h:
            print('selftest failed: missing chunk not handled', file=sys.stderr)
            return 1
        shot['seqs'] = saved
    print('selftest ok')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Decode SWEET SHOT kernel screenshots (patch 0141) into PNG files.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='example:\n'
               '  python3 -I tools/sweet-shot.py logs/xnu-0143r.txt --out logs/shots-0143r\n'
               '  python3 -I tools/sweet-shot.py logs/xnu-0143r.txt --out shots --scale 3')
    ap.add_argument('log', nargs='?', metavar='LOG',
                    help='kernel console log with SWEET SHOT lines (not needed with --selftest)')
    ap.add_argument('--out', default='shots', metavar='DIR',
                    help='directory for shot-N-why.png (default: shots)')
    ap.add_argument('--scale', type=int, default=1, metavar='N',
                    help='nearest-neighbour upscale factor (default: 1, example: 3)')
    ap.add_argument('--selftest', action='store_true',
                    help='encode and decode a synthetic image, print "selftest ok"')
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.log:
        ap.error('LOG is required unless --selftest is given')
    if a.scale < 1:
        ap.error('--scale must be at least 1')
    return run(a.log, a.out, a.scale)


if __name__ == '__main__':
    sys.exit(main())
