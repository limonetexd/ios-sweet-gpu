> State 2026-11-12 (device unless noted):
> - Phone root = `work1.raw` + payload 0001-0010. Rollback images in `~/Developer/ios-sweet-work/root/`: `work1-pre0010.raw` (0001-0009), `work1-pre0008.raw`. Phone left in fastboot; no daemon or boot test running.
> - 0010 scissor: `partially-working` (0161sA/sB, one boot each). Self-test 16 of 20. Kernel 0161 stays in every image; after any boot, `rg 'SMMU gfsr|fault address' logs/xnu-TAG.txt` first.
> - Frame time measured (host, 3 existing logs, `GPU_DECISION.md` "Metal frame time"): about 100 submissions per swap, 3-4 swaps/s, each submission about 0.9 ms of kernel cache cleaning (one drawable, about 11 MB). Cause: `finish_or_say_why` after every draw and clear in `air_metal.c` (7364, 6846). Verdict: fix in place, no R1-R3.
> - Builds: `bash tools/metal-build.sh ios|driver|test|payload` (tree `~/Developer/ios-sweet-work/metal-build/donor`, holds 0001-0010). Images need `PATH=$HOME/Developer/ios-sweet-work/bin:$PATH` and `RAMDISK MATCH`. The user runs `tools/metal-flash-test.sh` with `!`; the agent runs `tools/sweet-boot-test.sh`.
> - Budget: Fable weekly allowance used up until Nov 15 19:00 Europe/Madrid; check the meter first.

# Phase: patch 0011, one wait per command buffer (host first)

Read `CLAUDE.md`, `GPU_DECISION.md` "Metal frame time", `METAL_FINDINGS.md` section 10 item 6. Plan in ten lines, wait for go-ahead. Writer: `opus-impl` (library + plug-in = one subsystem, one writer); review: `reviewer`.

Spec 0011 (`userland/metal/0011-one-wait-per-commit.patch`):
1. Library (`tools/mesa/air/air_metal.c`, `air_metal.h`): add `int rwa_set_deferred_wait(struct rwa_device *, bool)`. When it is on, `rwa_render_draw` and the clear path skip `finish_or_say_why` (no flush, no wait). Dispatch still waits. Default off, so existing callers (`picture_host.c`, `air_metal_test.c`) are unchanged.
2. Plug-in (`userland/src/redwoodmetal.m`): `dlsym` the call (absent means the old path). In `-commit`, inside the 0009 lock and before `done:`, call `mesa.finish` once if any draw or clear ran. A failure there sets `_status = RW_CB_ERROR` and `_error` with its `why`. A dispatch in the same command buffer stays as it is, since it flushes and waits for everything queued before it. `_work` is still released after `done:` (0007 order kept).
3. Boot-arg `sweetmetal_drawwait=1` keeps the per-draw wait; one log line per process saying which mode is on (as 0009 and 0010 do).
4. Host test (softpipe, `air_metal_test.c`): with deferred waits, 64 draws to one target plus a draw that samples a texture rendered earlier in the same batch, then one `rwa_finish`. The pixels must equal the per-draw-wait run.
5. Self-test item 21 (`metaltest`): one command buffer, 64 quads, check pixels; print the commit time in both modes.
6. Device A/B after host pass and review (snapshot-first: `userdata` flash, snapshot `work1-pre0011.raw`): 0161wA (new) and 0161wB (`sweetmetal_drawwait=1`), same 420 s use. Compare subs/swap, swaps/s, cache CPU s, late swaps, SMMU lines. One boot each is not a frame rate.

Risk to watch: more draws per batch moves freedreno from sysmem to GMEM tiling (a full-screen load and store once per flush); item 1b (SMMU fault) could show up differently. Not in this phase: kernel `GPU_PUSH_AGAIN_MS` policy (the second candidate, after 0011 is measured), widgets, Control Centre, masks, battery icon.
