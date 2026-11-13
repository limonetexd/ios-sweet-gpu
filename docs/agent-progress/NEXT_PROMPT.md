> State 2026-11-13 (device unless noted):
> - Phone root = `work1.raw` + payload 0001-0011 (library 3560a9da..., `RedwoodMetal` 62645657..., `metaltest` 142d6a49...). Phone in fastboot (user); no daemon or boot test running. Snapshots in `~/Developer/ios-sweet-work/root/`: `work1-pre0011.raw` (0001-0010), `work1-pre0010.raw`, `work1-pre0008.raw`.
> - 0011: `partially-working`, 0161wA2, one boot. Subs/swap 7.3; steady-state submit-to-done 19-41 ms per submission (the 82.6 ms mean is skewed by two early intervals).
> - Host reading 2026-11-13 (`TEST_LOG.md` last section): UI batches run GMEM, about 24 bins (4x6 of 288x416 if GMEM is 512 KiB; the size our backend reports was not found), a load and a store per bin. Per-draw framebuffer rebind does not split the batch (inferred, batch-cache lookup unread). GPU clock is not logged anywhere.
> - Tools: `python3 -I tools/sweet-subs-per-swap.py logs/xnu-TAG.txt`, `tools/sweet-fps-summary.py`. After any boot, `rg 'SMMU gfsr|fault address|THE GPU DID NOT FINISH' logs/xnu-TAG.txt` first.
> - Builds: `bash tools/metal-build.sh ios`, `driver`, `test`, `payload`, in that order (`driver` empties `obj/`).
> - Budget: Fable weekly allowance; check the meter first. Delegate typing to opus/sonnet.

# Phase: A/B boot, GMEM against sysmem (patch 0012, plug-in only)

Read `CLAUDE.md` and the last section of `TEST_LOG.md`. Go-ahead for steps 1-4 (write, review, host build, images) already given by the user on 2026-11-13; state the plan in ten lines and proceed. Stop before anything touches the phone: the user flashes and boots.

Spec (one behaviour change, one build, one boot):

1. `redwoodmetal.m`, next to `rw_wait_per_commit` (about line 1355): read boot-arg `sweetmetal_fddebug=<word[,word]>` from `kern.bootargs` once per process, before the library opens the device. If present and made only of `[a-z,]`, at most 63 characters, `setenv("FD_MESA_DEBUG", value, 1)` and `rw_print("FD_MESA_DEBUG: %s (boot-arg sweetmetal_fddebug)\n", value)`. Absent: do nothing, print nothing. No library change, no kernel change, no new packets: the flag selects code paths that exist in Mesa 25.0.7.
2. In the same patch, one log line at device open with what freedreno decided: `screen->gmemsize_bytes` and the bin layout if the library can reach them without a new entry point; otherwise leave it out and say so (do not add an interface for it in this phase).
3. Writer: the lead itself (user, 2026-11-13: "dale puedes hacerlo tu"; this phase and this patch only), or `opus-impl` if the lead prefers; `reviewer` on the diff either way. Host: build `ios`, `driver`, `test`, `payload`; host tests must still pass (softpipe ignores the flag, so they prove only that the absent-boot-arg path is unchanged).
4. Images: `0162sB` = 0161wA args + `sweetmetal_fddebug=sysmem`. Control is the existing 0161wA2 log (same library); boot a fresh control `0162sA` (no flag) only if the payload hash changes anything but the plug-in. Auto-return to fastboot must be in the boot-args (check the payload).
5. Rung: reversible (`fastboot boot`, RAM only; payload flash is snapshot-first, snapshot `work1-pre0012.raw`). The user flashes and boots.
6. Read after the boot, in this order: faults (`SMMU gfsr`, `fault address`, `THE GPU DID NOT FINISH`), backboardd crashes, self-test count (17 of 21 expected, item 21), then `the GPU worked` per interval and swaps/s against 0161wA2. Sysmem writes the IOSurface directly, so a fault here is a real result, not noise: stop and record.
7. Outcomes: sysmem clearly faster (steady state well under 19 ms) -> next phase makes the choice per pass, behind the flag. No change -> tiling is not the cost; next phase is the GPU clock readback (kernel, read-only register reads, its own spec). Slower or faulting -> record, keep GMEM.
8. Optional second boot only with the user's approval: `sweetmetal_fddebug=nobin` (GMEM without the binning pass).
9. Record in `TEST_LOG.md`, `METAL_FINDINGS.md` 10 item 6, `GPU_DECISION.md`; one boot is `partially-working` at most; write the next prompt.

Not in this phase: GPU clock changes, widgets (check the `0xDEAD10CC` WidgetExtension kills first), Control Centre glyphs, masks, battery icon, brightness, Wi-Fi.
