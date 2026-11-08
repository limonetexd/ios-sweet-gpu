# Phase M2 — Metal: first picture

Read `CLAUDE.md`, `PROJECT_STATE.md`, `TEST_LOG.md` (Metal on device). Metal is the primary path. Reply style: caveman lite. `fastboot boot`, `userdata` flash (user's yes given), REA under protocol, and GitHub CI are allowed. Do not use any password the user pasted.

State: `logs/xnu-0160m4.txt`: backboardd runs on Metal without crashing, 5 presents, then stalls, black screen.

1. Symbolise the `SMP backboardd` stacks in that log; find what it waits on.
2. Handle pixel formats 550 and 554 (XR), or stop CoreAnimation asking for them. REA on QuartzCore is allowed for this one question.
3. Remove the temporary DBG code in the work-dir donor (`redwoodmetal.m`).
4. Boot: `tools/metal-flash-test.sh ~/Developer/ios-sweet-work/root/gpu3.raw shim/out/shim-boot-0160m1.img TAG 330`. Shim tools: `PATH=~/Developer/ios-sweet-work/bin:$PATH`.
5. Have `reviewer` read `userland/metal/0001-air-gaps.patch` (not yet reviewed).

Stop at first picture or at 70% context. Record in `TEST_LOG.md`.
