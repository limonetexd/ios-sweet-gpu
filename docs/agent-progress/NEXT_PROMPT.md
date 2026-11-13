> State 2026-11-13 night:
> - Phone (device): root = `work1.raw` + payload 0001-0012 (library 1d4c1505..., `RedwoodMetal` 3d35bc77..., `metaltest` 142d6a49...), in fastboot. Snapshot `work1-pre0012.raw` (0001-0011).
> - 0012 booted twice: 0162sA (control) and 0162sB (`sweetmetal_fddebug=sysmem`): same frame rate (9.6 / 9.7 swaps per active s, 7.4 / 7.5 subs per swap). Whether sysmem took effect is unknown.
> - Research: `FRAME_RATE_RESEARCH.md` (read it first; section 7 is the ordered work list). Upstream checkout: `~/Developer/ios-sweet-work/upstream/hakios-xnu-kernel` (`63fc2b4`), read-only reference, nothing imported.
> - The lead may run RAM-only boots itself (`tools/sweet-boot-test.sh IMG TAG 420`); flashing still needs the user's typed yes.
> - Traps: image builds need `PATH=~/Developer/ios-sweet-work/bin:$PATH` (check `RAMDISK MATCH`); a clean `ios` rebuild changes the library hash; never run `metal-flash-test.sh` in two tabs.
> - Budget: check the meter first. Delegate typing to opus/sonnet.

# Phase: see inside a frame (patch 0013, diagnostic only)

Read `CLAUDE.md`, `FRAME_RATE_RESEARCH.md` sections 6-7 and the last section of `TEST_LOG.md`. State the plan in ten lines and wait for the go-ahead.

Spec (no behaviour change; everything behind boot-arg `sweetmetal_passlog=1`, absent = today's path):

1. Library (`air_metal.c`, `opus-impl`): one line at device open with the `FD_MESA_DEBUG` flags the screen holds and whether the screen already existed; per flush, whether the batch ran sysmem or GMEM and its bin count (read from freedreno, no new packets).
2. Plug-in (`redwoodmetal.m`): per command buffer, draws grouped by fragment-function name (label or function name the pipeline was made from) with count; every 5 s the top ten names by draws and the submit-to-done time of the command buffers that held them. Cap the output: one block per 5 s.
3. `reviewer` on the diff; host build `ios`, `driver`, `test`, `payload`; host `air_metal_test` must pass (library changes this time).
4. Rung: snapshot-first (payload flash, snapshot `work1-pre0013.raw`, user's typed yes), then two RAM boots by the lead: `0163pA` (passlog) and `0163pB` (passlog + `sweetmetal_fddebug=sysmem`).
5. Read: faults first; then is `luma_boost` among the names, which names own the time, GMEM or sysmem in each boot.
6. Outcomes -> next phase: `luma_boost` present: one static REA question on QuartzCore (which condition adds the pass), then a skip behind a boot-arg. GMEM in pB: make sysmem real. Neither: GPU clock measurement (kernel, upstream `hakios.adreno.c` 693-782 as the model).
7. Record in `TEST_LOG.md`, `FRAME_RATE_RESEARCH.md`, `GPU_DECISION.md` (also fix its stale "430 MHz requested": the shim asks for level 6, 650 MHz); write the next prompt.

Not in this phase: any skip or mode change, GPU clock, `sweetfb_hz`, scale 2, wallpaper, the GPU address-space exhaustion (`table arena full`, its own phase), widgets, glyphs, masks.
