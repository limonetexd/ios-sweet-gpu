> State 2026-11-13 (device unless noted):
> - Phone root = `work1.raw` + payload 0001-0011 (library 3560a9da..., `RedwoodMetal` 62645657..., `metaltest` 142d6a49...). Phone being returned to fastboot by the user; no daemon or boot test running. Snapshots in `~/Developer/ios-sweet-work/root/`: `work1-pre0011.raw` (0001-0010), `work1-pre0010.raw`, `work1-pre0008.raw`.
> - 0011 (one GPU wait per command buffer): `partially-working`, 0161wA2, one boot. Subs/swap 98 -> 7.3, kernel cache cost 32.7 s/183 s -> 1.9 s/76 s, max 15 swaps/s; self-test 17 of 21, item 21 PASS. User: no better performance by eye; widgets and Control Centre still broken. Submit-to-done is now about 80 ms per submission (1310 of 1431 over 4 ms). Old path: `sweetmetal_drawwait=1` (image `shim/out/shim-boot-0161wB.img`, never booted).
> - Tools: `python3 -I tools/sweet-subs-per-swap.py logs/xnu-TAG.txt` and `tools/sweet-fps-summary.py`. After any boot, `rg 'SMMU gfsr|fault address|THE GPU DID NOT FINISH' logs/xnu-TAG.txt` first.
> - Builds: `bash tools/metal-build.sh ios`, `driver`, `test`, `payload`, in that order (`driver` empties `obj/`). Lesson from 0161wA: softpipe runs work at flush, so it cannot catch a lifetime bug in a deferred batch. Read freedreno's reference rules before changing what a batch holds.
> - Budget: Fable weekly allowance used up until Nov 15 19:00 Europe/Madrid; check the meter first.

# Phase: where the 80 ms per command buffer goes (measure before changing)

Read `CLAUDE.md`, the last two sections of `TEST_LOG.md`, and `GPU_DECISION.md` "Metal frame time". Plan in ten lines, wait for go-ahead.

1. Host, existing logs: the `0161wA` trace had `fd_gmem_render_tiles`, so batches now run tiled. Read (do not change) freedreno's sysmem/GMEM choice in Mesa 25.0.7 (`freedreno_gmem.c`, the `FD_MESA_DEBUG` flags `sysmem` and `gmem`), the bin count for a 1125x2436 BGRA target on the A618 GMEM size, and what each bin restores and resolves.
2. Host: does the library rebind the framebuffer per draw (`bind_pass_framebuffer` / `release_pass_framebuffer` with an empty framebuffer between draws), and does that cost anything inside one freedreno batch?
3. Kernel log: is the running GPU clock logged? If not, it is the missing measurement (read-only).
4. Output: one measurement boot, or one A/B pair, with a boot-arg that only selects an existing Mesa mode (for example `FD_MESA_DEBUG=sysmem` set by the plug-in before the device opens). No register writes, no new packets. Spec only until the user approves.
5. Record in `TEST_LOG.md` (host fidelity), `METAL_FINDINGS.md` 10 item 6, and `GPU_DECISION.md`; write the next prompt.

Not in this phase: widgets (check the `0xDEAD10CC` WidgetExtension kills first), Control Centre glyphs, masks, battery icon, brightness, Wi-Fi.
