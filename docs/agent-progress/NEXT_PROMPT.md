> State 2026-11-11 (device unless noted):
> - Metal UI renders recognisably with patches 0001-0007 (0160vA, one boot); faults remain: respring on app exit, blur pattern, low frame rate.
> - Root on the phone is `work1` with that driver; do not reflash without need.
> - Boot args: `sweetmetal=1 metal_profile=1 sweetmetal_procs=* sweetnull=backboardd,SpringBoard,metaltest`.
> - Self-test (`userland/metaltest`) passes 15 of 19 (0160vA).
> - Next: work list in `docs/agent-progress/METAL_FINDINGS.md` section 10, starting with the respring. Always rebuild `ios`, `driver`, `test`, `payload` together (the driver wipes `obj/`).

# Phase: Metal UI, fix the respring on app exit

Read `CLAUDE.md`, `docs/agent-progress/METAL_FINDINGS.md` (sections 5 and 10) and the routing in `docs/agent-progress/SUBAGENTS.md`. The lead plans and reviews; `opus-impl` writes driver code from a written spec; `reviewer` checks each diff. One fix at a time, in work-list order. First task: fix the respring on app exit (backboardd crash on app exit). Each fix is proved by the `metaltest` lines in the pulled log, not by a picture. Ask before any download (Metal Toolchain), flash or sudo.

Static analysis (REA) is allowed on graphics frameworks only, per `REA_SAFE_PROTOCOL.md`. Record results in `TEST_LOG.md` and `FEATURE_MATRIX.md`. 