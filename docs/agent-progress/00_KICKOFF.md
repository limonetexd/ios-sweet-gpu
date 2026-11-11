# KICKOFF — Phase 0: audit and GPU characterization

Paste this as the first message in a fresh session at the repository root. Nothing else.

---

You are the lead engineer on this repository. Read `CLAUDE.md` first, then `docs/agent-progress/REA_SAFE_PROTOCOL.md`.

Today is Phase 0 only: understand the tree, and characterize the existing GPU implementation well enough to decide whether to repair or replace it. Do not edit functional code. Do not start a rewrite. Do not touch the device's partitions.

## Do, in this order

**1. Session state (5 minutes).**
`pwd`, `git status -sb`, `git log -5 --oneline --decorate`, `git branch -vv`, `git remote -v`, `git tag --sort=-creatordate | head`, `git submodule status`, `git stash list`.
Record uncommitted and untracked work. Do not change, stash, or clean anything.

**2. Project's own instructions.**
Read `AGENTS.md`, `README.md`, `NOTES.md`, `CLAUDE.md`, and the index of `docs/` and `.github/workflows/`. Use the `scout` subagent for the inventory; read yourself only what it flags. Note where the local tree diverges from the public upstream README (2026-11-06) — especially whether `userspace/native-metal`, the kernel patches, and the `codex/native-adreno-metal` work exist locally, at which commits.

**3. Build and test reality.**
What builds, on which host, with which toolchain, how long, producing which artifact. How it reaches the device. How logs are read. Confirm the documented commands exist; do not run device steps yet.
If a build is needed to answer a question, run the smallest one and record the exact command.

**4. Device facts (read-only).**
Confirm variant and codename from repository documentation. If a device is already in fastboot mode, `fastboot getvar product`, `variant`, and `secure` are allowed — never `getvar all`, which prints the serial. Do not reboot the phone into fastboot to do this; ask first. No flashing, no booting.

**5. Feature matrix v0.**
Build `FEATURE_MATRIX.md` from repository evidence and logs, not from claims. Use the labels in `CLAUDE.md`. Where there is no log or test, write `not-tested`. Do not mark anything `verified-working` from a README.

**6. GPU characterization — the point of this phase.**
Map the current implementation as it actually exists locally:

- files, modules, and entry points;
- kernel interface and userspace runtime boundary;
- shader path end to end, and which stage is real versus assumed;
- buffer, synchronization, and presentation path;
- what renders correctly today, and what visibly fails.

Then answer, with evidence, where frame time goes. Use, in order: existing measurements and logs in the repo; the device's own instrumentation if already present; and only then a **measurement-only** patch — no behavior change, separate commit, revertible, behind a flag. Propose that patch and stop for approval before writing it. Do not optimize anything in this phase.

Classify the current pain as one or more of: correctness, CPU encoding, GPU execution, synchronization or fences, memory or bandwidth, presentation or compositing. Attach a number or a log line to each claim.

**7. Decision memo.** Write `docs/agent-progress/GPU_DECISION.md`, one page maximum:

- the current path in ten lines;
- evidence table: claim | source | confidence;
- bottlenecks ranked, each with evidence;
- recommendation `fix-in-place` or `isolate-and-replace`, citing R1/R2/R3 from `CLAUDE.md`;
- what evidence would change the recommendation;
- three smallest next tasks, each independently testable.

**8. State and handoff.**
Create or update `PROJECT_STATE.md`, `FEATURE_MATRIX.md`, `RESEARCH_LEDGER.md`, `DECISIONS.md`, `TEST_LOG.md`. Then write `docs/agent-progress/NEXT_PROMPT.md`: a self-contained Phase 1 prompt, under 40 lines, that names the decision, the exact files, the acceptance test, and the stop condition.
Follow the handoff format in `CLAUDE.md`. Stop.

## Boundaries

- No code changes except a measurement-only patch, and only after approval.
- No device writes, no flashing, no partition operations.
- No REA calls yet. If a binary question appears, propose the single artifact and the single question first.
- No rewrite, no "clean slate", no deleting the existing GPU path.
- If a question cannot be answered in about twenty minutes of tool use, write it as an open question instead of guessing.

## Report back

Twenty lines maximum:

1. current revision and branch, and whether the tree matches public upstream;
2. what the tree can actually do today, and at what evidence level;
3. what the GPU path is, in one sentence per layer;
4. where frame time goes, with the numbers you have and the ones you are missing;
5. fix-in-place or isolate-and-replace, and the single strongest reason;
6. the one decision you need from me next.
