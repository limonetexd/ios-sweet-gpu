# Research ledger

claim | source | date | hardware | confidence

## Repository and upstream (read this session, 2026-11-08)

| Claim | Source | Date | Hardware | Confidence |
| --- | --- | --- | --- | --- |
| Local `gpu` = `main` = `origin/main` = `c5d9aca`; 399 commits, no tags, no stashes, no submodules | `git` | 2026-11-08 | n/a | high |
| `origin` is `limonetexd/ios-sweet-gpu`, not `DC28088/ios-sweet` as `CLAUDE.md` describes | `git remote -v` | 2026-11-08 | n/a | high |
| `userspace/native-metal` is absent locally and from all local history | `git log --all -- userspace/native-metal` | 2026-11-08 | n/a | high |
| Upstream `codex/native-adreno-metal` head `67448d2` (2026-11-03) contains it; 654 commits ahead of shared ancestor `9202e5a` | `gh api` compare | 2026-11-08 | n/a | high |
| Upstream main claims UI through native Metal; says stable 60 fps not achieved | DC28088 README | read 2026-11-08 | A618 | upstream claim |
| Upstream native-metal path: Metal → AIR → NIR → freedreno/ir3 → NativeAdreno ABI1, reusing existing kernel GPU driver | DC28088 `userspace/native-metal/README.md` | read 2026-11-08 | A618 | upstream claim |
| README here ("no GPU", "6 cores", 20–30 fps CPU) is stale against `NOTES.md` | README:8,17,33 vs NOTES:143-147, `sweet-gpu-image.sh` | 2026-11-08 | sweet | high |
| `tools/sweet-gpu-userland.py`, named by `userland/build-gpu.sh:11`, does not exist | `ls tools/` | 2026-11-08 | n/a | high |

## Device facts

| Claim | Source | Date | Hardware | Confidence |
| --- | --- | --- | --- | --- |
| `product: sweet`, `variant: SM7 UFS`, `secure: yes` | `fastboot getvar` (phone already in fastboot; `getvar all` not used) | 2026-11-08 | this phone | high |
| Effective A618 clock unresolved: code requests level 6 (650 MHz), PLL set for 430 MHz, ring `perf 0x30000006`, notes say 430 | `shim/gpuprobe.c:200,721,1238`; `notes/agents/xnu-gpu-kernel.md:472,483` | read 2026-11-08 | sweet | high that it is open |

## Frame-time figures (copied from NOTES.md; logs not available to re-derive)

| Claim | Source | Date | Hardware | Confidence |
| --- | --- | --- | --- | --- |
| 0143r native 36.0/38 swaps/s, GL 14.6/17.0, present 3.37 | NOTES:190 | 2026-11-07 | sweet | medium |
| 0143r2 750×1624 28.7/49, GL 6.3/12.6, present 4.89 (36 of 302 s normal) | NOTES:192 | 2026-11-07 | sweet | low |
| 0144r 33.6/45, GL 10.1/28 | NOTES:163 | 2026-11-07 | sweet | medium |
| 0146r 23.3/41, GL 9.5/13.5 | NOTES:146 | 2026-11-07 | sweet | medium |
| 42 % of swaps miss the tick, ~32 swaps/s sustained | NOTES:114 | 2026-11-07 | sweet | low |
| 6.5 ms in GL + 9.8 ms outside per frame | NOTES:869 | 2026-11-02 | sweet | low, stale |
| Attach ~5.7, delete ~2.8, `glFlush` 5.6 of ~19 ms; new IOSurface each frame | NOTES:637-640 | 2026-11-06 | sweet | medium |

## Third-party inputs

| Source | Commit | License | Note |
| --- | --- | --- | --- |
| `MakrSas/ios-topaz` | `e477291` (`userland.yml:20`) | **none detected** by GitHub API | Builds the GL userland; kernel patches also credit it. Needs resolving |
| `oosexgang/hackios-xnu-kernel` | `a3384e0` (`userland.yml:22`) | **NOASSERTION** | Needs resolving |
| Mesa 25.0.7 | via topaz script | not re-checked this session | Fetched at build |

GPL scan of `0082`, `0083`, `userland/*`, `shim/gpuprobe.c`: no `GPL` or `General Public` text. Absence of a marker does not establish provenance.

## REA

No REA calls this session. Blocked: none.

## Phase 1 (2026-11-08)

- Lines before 0139 hold "the GPU worked" inside one combined line with wrong numbers; the parser ignores them by anchoring on `RedwoodGPU: the GPU worked` | `xnu/patches/0139-sweet-gpu-stats.patch:4-6,57-69` | 2026-11-08 | none (source) | high
- The 0139 figure is the mean per timed submission, with a top histogram bucket of 4 ms and over; per-frame cost needs submissions per swap | same patch `:67-69` | 2026-11-08 | none (source) | high

## Phase 1b (2026-11-08, parsed from real-device rings; host fidelity)

- The 0139 "worked" figure is ring write to first look that finds the submission done, not GPU execution | `xnu/patches/0083-sweet-gpu-redwood.patch:500-523` | 2026-11-08 | sweet (source) | high
- That figure overlaps wall clock (0143r: 4.4 s of "work" per second) and one window averages 4.6 s with no slow-submission report | `logs/xnu-0143r.txt` | 2026-11-07 run | sweet | high
- 0143r: ring has work outstanding at 49 % of 1 Hz samples (lower bound; upper 72 %), and 48 % of ticks with a new frame find it unfinished | `logs/xnu-0143r.txt`, 0097 fields | 2026-11-07 run | sweet, 539 VA errors | medium
- `late` in SWEET FPS is a swap gap over 20 ms, not a missed vsync | `xnu/patches/0097c-sweet-fps-time-units.patch:42-44` | 2026-11-08 | sweet (source) | high
- `stale` counts ticks at which `drawn()` found the GPU not done; `presents` excludes repeats since 0112 | `0095:67-85`, `0112:43-55` | 2026-11-08 | sweet (source) | high
- Requested GPU clock in four native runs is level 4, 430000 kHz | `logs/xnu-*.txt.shim.txt:160` | 2026-11-07 runs | sweet | high that it was requested; low as the running clock
- eagl's big/little frame counter is contradicted by `sweetfb_bind` cpu 7 in the same runs; donor source not local | `logs/xnu-0143r.txt`, `0118-sweet-fb-bind-render-a76.patch` header | 2026-11-07 runs | sweet | high that it is unusable

## Phase 2 donor read (2026-11-08; recorded before opening the file)

- Read for field meanings only, nothing copied: `MakrSas/ios-topaz` `userland/gpu/eagl.c`, commit `e4772911e116ab4ab6c4ac1f38e6106fefe8b483` (`.github/workflows/userland.yml:19-20`), blob `d6591ecf`, 150780 bytes | GitHub API | 2026-11-08 | n/a | high
- License at that commit: repository field null, no LICENSE/COPYING/NOTICE file at the root (README only). Treat as all rights reserved: no code from it may be imported or paraphrased into this tree | GitHub API | 2026-11-08 | n/a | high

- Correction to Phase 1b: eagl's big/little counter is not contradicted by the cpu 7 binding. It only tests CPU number < 4, so cpu 7 counts as "little" | donor `eagl.c:1064-1072` at `e477291` | 2026-11-08 | n/a | high
- "in GL calls" excludes `glFlush`; "outside" = frame time minus that, so it contains the flush | donor `eagl.c:407,1028,1059-1063`; cross-checked against `logs/` on five runs | 2026-11-08 | sweet | medium-high
- Kernel log ring is 4 MiB; the largest kept 440 s log is 1.1 MB, which leaves room for per-swap lines | `0047:40`, `logs/xnu-0143r.txt` | 2026-11-08 | sweet | high

## Metal assessment (2026-11-08; public source read through the GitHub API, nothing imported, no REA calls)

- `hackios-xnu-userland` `a79ff07` transport opens service `RedwoodGPU`, uses `IOConnectCallStructMethod` and surface request `0x7e` | `tools/mesa/redwood-drm/redwood_drm.c:19-20,56` | 2026-11-08 | n/a | high that it targets this interface; struct match unverified
- Same repo: GitHub detects no license; root `LICENSE` first line reads "MIT License"; DC28088 calls it MIT | GitHub API | 2026-11-08 | n/a | confirm the full text before importing
- `DC28088/ios-sweet` has no repository license, so its own code cannot be imported | GitHub API | 2026-11-08 | n/a | high
- DC28088 native Metal path needs its NativeAdreno ABI1 kernel; first hardware trial crash-looped BackBoard on an AIR shader | `userspace/native-metal/README.md` at `67448d2` | 2026-11-08 | A618 | upstream claim
- DC28088 reports UI on native Metal and that stable 60 fps is not achieved | DC28088 README | 2026-11-08 | A618 | upstream claim
- `hakios-metal` targets chip id 0x06030500 | its README | 2026-11-08 | not A618 | high
- No iOS 16.7.16 Metal.framework, QuartzCore or GPU bundle on this Mac | local search of `~/Developer`, `~/Downloads`, depth 4 | 2026-11-08 | n/a | medium (bounded search)

## Metal viability check (2026-11-08)

- Donor `rwd_surface` matches our `redwood_surface` field for field; donor opens `RedwoodGPU` and maps msm requests by low byte | `hackios-xnu-userland` `a79ff07` `userland/src/redwood_drawable.h`, `tools/mesa/redwood-drm/redwood_drm.c`; `0083:869-875` | 2026-11-08 | n/a | high by reading; not run
- Root `LICENSE` at `a79ff07` starts "MIT License", Copyright (c) 2026 OOSEX GANG | GitHub API | 2026-11-08 | n/a | medium until the full text is read
- No public note ties Safari video to Metal; DC28088 README claims it works, mechanism unstated; `NOTES.md:2051-2052` at `67448d2` says WebKit was denied by the bundle's client policy at that time | DC28088 | 2026-11-08 | A618 | upstream claim
- Fetching the donor repository onto this Mac was refused by the session's permission system ("Code from External"), so the build and shader-coverage steps have not run | this session | 2026-11-08 | n/a | blocked
- IPSW: `iPhone10,3` 16.7.16 20H392, Apple CDN via `api.ipsw.me`, 6.17 GB, expected SHA-1 `5606c298c1d908f8a48f617f0ceaf71f2a9f0193`, kept in `~/Downloads/ios-sweet-ipsw-20H392/`, never committed | ipsw.me | 2026-11-08 | iPhone X build | downloaded 2026-11-08, SHA-1 verified equal; 6171035648 bytes

- Metal shader failure classes on 20H392, A618: QuartzCore pointer store (2) and `air.imageblock` (4); VideoToolbox bitcast 4x16 to 2x32 (4) and `air.get_null_texture_2d` (3); across all libraries mostly `air.visible` library functions (5283) | `corpus.py` output in the work directory; tool `air2nir`/`ir3_compiler`, donor `a79ff07` | 2026-11-08 | host compile | high for compile status; says nothing about correctness
- Full MIT text present at donor root, SHA-256 starts `f6cfd96f40e34d36` | local clone | 2026-11-08 | n/a | high

## Metal donors and static analyses (2026-11-11; nothing imported from any of these)

| Claim | Source | Date | Hardware | Confidence |
| --- | --- | --- | --- | --- |
| `oosexgang/hakios-metal`: direct PM4 Metal driver, no Gallium; licence MIT (NOTICE records Mesa-derived facts); targets Adreno 660 chip 0x06030500; not imported | github.com/oosexgang/hakios-metal at d36f329 | 2026-11-05 | a660, not A618 | licence read from LICENSE; capability claims self-reported, not reproduced |
| `oosexgang/hakios-xnu-kernel`: kernel patch, `xnu/files/`, `drivers/` APSL-2.0; the rest MIT, per its LICENSE (GitHub shows NOASSERTION); a660 GPU code only; not imported | github.com/oosexgang/hakios-xnu-kernel at 63fc2b4 | 2026-11-06 | a660 | licence read from LICENSE; rest self-reported |
| `ry-diffusion/Chlorophyll`: README says MIT, GitHub shows NOASSERTION, relays donor code; licence unresolved; fixes in `docs/FIXES.md` are ideas only; not imported | github.com/ry-diffusion/Chlorophyll | 2026-11-11 | Adreno 630 | unresolved licence; fix claims self-reported, not reproduced |
| `UniXNU/AdrenoMetal`: MIT; Metal via metal2vulkan + Turnip; not imported | github.com/UniXNU/AdrenoMetal | 2026-11-11 | A740 per README | licence per research report; behaviour self-reported |
| `steelbrain/metal2vulkan`: GPL-2.0-or-later OR LGPL-3.0-or-later per hakios-xnu-kernel; GitHub shows NOASSERTION; excluded | github.com/steelbrain/metal2vulkan | 2026-11-11 | n/a | licence as stated by another repo, not checked here |
| MPSCore `MPSDevice::GetMPSDevice` (0x1d40702e8) queries `supportsFamily:` 1008 down to 1002, never 1001; profile 0 (Apple1 only) is refused | iOS 16.7.16 dyld shared cache (20H392), `ipsw`/`otool` disassembly, static only | 2026-11-11 | n/a (host); matches device 0160mh1 | high for the query order; the refusal path is consistent with device 0160mh1 |
| Metal discovery: nil from `initWithAcceleratorPort:` is skipped (0x181b14584); empty array gives nil default device; runs once per process | iOS 16.7.16 dyld shared cache, `ipsw`/`otool` disassembly, static only | 2026-11-11 | n/a (host) | high for the skip; "once per process" and "two devices fail" medium (not run). Device 0160t1 crash on refusal is not explained by it |
| QuartzCore format selection: XR formats 550-555 gated by a MobileGestalt answer plus `CAEnableDeepFramebuffer`; RG8 is YCbCr plane 1; no depth outputs in the metallib | iOS 16.7.16 dyld shared cache, `ipsw`/`otool` disassembly, static only | 2026-11-11 | n/a (host) | medium; interpreted by script from disassembly, no device check yet |
