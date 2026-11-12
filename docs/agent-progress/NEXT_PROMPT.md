> State 2026-11-12 (device unless noted):
> - Phone root = `work1.raw` + payload 0001-0010; left in fastboot; no daemon or boot test running. Snapshots in `~/Developer/ios-sweet-work/root/`: `work1-pre0011.raw` (= 0001-0010, APFS clone), `work1-pre0010.raw`, `work1-pre0008.raw`.
> - Patch 0011 (one GPU wait per command buffer, `userland/metal/0011-one-wait-per-commit.patch`): `experimental`. Host softpipe PASS, built for iOS; payload ready in `~/Developer/ios-sweet-work/metal-build/pay` (`RedwoodMetal` 62645657..., `libredwoodair.dylib` 1ba7090c..., `metaltest` 142d6a49... with item 21). Old path: `sweetmetal_drawwait=1`.
> - Images built, `RAMDISK MATCH`: `shim/out/shim-boot-0161wA.img` (b4203b3a..., 0011 on) and `shim-boot-0161wB.img` (e6ab6e09..., `sweetmetal_drawwait=1`), kernel 0161, `sweetgpu_reboot=300`.
> - Baseline, one boot each (`GPU_DECISION.md` "Metal frame time"): about 100 submissions per swap, 3-4 swaps/s, 0.9 ms of cache cleaning per submission.
> - Budget: Fable weekly allowance used up until Nov 15 19:00 Europe/Madrid; check the meter first.

# Phase: 0011 on the device, A/B (one boot each)

Read `CLAUDE.md`, then the last section of `TEST_LOG.md`. Plan in ten lines, wait for go-ahead.

1. Rung snapshot-first (`userdata` flash; snapshot exists). The user runs: `! tools/metal-flash-test.sh ~/Developer/ios-sweet-work/root/work1.raw shim/out/shim-boot-0161wA.img 0161wA 420`, then uses the phone the same way as in 0161sA (home swipes, open and close Settings, Control Centre).
2. The agent runs `bash tools/sweet-boot-test.sh shim/out/shim-boot-0161wB.img 0161wB 420` (RAM boot, same root); the user uses the phone the same way.
3. After each boot, first `rg 'SMMU gfsr|fault address|THE GPU DID NOT FINISH' logs/xnu-TAG.txt`, then `rg 'GPU waits:' logs/xnu-TAG.txt` (wA: "one per command buffer", wB: "forced by boot-arg").
4. Compare with `tools/sweet-fps-summary.py` and the per-second parser (the parser is not in git; add it to `tools/` as a host tool if it is used again): subs/swap, swaps/s while active, late swaps, cache CPU s, GPU wait mean. Self-test: wA 17 of 21 expected (21 PASS, 12/13/18/19 FAIL as before); wB 21 must also PASS. Item 21's commit-to-completed time in A against B.
5. Pass means: no new fault class, subs/swap down by about 10x or more in wA, and swaps/s up. One boot each is not a frame rate; any rate is reported as one boot.
6. If wA is worse or faults: roll back is `sweetmetal_drawwait=1` (wB image) with no reflash; the root snapshot is only needed to drop 0011's files.
7. Record in `TEST_LOG.md`, `METAL_FINDINGS.md` 10 item 6, `FEATURE_MATRIX.md`; write the next prompt. The next candidate after this: the kernel's surface clean every 4 ms (`GPU_PUSH_AGAIN_MS`), measured first.

Not in this phase: widgets, Control Centre glyphs, masks, battery icon, brightness, Wi-Fi.
