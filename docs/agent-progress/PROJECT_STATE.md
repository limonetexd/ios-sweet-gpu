# Project state — 2026-11-11

**Revision:** branch `gpu`; see `git log` for the commit holding these records. Local only, nothing pushed. Untracked and left alone: `.claude/`, `CLAUDE.md`, `SUBAGENTS.md`, and the kickoff, protocol and subagent files in this directory.

**Phase:** 0, 1, 1b done. Metal is the primary path (user, 2026-11-08). Metal draws the UI on the phone with `metal_profile=1` and patches 0003-0007 (0160vA: UI renders recognisably); on-device self-test 15 of 19 pass (0160vA). Details and work list: `METAL_FINDINGS.md`. `fix-in-place` still governs GL, which stays the default. No kernel or device changes.

## What works, at what evidence level

Nothing is `verified-working`. Full table: `FEATURE_MATRIX.md`.

- `partially-working` (real device, `NOTES.md` only): boot to SpringBoard, UFS/HFSX root, CPU-copy display, touch, CoreAnimation on the A618 via Mesa GL, 512 MiB GPU VA.
- `partially-working` (real device, two boots, `TEST_LOG` 0160s2, 0160w1): GL home screen (SpringBoard, lock screen, Control Centre, Settings, touch; laggy); second boot about 2 min.
- `partially-working` (real device, one boot, 0160vA): Metal UI renders recognisably (Settings, home, App Library, Control Centre). Faults: respring on app exit, blur dotted pattern, missing glyphs, low frame rate. Self-test 15 of 19 (0160vA).
- `experimental`: Wi-Fi (rungs 1–2 passed; rung 3 result unrecorded), battery.
- `not-working`: sustained 60 fps (best no-idle run 36 swaps/s; swipe runs are bursts with no per-frame data), 120 Hz, automated screenshots, blur-dismiss stability.
- Host: `check-patch.py` 144/144; `validate-repo.py` fails on known numbering.

## Environment gaps

- `logs/` recovered 2026-11-08 (gitignored); `reports/` absent. Metal work tree, IPSW and shaders are outside the repository.
- Missing here: `aarch64-linux-gnu-gcc`, `mkbootimg`, `qemu-system-aarch64`, `img2simg`, `ipsw`, `~/cxnu`.
- HEAD CI run 42508457273 was still in progress when checked.

## Top three next tasks

Re-planned 2026-11-11 (full list: `METAL_FINDINGS.md` section 10; routing: `SUBAGENTS.md`).

1. GPU fault then compositor crash (0160d9, `METAL_FINDINGS.md` 10 item 1b). Respring on app exit is `partially-working` with patches 0008+0009 (one boot, attribution unknown).
2. (withdrawn) Blue tint of whites: camera artefact, not on the screen (user, 2026-11-11).
3. Visual faults: patch 0010 (scissor rectangle) is on the phone, `partially-working` (0161sA/0161sB, one boot each, 2026-11-12): green fault and app-close fault gone with it, back without it; self-test 16 of 20. Left: status-bar battery icon, dotted blur, Control Centre glyphs, widgets.
4. Frame rate (user priority 1, 2026-11-12): measured on host from 3 logs: about 100 submissions per swap, 0.9 ms of cache cleaning each; fix in place as patch 0011, one wait per command buffer (spec `NEXT_PROMPT.md`). Then widgets and Control Centre; brightness and Wi-Fi later.

Video (decoder, YUV compositing) needs its own audit and is `not-tested`.

## Handoff

- **Changed:** created `FEATURE_MATRIX`, `GPU_DECISION`, `RESEARCH_LEDGER`, `DECISIONS`, `TEST_LOG`, `PROJECT_STATE`, `NEXT_PROMPT` in this directory. No code, no git writes.
- **Phase 1/1b:** `tools/sweet-fps-summary.py` parses 0139 lines, selftest passes, byte-identical on real pre-0139 logs. `analysis/gpu_windows.py` added. Results in `TEST_LOG.md`.
- **Finding:** the 0139 "worked" figure is latency, not GPU busy. Ring occupied 6–21 ms per swap at native; GPU unfinished on 19–48 % of native ticks with a new frame. Two Phase 0 readings corrected in `GPU_DECISION.md`.
- **Verified (host/CI/read-only device):** git state, upstream divergence, CI status, patch format check, phone is `sweet` / `SM7 UFS` / secure.
- **Verified by reading source:** the GPU path is GLES over Mesa freedreno, the msm-shaped kernel interface, CPU-copy present.
- **Not verified:** GPU execution per frame; running GPU clock (430 MHz requested); per-frame intervals; bandwidth; time before the first draw; Wi-Fi rung 3.
- **Risk:** donor license unresolved (`ios-topaz` none detected, `hackios` NOASSERTION). 0143r, the only no-idle run, has 539 VA errors. `tools/xnu-tree.sh:44-45` runs `git reset --hard` and `clean -fdx` in its `XNU_TREE` target (default `~/cxnu`), so never point it at this repository. `CLAUDE.md` names the wrong upstream for this clone. `NOTES.md` handoff not updated.
- **Next:** user starts M1. Prompt: `NEXT_PROMPT.md`.
