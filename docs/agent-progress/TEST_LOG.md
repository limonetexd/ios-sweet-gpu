# Test log

date | build | procedure | expected | actual | artifacts

Only runs performed and observed by the recording session go here. Earlier device runs live in `NOTES.md`; their logs are not on this Mac.

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-08 | `c5d9aca` (host) | `tools/check-patch.py` on each `xnu/patches/*.patch` | exit 0 | 144/144 exit 0 | none |
| 2026-11-08 | `c5d9aca` (host) | `PYTHONPYCACHEPREFIX=<scratch> python3 tools/validate-repo.py` | pass | **FAILED**: patch-number gaps, `0097c` name, `0147` header. 19 Python and 10 shell syntax checks passed | none |
| 2026-11-08 | device, already in fastboot | `fastboot getvar product`, `variant`, `secure` | sweet variant | `sweet`, `SM7 UFS`, `yes`. No boot, flash, or `getvar all` | none |
| 2026-11-08 | CI | `gh run list -R limonetexd/ios-sweet-gpu -L 6` | status of kernel builds | `e5a0e26` success (42407117041); HEAD `c5d9aca` (42508457273) in progress | GitHub |

Not run this session: any build, QEMU, or `fastboot boot`.

## Phase 1, 2026-11-08 (host fidelity; `tools/sweet-fps-summary.py` uncommitted on `c5d9aca`)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-08 | host | `python3 tools/sweet-fps-summary.py --selftest` (literal lines: whole, cut at 256 characters, cut inside a number, pre-0139 combined line) | exit 0 | `selftest ok`, exit 0 | none |
| 2026-11-08 | host | Same synthetic log without 0139 lines through the old and new tool, text and `--json`, `cmp` | byte-identical | byte-identical | none kept |
| 2026-11-08 | host | Run on `logs/xnu-0143r`, `0144r`, `0146r`, `0159r-rung2` | table of real values | `not-tested`: `logs/` is not on this Mac. No numbers exist | none |

The parser is `partially-working`: only synthetic lines copied from the patch text have been through it, never a real ring.

## Phase 1b, 2026-11-08 (host parsing of real-device rings captured 2026-11-07; tool uncommitted on `c5d9aca`)

Supersedes the `not-tested` row above: `logs/` was recovered (170 files, gitignored).

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-08 | host | `python3 tools/sweet-fps-summary.py --selftest` after renaming the labels | exit 0 | `selftest ok`, exit 0 | none |
| 2026-11-08 | host, real pre-0139 logs | `git show HEAD:tools/sweet-fps-summary.py` against the new tool on `logs/xnu-0130r.txt` and `xnu-0106r.txt`, text and `--json`, `cmp` | byte-identical | byte-identical | none kept |
| 2026-11-08 | host, real rings | Tool on the 10 logs with 0139 lines | no crash; histograms sum to the timed count | exit 0; 0 lines cut; every histogram sum equals its count | `logs/` (gitignored) |
| 2026-11-08 | host, real rings | `python3 tools/sweet-fps-summary.py logs/xnu-0143r.txt logs/xnu-0143r2.txt logs/xnu-0144r.txt logs/xnu-0146r.txt logs/xnu-0159r-rung2.txt` | table of real values | table 1 | `logs/` |
| 2026-11-08 | host, real rings | `python3 docs/agent-progress/analysis/gpu_windows.py` on the same five logs | tables of real values | tables 2 and 3 | `logs/` |

Status: parser `partially-working` (real rings parsed; run lengths and workloads are whatever the old runs had). No new device run.

**Table 1, tool output.** "Seen-done" is ring write to first look that finds the submission done: latency, not GPU busy.

| Run | Normal / active s | Swaps/s normal avg / p90 | GL p50 / p95 ms | Present ms | Seen-done mean us | % of those over 4 ms | Kernel waits (mean) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| xnu-0143r | 326 / 351 | 35.99 / 38 | 14.6 / 17.0 | 3.37 | 19163 (81546 timed) | 96.6 | 98 (4924 us) |
| xnu-0143r2 | 36 / 302 | 28.69 / 49 | 6.3 / 12.6 | 4.89 | 11340 (26658 timed) | 89.2 | 3 (1116 us) |
| xnu-0144r | 28 / 46 | 33.57 / 45 | 10.1 / 28.0 | 3.67 | 17084 (7159 timed) | 93.6 | 4 (5116 us) |
| xnu-0146r | 91 / 209 | 23.31 / 41 | 9.5 / 13.5 | 3.43 | 10422 (22730 timed) | 95.0 | 5 (2491 us) |
| xnu-0159r-rung2 | 20 / 48 | 25.05 / 39 | 9.3 / 26.9 | 3.53 | 16572 (4695 timed) | 94.7 | 1 (2800 us) |

**Tables 2 and 3, `gpu_windows.py`.** Definitions and limits are in the script's header.

| Run | Active / normal s | Swaps/s | Subs/s | Subs/swap | Late % active / normal | Stale % | Ring occupied, active (95% CI) | Upper | ms occupied per swap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| xnu-0143r | 351 / 326 | 35.1 | 232.2 | 6.62 | 98.4 / 98.9 | 48.4 | 172/351 = 49% (44-54); normal 164/326 | 72% | 14.0-20.6 |
| xnu-0143r2 | 302 / 36 | 14.9 | 88.7 | 5.94 | 51.5 / 4.1 | 8.0 | 11/302 = 4% (2-6); normal 0/36 | 13% | 2.4-8.4 |
| xnu-0144r | 46 / 28 | 26.2 | 166.6 | 6.35 | 89.2 / 89.3 | 19.0 | 7/46 = 15% (8-28); normal 4/28 | 32% | 5.8-12.2 |
| xnu-0146r | 209 / 91 | 23.7 | 110.1 | 4.65 | 37.2 / 25.5 | 33.5 | 31/209 = 15% (11-20); normal 0/91 | 26% | 6.3-10.9 |
| xnu-0159r-rung2 | 48 / 20 | 22.8 | 102.6 | 4.49 | 37.3 / 25.3 | 33.8 | 8/48 = 17% (9-30); normal 0/20 | 27% | 7.3-11.8 |

| Run | Frames | "in GL calls" ms | "outside" ms | glFlush ms/frame | glTexImage2D | glDeleteTextures |
| --- | --- | --- | --- | --- | --- | --- |
| xnu-0143r | 12200 | 3.9 | 11.0 | 8.4 | 4.0 | 3.4 |
| xnu-0143r2 | 4400 | 1.7 | 5.4 | 4.4 | 1.9 | 1.5 |
| xnu-0144r | 1200 | 4.0 | 8.4 | 6.7 | 4.8 | 3.4 |
| xnu-0146r | 5000 | 1.9 | 7.6 | 6.1 | 3.0 | 2.2 |
| xnu-0159r-rung2 | 1000 | 2.2 | 7.7 | 6.2 | 3.0 | 2.2 |

VA errors (`cannot be entered`): 0143r 539, 0144r 6, others 0. 0143r has no idle periods and is the only continuous run, so its GPU figures carry that caveat.

## Metal viability, 2026-11-08 (host fidelity only; nothing ran on the phone or in an emulator)

Work directory `~/Developer/ios-sweet-work/metal` (outside the repository, never committed). Donor `oosexgang/hackios-xnu-userland` `a79ff07`, MIT. Mesa 25.0.7. IPSW `iPhone10,3` 20H392, SHA-1 verified. QuartzCore `default.metallib` SHA-256 `11c74cc42ce5137b73d44d427f75764f886656d4ddb374422d56b609ed2762d9`.

Host adaptations on Intel macOS 15.7, Xcode 26.3: `sha256sum` wrapper over `shasum -a 256`; Homebrew `bison` and `gpatch`; `meson`, `mako`, `pyyaml`, `packaging` in a venv; donor `freedreno-darwin.patch` and `redwood-drm` added to the host tree; the glibc guard in `src/c11/threads.h` disabled.

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-08 | host x86-64 | Donor `tools/air/mk-host.sh`, adapted as above | tools build | `air2nir`, `ir3_compiler` built. `air_run` failed: arm64-only registers in its crash handler; not needed here | work directory |
| 2026-11-08 | iOS 16.0 arm64, SDK 26.2 | Meson cross-build with Xcode clang, all donor Mesa patches | dylibs | `libOSMesa.8.dylib` and `libredwoodair.dylib` (31 `rwa_` exports) built, exit 0 | work directory |
| 2026-11-08 | iOS 16.0 arm64, SDK 26.2 | clang: `redwoodmetal.m`, `redwooddrawable.m` as dylib and bundle | links | exit 0, no errors, 12 warnings; not loaded anywhere | work directory |
| 2026-11-08 | host | `corpus.py --ir3`, QuartzCore, A618 (`--gpu 618`) | module counts | container 141, reader 141, translate 135, ir3 135 of 141 | work directory `out/` |
| 2026-11-08 | host | `corpus.py --ir3`, all 142 libraries, A618 | module counts | 16912 modules: reader 16887, translate 5830, ir3 5749. VideoToolbox 2/9, AV1SW 11/11 | work directory `out/` |

Status: Metal `not-tested` on hardware. These results show compiling and linking only, with shaders at default function constants.

## Metal on device, 2026-11-09 (real device; kernel 0160, root gpu3 plus Metal payload, RAM boot)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-08 | 0160, no `sweetmetal` | `tools/sweet-boot-test.sh`, Mac-built image | GL boot, returns | SpringBoard reached, no panic, back in fastboot in 186 s | `logs/xnu-0160base.txt` |
| 2026-11-08 | 0160m1-m3 | `sweetmetal=1` on roots flashed with zero blocks skipped | Metal discovery | Plug-in loaded, then backboardd crashed 13-14 times on stale data in zeroed memory. **Tool bug: `raw2simg.py` used DONT_CARE for zero blocks; fixed to FILL** | `logs/xnu-0160m1..3.txt` |
| 2026-11-09 | 0160m4 | Fixed flash, `sweetmetal=1` | backboardd survives | 0 backboardd crashes; pipelines built; 5 swaps and presents, fence 21, then no more swaps. Black screen seen by the user. Returned to fastboot in 185 s | `logs/xnu-0160m4.txt` |

Status: Metal `experimental` on device; no picture yet. Open: pixel formats 550 and 554 unsupported, and why backboardd stops swapping (`SMP backboardd` stacks in the log).


## Stage A rows, 2026-11-10 (facts from the `NEXT_PROMPT.md` state note and recent commit messages only; no new run)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-09 | 0160m5 | Shim image `shim/out/shim-boot-0160m5.img` exists; boot procedure not described in the records | result not recorded | result not recorded | none recorded |
| 2026-11-09 | 0160m6 | Not described in the state note or commit messages | result not recorded | result not recorded | none recorded |
| 2026-11-09 | 0160m7, prepared | Root flashed: gpu3.raw with `*.csstore*` removed and the `org.ios-sweet.wland` launchd job removed; originals in `~/Developer/ios-sweet-work/root/saved/` | not booted yet | NOT booted. Context: plain GL (`xnu-0160base`) and Metal both stop with SpringBoard waiting in `_LSContextInitCommon` | none |

## GL boot with root fixes, 2026-11-10 (real device; GL path, kernel 0160, no sweetmetal)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-10 | 0160m7 (root with csstore removed) | Boot of the gpu3 root with `*.csstore*` removed | not recorded | NOT run. First attempt hung because the Mac did not see the phone on USB; superseded by the fixed root below | none |
| 2026-11-10 | gpu3 root fixes | `tools/sweet-root-fixes.py` default steps applied on the Mac without sudo. Checked on the image before: 32 apps still in staged_system_apps, no migrate sentinel, 0 PNG wallpapers, no SystemConfiguration/preferences.plist, no FeatureFlags | default steps applied | Applied. 3 chown warnings (image mounted noowners; intended owners of ExtensionKit.plist, preferences.plist and the migrate sentinel not set). Flashed to userdata (331 s + 216 s) | gpu3 root (userdata) |
| 2026-11-10 | 0160f1 | `shim-boot-0160base.img`, reboot 150 s | not recorded | Apple logo with progress bar seen by the user. 169 FPS records, 60 swaps/s, GL frame counter reached 7200. Before the fix the same image gave 3 presents in total | `logs/xnu-0160f1.txt` |
| 2026-11-10 | 0160f2 | `shim-boot-0160base600.img`, 600 s | not recorded | Logo, bar stops near half (user photo). 619 FPS records, about 30 presents/s from record 46 to the end; GL frame 34520; same scene throughout (5 draws, 10 triangles). com.apple.migrationpluginwrapper exec'd; fairplayd.H2 and bluetoothd exec'd 59 times each | `logs/xnu-0160f2.txt` |
| 2026-11-10 | 0160f3 | `shim-boot-0160base1800.img`, 1800 s | not recorded | Still logo and bar; home screen not reached. 1818 FPS records; GL frame 106300. com.apple.datamigrator exec'd once, migrationpluginwrapper 3 times, installd once, SpringBoard once, lsd once; lskdd exec'd 544 times, fairplayd.H2 178, bluetoothd 177; driverkitd killed once (sig 9) | `logs/xnu-0160f3.txt` |
| 2026-11-10 | 0160f4 | `shim-boot-0160base4500.img`, 4500 s, root with migrate sentinel | not recorded | Progress bar reached full (user photo), then drawing stopped. SpringBoard main thread in `-[BKSSystemShellService _checkIn]`; home screen not reached. Log ring wrapped (4 MB) | `logs/xnu-0160f4.txt` |
| 2026-11-11 | 0160f5 | Same root as 0160f4, 600 s | not recorded | Migration bar starts again from empty (user photos). Migration repeats every boot | not recorded |
| 2026-11-11 | 0160f6 | Root reflashed WITHOUT `/private/var/datamigrator/migrate`, other sweet-root-fixes steps kept; 600 s | not recorded | No bar. com.apple.datamigrator exec'd once; 5 GL frames. SpringBoard main thread waits on an unfair lock in `_LSContextInitCommon` (called from CCSModuleRepository) | `logs/xnu-0160f6.txt` |
| 2026-11-11 | 0160s1 | boot-args `sweetsample=SpringBoard,lsd,containermanagerd`, 400 s | not recorded | SpringBoard thread 1 in `___LAUNCH_SERVICES_IS_RESEEDING_ITS_DATABASE_AND_MAY_BLOCK__` (sync XPC to lsd). lsd scanning apps (`-[MIFilesystemScanner _scanAppsDirectory:withError:]`); in 2 of 3 samples waiting on a semaphore under `_GenerateBuiltInAppInstallSessionID`. fairplayd.H2 and bluetoothd restart about every 10 s. Not a deadlock: slow database seeding | `logs/xnu-0160s1.txt` |
| 2026-11-11 | 0160s2 | boot-arg `sweetgpu_reboot=4500`, `sweetsample=SpringBoard,lsd`; user rebooted to fastboot by hand after filming | not recorded | HOME SCREEN REACHED. User video shows lock screen, home screen with icons, Control Centre, Settings, touch working; user reports it laggy; clock, Wi-Fi, brightness, sound, haptics not working. Log: first non-trivial presents at FPS record 1090 (about 18 min after statistics start); 1508 one-second records, 137 with 10-44 presents, none with 45 or more, 1352 with 0; 1853 late swaps in total; 92 SWEET HID lines. Label: partially-working (one boot, one root, GL) | `logs/xnu-0160s2.txt` |
| 2026-11-11 | 0160w1 | Second boot on the same root with `shim-boot-0160base600.img` | not recorded | Started; result pending | none yet |

NOTES.md:661, :983, :1142-1144 (upstream): first-boot migration takes 15-60 min on this port; after it, upstream saw SpringBoard and backboardd stay up with nothing new drawn. Label for the GL logo/progress screen: partially-working (real device, three runs, one root).
