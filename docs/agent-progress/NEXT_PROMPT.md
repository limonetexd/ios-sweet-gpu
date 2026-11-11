> State 2026-11-11: GL home screen works on the phone, first boot ~18 min (lsd seeding), second boot ~2 min (0160s2, 0160w1); laggy, no second with 45+ presents. Metal on the same root (0160mh1): black screen; SpringBoard aborts in a loop because MetalPerformanceShaders refuses our device (`[MPSImageGaussianBlur initWithDevice:] Failed to get MPSDevice`); backboardd presents 3 frames then stops. Next (Stage B): 1) static REA question, one artifact: in MPSCore, what does MPSDevice require of an MTLDevice to accept it; 2) decide between satisfying that and hiding the Metal device from SpringBoard at first (per-process gate in the plug-in); 3) find why backboardd stops after 3 presents under Metal; 4) remove the DBG instrumentation (`DBG bss`, `DBG semaphore`) from the work-dir donor before the next Metal build. Root on the phone: gpu3 + sweet-root-fixes default steps minus the migrate sentinel, LaunchServices database seeded; do not reflash without need.

# Phase Stage A: known-good GL baseline

Read `CLAUDE.md`, `PROJECT_STATE.md`, `DECISIONS.md` (2026-11-10 staging), and the state note above. Routing: see `docs/agent-progress/SUBAGENTS.md`; the lead plans and reviews, and delegates bulk work per that table. Do Stage A only; do not start B or C.

Stages: A) GL home screen on an explainable root; B) Metal in app processes only, backboardd stays on GL; C) backboardd on Metal last, after it passes the same tests as GL.

Tasks, in order:
1. Diagnose why SpringBoard waits in `_LSContextInitCommon` (lsd/LaunchServices) from the existing logs (`logs/xnu-0160base.txt`, `logs/xnu-0160m4.txt`); log-triage may classify, the lead judges.
2. Boot the prepared m7 image: `tools/sweet-boot-test.sh ... 0160m7 350` with `shim/out/shim-boot-0160m5.img`. Confirm the boot-arg that returns the phone to fastboot is in the payload first.
3. If still stuck, plan a fresh root from stock with a recorded change list. Building it needs the user to run sudo; ask before that.

REA is used statically, one artifact and one question per call, per `docs/agent-progress/REA_SAFE_PROTOCOL.md`. Record results in `TEST_LOG.md`. Stop at a GL home screen on a root you can explain, or at 70% context.
