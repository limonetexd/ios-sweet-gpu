# Frame rate investigation, 2026-11-14

Question (user): find every route to 60 frames a second and apply them.

Fidelity: numbers are from the real device, one boot each, synthetic swipes, unless a row says host or read. "read" = the lead read that source line. Nothing here is `verified-working`.

## 1. Where a frame goes now (0166uA, payload 0001-0015, 1125x2436, 30 Hz copy)

Per command buffer (one a frame, about 97 draws), from `logs/xnu-0166uA.txt`:

| Part | Time | Source |
| --- | --- | --- |
| Command buffer, wall | 24.7 ms | passlog `mean 24.5-25.1 ms` |
| of it, thread CPU | 8.2 ms | passlog `cpu 939.76 ms of wall 2850` (33 %) |
| of it, blocked | 16.5 ms | the rest |
| Kernel wait for the GPU | 16.4 ms a frame | `115 waits of 16364 us` per 5 s, 113 command buffers |
| Kernel walk before each submission | 3.7 ms a frame | `946 us a submission`, 3.9 submissions a frame |
| Drawable surface mapped into the GPU again | 2.1 ms a frame | `117 IOSurfaces taken as buffers in 2112 us each` |
| Whole-surface cache clean of a new surface | about 1.2 surfaces a frame, 9.5 MB each | `140 first cleans of 1327 MB` per 5 s |
| Panel copy (kernel vsync thread, not backboardd) | 3.0-3.9 ms | `presents (3055 us average)` |

Reading: after 0015 the frame is GPU-bound. Two thirds of the command buffer is the wait in `rwa_finish`. The unbounded uploads of `NEXT_PROMPT.md` item 1 are about 110 uploads and 31 MB per 5 s, which is about 280 KB a frame: not worth a change now.

At 750x1624 (0164z2, before 0015) the same wait was 4.0 ms (`73 waits of 3922 us`), the walk 0.46 ms a submission, the take 0.95 ms. The GPU part scales 3.6 to 4 times for 2.25 times fewer pixels.

## 2. The 60 Hz faults are one over-fetch, not the refresh rate

Both faulty boots (0165fA profiler, 0167h60 60 Hz) have exactly one root fault, the same one:

- `FAR` is the first byte past the mapped bytes of a 281x609 IOSurface (1152 bytes a row, 704512 bytes mapped): `0xac000 from its start, in the slack past the mapped bytes, 0 past their end`. `FSYNR0 0x3`: a read.
- Mesa says why (`src/freedreno/fdl/fd6_layout.c` 242-250, read): the blits between memory and GMEM work in 16x4 blocks and over-fetch; Mesa over-allocates its own textures to a height multiple of 4. An imported IOSurface is not over-allocated. 609 rows round to 612; 612 x 1152 = 705024 is past the 704512 mapped.
- Everything after it in those logs is fallout: the GPU stops answering, every command buffer times out after 2 s, buffers pile up, `table arena full`.

So the fault needs a GMEM batch that restores a surface whose height is not a multiple of 4. It does not need 60 Hz. `sweetmetal_fddebug=sysmem` removes the blits (workaround, boot-arg only). The proper fix is one of: the kernel maps the slack after an imported surface to a scratch page, or the library refuses GMEM for a target whose allocation is shorter than its 4-row rounding. Not done.

## 3. backboardd makes a new 13.9 MB framebuffer surface every frame

`logs/xnu-0166uA.txt`: `SWEET SURF: backboardd create id N 1125x2436 ... size 13893632`, one id a frame, the older one freed. Known since 2026-11-07 as open question B1 (`notes/deepseek/ROADMAP-2026-11-07-B-near.md`). Upstream has the same behaviour and says so (`MiniIOMobileFramebuffer.cpp` 362, read). It asks for format `b3a8` and both kernels answer BGRA.

Cost a frame here: create, zero in a thread, map into the GPU (2.1 ms), whole clean of 13.9 MB, free. Cause not established. A cheaper kernel path is the bounded fix; making CoreAnimation reuse surfaces is the larger one.

## 4. Kernel walk before a submission

`RedwoodGPU.cpp` 1565-1599 and 1640-1671 (read): for every named surface that is not pool memory and not wrapped, `toMemoryWritten` visits every page (`getPhysicalSegment`, `pmap_is_modified`) at every submission. About 58 buffers are named a submission. This is the 946 us; the bytes actually cleaned are small (10.8 MB per 5 s).

Candidates: visit a surface once a frame instead of once a submission (the wrapped branch already uses a 4 ms rule), or keep the page numbers so a visit is one table look-up a page. Kernel change, own spec and review.

## 5. Other items

- Wait granularity: `gpuWait` polls every 200 us (`RedwoodGPU.cpp` 369-394, read). Not a cost.
- Panel copy runs in the kernel's vsync thread with 3 helpers; `sweetfb_threads`, `sweetfb_presenter`, `sweetfb_beam` exist. Not the limit at 30 Hz.
- GPU clock: the shim reads PLL0 after the DCVS vote without writing (`shim/gpuprobe.c` 1249-1252). At level 4 an old shim log shows `pll0 l=0x2C frac=0xCAAA` = 860 MHz, halved = 430 MHz, as asked. Level 6 (650 MHz) is acknowledged (`dcvs perf 0x30000006 return 0`) but its PLL reading is not in a pulled log: not verified.
- Serial design: `-commit` replays, submits and waits on one thread under the library lock (`redwoodmetal.m` 5200-5316, read). CPU and GPU never overlap. Returning before the wait needs completion handlers delivered from a waiting thread: correctness-critical, not started.

## 6. Boots of this phase (RAM boots, nothing flashed, one boot each; rows in `TEST_LOG.md`)

| Boot | Change against the one before | ms a command buffer | Thread CPU | GPU wait | Best second | Faults |
| --- | --- | --- | --- | --- | --- | --- |
| 0167h60 | 60 Hz copy | broken run | - | - | - | 12 |
| 0168s60 | + `sweetmetal_fddebug=sysmem` | 26.1 | 9.3 | 16.9 | 29 | 0 |
| 0168z60 | + 750x1624 (`SWEET_SCALE=2`) | 9.6 | 5.9 | 3.8 | 57 | 0 |
| 0168zM | + `SWEET_CPUMAX=1` | 9.15 | 5.4 | 3.8 | 59 | 0 |

At 1125x2436 a frame is over 16.7 ms, so 30 a second is the ceiling there. At 750x1624 the best seconds are 50-59 with 5 to 8 frames a second still taking two ticks. Sustained 60 is NOT reached. The picture at 750x1624 has not been looked at.

Kernel patch 0162 (`xnu/patches/0162-sweet-gpu-pagelist-surfclear.patch`, commit 16e1259, CI run 43588677901): `gpu_pagelist=1` and `sweet_surfclear_ms=N`, both off by default. Written by `opus-impl`, diff read by the lead. Not compiled locally, not booted.

## 7. Ranking (gain, risk, evidence)

| # | Option | Expected gain | Risk | Evidence | Needs |
| --- | --- | --- | --- | --- | --- |
| 1 | 750x1624 + sysmem + 60 Hz as the test configuration | done: 26.1 -> 9.6 ms | softer picture, not judged | one boot | user looks at the screen |
| 2 | 0162 `gpu_pagelist=1` | about 1.3 ms a frame at 750x1624 (three of four walks) | low, same decisions per page | host reading | CI artifact, one RAM boot |
| 3 | 0162 `sweet_surfclear_ms=0` | about 1-1.5 ms (no bzero on the render thread, no whole clean) | low; uses a core and memory bandwidth | host reading | one RAM boot after 2 |
| 4 | `SWEET_CPUMAX=1` | 0.5 ms | no thermal limit in the kernel | one boot | a thermal cap first |
| 5 | Commit returns before the GPU wait (completion handlers from a waiting thread) | up to 3.8 ms at 750x1624, the only route at 1125x2436 | high: lifetime of everything a frame names | read only | spec, `opus-impl`, `reviewer`, flash |
| 6 | Over-fetch fixed in the kernel (slack mapped to a scratch page) so GMEM is safe | none in speed; removes the need for the sysmem flag | medium | section 2 | spec, CI |
| 7 | Why CoreAnimation makes a surface a frame (B1) | take 0.9 ms + create | unknown | open since 2026-11-07 | research |
| 8 | `sweet_fbpool=1` | walk and clean gone at full size only | froze CoreAnimation with GL (NOTES 774) | old runs | not now |
| 9 | Unbounded uniform uploads (`fs_and`) | under 0.3 ms | low | section 1 | not now |


**Correction 2026-11-14 (user, photos of boot 0169pl):** at 750x1624 the screen shows only a strip at the top (part of the dock), glitching; touch works. The 750x1624 figures of 0168z60, 0168zM and 0164z2 are therefore NOT valid frame-rate evidence: a mostly empty frame is cheap. Which of the size, sysmem at that size, or kernel 0162 causes the strip is not established (0169pl changed the kernel as well). Do not boot `SWEET_SCALE=2` again until the picture is explained. Valid result of this phase: 0168s60 only (1125x2436, 26.1 ms, best second 29, 0 faults).

## 8. The 750x1624 strip is a band destination bug (0163)

Found by reading `sweet_fb_copy_band()` in the 0001-0162 tree (`SweetFramebuffer.cpp` 1205-1213):
the scaled loop took its destination row pointer from `job->dst` (the first band's panel row) and
added `(y - y0)` rows, while the 1:1 path uses the band-local `dst` (`job->dst + y0 * dstRowBytes`).
Every band therefore wrote panel rows `pdy .. pdy+63`; the other 2336 rows kept the previous frame.
All 38 bands still did their full scale work, so a band's cost — and the 9.6 ms a command buffer of
0168z60 — is real. What stayed on the screen was the last band written, rows 1578-1599 of the crop,
i.e. the dock: exactly the user's photo of 0169pl (strip at the top, glitching, touch correct).

Patch `0163-sweet-fb-scale-band-dst` (3 added lines, `check-patch.py` ok, apply check ok). Not built
before the push; one RAM boot at 750x1624 with the user watching is the test. The 0131 column map and
the crop 15,12 720x1600 -> 1080x2400 are unchanged, so the fix is either "the whole screen appears,
scaled and blocky" or nothing changes at all.

0162 flags, measured at 1125x2436 (0169a/pg/sf/sf2, four boots, TEST_LOG): `gpu_pagelist=1` flush
949 -> 892 us/sub; `sweet_surfclear_ms=0` moves the surface bzero off the window server's thread
(`zeroed now` -> `zeroed already`, first cleans 41 GB -> 0.2 GB). Neither lowers wall time at full
size (25.5-25.6 ms) because the frame is 16.9 ms of GPU wait. They are only worth a default at
750x1624, where the frame is ~9.6 ms and CPU work is the larger share: decide after the 0163 boot.
