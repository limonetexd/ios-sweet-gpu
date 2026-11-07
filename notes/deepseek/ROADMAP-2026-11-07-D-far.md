# Roadmap horizon D: far items (written 2026-11-07)

Part of `ROADMAP-2026-11-07.md`. These are large or uncertain. Each starts with a **research task** whose
output decides whether to continue; nothing here is built before its report exists and the user has seen it.
Use `researcher` agents; the lead reviews and records the decision in NOTES.md.

## D1: page flip / MDP direct scanout `[AGENT:researcher, then LEAD]` L / high

**Why.** Removes the CPU panel copy (3.4 ms native, 5.9 ms scaled) and tearing. It cannot raise the swap cadence by
itself (that is B5). **Facts.** [O] The panel memory sits at `0x9c000000` (ABL framebuffer; 1080x2400x4 = 10.4 MB), the
timing engine is left running by ABL, and our code reads `INTF_1` (DSI0 at `0x0ae6b800`) read-only (the beam probe,
patch 0125, comment in `SweetFramebuffer.cpp`). Two 10.4 MB frames (or three 4.9 MB frames on the scaled path) fit above it.
**References.** [R] DC28088 `sweet_display.c` (apollo `0156`) and ios-sailfish `sweet_fbcon_flip`: two buffers, latch at the
next START, refuse if the display SMMU stream translates. **Negative:** DC28088 `0181`: flush mask `0x20041` (pipe bit +
bit 17) gave "extreme flickering ... black flashes" and was reverted; Yofuness: present on its own thread, at SwapEnd, or
non-blocking were all worse.
**Steps.** researcher: map the SDE register path for sweet (`mdss_mdp@ae00000` in its DTB: CTL flush bits for the pipe in
use, which pipe/mixer ABL set up, SSPP source address registers) from the DTB and the Linux/downstream `sde_hw_*` sources, and
list exactly which writes a flip needs. Any prototype behind `sweetfbflip=0` (default off) with a log of flips,
latch-wait and timeouts. **Needs the user's eyes**: flicker cannot be seen by an unattended run or a screenshot (the
screenshot reads the buffer, not the scanout).
**Done when.** The register plan report; a go / no-go.

## D2: GPU blit present `[AGENT:researcher, then LEAD]` L / high

**Why.** Let the A618 copy (and for the scaled path scale) the CoreAnimation surface into the panel buffer; the CPU copy
disappears. [R] Done by frokfrdk (`0113`, `0116`), ios-sailfish (`0126`, `0164`); DC28088 measured the present thread
at ~20 ms CPU before. Needs the Mesa `fd6_blitter` command sequence for A618 as a small indirect buffer built by the
kernel, a fence before the panel latches (D1 helps), and care with cache attributes of the panel memory.
**Steps.** researcher reads those commits in `~/research/` (or via `gh`), writes the IB layout and the cache/coherence
rules. Prototype is a boot-arg (default off); success = present CPU time near 0 and no tearing artefacts the user can see.

## D3: Metal via Vulkan / native Metal frontend, feasibility `[AGENT:researcher]` M / none

**Why.** [R] HackiOS `hakios-metal` claims 110-115 fps swipes at 828x1792 on a 120 Hz panel (A642L); DC28088's
`codex/native-adreno-metal` branch has a native Metal frontend for **our** A618 (35-40 present fps measured); UniXNU does
Metal-on-Vulkan (`metal2vulkan`, Turnip) [R]. Metal would replace the GL path with something CoreAnimation uses directly.
**Output.** `reports/research-YYYY-MM-DD-metal-feasibility.md`: what each approach needs (user-client surface, shader
compiler = ir3, PM4 emission, IOSurface import), licences, what is closed source, how much of it can run on our kernel
without the rest of HackiOS, effort in weeks, and a recommendation. Do not implement. Postponed by decision (CLAUDE.md s9).

## D4: CPU frequency scaling and idle states `[AGENT:researcher]` M / med

**State.** The shim fixes the clocks (gold idx 10, silver idx 8; A6 explores the top of the LUT); nothing scales with load;
`PSCI SYSTEM_SUSPEND` is unsupported [R], so no deep sleep. **Output.** A report: the OSM/cpufreq-hw registers and LUT for
SM7150 (already used by the shim: `CPUFREQ0/1 + 0x920`), what a load-driven governor needs from XNU's scheduler hooks, idle
(`WFI` works? cpu-off states?), with ios-flame `docs/features/cpu.md`, `sleep-wake.md` as references. Idle-heat evidence:
[R] userland waste (PowerLog/CoreDuet/Biome, the PosterBoard 10 fps clock, mediaserverd) dominates idle heat (79-85 C vs 54 C
with the daemons moved aside): B9 is the cheaper first step.

## D5: AppleKeyStore, passcode, Secure Enclave stand-in `[AGENT:researcher]` M / none

Our `SweetKeyStore.cpp` is a stand-in (no SEP). The AKS wrap/unwrap draft (0137) gives keychain storage without security.
Report: what a passcode / Face ID-less unlock flow needs, what HackiOS does, and the honest security position (a research
device). Do not implement before the user asks.

## D6: PosterBoard hosted contexts and the static wallpaper hack `[LEAD]` M / low

Only if B14 says the wallpaper stays black after the root fixes. [R] On iOS 16.5 built-in wallpapers are rendered
procedurally by PosterBoard; the legacy `HomeBackground.cpbitmap` path is not read; the poster switcher (long press)
shows black even when extensions work (alioth: hosted contexts are not drawn by the window server, cause unknown). Last
resort [R alioth `inject_sb.c`]: a small injected SpringBoard library that draws a static picture as the wallpaper layer.
Label it a hack in code and notes; the user decides whether to keep it.

## D7: community release `[AGENT:doc-writer + LEAD]` M / none

The user's wording: "this is for the community". Tasks, each small:
1. **README.md**: rewrite the stale "What works" table from `HANDOFF.md` / NOTES.md facts (section 1.3 of the roadmap is a
   start); build steps for sweet end to end (kernel CI, userland CI, root image, shim, `fastboot boot`); known issues;
   hardware table; what is Wi-Fi/battery/GPU status. Never include Apple or Qualcomm/Xiaomi files, device dumps or serial
   numbers; say how a user gets their own IPSW and firmware.
2. **`site/`** (upstream project website): update the status text; keep it factual.
3. **CI gate**: a QEMU boot smoke test in `xnu.yml` (`tools/qemu-sweet.py`, `docs/QEMU_TESTING.md`) that boots the new
   kernel for ~60 s and greps for a known line, so patch drift is caught before a phone boot; plus `nm` symbol-leak check on
   the EAGL dylib (frokfrdk) in `userland.yml`.
4. **Repo hygiene**: update `tools/validate-repo.py` for non-gapless patch numbers (0097b/c, 0138 jump); a
   `CONTRIBUTING.md` short guide (how to make a patch: roadmap section 2.1); a licence check (upstream MIT).
5. **Demo**: ask the user for a short video or GIF of the home screen at the best fps; screenshots from `sweetshot` can
   illustrate the README.
**Done when.** Each item is a separate commit; no new binary blobs; the user reviews the README before it is pushed
(it is public).
