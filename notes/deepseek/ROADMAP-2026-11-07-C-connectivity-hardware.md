# Roadmap horizon C: Wi-Fi and hardware (written 2026-11-07)

Part of `ROADMAP-2026-11-07.md` (read its sections 1-3 first). Work here after horizon A is done and B's
root (B4/B13) exists, because most hardware items need root-side files. Reports of 2026-11-06 in `reports/`
are the detailed sources: `research-2026-11-06-wifi-current.md` (the plan, 456 lines),
`research-2026-11-06-wifi-port.md` (what each draft does and its proof log lines),
`research-2026-11-06-wifi.md`, `-battery.md`, `-ecosystem.md`.

## C1: promote the eight Wi-Fi drafts, then the boot ladder `[LEAD + AGENT:patch-writer]` L / high

**What exists.** `xnu/patches-pending/0130..0137` (they compiled in CI on branch `wifi-ci`, run 42278088612, on an
older base; **never booted**). In order: `0130` `/dev/pmem` | `0131` RPMh votes for Wi-Fi rails | `0132` BCM votes +
WLAN SMMU stream thread | `0133` RTC calendar | `0134` IO80211 / network objects | `0135` `/dev/wlan`, en0, Apple80211
ioctls (2439 lines, all new files) | `0136` IOKit quiesce | `0137` AKS wrap/unwrap selectors.
**2026-11-07: `0133` was promoted alone to `xnu/patches/0144-sweet-rtc-calendar.patch` for C14 (system time), body
unchanged; seven drafts remain here (`0130`, `0131`, `0132`, `0134`, `0135`, `0136`, `0137`).**
Defaults: everything is gated OFF except the RTC read (acts only when the calendar is before 2001, `sweetrtc=0`
disables) and the AKS selectors 10/11 (were "unsupported"). A kernel with the drafts and **no** new boot-args must behave
like today's.
**Steps.**
1. **Rename only, never edit the bodies** (they compiled as bytes): `git mv xnu/patches-pending/0130-... xnu/patches/NNNN-...`
   for the eight in order, consecutive numbers starting at the next free number. Put the old -> new map in the commit
   message. `tools/xnu-tree.sh update` must print `ok` eight times; any `SKIP` is a conflict with a newer patch:
   regenerate that patch on the current tree with `tools/xnu-mkpatch.sh` (new content, new commit).
2. `check-patch.py` on all eight; push as **its own batch**; CI must be green (`Skipping patch` = 0). Compile errors
   after the base drift are fixed with a new patch after the first green build, or by editing the draft before it
   (the series is not built until the push).
3. A default image (no Wi-Fi args) against `logs/xnu-0143r.txt` (or the newest baseline): same fps, `SWEET RTC: calendar set ...`
   present, `SWEET AKS: securityd sel 10 ... -> 0x0` present, no new crash.
4. The boot ladder, one unattended run per rung, images built with `SWEET_WLAN=1` only from rung 3 on
   (`SWEET_WLAN=1 tools/sweet-gpu-image.sh K TAG "<args>"`; C2). Stop at the first rung that fails:
   | Rung | Boot-args | Proof lines in the ring | Failure markers |
   | --- | --- | --- | --- |
   | 1 | `sweetpmem=1 sweetsmmuwlan=2` (pmem + BCM votes only) | `SWEET PMEM: /dev/pmem ready (major N)`; `SWEET RPMH: BCM SN15 addr=0x... vote 0x60004001 -> 0` (and `CN0`); `SWEET SMMU: BCM votes SN15=0 CN0=0`; `SWEET FPS` keeps ticking; touch events after the swipes | `refused`, `timeout; TCS quarantined`, `BCM votes failed` |
   | 2 | `sweetpmem=1 sweetsmmuwlan=1` (adds the SMMU stream) | `SWEET SMMU: ID0=... ID1=...: N SMRs, M context banks`; `SWEET SMMU: WLAN 0x240/0x1 -> CB<n> via SMR<m>: ... -> ok` | `NOT as written`, `no free SMR/bank`, or the ring ending right after a "reading ..." line = a CPU stalled in an SMMU read |
   | 3 | `sweetpmem=1 sweetsmmuwlan=1 sweetwifid=1` + `SWEET_WLAN=1` ADT + root files (C2/C3) | `flame wlan: /dev/wlan ready (major N)`; `RedwoodWLAN: a user client of type N is asked for: there is none` (expected); wifid `Falling back to IOCTL path`; `MiniIONetworkStack: opened by configd ...` | wifid spinning, configd `*TIMEOUT*` |
   | 4 | add `sweetquiesce=1` only if wifid/SpringBoard wait for the interface namer | `SWEET IOKIT: sweetquiesce=1: no busy hold for the IOKit daemon`; busy state 0 | any new hang at boot |
   Rung 2 is the riskiest: without effective BCM votes the first SMMU read can stall a CPU forever (the stream
   runs in its own kernel thread so one CPU stalls, not the boot). The timed reboot should still fire; if the phone is
   dead, the user must hold Power+Vol-. The SMMU hypervisor may reject mask 1 (GPU/GMU only accept exact stream ids,
   mask 0): record the exact lines and ask the user before trying a variant.
**Done when.** Rungs 1-2 recorded in NOTES with the log lines (pass or exact failure). Rung 3 belongs to C3.

## C2: ADT `--wlan` and the Wi-Fi root files `[LEAD]` M / med

**ADT.** `tools/proposed-mkadt-wlan.diff` adds `--wlan` to `tools/mkadt.py` (the `/arm-io/wlan` node) and
`SWEET_WLAN=1` to `tools/sweet-gpu-image.sh`. It predates 0138 and my edits to those two files (`--scale2`,
`SWEET_SCALE`): apply by hand, keep both features, test both ADTs with `python3 -I tools/mkadt.py /tmp/a.adt --highmem
--gpupool [--scale2] [--wlan] --dump | grep -E "canvas|wlan"`. Use the node **only with** `sweetwifid=1` (otherwise launchd
starts wifid with no en0).
**Root.** Not covered by `tools/sweet-root-fixes.py`: `/var/local/bin/wland`, `/var/local/fw/*` firmware incl. `bdwlan.b00`,
launchd job `org.ios-sweet.wland`, wland jetsam limit, explicit en0/DHCP service in `preferences.plist`
(`netprefs` step of `sweet-root-fixes.py` covers the service), deleting `/var/local/wland.boot`
(`wland-boot` step), and wland must get the same boot-args (`sweetsmmuwlan`) so it skips its own SMMU step.
Audit what the gpu2 root already has (read-only mount; the 0104 experiment edited a root in place) against
`reports/research-2026-11-06-wifi.md` section 2.3. Firmware blobs come from `firmware-modem/` (pulled from the phone;
Qualcomm firmware stays out of git). [R alioth] Settings' Wi-Fi pane opens only when `configd`, `securityd` and
`wifianalyticsd` are in the default launchd jobs.
**Done when.** A script/step list in `sweet-root-fixes.py` (`--only wifi-files`, dry run) and an audit table in NOTES.

## C3: Wi-Fi bring-up verification `[LEAD + USER]` M / med

After B13 (root with the Wi-Fi files) and rung 3: `ls -l /dev/wlan` is not observable (no shell), so judge by the ring
and screenshots: wland lines, en0 attach, Settings > Wi-Fi shows networks (screenshot). **The user types the Wi-Fi
password** (an agent never enters credentials). Then DHCP address, Safari page load, reboot and "known network"
(proves AKS 0137). Expected [R]: Wi-Fi scans fail while Bluetooth is on (shared WCN3990 coexistence): keep
`bluetoothd` down (C10).
**Done when.** NOTES entry: scan / join / DHCP / Safari yes-no with the evidence.

## C4: battery verification and polish `[AGENT:patch-writer]` M / low

**State.** [O] The real driver is on by default since 0106: `SWEET BATTERY: PM6150 / estimated SOC, 95% 4253mV external=1
charging=1` (SPMI observer reads of the PM6150 fuel gauge `qpnp-qg`; SDAM-seeded state of charge). `CLAUDE.md`'s "indicator
may be fake" is stale. Not implemented anywhere [V]: real temperature, cycle count, time remaining, critical-level shutdown.
**Steps.** (1) Compare 30-60 minutes of `SWEET BATTERY:` lines with the OrangeFox battery reading (plug/unplug included);
(2) read `reports/research-2026-11-06-battery.md` section 3: patches A (SPMI whitelist `0xb6`, `0x60`; 0x60 arrives with the
RTC draft), B (DC28088 0156+0158+0161+0162: SDAM seed, IR compensation, coulomb counting: check which of these 0106 already
has), D (ios-flame 0227: seed from SDAM only when within 15 % of the voltage estimate); (3) one small patch per gap found.
**Done when.** A NOTES table "claimed vs OrangeFox" over a discharge, and the gaps either patched or listed.

## C5: real panel off on the power key `[AGENT:researcher, then patch-writer]` M / med

**State.** [O] Power key -> IOMFB selector 12 -> our driver fades the frame; the panel stays powered (AMOLED, black pixels).
Real off saves power and heat. [R] ios-flame `0205` does DCS `0x28/0x10` (display off / sleep-in) and `0x11/0x29` over DSI
short writes with an MDP layer-mixer alpha blank; DC28088 `0079` deliberately stays with the fade. The panel is a DSC
video-mode one whose timing engine ABL left running (`SweetFramebuffer.cpp` comment, beam probe 0125).
**Steps.** researcher: what sweet's panel needs (DTB in `dtb/`: panel node, init/off command sequences), what
ios-flame/DC28088 did, what can go wrong (panel does not come back; only a reboot recovers). Patch only behind a boot-arg
(default OFF) with a watchdog that re-sends "on" after N seconds if the key is pressed again. Needs the user's eyes to test:
queue it for when they are present.
**Done when.** The report; the patch if the risks are acceptable; the user's verdict recorded.

## C6: thermal policy `[LEAD]` M / med

After A6 (`SWEET THERM` data) and B12 (soak): if the hottest sensor passes a threshold (start with 80 C) step the CPU
clocks down one OSM LUT index (the shim writes `CPUFREQ0/1 + 0x920`; the kernel can do the same write) and back up
under 70 C. Log `SWEET THERM: ... clocks gold N silver M`. Default on only if it never triggers in the normal fps tests.

## C7: interrupt-driven touch `[AGENT:researcher, then patch-writer]` M / med

**State.** `bsd/dev/sweet_touch.c` polls every 10 ms (`poll=10ms irq-hint=N`); boot-arg `sweettouchirq` exists (a hint).
[R] ios-sailfish `0181` (`xnu/patches/0181-sailfish-interrupts-wlan-touch.patch`, 399 lines): GICv3 SPI
attach/mask/dispatch (`pe_fiq.c`, `sleh.c`), the touch attention GPIO through the TLMM summary interrupt, polling fallback,
`sweettouchirq=0` to disable. For sweet the attention line is GPIO 9 [R ecosystem report]; the INTID and TLMM base must be
re-derived from sweet's DTB. Do this only if B3's latency probe shows polling is a real part of the lag.
**Done when.** Report with the register/INTID table and a go/no-go.

## C8: audio stage 1, a silent sink `[AGENT:researcher, then patch-writer]` M / low

**Why.** No audio hardware path exists yet, but a *software* sink removes mediaserverd and volume-HUD failure modes with no
hardware risk. [V] HackiOS public source (in `~/research/MrMoxing_ios-alioth/src/hackios-xnu-kernel-main/xnu/files/bsd/dev/`):
`redwood_audio.c` (a `/dev` device + `audio_plugin.c` user-level HAL plug-in), `redwood_sound.c` (1518 lines: ASM/ADM/AFE
streams, TDM; hardware), `redwood_adsp.c` (3240 lines: ADSP firmware load via TrustZone PAS, SMP2P/GLINK/QRTR; hardware).
The root currently *disables* the VirtualAudio HAL plug-in (`sweet-root-tweaks.py`, mediaserverd crash).
**Steps.** researcher: what iOS needs to consider audio present (HAL plug-in contract, what mediaserverd expects),
what `redwood_audio.c` implements, a plan to ship a "null sink" plug-in built in userland CI + the kernel device; list
licence status. patch-writer only after the plan is accepted.
**Done when.** The plan in `reports/`; a decision in NOTES.

## C9: audio stages 2-3, ADSP and speaker `[AGENT:researcher]` L / high

Research only: boot the ADSP through TrustZone PAS like topaz boots the modem (`ios-topaz` `0113-0118`, `0121-0122`), then
a TDM/codec path for sweet's speaker (sweet-specific: DTB `dtb/`, the Linux sm7150 audio topology). Output a feasibility
report with the real unknowns listed; do not implement.

## C10: Bluetooth `[AGENT:researcher]` S / low

[R] No project has it. WCN3990 shares the radio with Wi-Fi (scans fail while BT is on). Report: what `bluetoothd` does at
boot, whether it relaunch-loops in our logs (B10), and the root change to keep it down (a B9 item). No kernel work.

## C11: hardware research reports `[4 x AGENT:researcher]` S each

One report per item in `reports/research-YYYY-MM-DD-NAME.md`: **camera** (sensors/ISP on sweet from the DTB; what HackiOS
has: camera driver present in its source), **sensors** (accelerometer/gyro, proximity, ambient light: buses and
addresses, which iOS daemons need them: `sensord`, `thermalmonitord`), **haptics** (the vibrator: PMIC/GPIO, HackiOS haptic
driver), **cellular** (modem PAS boot as the foundation, QMI over QRTR, `redwood_qmi.c` in HackiOS; CommCenter is
removed on purpose, see `sweet-root-tweaks.py`). Each report: hardware path, existing reference code and licence, effort
(S/M/L), first safe experiment, what breaks if it goes wrong.

## C12: permanent boot (flash `boot`) `[USER decision]` M / high

[R] No project does it; all use `fastboot boot`. Facts: our `shim-boot-*.img` is an Android boot.img v2 of 17,399,808
bytes that the unlocked ABL already accepts. **CLAUDE.md section 7 forbids touching `boot`**: an agent prepares only a
written plan and waits for the user to lift the rule explicitly. Plan (from `reports/research-2026-11-06-ecosystem.md`
section 5): (1) with the user's OK, back up the current `boot` from OrangeFox with `dd` to the PC; (2) flash the shim image;
(3) keep OrangeFox reachable (`fastboot boot recovery.img` or the key combo); (4) bootloop recovery: Power+Vol- for fastboot,
reflash the backup. Risk: the Xiaomi "The system has been destroyed" screen if `boot` is erased or invalid (never erase it).

## C13: a USB debug channel `[AGENT:researcher, then LEAD]` M / med

**Why.** Today every log needs a trip through OrangeFox (`sweet-probe-loop.ps1`). A live log or an SSH shell would make every
later task faster and would show the userland (no shell exists on the phone now). Pieces that exist: `bsd/dev/sweet_usb.c`
(live log streaming from the 4 MiB ring via `sweet_log_copy`), boot-args `sweetusb`, `sweetusblog`, `tools/sweet-usbnet.sh`,
and a reference in `~/research/DC28088-ssh` (SSH over USB on this phone [R]).
**Steps.** researcher: what `sweetusb=1` does today, whether Windows enumerates a device, what is missing for usbnet (RNDIS/
CDC-ECM) and for an SSH daemon in the root, and the licence/security implications (an open shell on a research phone).
**Done when.** The report and a recommended first experiment; the user decides.
