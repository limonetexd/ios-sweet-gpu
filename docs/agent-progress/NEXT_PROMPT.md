> State 2026-11-12 (device unless noted):
> - Respring on app exit: `partially-working` with patches 0008+0009 together, one boot, 0160d9. Attribution between them unknown; no A/B against `sweetmetal_nolock=1`.
> - New fault in 0160d9: GPU SMMU fault (FAR 0x4c43c000), GPU never answers again, 102 draw timeouts, then backboardd sig 11 in `fd_bo_heap_alloc`. `METAL_FINDINGS.md` section 10 item 1b.
> - Patch 0008 (depth store discarded instead of refused) is on the phone but its path was never reached: unproven.
> - Phone root = `work1.raw` + payload 0001-0009. Rollback image `~/Developer/ios-sweet-work/root/work1-pre0008.raw` (before 0008).
> - Patches 0008 and 0009 are committed on branch `gpu` (cf0a53b). Tag `known-good-0160vA` = 2147ca8.
> - Self-test 15 of 19. Test boot image `shim/out/shim-boot-0160vA.img` (`sweetgpu_reboot=300`). The auto-mode permission check refuses `tools/metal-flash-test.sh`; the user runs it with `!`.
> - Patch 0161 (fault names its buffer, logging only): committed 5f6ec1f in `xnu/patches/`, reviewed ACCEPT, CI kernel built (`~/Developer/ios-sweet-work/kernel-0161`), image `shim/out/shim-boot-0161a.img` (SHA256 e2f28ce9..., same boot-args as 0160vA). `not-tested` on the device. The log read of 0160d9 is done; do not repeat it.
> - Next single unit: `bash tools/sweet-boot-test.sh shim/out/shim-boot-0161a.img 0161a 420` (RAM boot, no flash, reversible), user opens and exits apps; then `log-triage` on `logs/xnu-0161a.txt` for `SWEET GPU: fault address:` lines. No fault in one boot proves nothing; repeat.
> - Kernel builds go through GitHub CI (user, 2026-11-12). Image builds need `PATH=$HOME/Developer/ios-sweet-work/bin:$PATH` and must print `RAMDISK MATCH` (`TEST_LOG.md`).

# Phase: Metal UI, GPU fault after app use (item 1b)

Read `CLAUDE.md`, `docs/agent-progress/METAL_FINDINGS.md` section 10 and the last section of `TEST_LOG.md`. Only task: find what the GPU touched at FAR 0x4c43c000 in `logs/xnu-0160d9.txt`. Delegate the log to `log-triage`: every line naming that address range, buffer/IOSurface create and free lines in the 300 lines before line 5190, and the `zombies` count over time. Then read the kernel-side buffer free path and the plug-in's release-at-commit path (0005/0007) for a buffer freed while a submission still names it. Plan in ten lines and state the rung before any device step. Do not start the visual faults (blank widgets, Control Centre glyphs, dashed lines on rounded shapes, lag); they are the phase after, and REA on QuartzCore (graphics only, per `REA_SAFE_PROTOCOL.md`) is allowed there.
