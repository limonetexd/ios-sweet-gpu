# ROADMAP status board (started 2026-11-07)

One line per task. Change only the Status, Updated and Evidence cells; never edit the roadmap cards for status.
Status: TODO | DOING | BLOCKED (say what blocks) | DONE | DROPPED (say why). Evidence = commit, CI run id, log file,
NOTES.md entry title. Cards: `ROADMAP-2026-11-07.md` (A), `-B-near.md`, `-C-connectivity-hardware.md`, `-D-far.md`.

## Model budget (user, 2026-11-07)

Agents use `opencode/deepseek-v4.1-flash-free` (free) by default; other free models
(`opencode/glm-5.3-flash-free`, `opencode/mimo-v2.6-flash-free`) are fine. Never
`deepseek/deepseek-v4-pro` or any paid model without the user's explicit OK for that call.
`deepseek/deepseek-flash` only when no free model fits.

## Done so far (Claude Code, 2026-11-07)

- 0138 native resolution default: patch written, applies on the full series (`tools/xnu-tree.sh`), **not pushed, not built**.
- `tools/xnu-tree.sh`, `tools/xnu-mkpatch.sh`, `tools/check-patch.py`, `tools/sweet-fps-summary.py` (tested on
  `logs/xnu-0122b.txt`, `0130r`, `0131r`; the GL medians match the reports).
- `mkadt.py --scale2`, `SWEET_SCALE=2` in `sweet-gpu-image.sh`; both ADTs dump the right canvas.

## Board

| ID | Task | Status | Updated | Evidence / blocker |
| --- | --- | --- | --- | --- |
| A0 | 0138 native default | DONE | 2026-11-07 | local commit; CI pending (A7) |
| A1 | 0139 RedwoodGPU stats fix | DONE | 2026-11-07 | commit b6e6e35; apply/check ok; tree 133 |
| A2 | 0140 diagnostics (IOSurface props, IOMFB trace) | DONE | 2026-11-07 | commit 9a73ae4; apply/check ok; tree 133 |
| A3 | 0141 sweetshot kernel screenshots | DONE | 2026-11-07 | commit d42a076; apply/check ok; tree 134 |
| A4 | `tools/sweet-shot.py` decoder | DONE | 2026-11-07 | commit 85283c3; selftest ok |
| A5 | 0142 background clean of recycled surface memory | DONE | 2026-11-07 | commit 55fdd54; apply/check ok; tree 135 |
| A6 | shim CPU max + 0143 thermal log | DONE | 2026-11-07 | part 1 SHIM_CPUMAX + image env; 0143 commit f4523e1, apply/check ok, tree 136 |
| A7 | batch gate: push, CI, 4 images, 4 tests | DONE | 2026-11-07 | CI 42374790152 success; logs xnu-0143r/rm/r2/rc0.txt; 0143r quoting bug fixed, not a hang |
| A8 | decide defaults from the A/B | DONE | 2026-11-07 | surfclean on stays default (+32 % avg); CPU max opt-in (avg -21 %, 59.8 C); 750 opt-in; NOTES entry |
| A9 | 750 vs 1125 on screenshots, ask the user (Q1) | DONE | 2026-11-07 | user says the current native boot looks good; 750 deferred to B4/B13; SWEET SHOT tails lost in the ring |
| B1 | why a new IOSurface per frame | TODO | | needs A2 logs; maybe Q2 |
| B2 | promote 0124 GPU window 512 MiB | DONE | 2026-11-07 | 0145 (commit 925197a) failed CI 42384618325; 0146 build fix (commit bcbf363) passed CI 42386148293; 0146r booted, ring logs/xnu-0146r.txt shows "SWEET GPU: VA window 512 MiB: 320 tables", 0 freezes, 0 panics |
| B3 | touch latency probe | TODO | | |
| B4 | build root gpu3 (no flash) | TODO | | Q3 for the apt package |
| B5 | SpringBoard commit rate | TODO | | |
| B6 | eagl improvements (userland) | TODO | | after B1 |
| B7 | Mesa sysmem / pass-diet A/B | TODO | | after B4 |
| B8 | sandbox ops 5/6 tokens (assetsd) | TODO | | |
| B9 | daemon hygiene | TODO | | after B10 |
| B10 | crash triage | TODO | | Q2 for symbolication |
| B11 | App Library blur freeze repro | TODO | | needs the user + A3 |
| B12 | 60-minute soak | TODO | | after A6 |
| C14 | system time not set (RTC/NTP/timed) | DOING | 2026-11-07 | 0144r: PM6150 RTC read works but returns 53802463 s = 1971-09-15 (RTC is a free-running counter, DT qcom,qpnp-rtc-write=0). 0156 sets the calendar from sweetepoch= stamped by tools/sweet-gpu-image.sh; CI 42404108358. NTP via stock timed waits for C1/C3. Ring logs/xnu-0144r.txt |
| B13 | flash gpu3 | BLOCKED | | Q4: user's explicit OK |
| B14 | wallpaper / extensions verification | TODO | | after B13 |
| C1 | promote the 8 Wi-Fi drafts + boot ladder | DOING | 2026-11-07 | 0147 regenerated (commit 1ce29b4); 0154 scope/sender fix (ec63a90); 0155 PMEM_RPMH + typed BCM/ARC lookup + rail whitelist (eaf1a58); 0156 sweetepoch clock (eaf1a58). All apply clean (xnu-tree 143 commits), check-patch ok. CI 42404108358 building. Rung 1 pending kernel; rung 2 may stall CPU |
| C2 | ADT --wlan + Wi-Fi root files | TODO | | |
| C3 | Wi-Fi bring-up verification | TODO | | after B13, C1 rung 3 |
| C4 | battery verification and polish | TODO | | |
| C5 | real panel off | TODO | | research first; user's eyes |
| C6 | thermal policy | TODO | | after A6, B12 |
| C7 | interrupt-driven touch | TODO | | after B3 |
| C8 | audio stage 1 (silent sink) | TODO | | research first |
| C9 | audio stage 2-3 (ADSP, speaker) | TODO | | research only |
| C10 | Bluetooth | TODO | | research only |
| C11 | camera / sensors / haptics / cellular reports | TODO | | 4 research agents |
| C12 | permanent boot | BLOCKED | | Q8: CLAUDE.md s7 forbids touching `boot` |
| C13 | USB debug channel | TODO | | research first |
| D1 | page flip | TODO | | research first |
| D2 | GPU blit present | TODO | | research first |
| D3 | Metal feasibility | TODO | | research only |
| D4 | CPU DVFS and idle | TODO | | research only |
| D5 | AKS / SEP stand-in | TODO | | research only |
| D6 | static wallpaper hack | TODO | | only if B14 says black |
| D7 | community release | TODO | | Q9 before the README is pushed |
