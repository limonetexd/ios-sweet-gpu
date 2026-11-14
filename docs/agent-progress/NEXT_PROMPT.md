> State 2026-11-14:
> - Phone: root `work1.raw` + payload 0001-0015 (library accfbc7a..., `RedwoodMetal` e7ba170e..., `metaltest` 142d6a49...). Snapshots: `work1-pre0015.raw` (0001-0014), `work1-pre0014.raw`, `work1-pre0013.raw`. Phone in fastboot after a black 60 Hz boot (0167h60, faults).
> - Best result so far: 0015 on (0166uA) 18.7 command buffers per busy s (about 30 Hz display copy) against 11.1 with it off (0166uB). One boot each, `partially-working`.
> - Open: about 110 uploads per 5 s still take the unbounded path (variable index, `fs_and` in `air_metal_test`, bound lost in `u2u64`/`u2u32`), carrying nearly all the 31 MB copied.
> - `sweetfb_hz=60` crashes or blacks out the display at this workload (faults). Do not use it as a baseline until the faults are gone.
> - Tools: `tools/sweet-passlog-summary.py`, `tools/sweet-subs-per-swap.py`, `tools/sweet-prof-symbols.py` (needs a profiler boot).
> - Permissions: the user's flash/boot pre-authorisation covered 2026-11-13; ask again for flashes.

# Phase: investigate every route to the frame rate (research first, then one change per boot)

Read `CLAUDE.md`, `docs/agent-progress/FRAME_RATE_RESEARCH.md` sections 6-9, `HAKIOS_SEARCH_DEEPSEEK.md` (treat its web items as unverified), and the last sections of `TEST_LOG.md`. State a ten-line plan and wait for the go-ahead before any device step.

Investigate, in this order, and write findings to `docs/agent-progress/FPS_INVESTIGATION.md` (not the lead's chat):
1. The unbounded uniform uploads: why `fs_and`'s bound fails (`u2u64`/`u2u32` round trip), whether `nir_opt_algebraic` before the bound fixes it, and what the 110 per 5 s are (which shaders, which slots). Host test first, then a library change only if it passes all host cases.
2. The remaining replay-thread time: rerun the profiler (0014) on the 0015 payload; name the top `ours` and `api` entries; `drmCommandWrite` 28 % and `mach_msg2_trap` 37 % say the submit path and the wait are large. Compare with how upstream batches submissions (hakios-metal, `metal_defer`), read-only.
3. The display ceiling: why 60 Hz faults (GPU address space, `table arena full`), and what the 30 Hz copy costs; read the present path, not guess.
4. GPU clock: read-only check of the running frequency first (the shim's PLL and `gfx3d` readings); no register writes without a recovery path.
5. Pixels: 750x1624 gave 42.7 ms against 57.5 ms; check whether the display scale can be lowered for the window server without wrong output.
6. Anything else the profile or the logs point to. Rank every option by expected gain, risk and evidence.

Not in this phase: widgets, glyphs, masks, Control Centre.
