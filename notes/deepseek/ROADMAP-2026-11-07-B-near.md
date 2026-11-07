# Roadmap horizon B: performance, stability, root and wallpaper (written 2026-11-07)

Part of `ROADMAP-2026-11-07.md` (read its sections 1-3 first: recipes, delegation, checklists). Task index
and dependencies are in its section 4. Reference clones for researchers live in WSL `~/research/`
(`DC28088_ios-sweet`, `DC28088_hackios-sweet`, `MakrSas_ios-topaz`, `MrMoxing_ios-alioth`, `ios-flame`,
`ios-sailfish`, `UniXNU`, `hakios-xnu-kernel`, `edi194_ios-fajita`, ...; may be stale: `git -C DIR log -1`;
read-only, never push from them). Reports of 2026-11-06 are in `reports/` (gitignored, present).

## B1: why does CoreAnimation allocate a new framebuffer IOSurface every frame? `[AGENT:researcher, then LEAD]` M / low

**Why.** [O] Each swap names a brand-new 1125x2436 surface (`logs/xnu-0122b.txt`: swap:surface 1:2, 2:4, 3:6, 6:8 ...;
the old ones are freed soon after). That costs allocate + zero + whole-surface cache clean (A5) + eagl attach
3.5 ms + delete. 0120 recycles the memory; the cascade stays. If CA reused a few surfaces, a frame would lose
roughly 5-8 ms. The 0121 use-count probe saw only 29 up / 17 down calls (not per frame), so the usual
"in use" signal is not it.
**Inputs.** A2's log lines (`SWEET SURF: props ...`: the keys CA passes when it creates the surface; `SWEET FB: sel N call ...`);
`logs/xnu-0121*.txt`; `reports/research-2026-11-06-eagl-reuse.md`; HackiOS `MiniIOSurface.cpp` /
`MiniIOMobileFramebuffer.cpp` in `~/research/DC28088_hackios-sweet/xnu/files/iokit/Kernel/` (how a working
port answers IOSurface purgeable/use-count/lookup and IOMFB SwapBegin/SwapEnd/SwapWait); QuartzCore itself.
**Steps.**
1. researcher writes `reports/research-YYYY-MM-DD-ca-surface-per-frame.md`: (a) the property set of the per-frame
   surface and what each key means (`IOSurfaceName`, cache mode, purgeable, "IsGlobal", ...); (b) how HackiOS answers
   the calls CA makes around a swap (purgeable state returned, SwapWait semantics) and where ours differs;
   (c) 2-3 ranked hypotheses, each with a **cheap experiment** (one boot-arg or a few lines in the kernel).
2. Reverse engineering of QuartzCore (optional, only if (c) needs it): the dyld cache is in the IPSW
   (`ipsw/iPhone10_3_16.7.16_20H392_Restore.ipsw`, SystemOS dmg in `ipsw/dmg/`); extracted hard-linked files are under
   `firmware-modem/dsc/` (3.2 GB, unnamed `iNode*`). The `ipsw` tool is NOT installed: **ask the user before
   downloading it** (CLAUDE.md). Without it, `aarch64-linux-gnu-objdump`/`strings` work on a dylib you extracted yourself.
3. LEAD turns the best experiment into a patch (one new number) and A/B tests it (rule 2.8).
**Done when.** The report exists with the three parts; the lead has chosen an experiment or recorded "not
reachable from the kernel" in NOTES.md.

## B2: promote 0124, the 512 MiB GPU window `[AGENT:patch-writer]` S-M / med

**Why.** Port of frokfrdk/ios-sweet `a0b076c` (user-approved 2026-11-06): window 512 MiB, 256 L3 page tables
(1 MiB) from contiguous XNU memory (zeroed, cleaned to PoC, mapped with `ml_io_map_wcomb`), fallback to the
current 64/128 tables. Their symptom (big buffers refused when the window is nearly full) is ours; 0113 only
recycles kept buffers. The draft is `xnu/patches-pending/0124-sweet-gpu-window-512m.patch`; its audit was fixed
(320 tables, bounds checks, no `KMA_PERMANENT`) but the SMMU non-coherent-walk / retention TODOs remain.
**Steps.** `git mv` it to `xnu/patches/` under the next free number (edit its `Subject: [PATCH ...]`), run
`tools/xnu-tree.sh update` (must print `ok`), read the TODOs at the top of the patch and either resolve them or
write them in the commit message. Test after A8 so it does not confound the A/B: boot with the bind-on defaults,
open the widget picker via the synthetic swipes, and grep the ring for buffer refusals (`grep -a -i "refus"`; read the patch and `RedwoodGPU.cpp` for the exact
IOLog text; must be 0) and `SWEET FREEZE: RedwoodGPU` (must be 0).
**Done when.** CI green; the unattended run shows no refusals and the same or better fps; NOTES entry.

## B3: touch latency `[AGENT:researcher, then patch-writer]` S-M / low

**Why.** [R] HackiOS measured 88-169 ms from lifting a finger to the report and got 5 ms by reading a report on
every interrupt. Users call this "lag". Ours: `bsd/dev/sweet_touch.c` polls every 10 ms (`SWEET TOUCH: ... poll=10ms
irq-hint=N`) and coalesces moves to `sweettouchhz` (default 60 -> up to 16.7 ms); the boot-arg `sweettouchirq`
exists.
**Steps.** researcher reads `sweet_touch.c` and writes the latency path (report -> `sweet_hid_touch()` ->
`IOHIDEvent` dispatch), the real poll period under load, and what a lift costs. Then one patch: a probe line
`SWEET TOUCH: lat ...` with the time from the bus read to dispatch (microseconds, percentiles per 10 s), and
if justified a faster poll while a finger is down (e.g. 4 ms), default on.
**Done when.** The probe prints; the user is asked (Spanish, one line) whether touch feels better with the
variant image; recorded in NOTES. Do not remove coalescing without the user's feel test.

## B4: build the root `ios16-root-gpu3.simg` (no flash) `[LEAD]` L / med

**Why.** Everything userland-side needs a new root: root fixes for extensions and wallpaper (W: ExtensionKit
flag, migrate sentinel, staged apps, HEIC->PNG), en0 netprefs, `wland.boot`, the eagl dylibs from userland CI
(B6), SpringBoard commit-rate hook (B5), env vars (B7), daemon hygiene (B9). **Batch them: every userland change
means a full `userdata` flash.** Source of truth: `reports/research-2026-11-06-root-fixes.md` (steps, risks, the
exact command sequence) and `tools/sweet-root-fixes.py` (NEVER run against a real image yet; idempotent; supports
`--dry-run`, `--only`, `--skip`).
**Preconditions.** IPSW DMGs copied to the WSL ext4 disk first (reading them from `D:` was very slow and
`apfs-fuse` returned zeros); the self-built `hfsplus.ko` loaded with force (lost after `wsl --shutdown`; see
`../ios-sweet-local/build-hfsplus.sh`, one level above `ios-sweet/`); `libheif-examples` for the wallpaper step (`sudo apt install`: **ask the
user**); Ubuntu 26.04's `install` rejects numeric UIDs (finish those steps by hand). Base: `ipsw/ios16-root-gpu2.simg`
or a fresh `tools/mkiosroot.sh` run, then `tools/sweet-root-tweaks.py`, then `tools/sweet-root-fixes.py`.
**Steps.** Follow the report's command sequence; run `sweet-root-fixes.py --dry-run --migration-prefs` first and read
the list; run it twice (second run must print only `ok`); `df -h` for headroom (PNG twins can add hundreds of MB);
`fsck.hfsplus -f -n`; `img2simg`; `sha256sum`. Put the userland artifact in `/topaz/lib` exactly as gpu2 did
(compare with a read-only mount of gpu2). Keep gpu2 untouched as the rollback.
**Done when.** `ipsw/ios16-root-gpu3.simg` and its `.sha256` exist; fsck clean; second run all `ok`; a NOTES entry
lists every step applied and every step skipped. **Do not flash**: that is B13.

## B5: SpringBoard commit rate (`dl_max` / `anim_max`) `[AGENT:researcher, then LEAD]` M / med

**Why.** [O] Even a zero-cost GL frame cannot give 60 swaps/s unless SpringBoard / CoreAnimation commit faster
(`reports/research-2026-11-06-fps-next.md` section 0: 26 swaps/s while the GL frame is 10 ms). HackiOS fixes
this in userland (`display_link_rates`, a prebuilt `libhakios.sb.dylib` candidate) plus status-bar and
MobileGestalt cache fixes.
**Steps.** researcher reads the HackiOS source (inside `~/research/MrMoxing_ios-alioth/src/` and
`~/research/hakios-xnu-kernel/`) and writes what exactly is hooked (which CA / UIKit / SpringBoard symbols), how
it is injected (`DYLD_INSERT_LIBRARIES` via the launchd plist? the topaz injector `libtopaz-inject`?), and a
proposal for building our own small dylib in `userland/` (CI `userland.yml`). **Do not ship a prebuilt binary
from another project without the user's OK.** LEAD decides and ships it inside B4's root.
**Done when.** Report + decision in NOTES; if built, the A/B after B13 shows the commit rate (swaps/s p50) up.

## B6: eagl improvements (userland) `[AGENT:patch-writer]` M-L / med

**Why.** Port the ideas of frokfrdk/ios-sweet (branch `sunfish`): `7b131f9` one recursive mutex around every GL
entry (CA uses one context on several threads; observed crashes and torn labels without it), `748b7c2` one Mesa
resource per IOSurface with an LRU cache (kills the 3.5 ms attach when a surface comes back), `3572fed` IOSurfaces
bound as "in use" until the GPU retires the next submit. Our eagl is generated at build time by
`userland/eagl-sweet.py` (patches the topaz `eagl.c`); there are two proposals to merge:
`userland/proposed-eagl-reuse.diff` and `userland/proposed-freeze-fix.diff`. Userland CI run 42308528861 built the
last `gpu-userland` artifact.
**Steps.** One change at a time, each as its own diff on `eagl-sweet.py`. `userland.yml` starts by itself on a push
that changes `userland/**` (like `xnu.yml` for the kernel; use `gh workflow run userland.yml -R limonetexd/ios-sweet-gpu`
only when nothing under `userland/` changed, never both), one run per batch, artifact `gpu-userland`
(`libOSMesa.8.dylib`, `libtopaz-gl.dylib`, `libtopaz-inject.dylib`, `backboardd`, `gl_test`). Order: lock
(`7b131f9`), then in-use counts (`3572fed`), then resource-per-surface (`748b7c2`). Read `reports/research-2026-11-06-eagl-reuse.md` first:
B1 may show that reuse can never hit while CA makes a new surface per frame, in which case `748b7c2` is wasted effort.
**Done when.** The artifact builds; `nm` shows no stray exported symbols that clash (frokfrdk checks this in CI);
it ships in B4's root; verification waits for B13.

## B7: Mesa `sysmem` and pass-diet A/B `[AGENT:researcher, then LEAD]` S-M / low

**Why.** [R] The only measured multi-millisecond GPU win on the A618: `FD_MESA_DEBUG=sysmem` (GPU completion 16 vs
22 ms, DC28088) and removing a second colour attachment from a pass (4.53 -> 1.36 ms a pass). Safe long-term on our EAGL path:
unknown. Read `reports/research-2026-11-06-forks-deepseek.md` lines ~160-180 and ~900-920 and
`reports/research-2026-11-06-adreno-news.md` around "GMEM vs sysmem".
**Steps.** An environment variable for backboardd has to come from its launchd job (`EnvironmentVariables` in
`/System/Library/xpc/launchd.plist`; `tools/patch-launchd-plist.py` and `tools/sweet-root-tweaks.py` already edit
that plist). Add it as an optional step of `tools/sweet-root-fixes.py` (`--only gl-env`) so the A/B is one root build
with and one without; no code change in the kernel. Watch for icon corruption (Trogdor reports small-icon artifacts
with sysmem [R]).
**Done when.** The step exists with a dry run; the A/B waits for B13.

## B8: sandbox extension tokens for `assetsd` `[AGENT:researcher, then patch-writer]` M / med

**Why.** [O] `assetsd` aborts (sig 6) every boot: its sandbox extension for `kTCCServicePhotos` cannot be issued.
Our built-in Sandbox policy (`bsd/kern/sweet_amfi.c`, `sweet_sandbox_syscall`) returns ENOENT for ops 5 (extension
issue), 6 (extension consume) and 0x43 (container expected); op 4 (container path) already answers for app
extensions (patch 0107). topaz's patch "1001" that implements tokens is **not public**.
**Steps.** researcher: from `libsystem_sandbox` behaviour documented in the public ports (sailfish, topaz,
alioth `docs/`), write what ops 5/6 must return (argument layout, token string format, consume handle) and
what `assetsd` does with it; flag guesses. Then one patch with a minimal implementation (issue returns a
well-formed token string, consume returns a handle) and log lines `SWEET Sandbox: op 5 ...`.
**Done when.** After B13: no `CRASH assetsd` in the ring. Until then the patch builds and the boot has the same
fps.

## B9: daemon hygiene `[AGENT:researcher, then LEAD]` M / low-med

**Why.** Crash-looping or XPC-blocking daemons cost CPU and cause hangs [R sailfish: `fairplayd.H2` never answers
MIG requests and `locationd` blocks on it]. `tools/sweet-root-tweaks.py` already neutralizes CommCenter, the
VirtualAudio HAL plug-in, the MediaToolbox recorder, and renames `_PanicOnCrash`. Still open from the sailfish list:
`fairplayd.H2`, `vmd`, `ReportCrash`, `spindump`, `tailspind`, `aggregated`; and `sweetdeny=` (sailfish 0182)
to refuse exec of named executables at boot.
**Steps.** Evidence first: B10's table says which daemons actually crash or loop in OUR logs. researcher lists, per
candidate: what it does, who depends on it (XPC clients), what breaks if it is gone (its job in
`/System/Library/xpc/launchd.plist` or a plist under `/System/Library/LaunchDaemons`). LEAD removes only daemons with log evidence, one root build, with
`--skip` switches in `sweet-root-fixes.py` so each can be undone.
**Done when.** A NOTES table "daemon / evidence / action"; the steps in `sweet-root-fixes.py` with dry run.

## B10: crash triage `[AGENT:log-reader, then researcher]` S-M / none

**Why.** Every boot shows crashes nobody has explained. [O] `driverkitd` sig 9 at boot (every log), `PosterBoard` sig 5
(0130r, 0131r), `assetsd` sig 6, `Preferences` sig 11 three times in `logs/xnu-0122b.txt`.
**Steps.** log-reader runs `python3 -I tools/sweet-fps-summary.py logs/xnu-01*.txt` (crash column) and
`grep -a "CRASH "` over all logs, building a table: process, signal, first/last log, count, pc/lr/bt lines.
researcher symbolicates with `tools/sweet-crash.py CACHE ROOT [REPORT]` (it calls `ipsw dyld a2s`, so it needs the
`ipsw` tool, **not installed: ask the user to allow the download** (question Q2 in section 12), plus the
`dyld_shared_cache_arm64` file in a writable directory and the slide printed in `CRASH name[pid] sig N ... slide
0x...`). Without `ipsw`, work from process names, signals and raw frames only. Writes
`reports/research-YYYY-MM-DD-crashes.md` with one hypothesis per row (kill by code signing = sig 9? an assertion =
sig 5/6; a NULL deref = sig 11).
**Done when.** The report exists; each row has "benign / needs fix / unknown".

## B11: App Library blur / other freezes `[LEAD + USER]` S

**Why.** [O] 2026-11-06: swiping into the App Library blur froze backboardd (userland hang, GPU idle; log
`logs/xnu-0101s0-20261106-blurfreeze.txt`). The 0122 fix covers the widget picker only. [O] The user also
reported "sudden stops" (cause unknown).
**Steps.** With A3 in place, when the user next has the phone: boot a daily image with `sweetshot=60` (leave `sweetfreeze` at its default 1: dump only; `sweetfreeze=2` also
kills the stuck process); ask the user to open the blur and widget picker; on a freeze the kernel dumps every
thread of backboardd/SpringBoard (`SWEET FREEZE`) and takes a screenshot. Pull the ring at once
(`tools\sweet-pull-ring.ps1 -BootRecovery -Out logs\...`), read where backboardd is blocked
(`sweet_freeze_dump` output), compare with the 2026-11-06 log.
**Done when.** A NOTES entry with the blocked stack and a ranked cause list.

## B12: 60-minute soak `[LEAD]` S / low

**Why.** Leaks (zombie surfaces, wired MB, GPU window), thermal drift and the "sudden stops" only show over time.
**Steps.** Image `sweetgpu_reboot=3700 sweetgpu_swipe=60`; `-ProbeSeconds 3800`. In the ring read the `SWEET FPS`
tail: `surfaces`, `zombies`, `MB wired` must stay flat; `SWEET THERM` (A6) must plateau below 80 C; fps must not
decay. Record the curve in NOTES.
**Done when.** NOTES entry with first/last-10-minute averages.

## B13: flash gpu3 and first boot `[USER]` M / destructive

A `userdata` flash erases iOS state. **Ask the user every time** ("sí, flashea" was their wording), tell them the
first boot takes 15-30 min in `datamigrator` on the Apple logo, and that ABL may hang at "Sending" (Power+Vol-).
Command (PowerShell, from `ios-sweet`): `..\tools-win\platform-tools\fastboot.exe flash userdata ..\ipsw\ios16-root-gpu3.simg`;
log to `..\flash-userdata-gpu3.log`. First boot with `sweetgpu_reboot=1820` or more. Keep gpu2 as rollback.

## B14: wallpaper and extensions verification `[LEAD]` S

**Why.** [O] Without registered app extensions PosterBoard finds no poster provider (sig 5), the widget gallery waits
for them. The kernel side is in (0107 container path for `.appex`, 0108 AMFI sysctl `developer_mode_status` + the
`AppleMobileFileIntegrity` service, 0084 AMFI policy); the root side (B4) is what was missing.
**Steps.** After B13's first boot: screenshots of the lock screen and home screen (`sweetshot=60`); grep the ring for
`CRASH PosterBoard`, `CRASH assetsd`, `CRASH lsd`; ask the user to open the widget gallery. [R] Even with all of this the
poster switcher (long press) may stay black (hosted contexts of PosterBoard are not drawn; alioth). A static wallpaper
hack (injected SpringBoard library drawing a picture) is the labelled last resort: card D6.
**Done when.** A NOTES entry saying wallpaper visible yes/no, extensions registered yes/no, with screenshot paths.
