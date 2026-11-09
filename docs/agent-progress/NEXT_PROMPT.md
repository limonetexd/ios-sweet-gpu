> **State 2026-11-09, read this first.** Metal is not the blocker right now. Plain GL (`logs/xnu-0160base.txt`) and Metal both stop with SpringBoard t0 waiting in `_LSContextInitCommon` (LaunchServices), so the gpu3 root has its own fault; old roots reached UI at 65 s. Formats 550/554 look like probes. Last flash (0160m7, NOT booted): gpu3.raw with `*.csstore*` removed and the `org.ios-sweet.wland` launchd job removed; originals in `~/Developer/ios-sweet-work/root/saved/`. Next: boot `shim/out/shim-boot-0160m5.img` with `tools/sweet-boot-test.sh ... 0160m7 350`. If still stuck, rebuild a fresh root (needs the user to run sudo).

# Phase M2 — Metal: first picture

Read `CLAUDE.md`, `PROJECT_STATE.md`, `TEST_LOG.md` (Metal on device). Metal is the primary path. Reply style: caveman lite. `fastboot boot`, `userdata` flash (user's yes given), REA under protocol, and GitHub CI are allowed. Do not use any password the user pasted.

State: `logs/xnu-0160m4.txt`: backboardd runs on Metal without crashing, 5 presents, then stalls, black screen.

1. Symbolise the `SMP backboardd` stacks in that log; find what it waits on.
2. Handle pixel formats 550 and 554 (XR), or stop CoreAnimation asking for them. REA on QuartzCore is allowed for this one question.
3. Remove the temporary DBG code in the work-dir donor (`redwoodmetal.m`).
4. Boot: `tools/metal-flash-test.sh ~/Developer/ios-sweet-work/root/gpu3.raw shim/out/shim-boot-0160m1.img TAG 330`. Shim tools: `PATH=~/Developer/ios-sweet-work/bin:$PATH`.
5. Have `reviewer` read `userland/metal/0001-air-gaps.patch` (not yet reviewed).

Stop at first picture or at 70% context. Record in `TEST_LOG.md`.
