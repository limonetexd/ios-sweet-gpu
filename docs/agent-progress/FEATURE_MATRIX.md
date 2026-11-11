# Feature matrix v0 — 2026-11-08, tree `c5d9aca` (branch `gpu` = `main` = `origin/main`)

Labels from `CLAUDE.md`. **Nothing is `verified-working`**: no feature here has a cold + warm + stress pass recorded in `TEST_LOG.md`.

Evidence rule for this version: rows were written before `logs/` was recovered on 2026-11-08; only the 60 fps row has been re-read against it, and `reports/` is still absent. `NOTES:n` is a dated observation in `NOTES.md` that names a log file; the log itself could not be re-read. Such rows are capped at `partially-working`. A README sentence alone is `not-tested`.

Fidelity is the real device unless stated. Commit = the kernel/image the observation was made on.

| Feature | Status | Evidence | Commit |
| --- | --- | --- | --- |
| Boot path: ABL → `fastboot boot` shim → XNU → SpringBoard | partially-working | NOTES:34-40 (image 0156r, ring `logs/xnu-0156r-rung1.txt`, not local) | kernel `eaf1a58` |
| Kernel CI build | partially-working | `gh run list` this session: run 42407117041 success; run 42508457273 for HEAD still in progress. Host/CI fidelity | `e5a0e26` |
| Patch format guard | partially-working | this session: `tools/check-patch.py` exit 0 on 144/144 `.patch` files. Host | `c5d9aca` |
| Repo integrity script | not-working | this session: `tools/validate-repo.py` reports FAILED (numbering gaps, `0097c` name, `0147` header); python/shell syntax checks pass. Host | `c5d9aca` |
| Local builds on this Mac | blocked | `aarch64-linux-gnu-gcc`, `mkbootimg`, `qemu-system-aarch64`, `img2simg`, `ipsw` missing; `tools/xnu-tree.sh` is WSL-only and `~/cxnu` absent | n/a |
| QEMU smoke | not-tested | no QEMU on this host; `docs/QEMU_TESTING.md` unexercised this session | n/a |
| CPU: 8 cores (`cpus=8`), fixed clocks gold idx 10 / silver idx 8 | partially-working | `tools/sweet-gpu-image.sh` boot-args; NOTES:199, NOTES:980. README's "6 cores" is stale | 0143 |
| CPU DVFS / idle states | not-working | roadmap D4: clocks fixed, nothing scales with load | n/a |
| UFS driver + HFSX root, read/write | partially-working | NOTES:91-94 (gpu3 flash 331 s, sha `1d7334c5…`), persistent ring written on every run | 0159 |
| Kernel log ring pull | partially-working | NOTES:536 (`sweet-pull-ring.ps1`), tool present; Windows/WSL oriented | n/a |
| Calendar clock (sweetepoch) | partially-working | NOTES:55-61, launchd logs 2026-11-07 | `e5a0e26` |
| Display: IOMFB/AppleCLCD, CPU copy to ABL framebuffer | partially-working | NOTES:164 `modes 1125x2436@60`; present 3.37 ms NOTES:190 | 0144 |
| MDP page flip / direct scanout | not-tested | roadmap D1, research only | n/a |
| Touch (GT9896) | partially-working | NOTES:39 "touch alive", 0156r | `eaf1a58` |
| Hardware buttons | not-tested | README claim only; no log located this session | n/a |
| Home gesture / leaving an app | not-tested | README says it does not work; no later log located | n/a |
| GPU power, GMU, SMMU, CP handoff to XNU | partially-working | literal ring lines quoted at `notes/agents/xnu-gpu-kernel.md:470-477` (`0xbabeface`, IB ran, fence 1). Boot-time selftest only | 0105 |
| CoreAnimation composited on A618 via GL/Mesa | partially-working | NOTES:143-147 (0146r: 420 s, 0 freezes, 0 panics, 0 refusals) | `bcbf363` |
| 512 MiB GPU VA window | partially-working | NOTES:144; before it 539 VA errors in 0143r, NOTES:209 | `bcbf363` |
| 60 fps sustained, frame-paced | not-working | Best no-idle run 36.0 swaps/s (0143r, 539 VA errors); swipe runs are bursts, so their 23–34 swaps/s is not a frame-rate limit. No per-frame data. `TEST_LOG.md` Phase 1b | 0143–0159 |
| 120 Hz mode | not-working | `sweetfb_rate=120` no better than 60 (25.4 vs 26.4), NOTES:371 | 0122 |
| Metal | not-tested | No device run here. Host only: donor driver cross-builds, 135/141 QuartzCore shaders compile for A618. `TEST_LOG.md` | not in tree |
| Metal: SpringBoard with Metal device | not-working | TEST_LOG 0160mh1: aborts, MPSDevice refused | this commit |
| Automated image correctness (`sweetshot`) | not-working | PNGs mostly black, ring truncates blobs, NOTES:204 | 0143 |
| Visual correctness of UI | partially-working | user's eyes only: "looks good" NOTES:207, "still lags/glitches" NOTES:448. No reference image | 0143 |
| GL home screen (SpringBoard, lock screen, Control Centre, Settings, touch) | partially-working | TEST_LOG 0160s2 and 0160w1, real device, two boots, laggy | this commit |
| Blur-dismiss stability (App Library / Control Center) | not-working | intermittent freeze NOTES:535,802; roadmap B11 still TODO | 0101–0108 |
| Long soak | not-tested | roadmap B12 TODO; longest run recorded 420–632 s | n/a |
| Wallpaper / PosterBoard | not-working | NOTES:111-113,997; 0157 AMFI fix and gpu3 root not yet observed to fix it | 0159 |
| Wi-Fi WCN3990 | experimental | rungs 1–2 passed NOTES:34-61; rung 3 on gpu3 started NOTES:91-94, **result not recorded**. Association seen only on another kernel, NOTES:913-918 | 0159 |
| Battery / fuel gauge | experimental | SDAM 58 % / 4031 mV on a different image (`notes/agents/INDEX.md:32-36`); roadmap C4 TODO | n/a |
| TSENS thermal log | partially-working | NOTES:214 (44–59.8 °C) | 0143 |
| Audio, Bluetooth, camera, sensors, GPS, cellular, SEP | not-tested | README lists them absent; deferred by `CLAUDE.md` priority order or unbuilt here | n/a |
