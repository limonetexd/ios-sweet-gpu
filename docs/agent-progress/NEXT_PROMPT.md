> State 2026-11-13 late:
> - Phone (device): root = `work1.raw` + payload 0001-0013 (library a9e8c642..., `RedwoodMetal` 6922f55c..., `metaltest` 142d6a49...), in fastboot. Snapshots `work1-pre0013.raw` (0001-0012), `work1-pre0012.raw`.
> - 0013 booted three times (0163pA default, 0163pB sysmem, 0164z2 750x1624), all with `sweetgpu_swipe=90`: 58 / 59 / 43 ms per command buffer of about 97 draws; the kernel waits on the GPU for 17 / 16 / 6 % of wall time. Read `FRAME_RATE_RESEARCH.md` section 9 first.
> - Patch 0014 (sampling profiler, plug-in only) was specified and handed to `opus-impl` on 2026-11-13; check `userland/metal/0014-prof.patch` and `TEST_LOG.md` for how far it got.
> - The user pre-authorised flashes and RAM boots for the 2026-11-13 session only. A new session needs its own typed yes for a flash.
> - Traps: image builds need `PATH=~/Developer/ios-sweet-work/bin:$PATH` (check `RAMDISK MATCH`); a clean `ios` rebuild changes the library hash (0014 needs only `driver` and `payload`); never run `metal-flash-test.sh` in two tabs; about 29 GiB free and a flash needs 12.
> - Tools: `tools/sweet-passlog-summary.py LOG`, `tools/sweet-subs-per-swap.py LOG`.

# Phase: where the 40 ms before the wait goes (patch 0014, diagnostic only)

Read `CLAUDE.md`, `FRAME_RATE_RESEARCH.md` section 9 and the last three sections of `TEST_LOG.md`. State the plan in ten lines and wait for the go-ahead.

1. Finish 0014 if it is not on the phone: `reviewer` on the diff (the suspend window must take no lock and allocate nothing), `tools/metal-build.sh driver` and `payload` (library hash must stay a9e8c642...), snapshot `work1-pre0014.raw`, flash, one boot `0165fA` with `sweetmetal_passlog=1 sweetmetal_prof=1 sweetgpu_swipe=90`.
2. Symbolise the `prof:` offsets on the host against `metal-build/ios/build/src/gallium/drivers/freedreno/libredwoodair.dylib` and `metal-build/obj/RedwoodMetal` (`atos -o FILE -l BASE ADDR`); shared-cache leaves come with the nearest exported name.
3. Read: on a processor or blocked (cpu against wall in the passlog header, running against waiting in the prof header); the top ten of `ours` and `api`.
4. One fix for the top entry, behind a boot-arg, its own patch and boot. Then repeat from 3.

Not in this phase: GPU clock, `sweetfb_hz`, wallpaper, the GPU address-space exhaustion, widgets, glyphs, masks.
