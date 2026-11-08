# Project state — 2026-11-08

**Revision:** branch `gpu`; see `git log` for the commit holding these records. Local only, nothing pushed. Untracked and left alone: `.claude/`, `CLAUDE.md`, `SUBAGENTS.md`, and the kickoff, protocol and subagent files in this directory.

**Phase:** 0, 1, 1b done. Metal viability passed at host fidelity 2026-11-08 (user chose Metal over patch 0160). Next phase M1 not started. `fix-in-place` still governs GL, which stays the default. No kernel or device changes.

## What works, at what evidence level

Nothing is `verified-working`. Full table: `FEATURE_MATRIX.md`.

- `partially-working` (real device, `NOTES.md` only): boot to SpringBoard, UFS/HFSX root, CPU-copy display, touch, CoreAnimation on the A618 via Mesa GL, 512 MiB GPU VA.
- `experimental`: Wi-Fi (rungs 1–2 passed; rung 3 result unrecorded), battery.
- `not-working`: sustained 60 fps (best no-idle run 36 swaps/s; swipe runs are bursts with no per-frame data), 120 Hz, Metal (absent here), wallpaper, automated screenshots, blur-dismiss stability.
- Host: `check-patch.py` 144/144; `validate-repo.py` fails on known numbering.

## Environment gaps

- `logs/` recovered 2026-11-08 (gitignored); `reports/` absent. Metal work tree, IPSW and shaders are outside the repository.
- Missing here: `aarch64-linux-gnu-gcc`, `mkbootimg`, `qemu-system-aarch64`, `img2simg`, `ipsw`, `~/cxnu`.
- HEAD CI run 42508457273 was still in progress when checked.

## Top three next tasks

From `GPU_DECISION.md`:

1. M1: reproducible Metal build script in this repository, driven from the pinned donor.
2. M1: close the shader gaps (2 QuartzCore pointer stores, 2 VideoToolbox classes).
3. M1: boot-arg-gated kernel patch publishing the two Metal discovery properties.

## Handoff

- **Changed:** created `FEATURE_MATRIX`, `GPU_DECISION`, `RESEARCH_LEDGER`, `DECISIONS`, `TEST_LOG`, `PROJECT_STATE`, `NEXT_PROMPT` in this directory. No code, no git writes.
- **Phase 1/1b:** `tools/sweet-fps-summary.py` parses 0139 lines, selftest passes, byte-identical on real pre-0139 logs. `analysis/gpu_windows.py` added. Results in `TEST_LOG.md`.
- **Finding:** the 0139 "worked" figure is latency, not GPU busy. Ring occupied 6–21 ms per swap at native; GPU unfinished on 19–48 % of native ticks with a new frame. Two Phase 0 readings corrected in `GPU_DECISION.md`.
- **Verified (host/CI/read-only device):** git state, upstream divergence, CI status, patch format check, phone is `sweet` / `SM7 UFS` / secure.
- **Verified by reading source:** the GPU path is GLES over Mesa freedreno, the msm-shaped kernel interface, CPU-copy present.
- **Not verified:** GPU execution per frame; running GPU clock (430 MHz requested); per-frame intervals; bandwidth; time before the first draw; Wi-Fi rung 3.
- **Risk:** donor license unresolved (`ios-topaz` none detected, `hackios` NOASSERTION). 0143r, the only no-idle run, has 539 VA errors. `tools/xnu-tree.sh:44-45` runs `git reset --hard` and `clean -fdx` in its `XNU_TREE` target (default `~/cxnu`), so never point it at this repository. `CLAUDE.md` names the wrong upstream for this clone. `NOTES.md` handoff not updated.
- **Next:** user starts M1. Prompt: `NEXT_PROMPT.md`.
