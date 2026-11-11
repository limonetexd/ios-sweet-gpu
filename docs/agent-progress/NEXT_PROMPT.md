> State 2026-11-11 (device unless noted):
> - Metal draws the UI with `metal_profile=1` (0160mp1): lock screen, home, folders, touch; faults remain.
> - On-device self-test (`userland/metaltest`) passes 7 of 17 (0160t2).
> - Root on the phone is `work1` (seeded root + allow-list plug-in + metaltest job); do not reflash without need.
> - Boot image args: `sweetmetal=1 metal_profile=1 sweetmetal_procs=* sweetnull=backboardd,SpringBoard,metaltest`.
> - First boot after flashing the seeded root takes about 2 min, not 18.
> - Work list and findings: `docs/agent-progress/METAL_FINDINGS.md`.

# Phase: Metal driver, make the self-test pass

Read `CLAUDE.md`, `docs/agent-progress/METAL_FINDINGS.md` (sections 5 and 8) and the routing in `docs/agent-progress/SUBAGENTS.md`. The lead plans and reviews; `opus-impl` writes driver code from a written spec; `reviewer` checks each diff. One fix at a time, in work-list order, starting with the readback/clear and draw-crash failures. Each fix is proved by the `metaltest` lines in the pulled log, not by a picture. Ask before any download (Metal Toolchain), flash or sudo.

Static analysis (REA) is allowed on graphics frameworks only, per `REA_SAFE_PROTOCOL.md`. Record results in `TEST_LOG.md` and `FEATURE_MATRIX.md`. Do not start a later phase. Stop at 70% context.
