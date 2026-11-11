> **State 2026-11-11: GL home screen reached on the phone (0160s2). Root = gpu3 + sweet-root-fixes default steps minus the migrate sentinel. First boot after a flash needs about 18-30 min of black screen while lsd seeds the LaunchServices database; do not reflash or reboot early. The migrate sentinel must stay absent (migration never reports done and repeats every boot). Next: confirm a quick second boot (0160w1), then Stage B: Metal in app processes on this same root.**

# Phase Stage A: known-good GL baseline

Read `CLAUDE.md`, `PROJECT_STATE.md`, `DECISIONS.md` (2026-11-10 staging), and the state note above. Routing: see `docs/agent-progress/SUBAGENTS.md`; the lead plans and reviews, and delegates bulk work per that table. Do Stage A only; do not start B or C.

Stages: A) GL home screen on an explainable root; B) Metal in app processes only, backboardd stays on GL; C) backboardd on Metal last, after it passes the same tests as GL.

Tasks, in order:
1. Diagnose why SpringBoard waits in `_LSContextInitCommon` (lsd/LaunchServices) from the existing logs (`logs/xnu-0160base.txt`, `logs/xnu-0160m4.txt`); log-triage may classify, the lead judges.
2. Boot the prepared m7 image: `tools/sweet-boot-test.sh ... 0160m7 350` with `shim/out/shim-boot-0160m5.img`. Confirm the boot-arg that returns the phone to fastboot is in the payload first.
3. If still stuck, plan a fresh root from stock with a recorded change list. Building it needs the user to run sudo; ask before that.

REA is used statically, one artifact and one question per call, per `docs/agent-progress/REA_SAFE_PROTOCOL.md`. Record results in `TEST_LOG.md`. Stop at a GL home screen on a root you can explain, or at 70% context.
