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
| 2026-11-11 | 0160w1 | Second boot on the same root with `shim-boot-0160base600.img`, real device | not recorded | HOME SCREEN REACHED again (user confirmed "booted"). First busy second at FPS record 131 of 169, about 2 min 11 s after statistics start; the user restarted to fastboot by hand. 38 seconds with 10-44 presents, none with 45+ | `logs/xnu-0160w1.txt` |
| 2026-11-11 | 0160mh1 | `shim-boot-0160m6.img`, `sweetmetal=1`, 600 s, same seeded root, real device | not recorded | Black screen (user). backboardd: 3 presents in total (one second, record 46 of 619). SpringBoard exec'd 104 times and aborted 104 times (sig 6); message before each abort: "[MPSImageGaussianBlur initWithDevice:] Failed to get MPSDevice". Before aborting, SpringBoard loads the Metal plug-in and builds pipelines (labels SiriSphereMask, SiriSphereComposite, SiriShadow). Also 1 assetsd abort, 2 com.apple.MapKit sig 11. Heap string seen: "the framebuffer fetch reads its layer from VARYING_SLOT_LAYER ... this module cannot write". Label: Metal path not-working (real device) | `logs/xnu-0160mh1.txt` |
| 2026-11-11 | 0160mp1 | `sweetmetal=1 metal_profile=1`, real device, one boot | not recorded | UI drawn by Metal: lock screen, home screen, folders, touch (user video). Faults: black frames between views, blur/backdrop in garbage colours, home wallpaper missing, slow (9 seconds with 10+ presents out of 239, none 45+). backboardd crashed twice (sig 6, sig 11); SpringBoard exec'd 3 times. Label: partially-working (device, one boot) | `logs/xnu-0160mp1.txt` |
| 2026-11-11 | 0160t1 | process allow-list, `sweetmetal_procs=metaltest`, real device | not recorded | backboardd refused the Metal device and crashed 28 times (sig 11) while the kernel still advertised the plug-in. Self-test printed nothing because the job wrote to /dev/console. Label: allow-list experimental | `logs/xnu-0160t1.txt` |
| 2026-11-11 | 0160t2 | `sweetmetal_procs=*`, `sweetnull=backboardd,SpringBoard,metaltest`, real device | not recorded | Self-test 7 passed, 10 failed (list in `METAL_FINDINGS.md` section 5). Test program unreviewed; a FAIL can be the test's fault | `logs/xnu-0160t2.txt` |

Phone root from 2026-11-11 on: `work1.raw` = seeded root (copied back from the phone as `seeded1.raw`, LaunchServices database included) + new plug-in with allow-list + `/redwood/bin/metaltest` + launchd job `org.ios-sweet.metaltest`.

NOTES.md:661, :983, :1142-1144 (upstream): first-boot migration takes 15-60 min on this port; after it, upstream saw SpringBoard and backboardd stay up with nothing new drawn. Label for the GL logo/progress screen: partially-working (real device, three runs, one root).

## Metal fixes on device, 2026-11-11 (real device, RAM boot, one boot per run; patches in `userland/metal/`)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-11 | 0160c1 (patch 0003: load actions once per pass; clear-only passes clear) | `sweetmetal=1 metal_profile=1 sweetmetal_procs=*` | not recorded | Self-test 7 -> 11 of 17. Wallpaper visible. backboardd did not crash in this run | `logs/xnu-0160c1.txt` |
| 2026-11-11 | 0160f2c (patch 0004: `flatshade_first=1`) | Same boot-args plus `flatshade_first=1` | not recorded | No visible change. Kept as correct for Metal's provoking-vertex rule | `logs/xnu-0160f2c.txt` |
| 2026-11-11 | 0160vA (patches 0003-0007; 0006 widens 16-bit stage-boundary varyings to 32-bit) | Same boot-args, default varyings | not recorded | Diagonal half-rectangle garbage and saturated magenta/yellow/blue blocks gone (user photos). Settings, home screen with labels, App Library, Control Centre render recognisably. Self-test 15 passed, 4 failed of 19. Draws 08-11 no longer SIGSEGV (0005, 0007). Test 16: 100 passes in 18 ms. Faults: low frame rate; respring on app exit (backboardd sig 11 once, sig 6 once, exec'd 6 times; SpringBoard exec'd 3 times); (a light-blue tint seen in photos was the camera: user confirms white is white in person); fine dotted/checker pattern in blurred materials (confirmed real by the user in person, most visible behind the App Library folders); Control Centre button glyphs mostly missing; thin dashed outlines on some rounded rectangles; some widgets blank. assetsd aborts 7 times; com.apple.MapKit sig 11 twice | `logs/xnu-0160vA.txt` |
| 2026-11-11 | 0160vB (same root, `sweetmetal_f16vary=1`: old 16-bit varyings) | A/B against 0160vA | diagonal garbage absent if widening is the cause | Same diagonal garbage as before (user stopped early). Self-test 15 passed, 4 failed of 19. Cause confirmed by A/B: ir3 mishandles half-precision vertex outputs in VS->FS linkage for CoreAnimation's lph shaders | `logs/xnu-0160vB.txt` |

Self-test failures in vA and vB: 12 and 13 (`blitCommandEncoder` returns nil); 18 and 19 (new CoreAnimation-quad tests: pipeline nil, `fixed_vert_lph_spc` reads vertex attribute 4 (point_size, float) and the test's vertex descriptor configures no format there). The test is at fault for 18 and 19, not the driver.

Status: Metal UI `partially-working` (real device, one boot, 0160vA). Self-test 15 of 19 (0160vA, 0160vB). Not a frame-rate result: no per-frame data and no sustained run.

## Patch 0008, depth store without a depth attachment, 2026-11-12 (host only)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-12 | 0008 on 0001-0007, host softpipe, Mesa debugoptimized | `air_metal_test --draw-ms AppleMetalGLRenderer.bundle/default.metallib texturedFragment2DDepthMultisample`, once as is (test asks for the old refusal) and once with `RWA_TEST_DEPTH_DISCARD=1` (library default) | Refusal sentence in the first run; in the second a pipeline with no depth attachment that stores nothing to depth | As expected: first run refuses then retries with a depth attachment; second run prints `the fragment shader stores nothing to [[depth]], depth attachment none`. Neither run draws: softpipe cannot make the 4-sample texture (existing limit), so only pipeline creation is covered | patch `userland/metal/0008-depth-store-discarded.patch`; outputs not kept |
| 2026-11-12 | same, iOS arm64 build | `bash tools/metal-build.sh` for `ios`, `driver`, `test`, `payload` | Clean build, payload library equals build library | Clean; `libredwoodair.dylib` UUID 82334361-92B5-3478-8E94-E1A7FBABC262 in both, sha256 965b43ac…; `discard_depth_stores` and `sweetmetal_depthrefuse` present | `~/Developer/ios-sweet-work/metal-build/pay` |

Status: 0008 `not-tested` on the device. Review (`reviewer`, source reading): accept with fixes; applied: deref-chain guard in `discard_depth_stores`, shader-out mode check in `fragment_writes_depth`, host switch `RWA_TEST_DEPTH_DISCARD`. Open from review: library and plug-in have no runtime struct-size check, so they must always be deployed and rolled back together; whether ir3 on the A618 accepts a fragment shader left with no stored output is unknown until a device run.

## Patch 0008 on the device, 2026-11-12 (real device, RAM boot, one boot)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-12 | 0160d8 = patches 0001-0008, `shim-boot-0160vA.img` (same boot-args as 0160vA, `sweetgpu_reboot=300`), root `work1.raw` + new payload, `userdata` flashed (rollback `work1-pre0008.raw`) | `tools/metal-flash-test.sh work1.raw shim-boot-0160vA.img 0160d8 420`; user opened and exited apps | No `CRASH backboardd`; self-test no worse than 15 of 19 | backboardd crashed twice, both sig 11 inside `libredwoodair.dylib` (lines 3010, 4516). No sig 6 and no `refused ... [[depth]]` line, but no `store is discarded` line either: the 0008 path was not reached in this boot, so 0008 is neither confirmed nor refuted. Self-test 15 passed, 4 failed. User: respring on app exit, blank widgets, heavy lag, Control Centre and App Library blur faults unchanged (photos IMG_1430-1434) | `logs/xnu-0160d8.txt` |

Crash 1 (line 2991): fault address 0x1a8 in `fd6_draw_vbos` <- `fd_draw_vbo+472` <- `rwa_render_draw+3588` <- `runDraw` <- `commit`. Crash 2 (lines 4482-4515): two fault lines (0x1c, 0x8c) and two interleaved backtraces, one in `fd_bo_add_fence` <- `fd_submit_sp_flush` <- `fd_gmem_render_tiles` <- `fd_batch_flush` <- `fd_context_flush` <- `finish_or_say_why` <- `rwa_render_draw`, the other in `fd_pipe_fence_finish` <- `finish_or_say_why` <- `rwa_render_draw`; both under `-[RedwoodMetalCommandBuffer commit]`. Reading: two threads were inside the one `pipe_context` at the same time. Status: 0008 `not-tested` on device (path not reached); respring `not-working`.

## Patch 0009, library calls serialized, 2026-11-12 (host only)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-12 | 0009 on 0001-0008, iOS arm64 build | `bash tools/metal-build.sh` for `ios`, `driver`, `test`, `payload` | Clean build | Clean; `sweetmetal_nolock` present in the payload plug-in | `userland/metal/0009-library-calls-serialized.patch`, `~/Developer/ios-sweet-work/metal-build/pay` |

Status: 0009 `not-tested` (no host or mock test of the lock exists; device run not done: the second `userdata` flash was not carried out). Review (`reviewer`, source reading): ACCEPT, no blockers. Known limits from review: `finish` waits for the GPU while holding the lock (measure pacing against `sweetmetal_nolock=1`); a non-UTF-8 `why` string would throw under the lock; `finish` is device-wide, so a fault can be blamed on the wrong command buffer.

## Patch 0009 on the device, 2026-11-12 (real device, RAM boot, one boot)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-12 | 0160d9 = patches 0001-0009, `shim-boot-0160vA.img`, root `work1.raw` + new payload, `userdata` flashed by the user | `tools/metal-flash-test.sh work1.raw shim-boot-0160vA.img 0160d9 420` (run by the user); user opened and exited apps | No `CRASH backboardd`; self-test no worse than 15 of 19 | Lock active (line 986 `library calls: serialized by one recursive lock`). User: apps can be exited without a respring. One backboardd lived from boot to line 5791 (0160vA and 0160d8 each lost two). It then died of a different cause: SMMU fault `CB1 FSR 00000402 FAR 000000004c43c000` and `SweetAdreno: submission 36366 not done` (about line 5190), 102 `the draw failed: the GPU did not finish the draw within two seconds` lines, then sig 11 at 0x18 in `fd_bo_heap_alloc+208` <- `fd_bo_new_ring` <- `fd_batch_create` <- `fd_context_batch` <- `fd_draw_vbo` <- `rwa_render_draw`. No `store is discarded` line: 0008's path again not reached. Self-test 15 passed, 4 failed. Blank widgets, missing Control Centre glyphs, dashed lines on rounded shapes, lag unchanged (photos IMG_1435-1438) | `logs/xnu-0160d9.txt` |

Status: respring on app exit `partially-working` (real device, one boot; no A/B with `sweetmetal_nolock=1`, no cold/warm/stress set). Attribution: unknown. 0160d9 carried 0008 and 0009 together and no boot ran one without the other; the 0008 path never printed in 0160d9 (no `store is discarded` line, no refusal line), so the result belongs to the pair 0008+0009, not to either patch alone. New fault: GPU reads or writes an unmapped address, never recovers, and the driver then crashes on a failed buffer allocation: `not-working`. 0008 `not-tested` on device.


## Patch 0161 kernel build, 2026-11-12 (CI build + host image checks; nothing run on the device)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-12 | kernel 0161 = `xnu/patches/` 0001-0161 at 5f6ec1f | `gh workflow run xnu.yml --ref gpu -f keep_going=false` (run 43300161670) | Compiles and links | Success. Kernel SHA256 `12b12f60...b3a0b` matches `SHA256SUMS`; 13 `SWEET GPU: fault address` strings; `__DATA` vmsize 5668864 -> 6602752, total vmsize 22167552 -> 23117824 (+0.93 MiB) | `~/Developer/ios-sweet-work/kernel-0161/` |
| 2026-11-12 | `shim-boot-0161a.img` | `PATH=$HOME/Developer/ios-sweet-work/bin:$PATH bash tools/sweet-gpu-image.sh ~/Developer/ios-sweet-work/kernel-0161 0161a "sweetgpu_reboot=300 sweetmetal=1 metal_profile=1 sweetmetal_procs=* sweetnull=backboardd,SpringBoard,metaltest"` | Same boot-args as 0160vA, new kernel inside | `RAMDISK MATCH`; boot-args equal to 0160vA except `sweetepoch`; SHA256 `e2f28ce9...ca211` | `shim/out/shim-boot-0161a.img` |

Status: 0161 `not-tested` (compiled and packed only). Trap found: without `ios-sweet-work/bin` on `PATH` the shim build fails (`aarch64-linux-gnu-gcc: command not found`), the script hides the error and copies the previous `shim-boot.img`; the first 0161a image was byte-identical to 0160vB. Trust only an image whose build printed `RAMDISK MATCH`. Shim load window: `shim/loader.c` places the ADT at `kernel_end`, no fixed size cap found by reading; not proven by a boot.

## Patch 0161 on the device, 2026-11-12 (real device, RAM boot, one boot)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-12 | 0161a = kernel 0161, `shim-boot-0161a.img` (SHA256 e2f28ce9...), root unchanged (`work1.raw` + payload 0001-0009), nothing flashed | `bash tools/sweet-boot-test.sh shim/out/shim-boot-0161a.img 0161a 420`; user used the phone (158 touch lines, last at line 3867 of 3977) | Kernel boots; on a GPU fault a `SWEET GPU: fault address:` report | Booted, back in fastboot after 335 s. Self-test 15 passed 4 failed (unchanged). No `SMMU gfsr`, no `fault address`, no GPU timeout, no `CRASH backboardd`. `zombies` reached 788. Other crashes: AegirPoster sig 6 x2 processes, assetsd sig 6 x2, MapKit sig 11 x2, `mobilenotes.WidgetExtension` killed 0xDEAD10CC x3 (suspended with locked system files), driverkitd sig 9 | `logs/xnu-0161a.txt` |

Status: 0161 `partially-working`: the kernel with it boots and runs 300 s under use (one boot); the report itself is `not-tested` because no fault occurred. The 0160d9 fault did not recur in this boot: it is intermittent, and one clean boot says nothing about its cause. `zombies` at 788 without a fault (288 at the 0160d9 fault) is one more point against a link between that count and the fault. The bigger kernel (+0.93 MiB) loads: shim window concern closed for this size (one boot).

## Patch 0010, scissor rectangle, 2026-11-12 (host only; nothing built for iOS, nothing run on the device)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-12 | 0010 on 0001-0009 in `~/Developer/ios-sweet-work/metal-build/donor`, host softpipe, Mesa debugoptimized | `W=~/Developer/ios-sweet-work/metal-build`; copy `donor/tools/mesa/air/air_metal{.c,.h,_test.c}` to `host/mesa-25.0.7/src/compiler/air/`; `PATH=$W/venv/bin:$PATH ninja -C $W/host/build src/gallium/drivers/freedreno/air_metal_test`; `DYLD_LIBRARY_PATH=$B $B/air_metal_test --draw-scissor sc.metallib fs_pos` (`B=$W/host/build/src/gallium/drivers/freedreno`), then `--clear sc.metallib fs_color`. Run by the lead after `opus-impl`. `sc.metal` (not in git; `xcrun metal -c` then `metallib`): `fragment float4 fs_color(constant float4 &c [[buffer(0)]]) { return c; }` and `fragment float4 fs_pos(float4 p [[position]], constant float4 &c [[buffer(0)]]) { return float4(p.x, p.y, c.z, c.w); }` | Rectangle {8,4,16,12} of 64x48 draws exactly x 8..23, y 4..15 counted from the top; no rectangle after one draws all; zero width and x at the right edge draw nothing; a rectangle past the attachment is cut; clear unaffected | 5 of 5 PASS, exit 0: 192 texels at x 8..23 y 4..15 with readback row = `[[position]].y - 0.5` in each (y direction: top-left, no flip needed); 3072 with no rectangle; none for the two empty cases; 432 at x 40..63 y 30..47 for the cut one. `--clear` PASS | patch `userland/metal/0010-scissor-rect.patch` (SHA256 0f4f954af12db282...); outputs not kept |
| 2026-11-12 | same | `xcrun --sdk iphoneos clang -arch arm64 -fobjc-arc -fsyntax-only -Wall userland/metaltest/metaltest.m` | no diagnostics | exit 0, none (syntax only; `redwoodmetal.m` syntax check by `opus-impl`, not repeated by the lead) | none |

Status: 0010 `experimental`. Host softpipe proves the library half only. Not covered: freedreno's own scissor code (empty rectangle, switching back to none), the plug-in on the phone, IOSurface drawables, any visible fault. No negative control on the host beyond the no-rectangle case. `reviewer` (opus, reading only): no blocker; struct layouts identical in `air_metal.h` and `redwoodmetal.m`, no state leak into clears or later draws found, clamp safe. Taken from the review: self-test 20 now also runs a zero-width rectangle and a no-rectangle pass after it. Not taken: an IOSurface variant of test 20 (open); test 20 still FAILS under `sweetmetal_noscissor=1` on purpose (negative control for the A/B boot); the boot-arg value is matched on its first character only, like the existing keys.

## Patch 0010 on the device, A/B, 2026-11-12 (real device, one boot each)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-12 | payload 0001-0010 from `metal-build/donor` (reverse-check of all ten patches clean, so the `donor` stage applied nothing) | `bash tools/metal-build.sh ios`, then `driver`, `test`, `payload` (local, 70 s; no CI workflow builds this) | One build for plug-in and library; item 20 in `metaltest` | Built. `RedwoodMetal` SHA256 45d1c053..., `libredwoodair.dylib` 5b0bc5f8..., `metaltest` b7a86df1...; plug-in has `sweetmetal_noscissor=`, `metaltest` has the item 20 strings | `~/Developer/ios-sweet-work/metal-build/pay` |
| 2026-11-12 | `shim-boot-0161sA.img` (af5b7f57...), `shim-boot-0161sB.img` (96f45125...), kernel 0161 (12b12f60...) | `PATH=$HOME/Developer/ios-sweet-work/bin:$PATH bash tools/sweet-gpu-image.sh ~/Developer/ios-sweet-work/kernel-0161 0161sA "sweetgpu_reboot=300 sweetmetal=1 metal_profile=1 sweetmetal_procs=* sweetnull=backboardd,SpringBoard,metaltest"`; 0161sB the same plus `sweetmetal_noscissor=1` | `RAMDISK MATCH`, boot-args inside | Both `RAMDISK MATCH`; `sweetgpu_reboot=300` in both, `sweetmetal_noscissor=1` only in sB | `shim/out/` |
| 2026-11-12 | 0161sA: scissor on. Root `work1.raw` + payload 0001-0010, `userdata` flashed by the user (rung snapshot-first; snapshot `root/work1-pre0010.raw` = 0001-0009 state) | `tools/metal-flash-test.sh ~/Developer/ios-sweet-work/root/work1.raw shim/out/shim-boot-0161sA.img 0161sA 420` (user); user used the phone (84 touch lines) | Self-test 16 of 20, item 20 PASS; `scissor rectangles:` line; no fault report | 16 passed 4 failed (12, 13, 18, 19 as before); `20 scissor rect: PASS 192 px inside {8,4,16,12}, 3904 clear; zero width draws nothing; none draws all`; backboardd line 1263 `scissor rectangles: passed to the library`. No `SMMU gfsr`, no `fault address`, no draw timeout, no `CRASH backboardd`. User by eye: the green fault is gone, the fault when closing an app is gone, the status-bar battery icon is still wrong. Other crashes: assetsd, MapKit, driverkitd, `0xDEAD10CC` x2 | `logs/xnu-0161sA.txt` |
| 2026-11-12 | 0161sB: same root and payload, `sweetmetal_noscissor=1`, nothing flashed (RAM boot) | `bash tools/sweet-boot-test.sh shim/out/shim-boot-0161sB.img 0161sB 420` (agent); user used the phone (52 touch lines) and ended the boot with the keys at 198 s | Item 20 FAIL (negative control); faults return | 15 passed 5 failed; `20 scissor rect: FAIL px(0,0) BGRA got 64,128,255,255 want 255,0,0,255`; backboardd line 1206 `scissor rectangles: DROPPED (forced by boot-arg sweetmetal_noscissor=1)`. No fault report, no draw timeout, no `CRASH backboardd`. User by eye: the green fault and the app-close fault are both back; battery icon the same as in A | `logs/xnu-0161sB.txt` |

Status: scissor rectangle (0010) `partially-working` (real device, one A/B pair, one boot each; no cold/warm/stress set, no repeat). The A/B attributes two visible faults to the dropped scissor: the green fault and the fault when closing an app (user's words; which photo of `photos-2026-11-12/` each one is was not matched). The status-bar battery icon is not explained by 0010. Settings > Battery switch and the app-switcher card were not reported separately. Item 1b (GPU fault) did not recur in either boot; the 0161 report is still `not-tested`. The phone root is now `work1.raw` + payload 0001-0010; left in fastboot.

## Metal frame time from existing logs, 2026-11-12 (host only; device logs from earlier boots, nothing run)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-12 | logs of 0161sA, 0161sB, 0161a | `python3 -I tools/sweet-fps-summary.py logs/xnu-TAG.txt`; per-second `SWEET FPS:` and `RedwoodGPU:` lines summed by a scratch parser (not in the repository) | Where the frame time goes | subs/swap 98 / 99 / 115; swaps/s while active 4.4 / 3.4 / 3.4 (max 10); late 358/360, 134/136, 548/550; cache clean 0.93 / 0.90 / 0.90 ms and 11-12 MB per submission (32.7 / 12.1 / 56.8 s total); GPU wait 0.72-0.81 ms mean; submit-to-done 5.0-5.5 ms mean. One boot each; this is not a frame-rate claim | `GPU_DECISION.md` "Metal frame time" |

## Patch 0011, one wait per command buffer, 2026-11-12 (host and build only; nothing run on the device)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-12 | 0011 on 0001-0010 in `metal-build/donor`, host softpipe | copy `air_metal{.c,.h,_test.c}` to `host/mesa-25.0.7/src/compiler/air/`, `ninja ... air_metal_test`; `air_metal_test --draw-deferred dw.metallib` (`dw.metal`: `fs_pos`, `fs_color`, `fs_copy` = `t.read(p.xy) + (0,0,.5,0)`; scratch, not in git) | Clear + 64 scissored column draws + one draw reading that target, per draw and deferred, same bytes | per draw PASS, deferred PASS, same bytes PASS, NULL device refused; 0 checks failed. Regression: `--draw-scissor` 0 failed, `--clear` 0 failed. Softpipe runs work at flush, so this proves order and result without the waits, not GPU overlap. No negative control | scratchpad |
| 2026-11-12 | same, iOS | `bash tools/metal-build.sh ios`, `driver`, `test`, `payload` (order matters: `driver` empties `obj/`) | builds, no errors | `RedwoodMetal` 62645657..., `libredwoodair.dylib` 1ba7090c... (exports `rwa_set_deferred_wait`), `metaltest` 142d6a49... (item 21). `metaltest.m` syntax check clean | `metal-build/pay` |
| 2026-11-12 | kernel 0161 | `sweet-gpu-image.sh ... 0161wA "<0161sA args>"`, 0161wB the same plus `sweetmetal_drawwait=1` | `RAMDISK MATCH` | both MATCH; wA b4203b3a..., wB e6ab6e09...; `sweetgpu_reboot=300` in both, `sweetmetal_drawwait=1` only in wB | `shim/out/` |

Status: 0011 `experimental`. Reviewed by the lead only (the user asked for no agents this time); one change from the review: the boot-arg is read only once a device exists. Snapshot before the flash: `root/work1-pre0011.raw` (APFS clone of `work1.raw` = 0001-0010). Not done: the device A/B.

## Patch 0011 on the device, first boot 0161wA, 2026-11-13 (real device; FAILED)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13 | `shim-boot-0161wA.img` (b4203b3a...), root `work1.raw` + payload 0001-0011 (library 1ba7090c...), `userdata` flashed by the user (snapshot `work1-pre0011.raw`) | `tools/metal-flash-test.sh ... 0161wA 420` (user) | `GPU waits: one per command buffer`; no new fault | Mode line present. backboardd crashed 27 times, sig 11 every time, so no UI (boot-loop; the user saw the console only). Symbolized (`atos`, ios build): `emit_blit<6>+136` <- `fd6_emit_tile_init<6>+536` <- `fd_gmem_render_tiles+904` <- `fd_batch_flush` <- `fd_context_flush` <- `rwa_finish+56` <- `-[RedwoodMetalCommandBuffer commit]`. metaltest: 05 crash, 08/09 timeout, done 6 passed 3 failed. No `SMMU gfsr` checked yet in detail. Phone returned to fastboot by `sweetgpu_reboot` | `logs/xnu-0161wA.txt`, user photo `IMG_1460.jpeg` |

Cause (source reading, consistent with the trace): `release_pass_framebuffer` (`air_metal.c`) freed each draw's `pipe_surface` with `surface_destroy`, ignoring the reference the unflushed freedreno batch holds (`util_copy_framebuffer_state`). Waiting per draw hid it: the batch was already flushed. The tile pass at the deferred flush then read freed surfaces. Fix in 0011: release with `pipe_surface_reference(&s, NULL)`. Host tests pass again (deferred, scissor, clear), but softpipe cannot show this defect: no host test covers it. Rebuilt: library 3560a9da..., plug-in 62645657... and `metaltest` 142d6a49... unchanged. The 0161wB image (`sweetmetal_drawwait=1`) is safe with either library (per-draw wait).

## Patch 0011 on the device, 0161wA2, 2026-11-13 (real device, one boot)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13 | `shim-boot-0161wA.img` (b4203b3a...), root `work1.raw` + payload 0001-0011 with the surface fix (library 3560a9da...), `userdata` flashed by the user | `tools/metal-flash-test.sh ... 0161wA2 420` (user); user used the phone (46 touch lines) | Boots; fewer submissions per swap; no new fault | Boots to the UI. backboardd and SpringBoard `GPU waits: one per command buffer`. No `SMMU gfsr`, no `fault address`, no `THE GPU DID NOT FINISH`, no backboardd crash. Self-test 17 of 21 (12, 13, 18, 19 as before); `21 64 draws, one commit: PASS ... 2.87 ms`. `python3 -I tools/sweet-subs-per-swap.py`: 38 active s, 197 swaps, 195 late, max 15 swaps/s, 8 s at >= 10 (0161sA: 1 s); subs/swap 7.3 (0161sA 97.8); cache-clean CPU 1.9 s of 76 s (0161sA 32.7 of 183). But submit-to-seen-done mean 82.6 ms (0161sA 5.5), 1310 of 1431 submissions over 4 ms; GPU wait mean 10.8 ms. User by eye: no better performance; widgets and Control Centre still broken (not addressed by 0011). Other crashes: AegirPoster sig 6 x12, assetsd sig 6 x4, MapKit sig 11 x2 | `logs/xnu-0161wA2.txt` |

Status: 0011 `partially-working` (real device, one boot; no wB control boot run with this library). It does what it was for: 13x fewer submissions, the cache cost gone. Visible frame rate not improved (user). The time moved to GPU execution: a command buffer now takes about 80 ms from submit to done. Not yet known whether that is GMEM tiling of the 1125x2436 target, the GPU clock, or the work itself.

## Where the per-command-buffer GPU time goes, 2026-11-13 (host; source reading and the existing 0161wA2 log; nothing built or run)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13 | none (Mesa 25.0.7 ios tree as built for 0011; `logs/xnu-0161wA2.txt`) | Read `freedreno_gmem.c`, `fd6_gmem.cc`, `freedreno_state.c`, `freedreno_batch_cache.c`, `freedreno_autotune.c`, `air_metal.c` 6632-6705; `rg` on the log for clock lines and `the GPU worked` | Which mode a UI batch runs in; whether the clock is logged | GMEM for UI batches (below). GPU clock rate: never logged (only GDSC state, lines 349-351). `the GPU worked`: 82.6 ms mean is skewed by two early intervals (1458 ms x12 at line 2113, 261 ms x263 at 2378); the other eight intervals are 8-74 ms, six of them 19-41 ms; about 95% of submissions over 4 ms | this section |

Findings (host fidelity; "read" = seen in the code, "inferred" = arithmetic or unread callee):

- Mode choice, `fd_gmem_render_tiles` (`freedreno_gmem.c` 697-780), read: sysmem only if autotune says bypass, `FD_MESA_DEBUG=sysmem`, layered attachments, or tessellation. The no-history fallback (`freedreno_autotune.c` 138-149) refuses bypass when the batch has a clear, any `gmem_reason` (blend enabled is one), more than 5 draws, or MSAA. A blended UI pass is therefore GMEM, consistent with `fd_gmem_render_tiles -> fd6_emit_tile_init` in the 0161wA trace. Autotune's history branch was not read.
- Flags, read (`freedreno_screen.c` 61-64, 90, 900-903): `sysmem` forces sysmem, `gmem` forbids bypass, `nobin` turns hardware binning off. `FD_MESA_DEBUG` is read once per process in `fd_screen_create`.
- Bins, inferred: A618 limits are tile align 32x32, max tile 1024x1008 (`freedreno_devices.py`). For 1125x2436 at 4 bytes per pixel and a 512 KiB GMEM, `calc_nbins`/`layout_gmem` (148-257) give 4x6 = 24 bins of 288x416. The GMEM size our pipe backend reports was NOT found (not read); 512 KiB is the stock A618 value and an assumption here.
- Per bin, read (`fd6_gmem.cc` 832-884, 1615-1688, 1808-1903): a load blit when the target already holds valid content and was not cleared, the draws, a store blit. With hardware binning and no clear, a bin with no geometry skips load and store; with a clear, or without binning (`num_draws == 0`), every bin runs both. A full-screen blended layer therefore costs 24 loads and 24 stores of the 11 MB target per batch, plus the binning pass.
- Rebind per draw, read: every draw and clear does `create_surface`, `set_framebuffer_state`, the draw, `set_framebuffer_state({0})`, surface unref (`air_metal.c` 6632-6705, callers 6862/6871 and 7170/7394). In freedreno a changed framebuffer drops `ctx->batch` without flushing (`freedreno_state.c` 279-343, reorder on). The batch-cache key is the texture, format, level/layer and samples, not the surface pointer (`freedreno_batch_cache.c` 546-574), so the next draw to the same target should find the same batch: inferred, the lookup itself was not read. Cost inside a batch: redundant state only. Cost that matters: one tiled batch (24 load/store pairs) per distinct target per command buffer.
- Not known: the GPU clock, and so whether 20-40 ms is 24 bins at a low clock or at full clock.

## Patch 0012 (boot-arg `sweetmetal_fddebug` -> `FD_MESA_DEBUG`), 2026-11-13 (host; compiled and packed only, `not-tested`)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13 | 0012 on 0001-0011 in `metal-build/donor` (plug-in only, written by the lead, `reviewer`: ACCEPT) | `tools/check-patch.py`; `git apply --check` on the pre-0012 source; `bash tools/metal-build.sh ios`, `driver`, `test`, `payload` | Plug-in changes, library and `metaltest` do not | Plug-in 62645657... -> 3d35bc77... (strings `FD_MESA_DEBUG: %s (boot-arg sweetmetal_fddebug)` present). `metaltest` 142d6a49... unchanged. Library 3560a9da... -> **1d4c1505...** although no library source changed (clean `ios` rebuild; cause not looked for, the old binary was not kept to compare). Host `air_metal_test` NOT rerun: the library sources in `host/` are byte-identical to the donor's and no host test loads the plug-in, so nothing on the host exercises 0012 | `userland/metal/0012-fddebug-bootarg.patch`, `metal-build/pay/` |
| 2026-11-13 | kernel 0161 (`SHA256SUMS` OK) | `PATH=~/Developer/ios-sweet-work/bin:$PATH tools/sweet-gpu-image.sh ~/Developer/ios-sweet-work/kernel-0161 0162sA "<0161wA args>"`; 0162sB the same plus `sweetmetal_fddebug=sysmem` | `RAMDISK MATCH` | both MATCH; sA 804f083d..., sB 4b75d384...; `sweetgpu_reboot=300` in both, `sweetmetal_fddebug=sysmem` only in sB (read back from `check-*/ramdisk`). First attempt without the `PATH` hit the line-183 trap again (stale image e6ab6e09... copied); those were overwritten | `shim/out/shim-boot-0162s{A,B}.img` |

Notes:

- Because the library hash changed, the 0161wA2 log is no longer a same-payload control: the spec's rule asks for a fresh control `0162sA`. Two boots on one payload (sA then sB), one flash.
- Step 2 of the spec (log `gmemsize_bytes` and the bin layout) is left out: the plug-in reaches the library only through `rwa_*`, and none returns it. The 512 KiB / 24 bins figure stays an assumption.
- Review note: `setenv` runs once before the first `rwa_device_open`, under the plug-in's own lock only; another thread reading the environment at that moment is not excluded. Only boots with the boot-arg present are exposed (sB, not sA).
- `sweetmetal_fddebug` is silently ignored if `kern.bootargs` is 1024 bytes or more (sysctl fails); sB's are about 400.

## Patch 0012 on the device, control 0162sA, 2026-11-13 (real device, one boot; the sysmem boot 0162sB has NOT run)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13 | `shim-boot-0162sA.img` (804f083d...), root `work1.raw` + payload 0001-0012 (library 1d4c1505..., plug-in 3d35bc77...), `userdata` flashed by the user (snapshot `work1-pre0012.raw`) | `tools/metal-flash-test.sh ... 0162sA 420` (user). First flash stopped at sparse chunk 21 of 26 and the script hung in `fastboot reboot recovery`; a second run in another tab completed the flash and the boot | Same as 0161wA2: the rebuilt library behaves like 3560a9da... | Boots to the UI. `GPU waits: one per command buffer` in backboardd, SpringBoard, metaltest. No `FD_MESA_DEBUG` line (no boot-arg, as intended). No `SMMU gfsr`, no `fault address`, no `THE GPU DID NOT FINISH`. `sweet-subs-per-swap.py`: 160 active s, 1535 swaps, 1515 late, max 30 swaps/s, 78 s at >= 10; subs/swap 7.4; cache CPU 12.5 s of 273.5 s. `the GPU worked`: 41 intervals, 11341 submissions, mean 31.4 ms, last six intervals 11.9-31.7 ms. The sum (356 s) exceeds the 273.5 s the intervals cover, so the figure includes queueing behind other submissions; execution per submission is at most 273.5 s / 11341 = 24 ms. User by eye: as slow as before, the same visual faults, "not sure" about new ones (not photographed, not verified) | `logs/xnu-0162sA.txt` |

Reading (lead, host arithmetic on two logs, `experimental`): per-draw waits (0161sA) gave 35201 submissions in 81 active s, so at most 2.3 ms per one-draw submission; one wait per command buffer gives at most 14-24 ms per submission of about 13 draws. The cost per draw did not fall with batching (about 1-2 ms either way). Either each draw is still its own tiled pass inside the flush (the per-draw framebuffer rebind was only inferred not to split the batch), or the draws themselves cost that much. 0162sB (sysmem) separates the two only partly; a per-pass timer in the plug-in would do it directly.

## Patch 0012 on the device, sysmem 0162sB, 2026-11-13 (real device, one boot)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13 | `shim-boot-0162sB.img` (4b75d384...), same root and payload as 0162sA, nothing flashed | `tools/sweet-boot-test.sh shim/out/shim-boot-0162sB.img 0162sB 420` (lead; `fastboot boot`, RAM only); the user touched the phone (645 touch lines) | `FD_MESA_DEBUG: sysmem` line; faster or not | Line present in backboardd, SpringBoard, metaltest. No `SMMU gfsr`, `fault address`, `THE GPU DID NOT FINISH`, no backboardd crash; `table arena full` 7 times. Self-test 17 of 21. 208 active s, 2014 swaps (9.7 per active s; sA 9.6), max 27 swaps/s; subs/swap 7.5 (sA 7.4); submit-to-done 24.4 ms mean over intervals of 50+ (sA 29.2). **No change in frame rate.** Whether freedreno actually ran sysmem is not shown (no mode log; `redwooddrawable` also loads the library) | `logs/xnu-0162sB.txt`, `FRAME_RATE_RESEARCH.md` |

0012: `partially-working` (the flag reaches the environment, one boot); its effect on the render mode is `not-tested`. Correction to the 0162sA row above: backboardd crashed once in that boot (line 3796, NULL buffer after `table arena full`), see `FRAME_RATE_RESEARCH.md` section 5.

## Patch 0013 (boot-arg `sweetmetal_passlog=1`, diagnostic only), 2026-11-13 (host)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13 | 0013 on 0001-0012 in `metal-build/donor` (`opus-impl`; `reviewer`: ACCEPT-WITH-FIXES, the three should-fix items applied by the lead: interval test when `now` is older than the interval start, deltas clamped at 0, layout asserts on the plug-in's copy of `struct rwa_passlog`) | `tools/check-patch.py`; fresh worktree of the donor commit + 0001..0013 with `git apply`, `cmp` against the build tree | The series reproduces the build tree | `ok`; `air_metal.c`, `air_metal.h`, `air_private.h`, `air_metal_test.c`, `redwoodmetal.m`, `tools/mesa/freedreno-passlog.patch` identical; one whitespace warning (a context line of the embedded Mesa patch) | `userland/metal/0013-passlog.patch` (98a41159d3f86ec8...) |
| 2026-11-13 | same, host softpipe, Mesa debugoptimized (host tree is built WITHOUT `freedreno-passlog.patch`) | copy `air_metal{.c,.h}` to `host/mesa-25.0.7/src/compiler/air/`; `ninja ... air_metal_test`; `--draw-scissor sc.metallib fs_pos`, `--clear sc.metallib fs_color` (`sc.metal` rebuilt from the source in the 0010 row) | No regression in the library | scissor 5 of 5 PASS, clear PASS, exit 0. Passlog itself is NOT exercised on the host: no test sets it and softpipe has no hook | scratchpad |
| 2026-11-13 | same | `bash tools/metal-build.sh ios`, `driver`, `test`, `payload`; `nm -gU` on the packed library | Library and plug-in change, `metaltest` does not; the hook is exported | Library 1d4c1505... -> **a9e8c642...**, plug-in 3d35bc77... -> **6922f55c...**, `metaltest` 142d6a49... unchanged. `_fd_passlog_read`, `_rwa_set_passlog`, `_rwa_passlog_read` exported. The 0012 payload is kept in `metal-build/pay-0012` | `metal-build/pay/` |
| 2026-11-13 | kernel 0161 (`SHA256SUMS` OK) | `tools/sweet-gpu-image.sh` with the 0162sA args + `sweetmetal_passlog=1 sweetgpu_swipe=90`; pB also `sweetmetal_fddebug=sysmem` | `RAMDISK MATCH`, args read back | both MATCH; pA ecd50afe..., pB 7dd512a9...; args read back from `check-*/ramdisk` | `shim/out/shim-boot-0163p{A,B}.img` |

Notes:

- Deviation from the spec: mode and bins come from a Mesa hook (`donor/tools/mesa/freedreno-passlog.patch`, created by 0013): an exported accessor for `ctx->stats.batch_{total,sysmem,gmem,nondraw}` plus two per-process bin counters updated in the GMEM branch. The mode decision is untouched; no packets. Reason: freedreno clears `batch->gmem_state` before the library can read it.
- The per-name time is CPU wall clock from replay start to the end of the wait in the plug-in, per command buffer. It is not the kernel's `the GPU worked` figure and is shared by every name in the command buffer.
- `sweetgpu_swipe=90` (synthetic swipe every 3 s) is in both images because the user is away. pA and pB share that workload; neither is comparable with the hand-touched 0162 runs.
- Bin counters are per process, batch counters per context; with `sweetmetal_nolock=1` (not set here) all figures are approximate.

## Patch 0013 on the device, 0163pA and 0163pB, 2026-11-13 (real device, one boot each, unattended, synthetic swipes)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13 | `shim-boot-0163pA.img` (ecd50afe...), root `work1.raw` + payload 0001-0013 (library a9e8c642..., plug-in 6922f55c...); `userdata` flashed by the lead on the user's typed pre-authorisation, snapshot `work1-pre0013.raw` | `tools/metal-flash-test.sh ~/Developer/ios-sweet-work/root/work1.raw shim/out/shim-boot-0163pA.img 0163pA 420` (flash 461 s, back in fastboot after 334 s) | `passlog:` lines; no fault | 440 `passlog:` lines; open line in backboardd, SpringBoard, metaltest: `FD_MESA_DEBUG=0`, screen created by this open, hook found. No `SMMU gfsr`, `fault address`, `THE GPU DID NOT FINISH`, `table arena full`. `sweet-passlog-summary.py`, backboardd busy blocks: 198 s, 2148 command buffers (10.9/s), 97.4 draws/cb, 2.0 flushes/cb, 6.4 batches/cb = sysmem 4.37 + GMEM 1.81 + nondraw 0.26, 41.7 bins per GMEM batch (max 54); **57.5 ms per command buffer**. `sweet-subs-per-swap.py`: 198 active s, 2212 swaps, max 18/s, subs/swap 4.0. `the GPU worked`: last six intervals 3.7-4.8 s of submit-to-done per interval of about 5 s, 209-269 submissions each | `logs/xnu-0163pA.txt` |
| 2026-11-13 | `shim-boot-0163pB.img` (7dd512a9...), same root and payload, nothing flashed, + `sweetmetal_fddebug=sysmem` | `tools/sweet-boot-test.sh shim/out/shim-boot-0163pB.img 0163pB 420` (lead, RAM only) | GMEM batches go to 0 if the flag is real; faster or not | Open line `FD_MESA_DEBUG=0x200 (sysmem on ...)`, screen created by this open. backboardd busy blocks: 199 s, 2159 command buffers (10.8/s), 97.6 draws/cb, 6.5 batches/cb = **sysmem 6.18 + GMEM 0.00** + nondraw 0.28; **58.7 ms per command buffer**. 199 active s, 2174 swaps, max 17/s, subs/swap 3.9. No fault lines, no `table arena full`. Last six intervals 3.2-4.4 s of submit-to-done per about 5 s | `logs/xnu-0163pB.txt` |

Reading (lead, two logs, `experimental`):

- **The sysmem flag is real and changes nothing.** 1.81 GMEM batches of about 42 bins per frame become sysmem batches and the frame costs the same (57.5 against 58.7 ms). Tiling is not what costs us on this workload. This closes reading (b) of `FRAME_RATE_RESEARCH.md` section 6.
- **A frame is one command buffer of about 97 draws and it takes about 58 ms**, nearly all of it waiting: about 4 submissions per frame at 17-19 ms submit-to-done each, the GPU side occupied about 75-80 % of the time. 97 draws in 58 ms is 0.6 ms a draw.
- **`luma_boost` is not the cost here.** The only candidate name, `...PBGRAXm_TlubA2Xhf_` (truncated; unconfirmed that it is luma boost), is 29 draws of 209000 in pA. The names are cut at 47 characters and all start with `com.apple.coreanimation.draw.`, so suffixes are lost: fix in the plug-in before relying on names.
- The top name is `...PBGRABsovXm_TimgA2` (image, source-over), about 45 draws a frame; then `...PBGRAXm_TcimBdsoA2` (17), `...PBGRABsovXm_TmuaA2` (9), `...PBGRAXm_A2Xhfc` (7).
- Per-name time is the command buffer's, so every name that is in every frame shows the same 57-59 ms: the log ranks command buffers, not draws. A per-batch or per-draw GPU time needs another change.
- Workload caveat: page swipes every 3 s from `sweetgpu_swipe=90`, nobody at the phone. Not comparable with 0162sA/sB (hand touches; 9.6 swaps per active s there, 11 here).

0013: `partially-working` (two boots, the counters agree with the flag); passlog adds no fault. 0012's effect on the render mode: `partially-working` (one boot, 0163pB).

## 750x1624 with passlog, 0164z2, 2026-11-13 (real device, one boot, unattended, synthetic swipes)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13 | `shim-boot-0164z2.img` (37985535...), the 0163pA args built with `SWEET_SCALE=2`; same root and payload, nothing flashed | `tools/sweet-boot-test.sh shim/out/shim-boot-0164z2.img 0164z2 420` (lead, RAM only) | If the frame cost is pixels, 2.25 times less | `SWEET FB: device tree canvas 750x1624 ... scaled to the panel`. backboardd busy blocks: 194 s, 2703 command buffers (13.9/s), 81.3 draws/cb, 6.2 batches/cb = sysmem 4.19 + GMEM 1.77 + nondraw 0.21, 18.9 bins per GMEM batch; **42.7 ms per command buffer** (pA 57.5). 195 active s, 2796 swaps, max 22/s. Self-test 17 of 21. No fault lines | `logs/xnu-0164z2.txt` |

Kernel wait accounting, last 20 statistics intervals of each log (host arithmetic on `RedwoodGPU:` lines, `experimental`):

| Log | Wall | Waits for the GPU | Cache flush in submit | IOSurface take |
| --- | --- | --- | --- | --- |
| 0162sA | 122 s | 915 waits, 7.9 s (6 %) | 6.5 s (5 %) | 1.9 s (2 %) |
| 0163pA | 102 s | 1200 waits, 17.2 s (17 %) | 4.3 s (4 %) | 2.5 s (2 %) |
| 0163pB | 101 s | 1154 waits, 16.3 s (16 %) | 4.3 s (4 %) | 2.4 s (2 %) |
| 0164z2 | 102 s | 1468 waits, 5.9 s (6 %) | 2.4 s (2 %) | 1.4 s (1 %) |

Reading (lead, `experimental`):

- Command buffers occupy about 63 % of wall time in pA (10.9/s x 57.5 ms) and the kernel waits on the GPU for 17 %. About 40 of the 58 ms of a frame is therefore not a wait for the GPU: it is spent before the wait, in the plug-in, the library, Mesa or the submit call. Whether that time is on a processor or blocked is not known (no profile yet).
- `the GPU worked N us` is from the ring write to the first look that finds the submission done, and looks happen only while somebody waits (`SweetAdreno.cpp` 522-546, read 2026-11-13 in `~/Developer/ios-sweet-work/cxnu`). With one wait per command buffer the earlier submissions of a frame are noticed late, so that figure overstates GPU execution. The 0161wA2 reading "a command buffer takes about 80 ms on the GPU" is withdrawn.
- Two points give a rough split (different draws per frame, so indicative only): 57.5 = a + b and 42.7 = a + 0.444 b give a fixed part of about 31 ms and a pixel part of about 27 ms at 1125x2436.

## Library lock off with passlog, 0164nL, 2026-11-13 (real device, one boot, unattended, synthetic swipes)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13 | `shim-boot-0164nL.img` (05bad1db...), the 0163pA args + `sweetmetal_nolock=1`; payload 0001-0013, nothing flashed | `tools/sweet-boot-test.sh shim/out/shim-boot-0164nL.img 0164nL 420` (lead, RAM only) | Faster if the library's serialising lock (0009) is part of the frame | `NOT serialized` in three processes. backboardd busy blocks: 219 s, 2155 command buffers (9.8/s), 96.8 draws/cb; **61.7 ms per command buffer** (pA 57.5). 199 active s, 2132 swaps. Self-test 17 of 21. No fault lines. Passlog figures are approximate without the lock (0013 note) | `logs/xnu-0164nL.txt` |

Reading: the lock of 0009 is not what the frame waits on. `partially-working` (one boot).

## Patch 0014 (boot-arg `sweetmetal_prof=1`, sampling profiler; passlog names and thread CPU time), 2026-11-13 (host)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13 | 0014 on 0001-0013 in `metal-build/donor`, plug-in only (`opus-impl`; `reviewer`: ACCEPT-WITH-FIXES, all six items applied by `opus-impl`; the stop window and the register/unregister paths read by the lead) | `tools/check-patch.py`; fresh worktree of the donor commit + 0001..0014, `cmp` | The series reproduces the build tree; library source untouched | `ok`; `redwoodmetal.m` identical, `air_metal.c` identical | `userland/metal/0014-prof.patch` (6a39d99a16a7ed25...) |
| 2026-11-13 | the profiler block (between the `0014 prof: begin/end` markers) built alone for this Mac, **x86_64**, with the arm64 register names mapped in the test file | `scratchpad/prof-host/run.sh donor/userland/src/redwoodmetal.m && ./prof_test`, `leaks --atExit` (run by `opus-impl`, not rerun by the lead) | No crash or hang; samples; a second thread refused; a thread that exits registered is dropped and sampling resumes | 2679 samples, 5185 unsampled registrations, 1 error only after the leaked exit, target cleared in 1.1 ms, 268 samples after it, the spin function named in a `prof: leaf` row, 0 leaks. NOT covered: the arm64 register reads, the `api` table (every host sample was `(none)`) | scratchpad, not kept in git |
| 2026-11-13 | same | `bash tools/metal-build.sh driver`, `test`, `payload` (`driver` wipes `obj/`, so `test` must follow it) | Plug-in changes, library does not | Plug-in 6922f55c... -> **c466594f...**; library a9e8c642... and `metaltest` 142d6a49... unchanged | `metal-build/pay/` |
| 2026-11-13 | kernel 0161 | `tools/sweet-gpu-image.sh` with the 0163pA args + `sweetmetal_prof=1` | `RAMDISK MATCH`, args read back | MATCH; 09073ea3...; args read back | `shim/out/shim-boot-0165fA.img` |

Notes:

- The sampler stops the replaying thread about once a millisecond (suspend, read registers and frame pointers, resume). Stopped time is in the wall figure and not in the CPU figure, so cpu/wall of a prof boot is not comparable with a passlog-only boot, and frame times of a prof boot are a few percent high.
- A sample is one millisecond of wall time of the replaying thread inside a command buffer, on a processor or blocked. `ours` skips the link register unless the pc is in one of our images.

## Patch 0014 on the device, 0165fA, 2026-11-13 (real device, one boot, synthetic swipes)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13 | `shim-boot-0165fA.img` (09073ea3...), payload 0001-0014 (plug-in c466594f..., library a9e8c642...), flashed by the lead on the user's pre-authorisation, snapshot `work1-pre0014.raw` | `tools/metal-flash-test.sh ... 0165fA 420`; `tools/sweet-prof-symbols.py logs/xnu-0165fA.txt` | Top functions of the replay thread | 64946 samples (72 % running), 1617 command buffers sampled, 0 errors, 0 dropped, no `THREAD_RESUME FAILED`. `api`: `rwa_render_draw` 67.7 %, `rwa_finish` 31.1 %. `ours`: `bind_stage` 56.6 %, `drmCommandWrite` 28.3 %, `drmCommandWriteRead` 8.4 %. `leaf`: `_platform_memmove` 56.5 %, `mach_msg2_trap` 36.8 %; all Mesa draw encoding together under 7 %. **Faults in this boot only:** 14 `SMMU gfsr`, 9 `fault address`, 9 `THE GPU DID NOT FINISH`, 8 `table arena full` (first at log line 4244, late); whether the sampler's stops provoked them is not established. Self-test 17 of 21 | `logs/xnu-0165fA.txt` |

## Patch 0015 (uniform upload size; boot-arg `sweetmetal_ubowhole=1` = old behaviour), 2026-11-13

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13 | 0015 on 0001-0014 (`opus-impl`; `reviewer`: ACCEPT-WITH-FIXES, the wanted host cases added, two low items accepted as they are: possible 64-byte over-fetch if ir3 widens a load, a wrap that needs a 32-bit `size_t`), host softpipe x86_64 | `air_metal_test --draw-ubo ubo.metallib`, `--draw-scissor`, `--clear` (run by `opus-impl`) | Same texel in both modes; fewer bytes | `fs_ptr` (`c[0]` at byte 20 of 2048): 64 against 2028 bytes, same texel, PASS. `fs_any` (unbounded index): rest of buffer, PASS. `fs_none`: 64 bytes, PASS. **`fs_and` (`c[(x+5)&7]`): FAIL as a saving, correct as a picture**: the bound is not found (`iand -> u2u64 -> u2u32 -> ishl`) and the rest of the buffer is uploaded. Scissor and clear pass | `userland/metal/0015-ubo-upload-size.patch`; `ubo.metal` in the scratchpad, not in git |
| 2026-11-13 | same | `tools/metal-build.sh ios`, `driver`, `test`, `payload` | - | library a9e8c642... -> **accfbc7a...**, plug-in c466594f... -> **e7ba170e...**, `metaltest` unchanged; `_rwa_set_ubo_whole` exported | `metal-build/pay/` |
| 2026-11-13 | `shim-boot-0166uA.img` (52839803...), payload 0001-0015 flashed by the lead (user present), snapshot `work1-pre0015.raw`; passlog on, profiler off | `tools/metal-flash-test.sh ... 0166uA 420` | Faster | `uniform uploads: what the shader reads`. backboardd busy blocks: 198 s, **3699 command buffers (18.7/s)**, 96.8 draws/cb. 197 active s, **3710 swaps**, max 29/s. About 30000 uploads and 31 MB per 5 s block, of which about 110 uploads are `unbounded` and carry nearly all the bytes. No fault lines. Self-test 17 of 21. Picture not judged | `logs/xnu-0166uA.txt` |
| 2026-11-13 | `shim-boot-0166uB.img` (d080635e...), same payload + `sweetmetal_ubowhole=1` | `tools/sweet-boot-test.sh ... 0166uB 420` (RAM only) | As before the patch | `uniform uploads: rest of the buffer (forced ...)`. 197 s, **2183 command buffers (11.1/s)**, 97.7 draws/cb. 198 active s, **2218 swaps**, max 18/s. No fault lines | `logs/xnu-0166uB.txt` |

Reading: same payload, same workload, one boot each: 11.1 -> 18.7 command buffers per busy second (+68 %), 2218 -> 3710 swaps. 0015: `partially-working`. Left: the unbounded uploads; `sweetfb_hz=30` now caps the best second (29).

## sweetfb_hz=60 on 0015, 0167h60, 2026-11-14 (real device, RAM boot, not a clean run)

- Image `shim-boot-0167h60.img` (aee58e06...), 0015 payload, passlog on, profiler off, `sweetfb_hz=60`, synthetic swipes.
- Log: 12 `SMMU gfsr`, 14 `THE GPU DID NOT FINISH`, 8 `table arena full`. Screen went black; the user put the phone back in fastboot. Not a valid frame-rate result (the 1051 swaps / 42 per s figure is from a broken run).
- Reading: 60 Hz exposes the GPU address-space and fault problems; do not compare it with 0166uA/uB.

## 60 Hz with sysmem, 0168s60, 2026-11-14 (real device, RAM boot, one boot, synthetic swipes)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-14 | `shim-boot-0168s60.img` (4b582cf0...), kernel 0161, payload 0001-0015 on the phone, nothing flashed; the 0167h60 args + `sweetmetal_fddebug=sysmem` | `PATH=$HOME/Developer/ios-sweet-work/bin:$PATH bash tools/sweet-gpu-image.sh ...` with `SWEETFB_HZ=60`; `tools/sweet-boot-test.sh shim/out/shim-boot-0168s60.img 0168s60 420` (lead) | No fault if the 0167h60 fault is the GMEM restore over-fetch (`FPS_INVESTIGATION.md` section 2) | `FD_MESA_DEBUG: sysmem` in backboardd and SpringBoard; **0** `SMMU gfsr`, 0 `THE GPU DID NOT FINISH`, 0 `table arena full`. backboardd busy blocks: 208 s, 3573 command buffers (17.2/s), 96.5 draws/cb, 6.3 sysmem + 0 GMEM batches. 26.1 ms a command buffer, 9.3 ms of it thread CPU; 3682 waits of 16.9 ms; 986 us a submission in the kernel walk, 4.0 submissions a cb; surface take 2.1 ms; panel copy 4.9 ms. 168 active s, 3588 swaps, **max 29 a second, none above** | `logs/xnu-0168s60.txt` |

Reading: consistent with section 2 (one boot; 0166uA also had no fault at 30 Hz, so this does not prove it). At 1125x2436 a frame is over 16.7 ms, so every frame takes two ticks of the 60 Hz grid: 30 a second is the ceiling at this size whatever the copy rate. `partially-working`.

## 750x1624 at 60 Hz with sysmem, 0168z60, 2026-11-14 (real device, RAM boot, one boot, synthetic swipes)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-14 | `shim-boot-0168z60.img` (c86f35a9...), the 0168s60 args built with `SWEET_SCALE=2`; kernel 0161, payload 0001-0015, nothing flashed | `tools/sweet-boot-test.sh shim/out/shim-boot-0168z60.img 0168z60 420` (lead) | GPU wait about 4 ms, a frame under 16.7 ms | 0 fault lines; no backboardd or SpringBoard crash (assetsd, MapKit, driverkitd did, as in other boots). backboardd busy blocks: 199 s, **5518 command buffers (27.8/s)**, 84.8 draws/cb. **9.6 ms a command buffer**, 5.9 ms of it thread CPU; 5539 waits of 3.8 ms; 482 us a submission in the kernel walk, 4.0 a cb; surface take 0.9 ms; panel copy 4.7 ms. 176 active s, 5533 swaps; per second: **max 57**, 27 seconds at 50-59, 24 at 40-49; in the seconds of 50 or more, 3 to 17 frames each took two ticks (`33 ms longest`). Picture not judged: the only screenshot in the log is the boot bar | `logs/xnu-0168z60.txt` |

Reading: against 0168s60 one change (the size): 26.1 -> 9.6 ms a command buffer, best second 29 -> 57. Not sustained 60: frames that miss a tick remain. The per-second figures mix swipes and pauses, so they are a floor, not a frame-time distribution. `partially-working` (one boot).

## Top CPU frequency at 750x1624, 0168zM, 2026-11-14 (real device, RAM boot, one boot, synthetic swipes)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-14 | `shim-boot-0168zM.img`, the 0168z60 image built with `SWEET_CPUMAX=1` (shim: gold perf state 13 = 2304 MHz, silver 9 = 1805 MHz; default 10 and 8) | `tools/sweet-boot-test.sh shim/out/shim-boot-0168zM.img 0168zM 420` (lead) | Less thread CPU a frame | 0 fault lines, no backboardd or SpringBoard crash. 5583 command buffers in 197 busy s (28.3/s); **9.15 ms a command buffer** (0168z60: 9.61), **5.37 ms thread CPU** (5.92); waits 3.8 ms; walk 456 us a submission; best second 59 swaps (57); frames taking two ticks in the seconds of 50 or more: 5.5 on average (7.7). Peak 58.5 C CPU (53.7). The shim's `CPUFREQ` line is on the shim console, not in the pulled log: the state is inferred from the 9 % and the 5 C, not read | `logs/xnu-0168zM.txt` |

Reading: a small gain, inside what one boot can show. `experimental`. No thermal limit exists in this kernel: not a default until one does.


**Correction 2026-11-14 (user, photos of boot 0169pl):** at 750x1624 the screen shows only a strip at the top (part of the dock), glitching; touch works. The 750x1624 figures of 0168z60, 0168zM and 0164z2 are therefore NOT valid frame-rate evidence: a mostly empty frame is cheap. Which of the size, sysmem at that size, or kernel 0162 causes the strip is not established (0169pl changed the kernel as well). Do not boot `SWEET_SCALE=2` again until the picture is explained. Valid result of this phase: 0168s60 only (1125x2436, 26.1 ms, best second 29, 0 faults).

## Kernel 0162 gpu_pagelist, 0169pf, 2026-11-14 (real device, RAM boot, one boot, synthetic swipes, full size 1125x2436)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-14 | `shim-boot-0169pf.img` (ecdc6358...), kernel 0162 (CI 43588677901, sha256 a4ef071f...), payload 0001-0015, `gpu_pagelist=1`; nothing flashed | `tools/sweet-boot-test.sh shim/out/shim-boot-0169pf.img 0169pf 420` | `page lists kept` in the summary | gfsr, notfinish, arena empty; crashes MapKit 4, com.apple.mobile 3, assetsd 3, mediaserverd 1, no backboardd or SpringBoard. `cleared 40 ms after`; `page lists kept for the walk before a submission (gpu_pagelist)`. busy 146 s, 1892 cbs (12.9/s), 180389 draws (95.3/cb), flushes 2.0/cb, batches 17.7/cb (sysmem 17.26 + gm); **wall/cb 27.56 ms, cpu/cb 15.80 ms**; 1909 waits of 12076 us; 12292 submissions, flush 1251 us/sub, first cleans 2122 of 12712 MB; surface take 2068 us; panel copy 3835 us. 1781 swaps, best second 36, 82 active s (20.1/s); 237 seconds at 0-9, 39 at 10-19, 37 at 20-29, 6 at 30-39, none at 40 or more. Kept memory: 1000 reused, 12 made. Peak 55.6 C cpu and big, 52.1 gpu | `logs/xnu-0169pf.txt` |

Reading (mechanical, 0168s60 baseline `wall/cb 26.1`, `cpu/cb 9.3`, `flush 986 us/sub`, faults 0): gfsr, notfinish and arena are empty and there is no `CRASH backboardd` or `CRASH SpringBoard`, but `wall/cb` is 27.56 ms, i.e. 1.46 ms higher, not lower by 0.5 ms. Condition failed: `wall/cb` lower. Not better. `experimental` (one boot).

## Kernel 0162 gpu_pagelist + sweet_surfclear_ms=0, 0169sf, 2026-11-14 (real device, RAM boot, one boot, synthetic swipes, full size 1125x2436)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-14 | `shim-boot-0169sf.img` (e6c4fff9...), kernel 0162 (CI 43588677901, sha256 a4ef071f...), payload 0001-0015, `gpu_pagelist=1 sweet_surfclear_ms=0`; nothing flashed | `tools/sweet-boot-test.sh shim/out/shim-boot-0169sf.img 0169sf 420` | `cleared 0 ms after` in the summary | gfsr, notfinish, arena empty; crashes com.apple.mobile 2, assetsd 2, driverkitd 1, no backboardd or SpringBoard. `cleared 0 ms after`; `page lists kept for the walk before a submission (gpu_pagelist)`. busy 240 s, 4319 cbs (18.0/s), 392309 draws (90.8/cb), flushes 2.0/cb, batches 7.1/cb (sysmem 6.86 + gmem); **wall/cb 24.44 ms, cpu/cb 9.01 ms**; 4483 waits of 15544 us; 18149 submissions, flush 957 us/sub, first cleans 893 of 293 MB; surface take 2156 us; panel copy 3626 us. 4370 swaps, best second 42, 203 active s (20.9/s); 116 seconds at 0-9, 75 at 10-19, 125 at 20-29, 2 at 30-39, 1 at 40-49, none at 50 or more. Kept memory: 4000 reused, 19 made. Peak 55.6 C cpu and big, 51.4 gpu | `logs/xnu-0169sf.txt` |

Reading (mechanical, 0168s60 baseline `wall/cb 26.1`, `cpu/cb 9.3`, `flush 986 us/sub`, faults 0): gfsr, notfinish and arena are empty and there is no `CRASH backboardd` or `CRASH SpringBoard`, and `wall/cb` is 24.44 ms, i.e. 1.66 ms lower. Better. `experimental` (one boot). Batches per command buffer differ between the two boots (17.7 vs 7.1), so the boots are not the same workload.

## Kernel 0162 controls and the 0169sf repeat, 2026-11-14 (real device, RAM boot, one boot each, full size 1125x2436)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-14 | `shim-boot-0169a.img` (`1a5b490f...`), kernel 0162, **no** 0162 boot-arg | `tools/sweet-boot-test.sh shim/out/shim-boot-0169a.img 0169a 420` | reference for the two flags | gfsr, notfinish, arena empty, no backboardd or SpringBoard crash. `cleared 40 ms after`, no `page lists kept`. busy 242 s, 4123 cbs (17.1/s), 399368 draws (96.9/cb), batches 6.3/cb; **wall/cb 25.64 ms, cpu/cb 8.91 ms**; 4188 waits of 16897 us; 16128 submissions, flush 949 us/sub, first cleans 3856 of 41036 MB; take 2125 us; present 4658 us. 4139 swaps, best second 29, 213 active s (18.8/s). Kept memory (zeroed now): 4000 reused, 16 made. Peak 55.3 C | `logs/xnu-0169a.txt` |
| 2026-11-14 | `shim-boot-0169pg.img` (`b3a1a833...`), kernel 0162 + `gpu_pagelist=1` | `tools/sweet-boot-test.sh shim/out/shim-boot-0169pg.img 0169pg 420` | lower flush time | gfsr, notfinish, arena empty, no backboardd or SpringBoard crash. `page lists kept ... (gpu_pagelist)`. busy 197 s, 3589 cbs (18.2/s), 348271 draws (97.0/cb), batches 6.4/cb; **wall/cb 25.60 ms, cpu/cb 8.70 ms**; 3626 waits of 16987 us; 14087 submissions, **flush 892 us/sub**, first cleans 3801 of 41536 MB; take 2091 us; present 3651 us. 3644 swaps, best second 29, 169 active s (20.8/s). Peak 57.9 C | `logs/xnu-0169pg.txt` |
| 2026-11-14 | `shim-boot-0169sf2.img`, the 0169sf image booted a second time | `tools/sweet-boot-test.sh shim/out/shim-boot-0169sf.img 0169sf2 420` | repeat of 24.44 ms, or noise | gfsr, notfinish, arena empty, no backboardd or SpringBoard crash. `cleared 0 ms after`. busy 201 s, 3724 cbs (18.5/s), 359524 draws (96.5/cb), batches 6.3/cb; **wall/cb 25.46 ms, cpu/cb 8.70 ms**; 3776 waits of 16856 us; 14530 submissions, flush 905 us/sub, first cleans 679 of 195 MB; take 2151 us; present 4673 us. 3736 swaps, best second 29, 169 active s (21.3/s). Peak 59.5 C | `logs/xnu-0169sf2.txt` |

**Correction of the 0169sf reading:** the 24.44 ms of the first `sweet_surfclear_ms=0` boot did not repeat (25.46 ms). Against 0169a the three boots are 25.64 / 25.60 / 25.46 ms, so at 1125x2436 neither flag lowers the frame time by the 0.5 ms the rule asks. What they do change is measured and repeatable: first cleans 41 GB -> 0.2 GB, flush 949 -> 892-905 us/sub (pagelist), and the kept memory is `zeroed already` (the kernel thread call clears at once) instead of `zeroed now` (the window server's thread pays it). At this size the frame is 16.9 ms of GPU wait, so ~1.5 ms of CPU and clean work does not move the wall time. Not better at 1125x2436.

## Kernel 0163 (scaled band destination fix), 0163z, 2026-11-14 (real device, RAM boot, one boot, synthetic swipes, 750x1624)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-14 | `shim-boot-0163z.img` (`11c382c8...`), kernel 0163 (CI 43593893565, sha256 `dedd83d3...`), payload 0001-0015, `SWEET_SCALE=2`, args A + `gpu_pagelist=1 sweet_surfclear_ms=0` | `tools/sweet-boot-test.sh shim/out/shim-boot-0163z.img 0163z 420` (user watching) | the whole screen scaled 1.5x, not the strip | gfsr, notfinish, arena empty; `CRASH AegirPoster` 50 restarts (also 50 in 0168s60, 0 in 0168z60 and 0169a: intermittent, same pc `0x1cb1e7198`), no backboardd or SpringBoard crash. `cleared 0 ms after`; `page lists kept`. busy 215 s, 4319 cbs (20.1/s), 444039 draws (102.8/cb), batches 14.2/cb; **wall/cb 12.93 ms, cpu/cb 9.57 ms**; 4312 waits of 3492 us; 25600 submissions, flush 600 us/sub, first cleans 977 of 177 MB; take 953 us; **present 4910 us**. 4217 swaps, best second 56, 136 active s (30.4/s); 183 seconds below 10, 35 at 10-19, 27 at 20-29, 35 at 30-39, 31 at 40-49, 8 at 50-59. Peak 56.0 C | `logs/xnu-0163z.txt` |

User, watching: the picture is very pixelated (nearest 1.5x, expected); the wallpaper is missing; smoothness not judged by eye. Kernel screenshot (`tools/sweet-shot.py`, truncated tail): home screen icons and text over the whole width, so the band fix works. Against 0168z60 (strip boot, 9.6 ms, best 57): the full panel write costs 3.3 ms a command buffer and the fast seconds drop to 8; against full size (0169a: 25.6 ms, best 29) the best seconds double.

## Kernel 0163 at native resolution, 0163n, 2026-11-14 (real device, RAM boot, one boot, synthetic swipes, 1125x2436)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-14 | `shim-boot-0163n.img` (`35ab934f...`), kernel 0163, native ADT (1125x2436), args A + `gpu_pagelist=1 sweet_surfclear_ms=0` | `tools/sweet-boot-test.sh shim/out/shim-boot-0163n.img 0163n 420` | the native reference with the 0162 flags | gfsr, notfinish, arena empty; `CRASH AegirPoster` 50 restarts, no backboardd or SpringBoard crash. **wall/cb 26.56 ms, cpu/cb 9.42 ms**; 3771 waits of 17212 us; 14455 submissions, flush 986 us/sub; take 2140 us; present 3966 us; 3620 swaps, best second 29, 168 active s (20.7/s), none at 30 or more. Peak 57.9 C. `SWEET GPU: gfx3d cfg 0x101 dcvs perf 0x30000006 return 0` = the GMU accepted perf level 6 (650 MHz) | `logs/xnu-0163n.txt` |

Reading: the 0162 flags and 0163 change nothing at native (25.6-26.6 ms across five boots). 0163 only touches the scaled path, as intended. The GPU clock is at the top level the GMU accepts, so the 16.9 ms GPU wait of a frame cannot be bought down with a vote; the remaining lever is CPU/GPU overlap, spec `SPEC-0016-commit-no-wait.md`.

Note: `tools/sweet-plog-pull.sh` (new) reads the shim probe log from userdata. The area it reads held the 0163n text (seq 39) after the 0163d boots too, so that region is stale and must not be trusted for a fresh boot; the kernel log is the reliable channel (`SWEET GPU: gfx3d ... dcvs perf`).

## Userland 0016 (commit without the fence), host softpipe, 2026-11-14 (no device, no flash)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-14 | `metal-build/donor` at `a79ff07` + `userland/metal/0001-0016`, `tools/metal-build.sh` all stages | `ninja src/gallium/drivers/freedreno/air_metal_test`; `air_metal_test --draw-deferred dw.metallib`; `--clear` | the 0011 case still gives the same picture and bytes with `rwa_flush` before its one `rwa_finish` | `per draw` PASS, `deferred` PASS, `per draw and deferred give the same bytes` PASS, 0 checks failed; `--clear` 0 cases failed. Softpipe runs work at flush, so this proves order and result without the waits, not overlap | `tools/air/dw.metal`, `userland/metal/0016-commit-no-wait.patch` |

Note: `dw.metal` needs one function per compilation (`xcrun metal -c -DENTRY_fs_pos` / `-DENTRY_fs_copy`,
then `metalib`): a .metallib holds one LLVM module per function and `rwa_render_create` takes the
module's own entry point, so a module with two functions answers for only the first
("this module's entry point is fs_pos"). No vertex function: a draw with no vertex stream gets a
fullscreen quad from the library and `[[position]]` is the pixel centre.

## Userland 0016 v1 on the device (commit returns at submit, fence paid by a `rwa_finish` at the next commit), 0164a, 2026-11-14 (real device, RAM boot, one boot each, synthetic swipes, 1125x2436)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-14 | `shim-boot-0164a.img` (`25d0a3e6...`), kernel 0163, root `work1.raw` + payload 0001-0016 v1 (library `2a9802ec...`, plug-in `2bd7ea9b...`), flashed `userdata` (rollback = the two 0015 files in `root/rollback-0015/`) | `fastboot -S 512M flash userdata 0164a.simg`, then `tools/sweet-boot-test.sh shim/out/shim-boot-0164a.img 0164a 420` | overlap: wall/cb down, swaps up, no fault | Mode line `GPU commit: returns once the work is submitted` in 3 processes. wall/cb 13.52, cpu/cb 19.62 (the accounting moved: the wait is no longer inside commit), waits mean 11039 us (was 16904), **18.4 swaps/s over 213 active s, best second 33**, 17 s at 30-39. But **batches 15.6/cb (6.5 before), subs 26220 (16679), first cleans 906 of 519 MB (187 MB)**: the start-of-commit `rwa_finish` flushes again and ends the next batch early | `logs/xnu-0164a.txt` |
| 2026-11-14 | same root and image, args + `sweetmetal_commitwait=1` | `tools/sweet-boot-test.sh shim/out/shim-boot-0164b.img 0164b 420` | the old serial path for the A/B | Mode line `GPU commit: waits for the GPU (forced by boot-arg ...)`. wall/cb 17.95, cpu/cb 9.00, waits mean 9048 us, **23.7 swaps/s over 172 active s**, 44 s at 30-39, batches 6.5/cb, subs 16679, cleans 187 MB | `logs/xnu-0164b.txt` |

Verdict: v1 is **slower** than the control it was supposed to beat (18.4 against 23.7 swaps/s), and the log says why -- paying the fence with `rwa_finish` adds a flush per frame, which splits the next batch (batches/cb 6.5 -> 15.6, submissions +57%, cache cleans 2.8x) and adds more GPU work than the 8 ms of overlap saves. v2 keeps the submission's own fence instead (`rwa_flush` returns it, `rwa_wait_fence` waits for it and touches no batch). Not yet on the device.

## Userland 0016 v2 on the device (the submission's own fence), 0164c, 2026-11-14 (real device, RAM boot, 1125x2436)

| Date | Build | Procedure | Expected | Actual | Artifacts |
| --- | --- | --- | --- | --- | --- |
| 2026-11-14 | `shim-boot-0164c.img` (`fe872503...`), kernel 0163, root `work1.raw` + payload 0001-0016 v2 (library `d604ff13...`, plug-in `d9112327...`) | `fastboot -S 512M flash userdata 0164c.simg`, `tools/sweet-boot-test.sh shim/out/shim-boot-0164c.img 0164c 420` | batches per command buffer back to ~6, swaps above the 23.7 of 0164b | Mode line `GPU commit: returns once the work is submitted` in 3 processes. Batches 5.7/cb (**the v1 batch split is gone**), subs 11160 (16679), cleans 323 MB (519). But 19.8 swaps/s over 185 active s (best second 28) and **waits mean 16659 us, 3841 waits for 3794 cbs**: one wait a frame, 16.7 ms, and the passlog says it is not inside `-commit` (cpu 9.63, wall 9.58). It is CoreAnimation calling `-waitUntilCompleted` after every commit | `logs/xnu-0164c.txt` |

Verdict: v2 is neither a win nor a regression against v1 (18.4 / 19.8 / 23.7 across 0164a / 0164c / 0164b, and 0164b is the only boot of the three without the AegirPoster crash loop, so the A/B is confounded). The mechanism is now measured rather than guessed: **the client waits for the frame's own fence every frame**, so no commit-side change can overlap the CPU with the GPU. `waits`/`cbs` = 1.01 in all three boots. 0016 cannot pay for itself while that wait exists; it is not the lever.

## Where the 1125x2436 frame goes, 0164c (backboardd, steady state, one 5 s interval)

| Part | Time | Source |
| --- | --- | --- |
| Replay + submit, thread CPU | 9.5 ms | passlog `110 cbs, 10873 draws, cpu 1044.94 ms of wall 1045.79` |
| of it, per draw | 96 us | 10873 draws / 1044.94 ms |
| GPU, paid outside `-commit` | 16.7 ms | `waits 3841 mean 16659 us` |
| Panel copy (kernel vsync thread, 3 helpers) | 3.5-4.5 ms | `presents (3554-4783 us average)` |
| Kernel walk + surface take | 3.7 + 2.1 ms | `FPS_INVESTIGATION.md` 1, same kernel |
| Sum | 35-38 ms | matches the measured `38 ms longest` swap gap in good seconds |

60 Hz needs 16.67 ms. Both halves are over it, and they are serial.

## The GPU curve against pixels, 0164c (1125x2436) against 0164e (750x1624), 2026-11-14 (one RAM boot each, kernel 0163, same flags, same synthetic swipes)

| Size | Pixels | GPU wait a frame | Replay CPU a frame | Panel copy | Take | Swaps/s (active s) | Best second |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 750x1624 (`SWEET_SCALE=2`) | 1.22 Mpx | 3.63 ms | 5.87 ms | 4.70 ms | 0.98 ms | 31.1 (175 s) | 57 |
| 1125x2436 (native) | 2.74 Mpx | 16.66 ms | 9.63 ms | 3.81 ms | 2.14 ms | 19.8 (185 s) | 28 |

2.25x the pixels costs **4.6x** the GPU time and 4.0x the cache cleaning (82 -> 323 MB). A linear fit through the two points gives a negative intercept, so no `a + b*pixels` model holds: the cost per pixel at native is about 6.1 ns against 3.0 ns at 2x. That is the shape of congestion (utilisation approaching a shared limit), not of a fixed per-frame cost. It also means the 2x numbers of 0168z60/0168zM were not comparable for a second reason beyond the strip bug: the picture was mostly empty.

Verdict: at 2x the good seconds reach 57 and the frame fits a 16.67 ms tick; at native the frame is 35-38 ms and no amount of commit-side work changes that. The native GPU cost is the thing to attack, and the mode it runs in is the workaround, not the design: `sweetmetal_fddebug=sysmem` because a GMEM batch restores an imported IOSurface whose height is not a multiple of 4 and reads past its mapped bytes (`FPS_INVESTIGATION.md` 2).

## The GPU's own occupancy, from the kernel's five-second line (`RedwoodGPU: the GPU worked ...`)

The number `GPU_DECISION.md` calls missing ("GPU execution per frame: no valid number") was in every
boot log already: submission latency (submit to fence) times submissions per second is the GPU's
queue depth, and a depth that never reaches zero is a saturated GPU.

| Boot | Size | Submission latency | Submissions/s | Queue depth (Little's law) | Meaning |
| --- | --- | --- | --- | --- | --- |
| 0164c | 1125x2436 | **23.8 ms** | 52 | **1.24** | never empty: the GPU is the wall for every client |
| 0164e | 750x1624 | 6.8 ms | 69 | 0.47 | about half busy: the frame is CPU and pacing there |

3.5x the latency for 2.25x the pixels, and at native the queue is always occupied, so the 1125x2436
frame is decided by GPU execution and by nothing else. 60 Hz allows 16.67 ms a frame: at native the
GPU alone needs 23.8 ms a submission and 2.6 submissions a frame go out, so no commit, pacing or copy
change can reach 60 -- only less GPU work per frame can, by roughly 3x. At 2x there is headroom and
the CPU (5.87 replay + 4.70 panel copy + 0.98 take per frame) is what holds 57 fps to bursts.

Consequence for the next boot: a GMEM (tiled) A/B at native is the only bandwidth lever left, and it
needs the over-fetch that forced `sweetmetal_fddebug=sysmem` fixed first (`FPS_INVESTIGATION.md` 2).
