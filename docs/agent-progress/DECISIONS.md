# Decisions

decision | alternatives | why | revisit-if

| Decision | Alternatives | Why | Revisit if |
| --- | --- | --- | --- |
| **Accepted by the user (2026-11-08):** GPU path is `fix-in-place` behind build/boot flags | Isolate-and-replace; port DC28088 native Metal | R1, R2, R3 not demonstrated; measured losses are CPU-side or pacing. See `GPU_DECISION.md` | Any trigger in `GPU_DECISION.md` "What would change this" |
| Figures copied from `NOTES.md` stay medium or low confidence until the named logs are re-read | Treat them as measured | The logs are not on this Mac; several are short or unlike-for-unlike runs | `logs/` recovered and re-parsed |
| Evidence order holds: recovered logs, then existing kernel instrumentation, then a new measurement patch | Write `sweetfb_ftrace` now | Kickoff order; 0097 and 0139 already log most of it | Task 2 cannot attribute the frame interval |
| The 0139 "worked" figure is latency and is never used as GPU busy time | Treat it as busy time | `0083:500`; rate × mean exceeds wall clock | A patch changes how it is measured |
| Ring occupancy and stale ticks stand in for GPU busy until a fence-watch patch lands | Refuse to rank until then | Two separate channels agree on 0143r (49 % and 48 %) | Fence-watch numbers disagree |
| **Proposed, not accepted:** skip no-code 420 s runs and go to a read-only fence-watch patch | Run the baseline first | Existing instrumentation cannot measure GPU execution | User prefers a baseline first |
| **User chose (2026-11-08); host check passed:** pursue Metal as a second boot-arg path, GL staying the default until Metal passes the same tests. The fence-watch patch is deferred | Patch 0160 first; replace GL now | Same Mesa, kernel and CPU-copy, so no fps gain is shown; R1–R3 unshown | User chooses Metal for features, or R2 is shown |
| Metal is tracked as a separate missing feature | Treat Metal as the fix for frame rate | CA runs on GLES here; a new API does not change commit cadence | A required path is shown to need Metal |
