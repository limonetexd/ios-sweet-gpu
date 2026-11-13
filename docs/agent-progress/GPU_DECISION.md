# GPU decision memo — Phase 0, 2026-11-08, tree `c5d9aca`

**Decision: `fix-in-place`** (accepted by the user, 2026-11-08). None of R1/R2/R3 is demonstrated. Rows sourced `logs` were re-derived on 2026-11-08 from the recovered real-device rings (`TEST_LOG.md`); the rest still come from `NOTES.md`.

## Current path

1. backboardd's CoreAnimation draws through GLES. There is no Metal anywhere in this tree.
2. `libtopaz-gl.dylib` supplies EAGLContext (donor `eagl.c` + `userland/eagl-sweet.py`), loaded by `bbd_wrap`/`topaz_inject`.
3. GL → Mesa 25.0.7 `libOSMesa` (freedreno + softpipe), `userland/build-gpu.sh:2`. Donor source is pinned in CI, not in the tree.
4. Shaders: CA's GLSL → Mesa → ir3 on the CPU. Programs compile only at start-up (NOTES:640).
5. Kernel boundary: `RedwoodGPUUserClient` IOKit selectors shaped like Linux msm DRM (`GemNew`, `CpuPrep`, `Submit`, `WaitFence`, plus `kRedwoodSurface`), `0083:800-811`.
6. `RedwoodGPU.cpp` + `SweetAdreno.cpp`: ring, fences, GPU page tables, 512 MiB VA window (0145/0146).
7. Bring-up is in the shim before XNU: GDSC, clocks, SMMU, GMU/HFI, DCVS, SQE, zap (`shim/gpuprobe.c`), then `sweet_gpu.c` handoff (0082).
8. Buffers: IOSurfaces imported as GEM objects; a write-combined pool serves Mesa buffers ≥256 KiB; screen surfaces stay out of it (0094).
9. Sync: AppleCLCD presents a swap only once the GPU is done with its surfaces (0095).
10. Present: software 16.667 ms timer (0109), CPU copy in 64-row bands on 3 threads (0110/0111) into ABL's framebuffer. Not panel-locked by default (0126 off). No MDP flip.

## Evidence

| Claim | Source | Confidence |
| --- | --- | --- |
| Native run with no idle (0143r): 36.0 swaps/s, GL p50 14.6 / p95 17.0, present 3.37 (sum 18.0 > 16.67). 539 VA errors | logs, 326 normal s | high for the numbers; medium as a baseline |
| Same config elsewhere: 33.6 swaps/s at GL 10.1/28 (0144r, 28 normal s, 6 VA errors); 23.3 at GL 9.5/13.5 (0146r, 0 VA errors) | logs | high for the numbers; workloads differ |
| Scaled 750×1624 (0143r2): GL 6.3/12.6 + present 4.89; 28.7 swaps/s, p90 49, 36 normal s. Only 4.1 % of those swaps had a gap over 20 ms, so the low rate is short bursts, not slow frames. **Phase 0 misread this row** | logs | high for the numbers |
| "42 % of swaps miss the vsync tick": not reproduced. `late` means a swap gap over 20 ms (0097c), not a missed tick; normal-second values are 98.9 / 4.1 / 89.3 / 25.5 / 25.3 % for 0143r / 0143r2 / 0144r / 0146r / 0159r-rung2 | NOTES:114; logs | retracted as stated |
| eagl profile fields, read in donor source: "in GL calls" is in-frame GL time without `glFlush`, because `frame_end` clears `in_frame` before that call returns (`eagl.c:407,1028`). "outside" is frame time minus that, so it contains the whole flush. Per frame: in GL 1.7–4.0, flush 4.4–8.4, the rest (CoreAnimation between draws) 1.0–2.6 ms. `glFlush` matches "handing on" + "waiting" to about 1 ms. Time before the first draw is not covered | logs; donor `e477291` | medium-high |
| Per-call cost at native, cumulative per frame: `glFlush` 6.1–8.4 (of which Mesa "handing on" p50 3.9–7.0), `glTexImage2D` 3.0–4.8, `glDeleteTextures` 2.2–3.4 ms; attach ("before it") p50 2.4–3.7 ms. Slot timers are process-wide but divided by one context's frames, so slightly high. The earlier ~5.7 attach is not reproduced | logs; donor; NOTES:637-640 | medium |
| GPU execution per frame: **no valid number**. The 0139 "worked" figure runs from ring write to first look that finds it done, so it overlaps (0143r: 232 subs/s × 19.2 ms = 4.4 s per second) and includes time nobody looked (first window averages 4.6 s with no `not done after` report) | `0083:500-523`; logs | high |
| Ring occupancy (newest submission unfinished ≥ 1 ms, sampled once a second, active seconds): 0143r 49 % (CI 44–54), upper 72 %, so 14.0–20.6 ms per swap; native swipe runs 15–17 %, 5.8–12.2 ms; scaled 4 %, 2.4–8.4 ms. Includes queueing | logs, 0097 `pending` | medium for 0143r; low for short runs |
| Display readiness: GPU not done at the tick on 48 % (0143r), 34 % (0146r, 0159r-rung2), 19 % (0144r), 8 % (0143r2) of ticks with a new frame waiting; each defers that frame by 16.67 ms. On 0143r this agrees with the separate occupancy sample (48 vs 49 %) | logs, 0095/0097 `stale` | medium-high |
| Submissions per swap: 6.6 (0143r), 5.9 (0143r2), 6.4 (0144r), 4.7 (0146r), 4.5 (0159r-rung2) | logs, fence delta | high |
| eagl's "big/little" only tests CPU number < 4, a donor-device layout (`eagl.c:1064-1072`). On sweet, cpu 4–7 all count as "little", A76s included, so 99 % "little" fits the `bound to cpu 7` line and says nothing about core type | donor; logs | high |
| Effective GPU clock unresolved: the native shim logs request level 4, 430000 kHz (PLL L=0x2C), the kernel prints `dcvs perf 0x30000006`, and `gpuprobe.c` also has a 650 MHz path. Nothing measures the running clock | logs; `gpuprobe.c:200,721,1238`; `0082:251` | high that 430 was requested; effective unresolved |
| One-second swap counts cannot separate idle from slow: swipe runs draw in bursts with ~2.4 s gaps. No per-frame interval data exists | logs | high |

## Bottlenecks, ranked

1. **GPU not ready at the tick** (sync/GPU): 19–48 % of native ticks with a new frame find it unfinished, each a 16.67 ms deferral; ring occupied 6–21 ms per swap. Execution versus queueing unknown.
2. **Surface churn + Mesa encoding** (CPU encoding): the three top calls cost 11.3–15.8 ms per frame at native by eagl's counters; 4.5–6.6 submissions per swap. The "outside GL" bucket is mostly this flush, not CoreAnimation.
3. **CPU panel copy** (presentation): 3.4–3.7 ms native, 4.89 scaled (logs).
4. **Pacing**: software tick plus the deferral in item 1. No per-frame data, so its share is unmeasured.
5. **GPU execution alone**: unranked, no valid number; the occupancy figures are its ceiling.
6. **CPU blocking on the GPU**: small. Kernel waits 1–98 per run; eagl `waiting` p50 0.8–1.7 ms.
7. **Memory/bandwidth**: VA exhaustion fixed (539 errors in 0143r, 0 in 0146r, logs); bandwidth never measured.
8. **Correctness**: blur-dismiss freeze open (NOTES:535,802); no automated image check (NOTES:204).

Phase 1b (2026-11-08): GPU execution still cannot be ranked. The 0139 figure is latency, not busy time; ring occupancy and display readiness are the best available substitutes.

## Against the replacement rules

- **R1 not shown.** Past correctness failures each closed with a bounded patch (surface leak, pool clamp, VA window). The open freeze has no root cause.
- **R2 not shown.** The measured workload is GLES; Metal is a missing feature, not a limit of this path. DC28088's frontend claims to reuse the same kernel GPU driver (upstream claim, low confidence).
- **R3 not shown, but closer.** The Phase 0 statement that every measured loss is CPU-side or pacing no longer holds. Occupancy of 14–21 ms a swap appears only in 0143r (539 VA errors), includes queueing, and is at a requested 430 MHz (as written then; corrected 2026-11-13: the shim asks the GMU for level 6, 650 MHz, and the kernel logs `gfx3d cfg 0x101 dcvs perf 0x30000006 return 0` at boot, 0163pA; the PLL multiplier is not logged, so the running rate is still unverified) with no cut to encoding or churn, so the trigger below is unmet. R1 and R2 are unchanged.

## What would change this

- R3: at a confirmed clock, GPU busy per frame stays over ~14 ms after encoding and churn are cut.
- R1: the freeze traces to a GLES/Mesa behaviour no bounded eagl or Mesa change can fix.
- R2: a required CoreAnimation path or app is shown to need Metal with no GLES fallback.

## Metal assessment (2026-11-08; source reading only, nothing built or run: `not-tested`)

- **Possible as a second, selectable path.** `oosexgang/hackios-xnu-userland` at `a79ff07` has a Metal plug-in and AIR → NIR → freedreno, and its transport opens `RedwoodGPU` with msm-shaped calls and the `0x7e` surface request, as our kernel does. Struct-level compatibility is unverified.
- **DC28088 `native-metal`** shows the same phone can reach the home screen on Metal (upstream claim), but needs its own ABI1 kernel and its repository has no license, so its own code cannot be imported. Our 2026-11-02 trial of its bundle on this root gave green lines and was reverted (NOTES:936).
- **`hakios-metal`** targets chip 0x06030500 (A7c+ Gen 3), not the A618.
- **Not an fps fix.** Same Mesa backend, GPU, kernel and CPU-copy present. DC28088 reports stable 60 fps still not achieved and calls its compositor fill/pass bound. It might remove eagl's per-frame attach and delete cost (inference).
- **The value is features:** blur and Safari video (upstream claims), and apps that need Metal.
- **Rules:** R1–R3 are still unshown, so GL stays the default and Metal sits behind a boot-arg until it passes the same tests.
- **Viability check (user chose Metal, 2026-11-08), so far:** the donor opens service `RedwoodGPU`, routes msm calls by the low byte of the request, and its `rwd_surface` has the same layout as our `redwood_surface` (`0083:869-875`), so the kernel interface looks reusable. Our kernel publishes an empty `IOAcceleratorES` with no Metal plug-in properties (`0086`), which is where discovery would attach. Still open: does the donor build on this Mac, what share of QuartzCore's shaders compile, and any device result.
- **Verdict 2026-11-08, host fidelity: viable to continue.** On this Mac the donor's shader compiler built, and Mesa, `libredwoodair` and the `RedwoodMetal` bundle cross-built for iOS 16 arm64 with Xcode. 135 of QuartzCore's 141 shaders from 20H392 compile for the A618. Every kernel request the driver makes exists in our kernel. **Nothing has run on the phone**, and compiling is not correctness.
- **Known gaps:** `fixed_frag_lph_cph` and `_cpf` (pointer store; DC28088's first hardware trial crash-looped on these) and four tile shaders in QuartzCore. VideoToolbox's scaler compiles 2 of 9 (a 4×16 to 2×32 bitcast, and `air.get_null_texture_2d`), so enabling Metal could change video behaviour until those are fixed. All libraries: 5749 of 16912, mostly stitchable and library functions.
- **Safari video:** nothing found shows it needs Metal. DC28088 reports it working but gives no mechanism, and an earlier note says WebKit was denied by their bundle's client policy. On this tree it is `not-tested` and needs working Wi-Fi first.
- **REA:** no iOS 16.7.16 artifact is on this Mac and source answers the current questions. Later candidate, from files the user supplies and never committed: QuartzCore `default.metallib`, one question: which shader features must compile.

## Three smallest next tasks

1. **Done 2026-11-08:** donor `eagl.c` read at `e477291`; profile fields settled above. Nothing copied.
2. **Measurement-only patch, not written, needs approval:** `sweetfb_ftrace=1` (default off). A kernel thread reads the fence word about every 200 us while work is outstanding (reads only: no new packets or register writes), giving each submission's real completion, plus a per-swap ring of timestamps (swap arrival, last fence, fence done, tick index, copy start/end). Ring busy is the sum of `done − max(submit, previous done)`. Separate commit.
3. **Device, reversible (RAM boot), needs approval:** two identical 420 s runs of that kernel, `SWEETFB_HZ=60`, `sweetgpu_reboot=420 sweetgpu_swipe=60` confirmed in the payload, covering a swipe workload and a no-idle scene at 0 VA errors. Proposed: skip no-code runs first, because today's instrumentation cannot measure GPU execution.

## Metal frame time, 2026-11-12 (host; existing device logs 0161sA, 0161sB, 0161a, one boot each; source reading)

Verdict: **fix in place**, scheduling multiplied by cache maintenance. None of R1-R3 is shown.

| Boot | Active s | Swaps | Late | Swaps/s (max) | GPU subs | Subs/swap | Bufs named/sub | Cache clean per sub | Cache CPU total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0161sA | 81 | 360 | 358 | 4.4 (10) | 35201 | 98 | 15.9 | 12.3 MB, 0.93 ms | 32.7 s of 183 s |
| 0161sB | 40 | 136 | 134 | 3.4 (8) | 13475 | 99 | 15.6 | 11.5 MB, 0.90 ms | 12.1 s of 118 s |
| 0161a | 162 | 550 | 548 | 3.4 (10) | 63110 | 115 | 15.8 | 11.2 MB, 0.90 ms | 56.8 s of 271 s |

- Where it goes: every Metal draw and clear is its own kernel submission. `rwa_render_draw` (`air_metal.c` 7364) and the clear (6846) call `finish_or_say_why`, which is `pipe->flush` plus `fence_finish` (3088). The plug-in replays a command buffer's draws inside `-commit` (`redwoodmetal.m` 4204-4295), so a frame is about 100 flushes, each followed by a wait.
- Each submission costs the kernel about 0.9 ms of cache cleaning, because an IOSurface (ordinary cached memory) is cleaned again when more than `GPU_PUSH_AGAIN_MS` = 4 ms has passed since its last clean (`RedwoodGPU.cpp` 190). 11-12 MB per submission is about one 1125x2436 BGRA drawable (11.0 MB). About 100 x 0.9 ms = about 90 ms of CPU per frame before any GPU time. Waiting means polling every 200 us (`GPU_ASK_AGAIN_US`).
- Caveat: the submission counts cover the whole system (backboardd, SpringBoard, apps), so subs/swap is an upper bound for one frame. The GPU's own execution time per frame is not measured.
- Not architectural: the interface already accepts many draws per flush (Gallium batches). The per-draw wait was put there on purpose, for error reporting (docs/air.md section 5), not because anything requires it.
- After 0011 (0161wA2, one boot, 2026-11-13): 7.3 subs/swap, 1.9 s of cache cleaning in 76 s, but about 80 ms submit-to-done per submission (was 5.5 ms per draw). The cost is now GPU-side per command buffer. Still not R3: the candidates are tiling mode, clock and the per-draw framebuffer rebind, all of them local. The measurement that is missing: GPU time per submission split by mode (GMEM against sysmem) and the actual GPU clock.
- 2026-11-13 (host, source reading; `TEST_LOG.md` "Where the per-command-buffer GPU time goes"): UI batches run GMEM, 24 bins (4x6 of 288x416, assuming 512 KiB GMEM), each with a load and a store of its part of the 11 MB target; freedreno's own fallback picks GMEM for any blended pass. The per-draw framebuffer rebind does not split the batch (inferred). The GPU clock is not logged anywhere. Steady-state submit-to-done is 19-41 ms, not 80 (two early intervals skew the mean). Still not R3: both candidates (tiling mode, clock) are local. Next: one A/B boot, `FD_MESA_DEBUG=sysmem` selected by a boot-arg, against 0161wA2; the clock readback is a separate, later, kernel-side read-only change.
