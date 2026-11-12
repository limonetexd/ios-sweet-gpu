> State 2026-11-12 (device unless noted):
> - Phone root = `work1.raw` + payload 0001-0010 (flashed 2026-11-12). Rollback images in `~/Developer/ios-sweet-work/root/`: `work1-pre0010.raw` (0001-0009), `work1-pre0008.raw` (before 0008). Phone last left in fastboot; no daemon or boot test running.
> - Patch 0010 (scissor rectangle): `partially-working`, one A/B pair (0161sA on, 0161sB `sweetmetal_noscissor=1`). Green fault and app-close fault gone with it, back without it. Self-test 16 of 20 (12, 13, 18, 19 fail). Status-bar battery icon still wrong, not explained by 0010.
> - Respring on app exit: `partially-working` with 0008+0009, attribution unknown. 0008's path never reached: unproven.
> - GPU fault of 0160d9 (SMMU, FAR 0x4c43c000; `METAL_FINDINGS.md` 10 item 1b): did not recur in 0161a, 0161sA, 0161sB. Kernel 0161 (the trap, `~/Developer/ios-sweet-work/kernel-0161`) stays in every test image. After any boot, `rg 'SMMU gfsr|fault address' logs/xnu-TAG.txt` first.
> - Current test image: `shim/out/shim-boot-0161sA.img` (`sweetgpu_reboot=300`). Tag `known-good-0160vA` = 2147ca8.
> - Builds: Metal payload is local, `bash tools/metal-build.sh ios|driver|test|payload` (70 s; tree `~/Developer/ios-sweet-work/metal-build/donor` holds 0001-0010, `metal/donor` is stale). Kernel through CI (`gh workflow run xnu.yml --ref gpu`). Images need `PATH=$HOME/Developer/ios-sweet-work/bin:$PATH` and must print `RAMDISK MATCH`.
> - Boot-only tests: `bash tools/sweet-boot-test.sh IMAGE TAG 420`, run by the agent. The auto-mode permission check refuses `tools/metal-flash-test.sh`; the user runs it with `!`.
> - Leads not examined: `mobilenotes.WidgetExtension` killed 0xDEAD10CC (blank widgets candidate); AegirPoster sig 6; MapKit sig 11 at far 0x8; assetsd sig 6.
> - User order 2026-11-12: frame rate and performance most important; then widgets and Control Centre; brightness and Wi-Fi later, not now.
> - Budget: weekly Fable allowance was at 100% until Nov 15 19:00 Europe/Madrid; check the meter before starting.

# Phase: Metal frame rate, measure before changing (section 8 item 6, section 10 item 6)

Read `CLAUDE.md`, the last section of `TEST_LOG.md`, and `METAL_FINDINGS.md` section 10 item 6. Task: say where a Metal frame's time goes, with numbers, and name the one change to try first. No code change and no device step in this phase unless the user approves it after the plan. Plan in ten lines, wait for go-ahead.

1. Host, existing logs only: `python3 -I tools/sweet-fps-summary.py logs/xnu-0161sA.txt` and the same for `0161sB`, `0161a`. From 0161sA so far: 35201 timed submissions, mean submit-to-seen-done 5.5 ms, 18363 GPU waits of 0.72 ms mean. Count draws and submissions per swap, swaps per second while the user was touching, and late swaps, from the `SWEET FPS:` lines. Never state a frame rate from one trace: report it as one boot.
2. Read, do not change: where the plug-in finishes each draw (`redwoodmetal.m` in `metal-build/donor`, the finish-per-draw path) and what the library flushes per draw. One question: can the finish move from per draw to per command buffer without breaking the retain rules of patches 0005 and 0007?
3. Decide: is the cost encoding, scheduling, cache or presentation (fix in place behind a boot-arg), or architectural (R3)? Write it in `GPU_DECISION.md` terms, with the numbers.
4. Output: a spec for one patch (0011) with its boot-arg for the old path, its host test and its self-test item; or a statement of which measurement is missing and the one boot that would give it.
5. Record in `TEST_LOG.md` (host fidelity) and `METAL_FINDINGS.md`; write the next prompt.

Not in this phase: widgets (check the 0xDEAD10CC kills first), Control Centre glyphs, corner and mask textures (`MaskNode::apply`, `MaskCorners`, `fill_corner_rect` in QuartzCore, not read yet; REA protocol in `docs/agent-progress/REA_SAFE_PROTOCOL.md`), dotted blur, battery icon, brightness, Wi-Fi.
