# Frame rate research, 2026-11-13

Question (user): what causes the lag, how did others reach 120 frames a second (60 is enough here), and how do we apply it.

Fidelity: our numbers are from the real device, one boot each (`logs/xnu-0161sA.txt`, `xnu-0161wA2.txt`, `xnu-0162sA.txt`, `xnu-0162sB.txt`). Upstream's numbers are upstream's own, on another phone, read from its documents and source; none is reproduced here. "read" = seen in the file by the lead; "agent" = reported by a subagent with file and line, not re-read.

## 1. Who the "others" are

- The donor we pinned on 2026-10-22 (`oosexgang/hackios-xnu-userland` `a79ff07`) moved to `oosexgang/hakios-xnu-kernel` (checkout `63fc2b4`, 2026-11-06, outside this repository in `~/Developer/ios-sweet-work/upstream/`; MIT for user space, APSL for the kernel parts). Nothing was imported.
- Its phone is a POCO X5 Pro (SM7325, Adreno 642L at 550 MHz), the same 1125x2436 frame scaled to a 1080x2400 120 Hz panel by CPU copy, as ours.
- It did **not** reach 120. Upstream's own table (`docs/reference/metal-measurements.md`, read): page swipe 101, Settings scroll 89-91, home button 92 at 1125x2436; at 750x1624 (`fbscale=2`) scroll 118-120, swipes 107-118. GPU time about 10 ms a frame at the home screen. Its GL path (the one we also have) scrolled Settings at 107-114.
- Nobody else was found running this on an Adreno 618 (web, Reddit, GitHub issues; `RESEARCH_LEDGER.md` 2026-11-13).

## 2. What makes ours slow (measured, ours)

| Fact | Number | Source |
| --- | --- | --- |
| Submissions (command buffers) per swap | 7.4 | 0162sA |
| GPU time per submission, upper bound | 14-24 ms (about 13 draws each) | 0162sA: 11341 submissions in 160 active s / 273.5 s covered |
| GPU time per one-draw submission, upper bound | 2.3 ms | 0161sA: 35201 in 81 active s |
| So a frame costs the GPU about | 100-150 ms, 7-10 frames a second | 7.4 x 14-20 ms; observed 9.6 swaps/s over active seconds |
| Panel copy beat | capped at 30 a second by our own boot-arg `sweetfb_hz=30` | `tools/sweet-gpu-image.sh` |
| Mode of a CoreAnimation pass | GMEM, 24 bins, load and store per bin | `TEST_LOG.md` 2026-11-13 host reading |

Batching (0011) cut submissions 98 -> 7.4 per swap but the cost **per draw** stayed about 1-2 ms. The frame is GPU-bound, and the GPU is spending on the order of a millisecond per CoreAnimation draw.

## 3. Why, according to upstream (read in its source)

1. **Tiled rendering is the wrong mode for CoreAnimation.** `HakiosMetalCA.m` 5648-5652 (read): "a pass of 23 draws took the GPU 5 ms in GMEM against 0.13 in sysmem ... its passes touch little of the screen and read it back through framebuffer fetch, which the texture unit does from GMEM at a quarter of its rate from memory." Upstream renders every window-server pass in sysmem; GMEM is opt-in (`metal_gmem=1`). Our Mesa path does the opposite: a pass with blending or framebuffer fetch has a `gmem_reason`, so freedreno refuses bypass and tiles it.
2. **`luma_boost` is most of the GPU time.** `HakiosMetalCA.m` 8185-8207 (read): a full-screen pass that reads the colour already drawn by framebuffer fetch through a LUT, "1.5 ms a draw, 83% of the GPU's timed passes"; upstream leaves the draw out (`metal_luma_boost=1` puts it back). Our system's `QuartzCore.framework/default.metallib` contains `luma_boost_lph/lpf`, `edr_scale_*`, `inplace_copy_*` (`ios-sweet-work/metal/out/final/QuartzCore.json`, read). Whether our frames draw it is **not known**: the plug-in does not log program names.
3. **The wallpaper** (many full-screen layers from another process): home button 50 -> 92 with `wallpaper_freeze=1`.
4. **Fewer pixels**: 750x1624 is 2.25 times fewer; a main pass 5 ms; scroll 118-120.
5. Smaller, each measured by upstream: recording on its own thread (`metal_defer=1`, a draw 40 -> 5 us of CPU), six copy threads (scroll 75 -> 84), copy rows written behind the panel's scan (`fb_beam`), touch read every 4 ms, Reduce Transparency/Motion (`ui_lite=1`).

## 4. Kernel side, upstream against ours (agent, file:line in the task table; spot-checked where marked)

| Topic | Upstream | Ours | Gap |
| --- | --- | --- | --- |
| GPU clock | 550 MHz, the top level; **measured** with the GCC frequency counter (`hakios.adreno.c` 693-782) | top level 650 MHz requested through legacy DCVS (`shim/gpuprobe.c` 721, 1236-1248, read; log `dcvs perf 0x30000006` = level 6) | never measured. `GPU_DECISION.md` still says 430: stale |
| DDR | max vote with `cpufreq=1`; `membench` measured writes 12.4 -> 14.8-15.4 GB/s | one vote in the shim before the GMU boots (`gpuprobe.c` 652-667) | effect never measured |
| CPU | top row of the table | gold 1939 MHz, silver 1709 MHz by default; 2304 / 1805 only with `SWEET_CPUMAX=1` at build time | top state is opt-in |
| GPU buffers | write-combined by default, so few cache flushes per submission | cached, cleaned per submission (12.5 s of 273.5 s in 0162sA) | minor since 0011 |
| Completion | polled every 200 us, no interrupt | the same | none |
| Panel | CPU copy, 120 Hz beat, 6 threads, behind the scan | CPU copy, 60 Hz grid, 3 threads, `sweetfb_hz=30` in our images, beam sync off | our cap is 30 |
| `a6xx_hw_init` | not compared | `NOTES.md` 781 lists UCHE/GBIF/QoS/HWCG as never set | open |

## 5. Also found in 0162sA (real device)

backboardd crashed once (log line 3796): `fd_bo_ref+4` <- `fd_bo_heap_alloc` <- ... <- `fd_set_constant_buffer` <- `rwa_render_draw`, a NULL buffer after the GPU address space ran out (`SWEET GPU: table arena full (1280 KiB, 320 tables)` five times from line 3758; `no room in the GPU's address space`; a 1380x900 texture refused). Zombie surfaces reached 475-482. This was a longer session than 0161wA2 (160 active s against 38), which had none of these lines. It is the likely source of the "new visual bugs" the user was unsure about; it is an exhaustion under use, not shown to be new in 0012.

## 6. The sysmem boot, 0162sB (real device, one boot, booted by the lead with `fastboot boot`)

| | 0162sA (control) | 0162sB (`sweetmetal_fddebug=sysmem`) |
| --- | --- | --- |
| `FD_MESA_DEBUG: sysmem` line | absent | backboardd, SpringBoard, metaltest |
| Faults (`SMMU gfsr`, `fault address`, `THE GPU DID NOT FINISH`) | 0 | 0 |
| backboardd crash | 1 (address space) | 0 |
| `table arena full` | 5 | 7 |
| Self-test | 17 of 21 | 17 of 21 |
| Active s / swaps / per active s | 160 / 1535 / 9.6 | 208 / 2014 / 9.7 |
| Submissions per swap | 7.4 | 7.5 |
| Submit-to-done, intervals of 50+ submissions | 29.2 ms mean | 24.4 ms mean (last six 14.6-15.4) |
| Touch lines | user session | 645 |

**No change in frame rate.** Two readings, not separated by this boot: (a) tiling is not what costs us, or (b) the flag did not change the mode. (b) is open because nothing in the library logs the mode it used, and `redwooddrawable` also loads the library in each process (`the compiler library is loaded in this process`), so a screen may exist before the plug-in sets the variable. Upstream's 38x gain from sysmem is therefore neither confirmed nor refuted for our path.

## 7. What to apply, in order (one change, one boot each)

1. **See inside a frame** (diagnostic only, plug-in + one library log line, behind a boot-arg): per command buffer, the draws by fragment-function name with GPU time, and the render mode freedreno actually used. This answers three open questions at once: is `luma_boost` drawn, did sysmem take effect, which pass costs the time. Everything below is a guess until this exists.
2. **Leave `luma_boost` out** behind a boot-arg, if step 1 shows it. Upstream: 83% of timed GPU passes. Before that, one REA question on our QuartzCore (static): which condition adds the `luma_boost` pass, so it can be turned off by configuration rather than skipped.
3. **Sysmem for window-server passes for real**, if step 1 shows GMEM was still used in 0162sB.
4. **Measure the GPU clock** (upstream's GCC frequency counter, `hakios.adreno.c` 693-782, as the model; kernel, its own spec). 650 MHz is requested and never checked. Correction 2026-11-13 (read by the lead at `63fc2b4`, lines 725-773): the counter is NOT read-only. It writes the gpucc and gcc debug mux, divider and clock-enable registers and the measure control, then restores them; its offsets are for SM7325. On SM7150 the offsets must come from a documented source (Linux `gcc-sm6150`/debugcc) before anything is written: rung needs-recovery-path, not for an unattended run.
5. **`sweetfb_hz=60`** in the test images: today's cap is 30 whatever the GPU does. Costs nothing to try; meaningless until frames are under 16 ms.
6. **750x1624 (`SWEET_SCALE=2`, already in `tools/sweet-gpu-image.sh`)**: 2.25 times fewer pixels; upstream's route to 118. A build option, not a patch.
7. **Wallpaper frozen, Reduce Transparency/Motion**: upstream's largest home-screen gain; SpringBoard-side, later.
8. **GPU address space** (section 5): 320 page tables run out under use and backboardd dies. Its own phase; it will block any long test.
9. Later: `SWEET_CPUMAX=1`, DDR vote measured, six copy threads, beam sync, `a6xx_hw_init` compared with Linux.

Not recommended now: porting upstream's C++ driver (`hakios-metal`). It targets another chip, R1-R3 are not shown for our path, and steps 1-3 test the same ideas in place.

## 8. Not verified

Upstream's figures; that any of them carries to an A618; the render mode in 0162sB; whether `luma_boost` runs here; the running GPU clock; DDR rate. One boot each: `partially-working` at most.
