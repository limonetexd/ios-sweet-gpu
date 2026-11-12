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

# Phase: patch 0010, the scissor rectangle (section 10 item 3)

Read `CLAUDE.md`, `docs/agent-progress/METAL_FINDINGS.md` section 10 item 3 (photo notes and "Mask lead"), and the last section of `TEST_LOG.md`. Task: one behaviour change, the scissor rectangle, as patch `userland/metal/0010-scissor-rect.patch` against the Metal work tree (`~/Developer/ios-sweet-work/metal/donor`). Plan in ten lines, wait for go-ahead, state the rung before any device step.

Spec for `opus-impl` (one writer; it never touches the device and never commits):
- `tools/mesa/air/air_metal.h`: add to `struct rwa_draw` a field `const unsigned *scissor; /* NULL, or { x, y, width, height } in pixels, origin top-left, Metal's MTLScissorRect */`. NULL means the whole attachment, which is what every draw before this one did.
- `tools/mesa/air/air_metal.c` (viewport and rasterizer state near 6252 and 6784): when `scissor` is not NULL set the rasterizer's scissor enable and `set_scissor_states` with the rectangle cut to the attachment; a zero-area rectangle draws nothing. Get the y direction from how the library already orients the framebuffer; prove it with a test, do not assume it.
- `userland/src/redwoodmetal.m` (4403, 4760): keep the rectangle in the encoder (default: none), pass it in every `rwa_draw` until changed; `setScissorRects:count:` takes the first. A clear with a scissor set must still clear the whole attachment (Metal load actions ignore the scissor).
- Host test in `air_metal_test.c`: a full-attachment quad with a scissor in one corner, off-centre in both axes, checked pixel by pixel inside and outside; one case with NULL. Add an on-device self-test case to `userland/metaltest/metaltest.m` (item 20).
- Behind a boot-arg, `sweetmetal_noscissor=1` restores today's behaviour (old path selectable).
- Plug-in and library have no size handshake (item 7): build and flash both together.

Then: `reviewer` on the diff; host tests; build; state the rung (`snapshot-first`: the payload goes into `userdata`, rollback image `work1-pre0008.raw` exists; the user runs `tools/metal-flash-test.sh` with `!`); one boot with kernel 0161, A/B against `sweetmetal_noscissor=1`. The user checks by eye: Settings > Battery switch, status-bar battery, the app-switcher card (p5, p6-p9). After the boot, `rg 'SMMU gfsr|fault address' logs/xnu-TAG.txt` first; if a `fault address` report appears, stop and record it under item 1b. Record in `TEST_LOG.md`.

Not in this phase: corner and mask textures (`MaskNode::apply`, `MaskCorners`, `fill_corner_rect` in QuartzCore, not read yet), the dot pattern, Control Centre glyphs, blank widgets (check the WidgetExtension 0xDEAD10CC kills first), dashed outlines.
