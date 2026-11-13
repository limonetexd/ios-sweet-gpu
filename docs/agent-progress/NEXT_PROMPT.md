> State 2026-11-13 evening (host unless noted):
> - Phone root (device) = `work1.raw` + payload 0001-0011 (library 3560a9da..., `RedwoodMetal` 62645657..., `metaltest` 142d6a49...). Phone in fastboot (user); nothing flashed or booted for 0012 yet.
> - 0012 built, `not-tested`: `metal-build/pay/` = library 1d4c1505... (clean rebuild, source unchanged, hash changed), `RedwoodMetal` 3d35bc77..., `metaltest` 142d6a49.... Patch `userland/metal/0012-fddebug-bootarg.patch`, `reviewer` ACCEPT.
> - Images: `shim/out/shim-boot-0162sA.img` 804f083d... (control, 0161wA args), `shim-boot-0162sB.img` 4b75d384... (plus `sweetmetal_fddebug=sysmem`). Both carry `sweetgpu_reboot=300`.
> - Trap: image builds need `PATH=~/Developer/ios-sweet-work/bin:$PATH` or the script silently copies the previous image (check `RAMDISK MATCH`).
> - Tools: `python3 -I tools/sweet-subs-per-swap.py logs/xnu-TAG.txt`, `tools/sweet-fps-summary.py`. After any boot, `rg 'SMMU gfsr|fault address|THE GPU DID NOT FINISH' logs/xnu-TAG.txt` first.
> - Budget: Fable weekly allowance; check the meter first. Delegate typing to opus/sonnet.

# Phase: 0012 on the device, control 0162sA then sysmem 0162sB (the user flashes and boots)

Read `CLAUDE.md` and the last section of `TEST_LOG.md`. Host work is done; this phase is the device half of the 0012 spec.

1. Rung: snapshot-first. User: `cp ~/Developer/ios-sweet-work/root/work1.raw ~/Developer/ios-sweet-work/root/work1-pre0012.raw`, then `tools/metal-flash-test.sh ~/Developer/ios-sweet-work/root/work1.raw shim/out/shim-boot-0162sA.img 0162sA 420` (flashes `userdata` with the 0012 payload, boots the control). Verify the image hashes above first.
2. Second boot, no flash (`fastboot boot shim/out/shim-boot-0162sB.img`, RAM only) and the log pull; check how `metal-flash-test.sh` pulls the log and reuse that part only.
3. Read each log in this order: faults (`SMMU gfsr`, `fault address`, `THE GPU DID NOT FINISH`), backboardd crashes, self-test count (17 of 21 expected), `FD_MESA_DEBUG: sysmem (boot-arg sweetmetal_fddebug)` present in sB and absent in sA, then `the GPU worked` per interval and swaps/s, sB against sA (0161wA2 as a second reference only: different library hash). Sysmem writes the IOSurface directly, so a fault in sB is a real result: stop and record. A fault in sA means the rebuilt library differs: stop, restore `work1-pre0012.raw`.
4. Outcomes: sysmem clearly faster (steady state well under 19 ms) -> next phase makes the choice per pass, behind the flag. No change -> tiling is not the cost; next phase is the GPU clock readback (kernel, read-only register reads, its own spec). Slower or faulting -> record, keep GMEM.
5. Optional third boot only with the user's approval: `sweetmetal_fddebug=nobin`.
6. Record in `TEST_LOG.md`, `METAL_FINDINGS.md` 10 item 6, `GPU_DECISION.md`; one boot each is `partially-working` at most; write the next prompt.

Not in this phase: GPU clock changes, widgets (check the `0xDEAD10CC` WidgetExtension kills first), Control Centre glyphs, masks, battery icon, brightness, Wi-Fi, finding why the library hash is not reproducible (worth its own short host task).
