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
