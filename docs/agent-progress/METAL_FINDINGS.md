# Metal findings — 2026-11-11

Fidelity per item: "device" = real phone, one boot per run; "static" = host disassembly of the iOS 16.7.16 dyld shared cache (unslid addresses), nothing run. Nothing here is `verified-working`. Static notes are summaries; no disassembly or Apple code is stored in the repo.

## 1. State 2026-11-11

- Boot-args `sweetmetal=1 metal_profile=1`: the Metal driver draws the lock screen, home screen and folders; touch works. Run 0160mp1, user video, device, one boot. Label: partially-working.
- Faults seen: black frames between views; blur and backdrop in garbage colours; home wallpaper missing; slow (9 seconds with 10+ presents out of 239, none with 45+).
- backboardd crashed twice (sig 6, sig 11); SpringBoard was exec'd 3 times.
- Log: `logs/xnu-0160mp1.txt`.

## 2. Why profile 1

Static, MPSCore. `MPSDevice::GetMPSDevice` (0x1d40702e8) calls `supportsFamily:` with 1008 down to 1002 (0x3f0 at 0x1d407032c ... 0x3ea at 0x1d40706a8) and never 1001. Profile 0 claims Apple1 only, so every query fails and MPS logs "Failed to get MPSDevice"; SpringBoard then aborts (device, 0160mh1: 104 aborts). Profile 1 (Apple2) is accepted. Upstream HakiosMetal comments reach the same conclusion for its own profile 1 (self-reported, source read only).

## 3. Metal discovery

Static, Metal.framework:
- A plug-in whose `initWithAcceleratorPort:` returns nil is skipped cleanly (`cbz` at 0x181b14584 in `_MTLRegisterDevices`).
- `MTLCreateSystemDefaultDevice` returns nil when the array is empty.
- Discovery runs once per process.
- Two devices in one process report failure.

Device, run 0160t1 (`sweetmetal_procs=metaltest`): backboardd crashed 28 times (sig 11) when refused the device while the kernel still advertises the plug-in. The backtrace has frames in a non-cache image (the GL shim). Cause not found.

So "compositor on GL, apps on Metal" is NOT working yet. Label: not-working.

## 4. CoreAnimation format selection

Static, QuartzCore. Summary of the notes:
- XR formats 550-555 are gated by one MobileGestalt answer (obfuscated key `Aixt/MEN2O2B7f+8m4TxUA`, read at 0x188381f60). If true, the CFPreferences boolean `CAEnableDeepFramebuffer` overrides it (0x188381f8c). Display flag +0x220 bit 3 is set from it (0x1883ad02c).
- Framebuffer format comes from `IOMFBDisplay::framebuffer_pixel_format` (0x1882c5320); offscreen surfaces inherit the destination format (`create_surface` 0x18830cb4c). `warmup_shaders` (0x18847ed48) tries the XR formats when the answer is true.
- Limits word at MetalContext+0xa3c is set in `new_metal_context` (0x188487e28): supportsFamily 1001 / 1002 / 1003 set separate bits. `four_cc_to_mtl_format` (0x1882d69f4) takes it by value: 'w30r' -> 554 and 'w40a' -> 552 need the Apple2 bit; 'b3a8' -> 550 needs the Apple3 bit. Our profile 1 has Apple2, not Apple3.
- Format 30 (RG8) is plane 1 of YCbCr IOSurfaces, via `newTextureWithDescriptor:iosurface:plane:` (`update_surface` 0x18831de7c; call at 0x18831ee5c).
- QuartzCore's metallib has no depth outputs (`air.depth` 0 occurrences). The driver's refusal "fixed_frag_lph_cpf stores to [[depth]]" is therefore a misread in our AIR front end. `create_pipeline_state` (0x188380b94) sets no depth or stencil format.
- Bring-up environment variables (names from the QuartzCore table, read via getenv in `init_debug` 0x1883794f8; table walked statically, none tried on device):
  - `CA_DISABLE_FRAMEBUFFER_COMPRESSION` — framebuffer compression off.
  - `CA_DISABLE_OPAQUE_FRAMEBUFFER` — opaque framebuffer path off.
  - `CA_DISABLE_BACKDROP_CACHE` — backdrop cache off.
  - `CA_ENABLE_MPS_BLURS` — blur through MPS.
  - `CA_DISABLE_GENERIC_SHADERS` / `CA_FORCE_GENERIC_SHADERS` — generic shader path off / forced.
  - `CA_DISABLE_PRECOMPILED_PIPELINES` — no precompiled pipelines.
  - `CA_DISABLE_COLOR_PROGRAM_CACHE` — colour program cache off.
  - `CA_DISABLE_FILTER_MERGING` — filter merging off.
  - `CA_DISABLE_OCCLUSION_CULLING`, `CA_DISABLE_HIDDEN_CULLING`, `CA_DISABLE_DIRTY_REGIONS` — culling and dirty-region off.
  - `CA_DISABLE_ENCODER_SHARING` — one encoder per pass.
  - `CA_DISABLE_ASYNCHRONOUS`, `CA_FORCE_RESOURCE_SYNC` — serialise work.
  - `CA_DISABLE_LOW_LATENCY` — low-latency mode off.
  - `CA_FORCE_FP16_FRAMEBUFFER` — forces 'RGhA' framebuffer.
  - `CA_PRINT_SHADERS` — print shaders.
  - Full list of 207 entries is in the analysis notes (outside the repo).

## 5. Driver self-test (userland/metaltest), run 0160t2, device

Boot-args `sweetmetal_procs=*`, `sweetnull=backboardd,SpringBoard,metaltest`; log `logs/xnu-0160t2.txt`.

| # | Test | Result |
| --- | --- | --- |
| 01 | device | PASS (name "Adreno 7c+ Gen 3 (chip 0x6010800, Redwood)"; families 1001=1 1002=1 1003=0 1004=0 1005=0) |
| 02 | queue + empty commit | PASS |
| 03 | buffer roundtrip | PASS |
| 04 | texture roundtrip | PASS |
| 05 | render clear | FAIL px(0,0) got 0,7,14,21 want 191,128,64,255 |
| 06 | library from source | PASS |
| 07 | library from metallib | FAIL (metallib missing: Metal Toolchain not installed on the Mac) |
| 08 | solid triangle | FAIL crash signal 11 |
| 09 | textured quad | FAIL signal 11 |
| 10 | alpha blend | FAIL signal 11 |
| 11 | depth test | FAIL signal 11 |
| 12 | blit texture copy | FAIL blitCommandEncoder returned nil |
| 13 | blit mipmaps + tex2buf | FAIL nil |
| 14 | compute | PASS |
| 15 | iosurface texture | FAIL got 0,0,0,0 want 255,64,128,255 |
| 16 | 100 passes | FAIL px(5,5) got 145,152,159,166 want 128,26,230,255 |
| 17 | completion handler | PASS (GPUStartTime/GPUEndTime 0) |

Total 7 passed, 10 failed. Label: partially-working (device, one boot).

Caveats: failures 05, 15 and 16 may be readback (getBytes after render) rather than rendering. The 08-11 crash is unexplained. The test program is unreviewed and unverified against a reference Metal implementation, so a FAIL can be the test's fault.

## 6. AGX comparison

Static, class-dump of the dyld cache (AGXMetalA11, IOGPU, Metal). Counts only:
- AGX device stack: 491 selectors. Our Redwood device: 77. `_MTLDevice`: 524.
- 420 selectors are missing in ours (after NSObject basics): 339 have an `_MTLDevice` default, 81 have none.
- Gaps that matter now: no blit encoder, no texture views, no GPU timing.
- AGX sits on IOGPU, a different kernel interface. We stay on `_MTLDevice` and do not emulate IOGPU.

## 7. Upstream and relatives

All claims below about other projects are self-reported by them and were not reproduced here. Read-only research 2026-11-11; nothing imported.
- Our pinned donor (`hackios-xnu-userland` at a79ff07, 2026-10-22) is abandoned upstream: its default branch is a 2-commit pointer repo; development moved into `oosexgang/hakios-xnu-kernel`.
- `oosexgang/hakios-metal` (d36f329, 2026-11-05, MIT): direct PM4 driver, no Gallium; targets Adreno 660 (chip 0x06030500). Different lineage from our donor. Its successor code targets Adreno 660-class only; no Adreno 618 code found in any of these repos.
- `hakios-xnu-kernel` (63fc2b4): kernel patch, `xnu/files/`, `drivers/` are APSL-2.0; the rest MIT. Do not import kernel parts into this tree.
- Chlorophyll (`ry-diffusion/Chlorophyll`, Adreno 630, same donor lineage; README says MIT, GitHub says NOASSERTION): its `docs/FIXES.md` documents fixes for blur, colours, mipmaps, black wallpaper and refused draws. Unreviewed hobby code; licence unresolved.
- Licence flags: HakiosMetalCA.m "begun from vcvkk's plug-in", provenance unverified (repo 404); `metal2vulkan` patches are GPL/LGPL, kept out.
- Ideas and measurements can be adopted; copying needs a per-file licence check.

Top 5 to adopt (research recommendation, not tested here):
1. Framebuffer-fetch barrier under batch reordering, and sysmem for fetch shaders (Chlorophyll) — likely the blur/backdrop colours.
2. Nearest-variant selection for run-time CoreAnimation pipelines (upstream 3b9db78) — likely wrong colours and missing wallpaper head. Unverified whether our pipelines hit the same case.
3. Skip a refused draw instead of failing the command buffer; skip empty colour slots; DontCare clears (Chlorophyll) — black frames and wallpaper.
4. Blit encoder, texture views, generateMipmaps in order with draws, flat-shade provoking vertex.
5. Compiled-stage disk cache and per-command-buffer timeline — shader stalls and frame-pacing measurement.

Not found upstream: XR/10-bit format support, layered-render fixes, MPS beyond crash avoidance.

## 8. Work list, in order

1. Install the Metal Toolchain (needs the user's yes: download) and have the self-test reviewed against expectations.
2. Fix readback/clear (tests 05, 15, 16) and the draw crash (08-11).
3. `CAEnableDeepFramebuffer=NO` for backboardd to stop XR formats (root change, needs a flash).
4. Accept the lph_cpf pipeline (AIR front-end depth misread).
5. RG8 plane-1 IOSurface textures.
6. Blit encoder, texture views, generateMipmaps.
7. Chlorophyll-style fixes re-implemented one at a time (fetch barrier under batch reordering, skip a refused draw instead of failing the buffer, DontCare clears), after a licence check.
8. Find the two backboardd crashes and the GL-shim crash when refused.
9. Frame pacing measurement against the GL baseline.

Later: evaluate porting upstream's HakiosMetal to Adreno 618, using only Mesa's public register tables.

## 9. Lead from user video, run 0160t2 (real device, one boot, not yet tested)

Frames show: lock screen wallpaper right, but clock, date and flashlight button drawn solid blue
(vibrancy materials); home screen mostly black with icons appearing only where something changed
(one icon, then the dock, then rows); App Library shows all icons at once; rainbow blocks behind
dock, folders and App Library tiles.

Superseded by section 10: the real cause was the per-draw clear (patch 0003).

Hypothesis: CoreAnimation redraws only dirty regions and expects the previous frame's contents to
be kept (load action Load on the drawable / preserved render targets); the driver hands back empty
contents. Self-test 05, 15, 16 (wrong pixels on readback of kept content) point the same way.

Check without code: set `CA_DISABLE_DIRTY_REGIONS=1` in backboardd's environment (launchd.plist
EnvironmentVariables; root change, needs a flash). If the home screen fills in, the hypothesis
holds. Fix: honour kept contents for render targets in the driver. Do this before work-list item 3.
The rainbow blocks are a separate fault (blur scratch surfaces, XR formats).

## 10. Fixes on 2026-11-11 and what remains

Patches in `userland/metal/`; device, one boot per run; logs in `logs/`.
- 0003 load actions once per pass; clear-only passes clear. 0160c1: self-test 7 -> 11 of 17; wallpaper visible; no backboardd crash in that run. The real cause of section 9's symptoms was the per-draw clear.
- 0004 `flatshade_first=1`, correct for Metal's provoking-vertex rule. 0160f2c: no visible change.
- 0005 recorded work retains the objects it names; 0007 work released at end of commit, on the committing thread (from review). Self-test draws 08-11 no longer SIGSEGV.
- 0006 16-bit stage-boundary varyings widened to 32-bit when the compiler has 16-bit ALU; `sweetmetal_f16vary=1` restores the old behaviour. A/B on one root: 0160vA (widened) removes the diagonal garbage and saturated blocks; 0160vB (old) shows them again. Cause: ir3 mishandles half-precision vertex outputs in VS->FS linkage for CoreAnimation's lph shaders.

Self-test 15 of 19 in both vA and vB. Failing: 12, 13 (blit encoder nil); 18, 19 (test's vertex descriptor lacks attribute 4, point_size float, that `fixed_vert_lph_spc` reads; fix the test, not the driver).

Remaining in 0160vA (user report, photos, log): respring on app exit; dotted pattern in blur; missing Control Centre glyphs; blank widgets; dashed outlines; low frame rate.

Work list, in order:
1. Respring on app exit: get the backboardd backtraces (sig 11 once, sig 6 once) from `logs/xnu-0160vA.txt` and symbolize. Then the other crashes (assetsd x7, MapKit sig 11 x2).
2. (withdrawn) Blue tint of whites: the user confirmed in person that white is white; the tint was the camera. Lesson: colour judgements from photos need the user's eyes; the dot pattern in blur may also be partly camera moire and needs the same check.
3. Dotted pattern in blur, missing glyphs, blank widgets, dashed outlines. Candidates: XR formats 550-555 via `CAEnableDeepFramebuffer` (section 4), RG8 plane-1 IOSurface textures, framebuffer-fetch handling (section 7).
4. Blit encoder (self-test 12, 13).
5. Self-test 18, 19 descriptor: add attribute 4 (point_size, float).
6. Frame rate: each draw waits for the GPU (finish per draw). Measure first, then batch.
7. Open review items: encoder tables do not yet retain objects between set and draw; no runtime size/version handshake between RedwoodMetal and libredwoodair (build and flash together); the 0006 widened path has no host render test (softpipe lacks 16-bit ALU).
