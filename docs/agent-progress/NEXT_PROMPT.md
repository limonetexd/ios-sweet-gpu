> State 2026-11-12 (device unless noted):
> - Respring on app exit: `partially-working` with patches 0008+0009 together, one boot, 0160d9. Attribution between them unknown; no A/B against `sweetmetal_nolock=1`.
> - New fault in 0160d9: GPU SMMU fault (FAR 0x4c43c000), GPU never answers again, 102 draw timeouts, then backboardd sig 11 in `fd_bo_heap_alloc`. `METAL_FINDINGS.md` section 10 item 1b.
> - Patch 0008 (depth store discarded instead of refused) is on the phone but its path was never reached: unproven.
> - Phone root = `work1.raw` + payload 0001-0009. Rollback image `~/Developer/ios-sweet-work/root/work1-pre0008.raw` (before 0008).
> - Patches 0008 and 0009 are committed on branch `gpu` (cf0a53b). Tag `known-good-0160vA` = 2147ca8.
> - Self-test 15 of 19. Test boot image `shim/out/shim-boot-0160vA.img` (`sweetgpu_reboot=300`). The auto-mode permission check refuses `tools/metal-flash-test.sh`; the user runs it with `!`.
> - Patch 0161 (a GPU fault names its buffer, logging only): kernel `~/Developer/ios-sweet-work/kernel-0161`, image `shim/out/shim-boot-0161a.img`. Boots and runs (one boot, `logs/xnu-0161a.txt`); the fault did not recur, so the report is still `not-tested` and item 1b is still open. Keep kernel 0161 in every later test image: it is the trap. After any boot, `rg 'SMMU gfsr|fault address' logs/xnu-TAG.txt` first.
> - Kernel builds go through GitHub CI (`gh workflow run xnu.yml --ref gpu`). Image builds need `PATH=$HOME/Developer/ios-sweet-work/bin:$PATH` and must print `RAMDISK MATCH` (`TEST_LOG.md`). Boot-only tests: `bash tools/sweet-boot-test.sh IMAGE TAG 420`, run by the agent; the user only touches the phone.
> - Leads from 0161a, not examined: `mobilenotes.WidgetExtension` killed 0xDEAD10CC three times (suspended with locked system files) - a non-GPU candidate for blank widgets; AegirPoster sig 6; MapKit sig 11 at far 0x8.
> - Mask lead 2026-11-12 (host, reading only): CoreAnimation clips with `setScissorRect:` and the plug-in drops it (`METAL_FINDINGS.md` 10 item 3, mask lead). `experimental`: which visible faults it causes is untested. Viewport rectangle and stencil ruled out as the first suspects. `IMG_1443.mov` viewed (frames in `photos-2026-11-12/mov-frames/`).
> - Patch 0010 (scissor rectangle) 2026-11-12: written, host softpipe 5 of 5, reviewed, committed; `experimental`. Not built for iOS, not on the phone. The patched Metal tree is `~/Developer/ios-sweet-work/metal-build/donor` (already has 0010 applied); `~/Developer/ios-sweet-work/metal/donor` is stale, do not use it.
> - Budget 2026-11-12: weekly Fable allowance is at 100% until Nov 15 19:00 Europe/Madrid. Run this phase with `/model` on Sonnet or Opus; it needs no code change and no `opus-impl` spawn. Device state unchanged since 0161a: phone root is still `work1.raw` + payload 0001-0009, nothing of 0010 flashed, no daemon or boot test running, phone last left in fastboot.

# Phase: patch 0010 on the device (section 10 item 3)

Read `CLAUDE.md`, the last section of `TEST_LOG.md`, and `METAL_FINDINGS.md` section 10 item 3 (last bullet). Task: build 0010, put it on the phone, one A/B. Plan in ten lines, wait for go-ahead, state the rung before every device step. No code changes in this phase; if the build needs one, stop and report.

1. Build: read `tools/metal-build.sh` first (stages `ios`, `driver`, `test`, `payload`). `metal-build/donor` already holds 0001-0010, so the `donor` stage must not re-apply; check that before running. Plug-in and library have no size handshake (item 7): both from the same build. Confirm `obj/metaltest` has item 20.
2. Images: two test images with kernel 0161, one plain and one with `sweetmetal_noscissor=1`, both with `sweetgpu_reboot=300`; `PATH=$HOME/Developer/ios-sweet-work/bin:$PATH`, must print `RAMDISK MATCH`; verify the boot-args are in the payload.
3. Rung `snapshot-first`: the payload goes into `userdata`. Rollback images `~/Developer/ios-sweet-work/root/work1-pre0008.raw` (before 0008); decide with the user whether to snapshot the 0001-0009 state first. The user runs `tools/metal-flash-test.sh` with `!`. First boot after a flash can take 30+ min.
4. Boot A (scissor on), then boot B (`sweetmetal_noscissor=1`): `bash tools/sweet-boot-test.sh IMAGE TAG 420`. After each, `rg 'SMMU gfsr|fault address' logs/xnu-TAG.txt` first; a `fault address` report stops the phase and goes under item 1b.
5. Expected: self-test 16 of 20 in A (item 20 PASS, with its note line), item 20 FAIL in B (negative control); `scissor rectangles:` line in both logs. The user checks by eye in A and B: Settings > Battery switch, status-bar battery, the app-switcher card (p5, p6-p9).
6. Record in `TEST_LOG.md`; one boot each is `partially-working` at most.

Open from the 0010 review: no IOSurface variant of self-test 20; the boot-arg value is matched on its first character.

Not in this phase: corner and mask textures (`MaskNode::apply`, `MaskCorners`, `fill_corner_rect` in QuartzCore, not read yet), the dot pattern, Control Centre glyphs, blank widgets (check the WidgetExtension 0xDEAD10CC kills first), dashed outlines.
