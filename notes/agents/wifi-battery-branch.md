# Wi-Fi, battery, and the DC28088 branch on the iOS 16.7.16 sweet port

**Audience:** another AI taking over this front.
**Date of evidence:** 2026-11-03 (filesystem timestamps are local, UTC+1; commit/CI times are UTC unless quoted from `NOTES.md`).
**Repository state:** `dipa-studio/ios-sweet`, HEAD `e1ce648` (`notes: both macOS runner queues still empty at 18:38Z; leave runs queued`).
**Method:** read-only static analysis. No `fastboot`, `adb`, boot, flash, or device command was run while producing this note. No code, `NOTES.md`, or `HANDOFF.md` was modified. The only write is this file. WSL donor files were read with `cat`/`ls` only.
**Conventions:** **Observed** = directly present in a log, patch, binary, or hash. **Inferred** = a conclusion from those observations. **Unknown** = not established by available evidence. `path:line` citations are 1-based. `0104` and `0105` mean `xnu/patches/0104-super-wifi-battery.patch` and `xnu/patches/0105-super-link-fix.patch`.

---

## 1. Scope and current state

### 1.1 What this front is

The project boots iOS 16.7.16 (Darwin 22.6.0, xnu-8796.141.3) on a Redmi Note 10 Pro (`sweet`, SM7150, Adreno 618). Two kernel lines existed before this front:

1. **Fast line:** `0101`/`0102`/`0103` on the `dipa` base, with the fast topaz/Redwood GPU and display stack. It reaches SpringBoard, presents frames, and has no Wi-Fi or real battery.
2. **DC28088 branch line:** the donor tree from `Yofuness/ios-flame sunfish` at commit `f09fdb58a2c074d131072947b247240532b7d97d`, with WCN3990 Wi-Fi (`wland`, `netsvc`), PMEM/RPMh/SMMU support, real battery, and the branch's NativeAdreno/Metal GPU. It joins WPA2 on `sweet` but its GPU is slow/incompatible with the topaz root.

The "super" objective is **branch Wi-Fi + battery on the fast topaz kernel**, not the branch GPU. `0104` ports the branch Wi-Fi/battery source onto the fast tree; `0105` supplies the missing link symbols. The branch's own GPU stack is deliberately excluded.

### 1.2 State table (as of this note)

| Area | State | Evidence |
|---|---|---|
| `0104` source | Applied after `0103`; 22 files, +4578/−58 | `git apply --stat` on `0104` |
| `0104` compile | CI run `41494548855` built it | `NOTES.md:199` |
| `0104` link | Failed with exactly 7 undefined symbols | `NOTES.md:208-213` |
| `0105` source | 3 files, +70 lines; stubs + VFS wrappers | `git apply --stat` on `0105` |
| `0105` link/CI | Not confirmed. `41498675277` cancelled for arm64 capacity; `41501352880` (`macos-15-intel`) and `41502238106` (`macos-latest`, branch `ci-macos-latest`) queued with no runner at 18:38Z on 2026-11-02 | `NOTES.md:216-222`, commits `61c27e9`, `34e3a8f`, `e1ce648` |
| Super payload binary | Exists: `shim/out/payload-super.bin`, 16,757,888 B, SHA256 `8201E7DE…6D7BFE`, begins `SWEETXNU`, contains `flame wlan`, `SWEET BATTERY`, `RedwoodWLAN`, `IO80211Controller` | file read, string offsets below |
| Super boot image | `shim/out/shim-boot-super.img`, 17,494,016 B, SHA256 `67FF470F…4B5F3F`, built 2026-11-03 18:24:51 | `Get-FileHash`, `Get-Item` |
| Super boot proof | **None trustworthy.** Named `logs/xnu-super-panic.txt` is byte-identical to `logs/xnu-0101s0reboot.txt`, contains no panic, and its paired shim log says `LOADER no SWEETXNU payload` | SHA256 `576CDB1A…EB99F`, shim log lines 1-3 |
| Branch kernel Wi-Fi | **Works.** WCN3990 boots, scans, joins `casa j`, link up, 833 RX frames | `logs/xnu-wifi-boot.txt`, `logs/wland-connected.log` |
| `en0` / Apple80211 | Works in-kernel: interface attached, ioctls answered, association result 1 | `logs/xnu-wifi-boot.txt:2636-4378` |
| DHCP / routable service | **Not working.** `configd` configures only `lo0`; no `en0` address, no DHCP | `logs/xnu-wifi-boot.txt` `SWEET NET:` lines |
| Battery | Real PM6150 reads, QG SDAM seed, 5 s poll, coulomb count | `logs/xnu-wifi-boot.txt:68-121`, `2355-8372`; `0104:4730-4961` |
| Battery accuracy | Plausible but drifting under load; charger flag contradicts current sign | 40 samples, 61% → 57% while `charging=1` |
| RTC | Set from PM6150; reads ~1971 epoch | `logs/xnu-wifi-boot.txt:84`, `logs/xnu-super-panic.txt:80` |
| Branch-reboot image | `shim-boot-branch-reboot.img`, 17,723,392 B, SHA256 `833B199C…6821F9`, built 2026-11-03 18:35; **no ring/log** | `Get-FileHash`; `logs/` inventory |

### 1.3 The single most important correction to earlier summaries

Earlier handoff text treated `logs/xnu-super-panic.txt` as a duplicate 0101s0 log and therefore as no evidence at all. That is half right and half wrong:

- **Observed:** it is byte-identical to `logs/xnu-0101s0reboot.txt` (SHA256 `576CDB1ACA91C3975CE4C2BCFCEA0360ABC2D43EAED55894462C050D2FFEB99F`), and it contains no occurrence of `panic` (case-insensitive).
- **Observed:** it nonetheless contains `0104`-only lines: `flame wlan: /dev/wlan ready (major 20)` at line 208, `SWEET SMMU: WLAN 0x240/0x1 -> CB4 via SMR6 …` at line 400, and `SWEET BATTERY: QG SDAM b640: …` at line 103.
- **Observed:** its boot args at line 328 include `sweetfb_hz=60 sweetgpu=2 sweetpmem=1 sweetsmmuprobe=1 sweetsmmuwlan=1 sweetwifi=1`, i.e. the super-style argument set, not the branch `sweetfb_hz=30 … sweetgpu_reboot=600` set.
- **Inferred:** the file is a **real kernel log from some boot of a 0104-bearing kernel at 60 Hz**, not a panic and not a 0101s0-only log. It is misnamed and duplicated. It is still **not** proof that `shim-boot-super.img` booted, because the shim log paired with it records a loader failure before XNU entry.
- **Observed:** the same pattern occurs for the working branch Wi-Fi boot: `logs/xnu-wifi-boot.txt.shim.txt` also says `INITRD lo=855FE000 hi=855FE060` / `LOADER no SWEETXNU payload`, while `logs/xnu-wifi-boot.txt` is a full successful Wi-Fi boot. Therefore the `.txt` kernel log and the `.shim.txt` loader log in a pair can come from **different physical boots**: the kernel log is the persistent last-good UFS log; the shim log is the failed attempt that just happened.
- **Inferred:** a 0104-bearing kernel booted at least once with 60 Hz and the super-style argument set, but whether it was the fast-topaz super image or a branch kernel booted at 60 Hz cannot be told from this log. The exact image/run is unidentified, and every named "super" attempt in the captured shim logs failed at the initrd handoff, not in XNU.

This distinction governs everything below.

---

## 2. Chronology

All commits are from `git log --format="%h %ad %s" --date=iso-strict`.

| Time (UTC) | Commit / event | Relevance |
|---|---|---|
| 2026-11-02 15:24 | `11851c8` notes: Wi-Fi WCN3990 joined `casa j` over the DC28088 kernel + USB file-server deploy; battery; branch Metal findings | Establishes branch Wi-Fi as functional on `sweet` |
| 2026-11-02 17:37 | `519bf9c` notes: branch Metal bundle incompatible with our root; reverted; super needs a real Wi-Fi/battery kernel port | Kills the shortcut of dropping branch `SweetMetal2.bundle` into the topaz root |
| 2026-11-02 17:47 | `5639176` xnu 0104: super build — Wi-Fi WCN3990 (PMEM/RPMh/SMMU, wland en0/Apple80211) and battery on fast topaz GPU | Main patch |
| 2026-11-02 17:48 | `ede4419` notes: 0104 CI `41494548855`; watcher builds `shim-boot-super` | Build record |
| 2026-11-02 18:14 | `771481a` xnu 0105: super link fix — compat stubs and VFS wrappers | Link fix |
| 2026-11-02 18:16 | `9222114` notes: 0105 and Wi-Fi service/spinner notes | Handoff |
| 2026-11-02 18:31 | `34e3a8f` ci: `macos-15-intel` because arm64 hosted capacity unavailable | CI workaround |
| 2026-11-02 18:32 | `61c27e9` notes: arm64 runner capacity cancelled 0105; retry on `macos-15-intel` (`41501352880`) | Cancellation |
| 2026-11-02 18:38 | `e1ce648` notes: both macOS queues still empty; leave runs queued | Last committed state |
| 2026-11-02 16:59 local | `logs/xnu-wifi-boot.txt` written (575,997 B, 8,442 lines) | Branch kernel full Wi-Fi boot |
| 2026-11-02 16:23 local | `logs/wland-connected.log` written (111,945 B, 1,372 lines) | wland WCN3990 bring-up, scan, join |
| 2026-11-03 18:24 local | `shim-boot-super.img` + `payload-super.bin` + `check-super` written | Super artifacts |
| 2026-11-03 18:28 local | `logs/xnu-super-panic.txt` / `.shim.txt` written | Misnamed pair; shim failure |
| 2026-11-03 18:29 local | `shim-boot-0101s0reboot.img` + `payload-0101s0reboot.bin` written | Control image |
| 2026-11-03 18:32 local | `logs/xnu-0101s0reboot.txt` written; byte-identical to super log | Duplication proven |
| 2026-11-03 18:35 local | `shim-boot-branch-reboot.img` + `payload-branch-reboot.bin` written | Branch reboot test image; no log |

The chronology has a gap: **there is no committed `NOTES.md` entry after `e1ce648` for the 2026-11-03 artifacts.** Their existence must be read from the filesystem, not from the narrative. The `check-super`, `check-0101s0reboot`, and `check-branch-reboot` files exist but are access-denied to this session (`Get-Content` → `PermissionDenied`), so their contents are unknown.

---

## 3. Wi-Fi / battery architecture

### 3.1 Two kernels, one boot image

The Android boot image is not XNU. `shim-boot-super.img` has `ANDROID!` header v2, `kernel_size = 380,928`, `ramdisk_size = 16,757,888`, `page_size = 4096`, `kernel_addr = 0x8000`, `ramdisk_addr = 0x1000000`, cmdline `console=null`. The 380,928-byte "kernel" is the shim (`shim/shim.c`, `start.S`, `loader.c`, `mmu.c`, `ufs.c`, `gpuprobe.c`). The 16.7 MB "ramdisk" is the **SWEETXNU payload**: XNU segments, embedded ADT, embedded boot args. The shim's job is to find `SWEETXNU` at the initrd address, copy the segments, place the ADT and `boot_args`, and jump to the XNU entry with the MMU off (`shim/loader.c:79-146`).

Image layout is correct for page size 4096: kernel at 0x1000, kernel end 0x5E000, payload at 0x5E000. The three images (`super`, `branch-reboot`, `0101s0reboot`) all have:

```
kernel_size  = 380928
ramdisk_size = 16757888 / 16989856 / 16663456
ramdisk_off  = 4096 + 380928 = 385024 = 0x5E000
payload magic at 385024 = "SWEETXNU"
```

So the packaging is not misaligned. The failure is in the **initrd pointer handed to the shim**, discussed in §4.5 and §6.

### 3.2 Layer map

```
userland wland (Mach-O arm64, phone/wifi)
    │  open/read/write /dev/wlan, one fw message per syscall
    ▼
bsd/dev/flame_wlan.c            /dev/wlan character device, queue, FW protocol
    │  flame_wlan_* C API
    ▼
bsd/dev/flame_sta.c             station ops for struct redwood_sta_*
    │  redwood_sta_ask_* / callbacks
    ├──────────────► bsd/dev/redwood_apple80211.c   SIOCS/GA80211, scan/join/state
    │                        │ kernel events class KEV_IEEE80211_CLASS, subclass 1
    │                        ▼
    │                 wifid / IO80211.framework (fallback IOCTL path)
    └──────────────► bsd/dev/redwood_net.c          en0 ifnet, ether_demux, net_ioctl
                             │
                             ▼
                      BSD socket stack / configd
```

Registry-side, `iokit/Kernel/arm/RedwoodWLAN.cpp` publishes `IO80211Controller` and a `RedwoodWLAN : IONetworkInterface` object so `SCNetworkInterfaceCopyAll()` classifies `en0` as Wi-Fi. `iokit/Kernel/arm/MiniIONetworkStack.cpp` publishes a fake `IONetworkStack` so configd's InterfaceNamer can reach `*QUIET*`. `iokit/Kernel/IOStartIOKit.cpp` disables the IOKit-daemon busy hold on SWEET so the registry can quiesce.

### 3.3 `/dev/wlan` protocol

`bsd/sys/flame_wlan.h` (`0104:4149-4223`) defines one message per `read()`/`write()`:

```c
struct fw_hdr { uint16_t type; uint16_t len; };

/* kernel -> wland */
FW_SCAN = 1;   /* no payload; answer BSS_BEGIN, BSS..., SCAN_DONE */
FW_JOIN = 2;   /* struct fw_join; answer JOIN_DONE */
FW_LEAVE = 3;  /* no payload; answer LEFT */
FW_TX = 4;     /* Ethernet frame */

/* wland -> kernel */
FW_HELLO = 16;      /* struct fw_hello { uint8_t address[6]; } */
FW_BSS_BEGIN = 17;
FW_BSS = 18;        /* struct fw_bss */
FW_SCAN_DONE = 19;  /* int32_t status */
FW_JOIN_DONE = 20;  /* int32_t status */
FW_LEFT = 21;       /* int32_t status */
FW_LINK = 22;       /* struct fw_link { up, ssid, bssid } */
FW_RX = 23;         /* Ethernet frame */
```

`FW_FRAME_MAX = 1514`, `FW_MSG_MAX = sizeof(struct fw_hdr) + 1600 = 1604` (`0104:4190-4191`; `struct fw_hdr` is 4 bytes). `struct fw_bss` carries BSSID, SSID, frequency, RSSI, beacon interval, capability, age, and up to 768 bytes of information elements (`0104:4212-4221`).

`flame_wlan.c` has a 64-entry queue (`FW_QLEN 64`), one reader and one writer, `msleep` waiters, and these timeouts:

| Request | Timeout | Code |
|---|---|---|
| scan | 20 s | `0104:397-400` |
| join | 40 s | `0104:420-440` |
| leave | 10 s | `0104:457-460` |

TX frames are dropped when the queue is full and counted in `fw_tx_dropped` (`0104:493-501`). Closing `/dev/wlan` marks the link down and wakes all waiters (`0104:519-536`).

### 3.4 Station layer

`flame_sta.c` implements `struct redwood_sta_ops` over the `flame_wlan_*` API:

- `sta_power()` is a no-op: the radio stays up with the modem (`0104:72-76`).
- `sta_scan()` calls `flame_wlan_scan()` (`0104:78-82`).
- `sta_join()` copies the join result into `sta_joined_bss`; it handles both `FW_KEY_PMK` and passphrase (`0104:110-142`).
- State reports `REDWOOD_STA_JOINED` if `flame_wlan_joined()` is true, including the case where **wland joined by itself from `wlan.conf` before wifid asked** (`0104:156-163`).
- RX and link callbacks are installed at init (`0104:236-243`).

### 3.5 Apple80211 in the kernel

`redwood_apple80211.c` (`0104:712-1456`) is the largest Wi-Fi file (739 lines). It answers the two ioctls that IO80211.framework falls back to when a driver has no user client:

```c
#define SIOCSA80211 0x802869c8u   /* _IOW('i', 200, struct apple80211req) */
#define SIOCGA80211 0xc02869c9u   /* _IOWR('i', 201, struct apple80211req) */

struct apple80211req {
    char req_if_name[16];
    int32_t req_type;
    int32_t req_val;
    uint32_t req_len;
    user_addr_t req_data __attribute__((aligned(8)));
};
```

Layouts are statically asserted against iOS 16.5's IO80211.framework (`0104:897-909`):

| Structure | Size | Key offsets |
|---|---:|---|
| `apple80211_scan_request` | 5456 | channels 0x48, flags 0x1308, names 0x1318 |
| `apple80211_scan_result` | 1164 | ssid_length 0x60, age_ms 0x84, elements 0x8c |
| `apple80211_assoc` | 592 | key 0x48 |
| `apple80211_channels` | 4824 | — |
| `apple80211_channels_info` | 10016 | number 0x32e, flags 0x12d0 |
| `apple80211_link_changed` | 32 | reason 0x14 |

Request types seen in the log and their handlers:

| Type | Name | Behaviour |
|---:|---|---|
| 1 | SSID | ENXIO unless joined; returns BSS SSID and sets `req_len` |
| 9 | BSSID | ENXIO unless joined; 6 bytes |
| 10 | SCAN_REQ | copies 5456-byte request, maps channels, queues `FW_SCAN` |
| 11 | SCAN_RESULT | one BSS per request; EIO when the list is exhausted |
| 12 | CARD_CAPABILITIES | 13 bytes; AES/AES-CCM/PM/WPA2/WME/SGI bits |
| 13 | STATE | 0 init, 1 scan, 2 auth, 4 run |
| 15 | OP_MODE | sets `req_val = 1` (station) |
| 19 | POWER | one radio; on unless station absent and unpowered |
| 20 | ASSOCIATE | copies 592-byte request, queues `FW_JOIN` |
| 21 | ASSOCIATE_RESULT | `req_val` = 0 running, 1 success, 21 bad PMK, 9 timeout, 2 other |
| 27/254 | SUPPORTED/HW_SUPPORTED_CHANNELS | 4824-byte channel list |
| 103 | CURRENT_NETWORK | ENXIO unless joined; scan-result form |
| 207 | CHANNELS_INFO | 10016-byte per-channel table |

Events are posted as kernel events with `vendor_code = KEV_VENDOR_APPLE`, `kev_class = KEV_IEEE80211_CLASS`, `kev_subclass = 1`, and `event_code` 1/2/3/4/9/10. `dv[0]` is 16 bytes of interface name (`en0`); `dv[1]` carries the link struct for code 4 (`0104:1314-1372`). The comment records the reason: IO80211.framework reads these from a `PF_SYSTEM` socket and compares the name.

A cosmetic mismatch: the driver/hardware name string is `"redwood: ath11k for the WCN6750"` (`0104:1013-1016`), although the hardware is WCN3990. It is not known whether anything keys off this string; iOS only logs it.

### 3.6 `en0` without IONetworkingFamily

`redwood_net.c` (`0104:1457-1832`) creates `en0` with the BSD interface KPI, the same mechanism as `if_fake.c`'s `feth`:

```c
struct ifnet_init_eparams init = {
    .ver = IFNET_INIT_CURRENT_VERSION,
    .len = sizeof(init),
    .flags = IFNET_INIT_LEGACY | IFNET_INIT_NX_NOAUTO,
    .uniqueid = "redwood-en0", .uniqueid_len = 11,
    .name = "en", .unit = 0,
    .family = IFNET_FAMILY_ETHERNET,
    .subfamily = link->wireless ? IFNET_SUBFAMILY_WIFI : IFNET_SUBFAMILY_ANY,
    .type = IFT_ETHER,
    .output = net_output, .demux = ether_demux,
    .add_proto = ether_add_proto, .del_proto = ether_del_proto,
    .check_multi = ether_check_multi,
    .framer_extended = ether_frameout_extended,
    .ioctl = net_ioctl,
    .broadcast_addr = etherbroadcastaddr, .broadcast_len = ETHER_ADDR_LEN,
};
```

Then: `ifnet_allocate_extended`, capabilities 0, addrlen 6, baudrate 100 Mbps, MTU 1500, flags `IFF_BROADCAST|IFF_MULTICAST|IFF_SIMPLEX`, hdrlen 14, offload 0, `ifnet_attach`, `ifnet_set_lladdr`, `bpfattach`. If the link is wireless it calls `RedwoodWLANStart("en0", address)` (`0104:1755-1830`). `net_ioctl` logs the first 80 unknown ioctls and forwards `SIOCSA80211`/`SIOCGA80211` to the Apple80211 handler (`0104:1641-1665`).

### 3.7 Registry objects and the IOCTL fallback

`RedwoodWLAN.cpp` (`0104:4587-4729`) deliberately gives the interface **no user client**:

- `IO80211Controller` is a bare `IOService` subclass, published as `RedwoodWLANController`; it gets `IOMACAddress` from the 6-byte FW address and `IOBuiltin = true`.
- `RedwoodWLAN` is an `IONetworkInterface` subclass published under the controller, with `IOInterfaceName = en0`, `BSD Name = en0`, `IOInterfaceNamePrefix = en`, `IOInterfaceType = 6`, `IOInterfaceUnit = 0`, `IOBuiltin = true`, `IOPrimaryInterface = true`, `IO80211InterfaceRole = Infrastructure`.
- `newUserClient()` logs `a user client of type 0 is asked for: there is none` and refuses. That is intentional: IO80211.framework then logs "Falling back to IOCTL path" and sends `SIOCS/GA80211` on a socket, which the kernel answers.

The comment at `0104:4593-4615` states the exact dependency: configd makes a network service only for an interface listed by `SCNetworkInterfaceCopyAll()`, and only an interface with a service can become routable; wifid waits for that ("failed to become routable interface") before Settings ticks the network. This is the architectural root of the spinner.

### 3.8 `MiniIONetworkStack` and IOKit quiesce

`MiniIONetworkStack.cpp` (`0104:4467-4586`) publishes `IONetworkStack` and a user client. It never names an interface (the BSD interface is born named), but opening it lets configd's InterfaceNamer write `Plugin:InterfaceNamer = "*QUIET*"` instead of waiting five minutes for `*TIMEOUT*`. `SCNetworkInterfaceCopyAll()` waits for one of those, and wifid/SpringBoard wait behind it. The observed log line is:

```
MiniIONetworkStack: opened by configd; the registry's busy state is 0
```

`0104` also removes the IOKit-daemon busy hold on SWEET in two places:

- `IOService::iokitDaemonLaunched()` skips `getServiceRoot()->adjustBusy(-1)` (`0104:4432-4445`).
- `StartIOKitMatching()` wraps the daemon-available hold in `if (false)` (`0104:4446-4466`), because no IOKit daemon ever reports launch and the hold would keep the registry busy forever.

### 3.9 PMEM, RPMh, rails, BCM, and the WLAN SMMU

**`/dev/pmem`**: `sweet_pmem.c` (`0104:2577-2999`) creates a root-only 0600 node when `sweetpmem=1`. It exposes `PMEM_RPMH = _IOW('P', 5, struct pmem_rpmh)` (`0104:2653-2659`). Userland wland uses it to vote the WCN3990 rails. The whitelist is exact (`0104:3669-3708`):

| Resource | Allowed voltage (mV) | Other allowed offsets |
|---|---|---|
| `ldoa9` (cx-mx) | 624–760 | enable@4 ≤1, mode@8 = 7 (HPM) |
| `ldoc1` (1.8-xo) | 1616–1984 | same |
| `ldoc2` (1.3-rfa) | 1200–1352 | same |
| `ldoc10` (3.3-ch0) | 3200–3312 | same |
| `rfclka2` | — | enable@4 ≤1 |
| `cx.lvl`, `mss.lvl` | ARC table index | offset 0, index < 16 |

Anything else, including touch L11C, is refused with `EPERM`. The observed wland votes match this table exactly:

```
wlan power: ldoa9 640 mV on -> 0
wlan power: ldoc1 1800 mV on -> 0
wlan power: ldoc2 1304 mV on -> 0
wlan power: ldoc10 3312 mV on -> 0
wlan power: rfclka2 on -> 0
```

**RPMh**: `sweet_rpmh.c` (`0104:3000-4086`) is extended by ~922 lines. It resolves command-DB entries for slaves `RH_ARC=3`, `RH_VRM=4`, `RH_BCM=5`; validates aux data; decodes ARC level tables (u16, +1 because zero is invalid, monotonic, zero padding allowed); polls completion with `RH_GIC_INTID=37` (SPI5) and refuses ownership if another user enabled/activated the SPI; quarantines an uncertain transaction by masking only its own IRQ source, never acking/resetting/retrying. `RH_READ_ACK = 8 | (1<<8)`, `RH_WRITE_ACK = RH_READ_ACK | (1<<16)`.

**BCM votes**: `sweet_rpmh_bcm_vote(res, x, y)` allows:

- `SN15`/`CN0` — the apps-SMMU path (`msm-bus 161 → 627`, active-only, 1000 KBps), small levels ≤16.
- `MC0`/`SH0`/`ACV` — memory, levels ≤0x3fff.

The command is `commit | valid | x<<14 | y`, Linux `BCM_TCS_CMD`. This exists because `0131`'s wland stalled a CPU on its first apps-SMMU read without the vote (`0104:3740-3746`).

**WLAN SMMU**: with `sweetsmmuwlan=1`, the kernel programs the stream at boot (`0104:3875-4086`):

- SID `0x240`, mask `1`.
- Find the lowest free SMR and a free context bank.
- `CBAR = 0x1f000` (stage-1 translate, stage-2 bypass), `CBA2R` AArch64, `SCTLR = 0xe0` (fault reporting, M=0).
- The observed result is `SMR6`, `S2CR 0x4`, `CB4`.

`wland` then does **not** touch the apps SMMU; its log says so explicitly:

```
smmu: WLAN 0x240/0x1 stream programmed by the kernel at boot (sweetsmmuwlan=1); not touching the apps SMMU
```

**Memory votes**: `sweet_rpmh_ddr_raise()` votes `MC0`, `SH0`, `ACV` (`0104:4081-4083`). Observed in the super log: `MC0`/`SH0` `0x6fffffff`, `ACV` `0x60000008`, all returned 0.

### 3.10 Battery

`SweetBattery.cpp` (`0104:4730-4961`) is an `IOPMPowerSource`. `sweetbattery=0` forces the old static 100%; the default is now **real reads** (`int real = 1`, `0104:4943-4948`). The poll timer is 5 s, not 30 s (`0104:4881-4887`, `4953-4958`).

**Voltage and current**

- Raw voltage is scaled by `194637 / 1,000,000` (`0104:4777`).
- Valid window 2800–4600 mV; zero/reset/floating/implausible data cannot publish 0%.
- Current subtype 3 scale 152588; subtype 4 scale 305176; raw `0x8000` and exact 0 are invalid (`0104:4798-4808`).
- Linux sign is negative=charging; IOPMPowerSource wants positive=charging, so `ma = -raw * scale / 1e6`.

**State of charge**

- 27-point OCV table from 3000 mV (0%) to 4433 mV (100%), taken from the stock DT `qcom,pc-temp-v1-lut`, Sunwoda and NVT 5020 mAh profiles agreeing within ~10 mV (`0104:4765-4772`).
- IR compensation: `ocv = mv - ma * 150 / 1000` (150 mΩ).
- Coulomb count: `fSocMilli += ma * ms / 180720`, where the divisor comes from `mA * ms / 3600000 * 100 / 5020 * 1000` (`0104:4849-4851`).
- If not SDAM-seeded and `|ma| < 100`, drift 2% of the difference to the curve per poll (`/50`) (`0104:4853-4857`).
- Clamp 0..100000; publish `(fSocMilli + 500) / 1000`; while charging and not full, cap at 99 (`0104:4860-4872`).

**QG SDAM seed**

The PM6150 QG driver keeps SOC in SDAM at `0xb600`; the code reads 16 bytes at `0xb640`, checks `sdam[6] != 0` (offset `0xb646`, valid) and `sdam[7] <= 100` (offset `0xb647`, SOC percent), and seeds `fSocMilli = sdam[7] * 1000` (`0104:4824-4845`). Observed:

```
SWEET BATTERY: QG SDAM b640: 00 01 4f 00 04 00 01 3d 53 01 00 00 54 3b 43 00
SWEET BATTERY: seed 61% from QG SDAM (curve 48%)
```

and in the other boot:

```
SWEET BATTERY: QG SDAM b640: 00 01 4f 00 04 00 01 3a 39 01 00 00 54 3b 43 00
SWEET BATTERY: seed 58% from QG SDAM (curve 60%)
```

**Failure policy**

- Consecutive invalid reads are held; after 12 (≈60 s at 5 s polls) it publishes static 100% and logs `12 failed reads in a row; static fallback` (`0104:4780-4793`).
- A valid read resets `fFailures`.

**RTC**

`SweetBattery::start()` calls `sweetSetCalendarFromRtc()` if `sweet_spmi_init()` succeeds (`0104:4947-4949`). The function reads PM6150 RTC control at `0x6046` (bit 7 enabled) and seconds at `0x6048..0x604b` little-endian, re-reads the low byte to avoid a torn read, rejects `secs < 86400`, and calls `clock_set_calendar_microtime()` only if the current calendar is ≤ 978307200 (2001-01-01) (`0104:4890-4935`). Observed:

```
SWEET RTC: calendar set from the PM6150 RTC: 53371308 s (boot time now 53371308)
```

53371308 s = 1971-09-10 17:21:48 UTC. The other boot used 53464448 s = 1971-09-11 19:14:08 UTC. The RTC is running but is not wall-clock time.

### 3.11 Boot wiring and arguments

`sweet_ufs_init()` calls the new subsystems in this order (`0104:4129-4146`):

```
sweet_log_start();
sweet_sample_start();
sweet_native_adreno_reserve_pool();   /* 0105: returns 0 */
sweet_pmem_init();                    /* /dev/pmem if sweetpmem=1 */
sweet_rpmh_ddr_raise();               /* MC0/SH0/ACV */
sweet_smmu_probe_start();             /* sweetsmmuprobe=1 */
sweet_haptic_init();                  /* 0105: no-op */
sweet_bt_init();                      /* 0105: no-op */
flame_wlan_init();                    /* /dev/wlan, en0, Apple80211 */
sweet_keys_init();
sweet_touch_init();
sweet_gpu_probe();                    /* 0105: forwards to sweet_gpu_init() */
sweet_usb_probe();
```

Boot-arg sets observed:

| Image | Boot args |
|---|---|
| Branch Wi-Fi (`xnu-wifi-boot.txt:419`) | `debug=0xc serial=0 cpus=8 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=30 sweetgpu=2 sweetusb=2 sweetfiles=1 sweetpmem=1 sweetsmmuprobe=1 sweetsmmuwlan=1 sweetwifi=1 sweetgpu_reboot=600` |
| Super-style (`xnu-super-panic.txt:328`) | same but `sweetfb_hz=60`, no `sweetusb`, no `sweetfiles`, no `sweetgpu_reboot` |

`flame_wlan_init()` is gated by `sweetwifid=0` to disable `/dev/wlan` and `en0` entirely (`0104:692-710`). The ADT path is `sweet-wlan.adt`, which adds only:

```
/arm-io/wlan {
    device_type = 'wlan';
    compatible = 'flame,wcn3990';
}
```

The product node has `wifi-chipset = '4357'`. **No MAC address properties exist in the ADT.** The interface MAC therefore comes from `FW_HELLO`; observed `02:50:49:58:45:4c`, which has the locally-administered bit set (`02`), so it is a generated/random address, not a fused one. This is inferred, not stated by wland's log.

### 3.12 `0105` link fix

`0105` is intentionally minimal (3 files, +70):

- `bsd/dev/sweet_super_compat.c`: `sweet_gpu_probe()` forwards to `sweet_gpu_init()`; `sweet_bt_init()`, `sweet_haptic_init()` no-op; `sweet_native_adreno_reserve_pool()` returns 0.
- `bsd/vfs/vfs_syscalls.c`: `sweet_vfs_mkdir()` → `mkdir1at(..., UIO_SYSSPACE)`, `sweet_vfs_symlink()` → `symlinkat_internal(...)`, `sweet_vfs_unlink()` → `unlink1(...)`, for `sweet_files.c`'s USB file server.
- `bsd/conf/files`: adds `sweet_super_compat.c`.

The seven undefined symbols in the first link were `sweet_bt_init`, `sweet_haptic_init`, `sweet_native_adreno_reserve_pool`, `sweet_gpu_probe`, `sweet_vfs_mkdir`, `sweet_vfs_symlink`, `sweet_vfs_unlink` (`NOTES.md:208-213`). `0105` addresses all seven.

---

## 4. Raw evidence

### 4.1 Patch shape

`git apply --stat` on `0104-super-wifi-battery.patch`:

```
 bsd/conf/files                          |    7
 bsd/dev/flame_sta.c                     |  242
 bsd/dev/flame_wlan.c                    |  442
 bsd/dev/redwood_apple80211.c            |  739
 bsd/dev/redwood_net.c                   |  376
 bsd/dev/redwood_sta.c                   |  371
 bsd/dev/sweet_files.c                   |  355
 bsd/dev/sweet_pmem.c                    |  417
 bsd/dev/sweet_rpmh.c                    |  922
 bsd/dev/sweet_spmi.c                    |    6
 bsd/dev/sweet_ufs.c                     |   18
 bsd/sys/flame_wlan.h                    |   69
 bsd/sys/redwood_input.h                 |    5
 bsd/sys/redwood_net.h                   |   63
 bsd/sys/redwood_sta.h                   |  122
 iokit/Kernel/IOService.cpp              |    2
 iokit/Kernel/IOStartIOKit.cpp           |    9
 iokit/Kernel/arm/MiniIONetworkStack.cpp |  114
 iokit/Kernel/arm/RedwoodWLAN.cpp        |  137
 iokit/Kernel/arm/SweetBattery.cpp       |  160
 iokit/Kernel/arm/SweetKeyStore.cpp      |   58
 iokit/conf/files.arm64                  |    2
 22 files changed, 4578 insertions(+), 58 deletions(-)
```

`0105`:

```
 bsd/conf/files               |  1 +
 bsd/dev/sweet_super_compat.c | 37 ++++++++++++++++++++++++++++++++++++
 bsd/vfs/vfs_syscalls.c       | 32 ++++++++++++++++++++++++++++++++
 3 files changed, 70 insertions(+)
```

### 4.2 Artifact hashes and sizes

| Artifact | Size (B) | SHA256 | Time |
|---|---:|---|---|
| `shim/out/shim-boot-super.img` | 17,494,016 | `67FF470F24ACC5D3A92919FC8FBFDE00E9F485E7E46C30AA8AB894BAD24B5F3F` | 2026-11-03 18:24:51 |
| `shim/out/payload-super.bin` | 16,757,888 | `8201E7DE7B17B39AF59142F23CACDEFD4A93B73A5F3811B9D7809AA24F6D7BFE` | 18:24:46 |
| `shim/out/shim-boot-branch-reboot.img` | 17,723,392 | `833B199CE8124DD9EBB36AF0A1A17E3D03D3A483A5B88A860DAA7080146821F9` | 18:35:14 |
| `shim/out/payload-branch-reboot.bin` | 16,989,856 | `FF6FEF0409ED9EECE33AB8C6C75E7739BD632CFDAC7C1C9FE3D35AB39E42584F` | 18:35:10 |
| `shim/out/shim-boot-0101s0reboot.img` | 17,399,808 | `E0BE26FCA701C96C5862B579F14B58A31A36A560F82DF1F5300D127E28A7949C` | 18:29:55 |
| `shim/out/payload-0101s0reboot.bin` | 16,663,456 | `B1A21BA8194636A0BCEB54B1394F2CEB24C13B0C584C959875E211FF422EFAFE` | 18:29:51 |
| `shim/out/shim-boot-wifi-auto.img` | 17,723,392 | `F5AB5524F163879B965A5855C3A952FCA1954E6457566F98B435201E8FD7FEFC` | 2026-11-02 16:16 |
| `logs/xnu-wifi-boot.txt` | 575,997 | `A7E90EC555DB36A646958367C6FC60C5A77527973CCE6FADC844FD935408DB35` | 2026-11-02 16:59 |
| `logs/wland-connected.log` | 111,945 | `1C1F8BBECE851C11DE281C1EF29B7A653DB7BA4787177FDC24A5417E666C8843` | 2026-11-02 16:23 |
| `logs/xnu-super-panic.txt` | 50,094 | `576CDB1A…EB99F` | 2026-11-03 18:28 |
| `logs/xnu-0101s0reboot.txt` | 50,094 | `576CDB1A…EB99F` (same) | 18:32 |

`payload-super.bin` starts at offset 0 with `SWEETXNU`; string offsets inside it:

```
SWEETXNU          0
sweetgpu        307
SWEET BATTERY   554624
wcn3990        1183642
flame wlan     1183685
IO80211Controller 1318308
RedwoodWLAN    1318373
```

This proves the 0104 code is in the payload even though `sweet_super_compat` does not appear as a literal (symbols may be stripped/optimized).

### 4.3 Branch kernel boot: interface and Apple80211

`logs/xnu-wifi-boot.txt` (8,442 lines) shows the full userland boot and Wi-Fi path. Key lines:

```
220:  flame wlan: /dev/wlan ready (major 20)
781:  exec wland
855:  MiniIONetworkStack: opened by configd; the registry's busy state is 0
2636: flame wlan: the radio is up (02:50:49:58:45:4c): en0 for wifid
2638: net: en0 attached on wcn3990 (a radio), link down
2640: flame wifi: en0 and the station are up for iOS
2649: RedwoodWLAN: a user client of type 0 is asked for: there is none
3710: apple80211: wifid sets 10 (SCAN_REQ), value 0, 5456 bytes
      (a scan: type 1, 13 channels of which 0 are not the radio's, 0 ms on each,
       a name of 0 bytes, 0 more names, flags 0x20): answered
3760: apple80211: wifid gets 11 (SCAN_RESULT), value 0, 1164 bytes: error 5
4309: apple80211: wifid sets 20 (ASSOCIATE), value 0, 592 bytes
      (a join: a name of 6 bytes, any access point, authentication 0x1/0x8,
       a key of 32 bytes of kind 6): answered
4372: net: the link (wcn3990) is up
4373: flame wifi: join -> 0
4375: apple80211: the station says: the link, 1
4376: apple80211: wifid gets 21 (ASSOCIATE_RESULT), value 1, 0 bytes: answered
4378: apple80211: wifid gets 103 (CURRENT_NETWORK), value 0, 1164 bytes: answered
```

Counts:

| Pattern | Count |
|---|---:|
| `gets 103 (CURRENT_NETWORK)` total | 149 |
| of those before line 4378 (pre-join) | 139 |
| of those at/after 4378 (post-join) | 10 |
| `gets 11 (SCAN_RESULT) … error 5` | 8 |
| `a scan is over` events | 196 |
| `sets 20 (ASSOCIATE)` | 1 |

**Interpretation:** error 6 is `ENXIO` (`0104:1153-1155`), returned for CURRENT_NETWORK when the station is not joined. The 139 pre-join errors are correct behaviour, not a fault. Error 5 is `EIO` (`0104:1089-1103`), the documented end-of-scan-list sentinel, not a failed scan. After the single successful association, CURRENT_NETWORK is answered, link is up, and the station stays up.

### 4.4 `wland` WCN3990 bring-up and join

`logs/wland-connected.log` (1,372 lines) is the strongest end-to-end Wi-Fi evidence:

```
2:  smmu: WLAN 0x240/0x1 stream programmed by the kernel at boot (sweetsmmuwlan=1); not touching the apps SMMU
3:  wlan power: ldoa9 640 mV on -> 0
4:  wlan power: ldoc1 1800 mV on -> 0
5:  wlan power: ldoc2 1304 mV on -> 0
6:  wlan power: ldoc10 3312 mV on -> 0
7:  wlan power: rfclka2 on -> 0
15: qmp: "{class: image, res: load_state, name: modem, val: on}" -> acked
17: [     0] smp2p: modem state 6 ready handover
200: tftp: read "/readonly/firmware/image/wlanmdsp.mbn" ... rsize=3812144
226: wlfw: MSA region 0: 97d00000+4000 secure
231: wlfw: chip 0x140 family 0x4002 board 0 soc 0x40090000
     fw 0x301a80a5 "QC_IMAGE_VERSION_STRING=WLAN.HL.3.0.1.c3-00165-QCAHLSWMTPLZ-1"
232: wlfw: BDF try 0: file_id 0 type -1 seg 6144 /var/local/fw/modem/bdwlan.b00
233: wlfw: board data sent (/var/local/fw/modem/bdwlan.b00, 19152 bytes, 4 segments)
234: wlfw: mac address -> 0
245: [ 20686] radio: ce: 12 rings programmed, rx buffers posted
246: bridge: /dev/wlan open: en0 and wifid
257: [ 20727] radio: *** WMI READY (fw MAC 02:50:49:58:45:4c) ***
260: [ 20743] radio: *** HTT VERSION_CONF 3.61 ***
294: [ 23293] radio: net 23: e0:63:da:**:**:** ch 44 -75 dBm WPA2/3 'casa j'
324: [ 26589] bridge: hello: the kernel makes en0
507: [109311] bridge: scan done, 51 networks for wifid
793: [154690] bridge: leave
795: [154754] bridge: join 'casa j' (PMK) -> 0
796: [154758] radio: join: 'casa j' e0:63:da:**:**:** 2437 MHz -71 dBm WPA2
799: [154891] radio: join: auth reply status 0
800: [154895] radio: join: assoc reply status 0 aid 4
801: [154895] radio: join: associated, waiting for the 4-way handshake
804: [154949] radio: *** joined 'casa j' ***
805: [154949] bridge: link up 'casa j'
878: [180542] radio: stats: state 5, tx 2 sent 2 done 0 failed,
     rx 135 to the IP side, htt msdus 137, ce tx full 0/0/0
1018:[210625] radio: stats: state 5, ... rx 353 ... htt msdus 355
1372:[300795] radio: stats: state 5, ... rx 833 ... htt msdus 835
```

This is a complete WCN3990 path: modem firmware load, QMI/WLFW, MSA assignment, BDF download, CE rings, WMI, HTT 3.61, scan, PMK join, 4-way handshake, link up, 833 RX frames over 300 s. The SSID `casa j` and BSSIDs are redacted in this note only where the log itself redacts them; the log contains full BSSIDs for many networks, so treat it as sensitive.

### 4.5 The super/branch-reboot boot failure

Both `logs/xnu-super-panic.txt.shim.txt` and `logs/xnu-0101s0reboot.txt.shim.txt` are byte-identical (SHA256 `3703A528…B7CFD`) and begin:

```
SHIM sweet milestone 4: xnu loader
INITRD lo=855FE000 hi=855FE060
LOADER no SWEETXNU payload
REBOOT pon spare=00000004 rc=00000000
```

`shim/loader.c:83-90`:

```c
if (!fdt_chosen_u64(dtb, "linux,initrd-start", &rd_start) ||
    !fdt_chosen_u64(dtb, "linux,initrd-end", &rd_end))
    return "no initrd in /chosen";
const struct payload *p = (const struct payload *)rd_start;
if (!magic_ok(p->magic))
    return "no SWEETXNU payload";
```

So the shim looked at `0x855FE000..0x855FE060` (96 bytes), not at the image's payload at `0x5E000` (385,024). The payload is present in the image; the initrd property handed to the shim does not describe it (likely a stale/wrong `/chosen` value, not a corrupted payload). `logs/xnu-wifi-boot.txt.shim.txt` has the exact same three lines, yet `logs/xnu-wifi-boot.txt` is a successful full boot. This proves the log pairs are stale/mixed: the kernel log is the previous good boot, the shim log is the current failed boot.

The super kernel log itself (`logs/xnu-super-panic.txt`, 610 lines) contains:

```
73:  SWEET FB: statistics every second (SWEET FPS)
75:  SWEET FB: modes published: 1125x2436 at 60 Hz
80:  SWEET RTC: calendar set from the PM6150 RTC: 53464448 s
103: SWEET BATTERY: QG SDAM b640: 00 01 4f 00 04 00 01 3a 39 01 00 00 54 3b 43 00
104: SWEET BATTERY: seed 58% from QG SDAM (curve 60%)
105: SWEET BATTERY: 58% (curve 60%) 4031mV ocv 3995mV 240mA external=1 charging=1 full=0
154: SWEET PMEM: /dev/pmem ready (major 19)
208: flame wlan: /dev/wlan ready (major 20)
223: BSD root: ufsroot0, major 1, minor 0
234: exec launchd
328: boot-args = ... sweetfb_hz=60 sweetgpu=2 sweetpmem=1 sweetsmmuprobe=1 sweetsmmuwlan=1 sweetwifi=1
400: SWEET SMMU: WLAN 0x240/0x1 -> CB4 via SMR6: SMR 0x80010240 S2CR 0x4 SCTLR 0xe0 CBAR 0x1f000 -> ok
```

It reaches `launchd` boot tasks through `launchd_cache_loader` (line 586), then emits only `SWEET FPS: 0 swaps ...` for lines 587-610. There is **no** `exec wland`, **no** `exec wifid`, **no** `exec SpringBoard`, **no** `net: en0`, **no** Apple80211 line, and **no** panic. The ~59 one-second FPS lines cover about a minute. Whether this is an early log capture or a boot stall after `launchd_cache_loader` is unknown; the absence of SpringBoard is real in the captured window.

### 4.6 Battery observations

`logs/xnu-wifi-boot.txt`:

```
68:  SWEET BATTERY: SPMI arb=0x50000000 APIDs=512, observer reads only
84:  SWEET RTC: calendar set from the PM6150 RTC: 53371308 s (boot time now 53371308)
118: SWEET BATTERY: QG SDAM b640: 00 01 4f 00 04 00 01 3d 53 01 00 00 54 3b 43 00
119: SWEET BATTERY: seed 61% from QG SDAM (curve 48%)
120: SWEET BATTERY: 61% (curve 48%) 3884mV ocv 3884mV -3mA external=1 charging=1 full=0
121: SWEET BATTERY: PM6150 / estimated SOC, 61% 3884mV external=1 charging=1
2355: SWEET BATTERY: 61% (curve 46%) 3884mV ocv 3877mV 49mA external=1 charging=1 full=0
8220: SWEET BATTERY: 57% (curve 37%) 3808mV ocv 3832mV -164mA external=1 charging=1 full=0
8372: SWEET BATTERY: 57% (curve 36%) 3771mV ocv 3829mV -389mA external=1 charging=1 full=0
```

- 40 battery samples, each 12 polls (≈60 s) apart, span ≈40 min.
- SOC fell 61% → 57%.
- Every sample says `external=1 charging=1`, but current is frequently negative (discharging): −164 mA, −389 mA, −533 mA.
- The SDAM seed (61%) disagrees with the OCV curve (48%) by 13 points; the coulomb count holds near the seed while the curve falls, which is the intended SDAM-seeded behaviour.
- In the super log, the seed is 58% vs curve 60%, 4031 mV, +240 mA, consistent with charging.

**Observed contradiction:** “charging” is asserted while net current is negative. It may be a real USB-host current limit (the phone draws more than the port supplies), a sign/scaling error, or a charger-state misread. Not resolved.

### 4.7 ADT

`python tools/adt.py dump shim/out/sweet-wlan.adt` (read-only) shows:

```
compatible = 'D22AP|iPhone10,3|xiaomi,sweet|qcom,sm7150|AppleARM'
model = 'iPhone10,3'
target-type = 'D22'
...
wlan {
    AAPL,phandle = 0x18
    device_type = 'wlan'
    compatible = 'flame,wcn3990'
}
...
wifi-chipset = '4357'
```

There is no `local-mac-address`, `mac-address`, or `address` property under `/arm-io/wlan` or the product node. The only Wi-Fi-specific ADT change is the `/arm-io/wlan` node.

### 4.8 CI and donor provenance

CI:

- `41494548855`: 0104 build (per `NOTES.md:199`).
- `41498675277`: 0105, cancelled for macOS arm64 runner capacity (`NOTES.md:216-218`).
- `41501352880`: `macos-15-intel`, queued, no runner at 18:38Z 2026-11-02.
- `41502238106`: `macos-latest`, branch `ci-macos-latest`, queued, no runner at the same time.

`.github/workflows/xnu.yml:37-41` records why: `macos-14` retired, `macos-15` arm64 capacity constrained, `macos-15-intel` has Xcode 16 and cross-compiles arm64.

Donor (WSL, read-only):

```
/home/pablo/research/DC28088-wifi/
  SHA256SUMS
  netsvc        88,160 B
  wifi-build.json
  wland        247,696 B
/home/pablo/research/DC28088-kernel/
  kernel.development.sweet  17,565,712 B (Mach-O, not a source tree)
```

`wifi-build.json`:

```json
{
  "donor": "Yofuness/ios-flame sunfish",
  "donor_commit": "f09fdb58a2c074d131072947b247240532b7d97d",
  "patches": {
    "userspace/wifi/patches/0001-sweet-board-rails-msa-bdf.patch": "f2d208e0...",
    "userspace/wifi/patches/0002-sweet-kernel-programs-wlan-smmu-stream.patch": "f6a6e8a7..."
  },
  "files": {
    "wland": "951a05a2e2d68260c50b097286bfb2561d00615b74793e2cb4f21dd4d974d0e1",
    "netsvc": "005e61f876f9874ef433c9c0be040458c747c17896f6a3a0f8e9e44c8e39c6d9"
  }
}
```

This is a **userland + two small kernel patches** donor, not a drop-in kernel. The branch tree's larger Wi-Fi work is in the 0104 port.

---

## 5. Observed vs inferred vs unknown

### 5.1 Observed

| # | Observation | Evidence |
|---|---|---|
| O1 | WCN3990 firmware boots, BDF downloads, WMI/HTT come up | `wland-connected.log:200-261` |
| O2 | wland scans 51–64 networks | `wland-connected.log:507,584,655,723,791` |
| O3 | wland joins `casa j` with PMK, auth/assoc status 0, 4-way completes | `wland-connected.log:793-805` |
| O4 | Link stays up; state 5; 833 RX frames / 835 HTT MSDUs at 300 s | `wland-connected.log:878,1018,1372` |
| O5 | Kernel creates `/dev/wlan`, `en0`, and the Apple80211 path | `xnu-wifi-boot.txt:220,2636-2640` |
| O6 | RedwoodWLAN refuses a user client by design | `xnu-wifi-boot.txt:2649,2742,2764,4355` |
| O7 | wifid scans, associates once, gets result value 1 | `xnu-wifi-boot.txt:3710,4309,4376` |
| O8 | CURRENT_NETWORK is answered after join, ENXIO before join | `xnu-wifi-boot.txt:4378-4846`; `0104:1153-1155` |
| O9 | configd configures only `lo0`; no `en0` address/DHCP | `xnu-wifi-boot.txt` `SWEET NET:` lines |
| O10 | Battery seeds from QG SDAM and counts charge | `xnu-wifi-boot.txt:118-121`, `0104:4824-4877` |
| O11 | 40 samples show 61% → 57% while `charging=1`, negative current | `xnu-wifi-boot.txt:120,2355,8220,8372` |
| O12 | RTC sets calendar to ~1971 epoch | `xnu-wifi-boot.txt:84`, `xnu-super-panic.txt:80` |
| O13 | Super log and 0101s0reboot log are byte-identical, no panic, contain 0104 lines | SHA256; `xnu-super-panic.txt:103,208,400` |
| O14 | Paired shim logs say `INITRD lo=855FE000 hi=855FE060`, `no SWEETXNU payload` | `.shim.txt` lines 1-3 |
| O15 | `shim-boot-super.img` contains a valid `SWEETXNU` payload at 0x5E000 | image header + string scan |
| O16 | `payload-super.bin` contains 0104 strings and starts with `SWEETXNU` | string offsets |
| O17 | `0105` CI link result is not recorded; runs were cancelled/queued | `NOTES.md:216-222` |
| O18 | Branch-reboot image exists with no ring/log | file inventory |

### 5.2 Inferred

| # | Inference | Basis | Confidence |
|---|---|---|---|
| I1 | The super kernel has been built and linked at least once | `payload-super.bin` exists and is a valid XNU payload; 0104 alone failed at link, so a fix (0105 or equivalent) must have been present | High |
| I2 | A 0104-feature kernel booted at least once with 60 Hz and super-style args | `xnu-super-panic.txt` has 0104-only lines and 60 Hz args; branch/super identity not proven | Medium |
| I3 | The named super image attempt did not boot | paired shim log fails before XNU | High |
| I4 | The spinner is a configd service problem, not association | link up + CURRENT_NETWORK answered + only `lo0` configured | High |
| I5 | wland's MAC is generated, not fused | `02:` locally-administered prefix; no MAC in ADT; `wlfw: mac address -> 0` | Medium-high |
| I6 | The super boot captured in `xnu-super-panic.txt` did not reach SpringBoard within ~60 s | no `exec SpringBoard`, 60 × `0 swaps` | Medium |
| I7 | `0105` likely links | payload exists; stub set covers all seven symbols | Medium |
| I8 | The 0104 kernel + topaz GPU can coexist at the source level | 0104 excludes branch GPU and `0105` forwards `sweet_gpu_probe` to `sweet_gpu_init` | Medium |
| I9 | The initrd failure is a DTB/`/chosen` handoff bug, not payload corruption | payload magic intact; 96-byte initrd range | High |
| I10 | The negative current while “charging” is a supply limitation or sign/scaling issue | 40 consistent samples, USB host context | Medium |

### 5.3 Unknown

| # | Unknown | Why it matters |
|---|---|---|
| U1 | Which physical boot produced the 0104 kernel log | Can't tie it to `shim-boot-super.img` |
| U2 | Whether `41501352880` / `41502238106` ever ran | `0105` link unproven |
| U3 | Why `/chosen/linux,initrd-start` is `0x855FE000` | Blocks every image using that boot path |
| U4 | Whether `wland` launches under the super kernel | No `exec wland` in the captured 60 s |
| U5 | Whether Apple80211 16.5 layouts are exact for 16.7.16 | REFUSED types 96/97/383/115 may be layout drift |
| U6 | Why 0 swaps for 60 s in the super log | No SpringBoard/backboardd in window; could be early capture or stall |
| U7 | Why RTC is 1971 | Time-based TLS/cert flows may fail |
| U8 | Whether the MAC is stable across boots | DHCP leases, captive portals, AP ACLs |
| U9 | Battery gauge accuracy under real load | 13-point SDAM/OCV disagreement is large |
| U10 | Whether the charger actually sources current | `charging=1` + negative mA |
| U11 | Whether `sweet-wlan.adt` is sufficient for 16.7.16's Wi-Fi stack | Only `/wlan` added; no MACs/calibration |
| U12 | Branch-reboot image behaviour | No ring/log |

---

## 6. Failed attempts

### 6.1 Branch Metal bundle on the topaz root

Installing the DC28088 `SweetMetal2.bundle` and setting `CA_FORCE_TIMER=1` in the backboardd job produced green lines, no blur, a non-smooth UI, and **Wi-Fi scan stopped**. It was reverted (bundle removed, launchd restored). The branch Metal stack expects the branch root/userland. This is why the super plan ports Wi-Fi/battery source instead of importing the branch GPU stack (`NOTES.md:191-198`, commit `519bf9c`).

### 6.2 Branch kernel + topaz root

The branch kernel's GPU is NativeAdreno/Metal; with the topaz root it falls back/lags, described as a red clock and CPU-like rendering (`NOTES.md:186-190`). It gives Wi-Fi + battery but not fast UI. This is the baseline the super image is meant to replace.

### 6.3 `0104` first link

Seven undefined symbols, exactly the branch UFS hooks and file-server VFS helpers (`NOTES.md:208-213`). The link failure is not a Wi-Fi logic failure; it is a missing-symbol failure caused by excluding branch drivers. `0105` adds no-op stubs and wrappers.

### 6.4 `0105` CI

The macOS arm64 runner was cancelled for capacity; the workflow moved to `macos-15-intel`; two runs were left queued with no runner. No link map or final binary is recorded in `NOTES.md`. If `payload-super.bin` was produced from a local link, the CI result is still not documented.

### 6.5 Super boot attempts

- `shim-boot-super.img` built at 18:24:51.
- At 18:28 the shim log shows `INITRD lo=855FE000 hi=855FE060` and `no SWEETXNU payload`, then `REBOOT pon spare=4`.
- At 18:29 a control `0101s0reboot` image was built.
- At 18:32 the control log was written and is byte-identical to the “super panic” log.
- At 18:35 a `branch-reboot` image was built; no log follows.

The attempt did not test XNU. It tested the shim's initrd handoff and failed there.

### 6.6 The “panic” mislabel

`xnu-super-panic.txt` contains zero `panic` strings and ends with 60 FPS lines. Naming it a panic caused the earlier handoff to discard it. The correct label is “0104 60 Hz kernel log, provenance unknown, duplicated as 0101s0reboot”.

### 6.7 Spinner after association

Association + link up is insufficient. The branch note 0145 records that configd needs a standard Wi-Fi service in `/Library/Preferences/SystemConfiguration/preferences.plist` (`en0`, AirPort, IPv4 DHCP, IPv6 Automatic). A plist with only `HostNames` (configd's rewrite) sends no DHCP. The root's old plist was moved to `.pre-wifi` (`NOTES.md:223-227`). The super logs corroborate: `configd` configures `lo0` only, and there is no `en0` address.

### 6.8 Earlier battery/performance experiments

- Static 100% battery was the old default; real reads are now default (`0104:4943-4948`).
- 30 s poll was too slow for plug/unplug; now 5 s.
- A single failed poll previously published 100% and not-charging for 5 s; now up to 12 failures hold the last good value.
- Trust-cache/AMFI is unavailable (`xnu-wifi-boot.txt:58`), so the root runs unsealed; this is context, not a Wi-Fi failure.
- `0103 ca_vbl=1` was worse (6.82 vs 17.19 swaps/s) and was discarded (`NOTES.md:160-167`); the super line keeps `0101`/`0102` GPU behaviour.

---

## 7. Open hypotheses and discriminating tests

### H1 — The initrd handoff is the only thing blocking the super image

**Claim:** the payload is valid; `0x855FE000..0x855FE060` is a DTB/`/chosen` stub, not the boot-image ramdisk. The boot header declares `ramdisk_addr = 0x1000000`, `ramdisk_size = 16,757,888`, and the payload sits at image offset `0x5E000`; the DTB's initrd property is what the shim actually follows.

**Test:** log `linux,initrd-start/end` and the boot header's `ramdisk_addr/size` in the shim; compare. Patch `/chosen` at build time or make the shim fall back to `ramdisk_addr`. This is a code change and is out of scope for this read-only note.

**Prediction if true:** with the correct pointer, `LOADER` advances to `PHYS/VIRT/ENTRY/SEGS/BOOTARG/JUMP`, and XNU prints its version banner.

### H2 — The spinner is the missing standard network service

**Claim:** configd never creates an `en0` service because the preferences plist lacks the standard Wi-Fi/AirPort/DHCP/IPv6 service. wifid joins and gets CURRENT_NETWORK, but waits for `en0` to become routable.

**Test:** install/create the standard service (or let configd create it from a clean plist), then look for `SWEET NET: configd en0 add address …` and a DHCP lease in the kernel log. Compare with the branch 0145 result.

**Prediction:** Settings ticks the network and the spinner clears without any kernel change.

### H3 — `0105` links but the CI record is missing

**Claim:** `payload-super.bin` proves a linked 0104+fix kernel exists; the queued runs may have completed after the last note.

**Test:** query the two run IDs and capture `link`/`undefined symbol` output and the downloaded kernel hash.

**Prediction:** one run is green, and the payload hash matches its artifact.

### H4 — RTC epoch is wrong but boot-unique

**Claim:** the PM6150 RTC is running from a reset point around 1971, not wall time. `wland`'s auto-start uses the boot time only for uniqueness, so Wi-Fi works, but TLS/certificate/time-based services see 1971.

**Test:** read the RTC registers twice with a known delay, compare to a host clock, and check whether iOS sets time from network after DHCP. If the RTC is simply unset, setting it once may persist.

**Prediction:** the RTC advances at 1 Hz but is offset by ~55 years; correcting it does not change wland's uniqueness logic.

### H5 — The MAC is random per boot

**Claim:** no MAC in the ADT; `wlfw: mac address -> 0`; `FW_HELLO` gives `02:50:49:58:45:4c`. The `02` bit is locally administered.

**Test:** capture `flame wlan: the radio is up (…)` across three boots. If it changes, it is generated. If it is stable, wland persists it somewhere (e.g., `/var/local`).

**Prediction:** it changes unless a persistence file exists.

### H6 — The charger reports “charging” but the port cannot supply the load

**Claim:** `external=1 charging=1` comes from the SMB5 path, while negative current and falling SOC show net discharge. A PC USB port (500 mA) may be below the phone's idle+Wi-Fi load.

**Test:** repeat on a real charger; log `usb`, `path`, `charger`, `rawCurrent`, and `subtype` at each poll; compare sign and magnitude with a known ammeter.

**Prediction:** on a 2 A charger, current becomes positive and SOC rises; the flag logic is correct.

### H7 — Scan `error 5` is normal end-of-list

**Claim:** `get 11` returns one BSS per request and `EIO` when `result_next` exceeds `fw_nbss` (`0104:1089-1103`). The 8 error-5 lines are list terminators, not failures.

**Test:** count SCAN_RESULT successes before each error-5 and compare to the BSS count (51–64). If successes + 1 = count, confirmed.

**Prediction:** yes.

### H8 — REFUSED Apple80211 types indicate 16.5 → 16.7.16 drift

**Claim:** types 96, 97, 106, 115, 383, 422, 25, 365 are unhandled. Some may be new/changed in 16.7.16, or may be optional. `CARD_CAPABILITIES`, `POWER`, channels, scan, and associate are the critical ones and are handled.

**Test:** map the refused type numbers against 16.7.16's IO80211.framework; add handlers only where wifid's flow needs them. Do not guess layouts; static-assert sizes.

**Prediction:** the join path works without them; Settings polish may need a few.

### H9 — The 0-swap super log is an early capture, not a GPU stall

**Claim:** the log ends at `launchd_cache_loader` + ~24 s of FPS lines. SpringBoard may simply not have been reached before capture.

**Test:** capture for 5 minutes and look for `exec SpringBoard`, `exec backboardd`, and nonzero swaps. If it never arrives, investigate launchd job ordering / IOKit quiesce.

**Prediction:** SpringBoard appears later; if not, the 0104/IOKit changes broke a boot task.

### H10 — `sweetsmmuwlan=1` is mandatory for wland

**Claim:** the kernel programs the WLAN stream at boot; wland does not touch the apps SMMU. Without the arg, wland's first SMMU access may stall a CPU (the 0131 failure).

**Test:** boot the branch kernel with `sweetsmmuwlan=0` and capture; expect the wland SMMU message to change or a stall.

**Prediction:** the arg is required on this kernel.

### H11 — `sweetpmem=1` is mandatory for rail votes

**Claim:** wland votes rails through `PMEM_RPMH`; without `/dev/pmem` those votes fail and the firmware load may fail or the radio may be unstable.

**Test:** boot with `sweetpmem=0` and observe wland's rail lines/`open /dev/pmem` failure.

**Prediction:** Wi-Fi does not come up.

### H12 — `0104`'s IOKit quiesce changes are required for wifid

**Claim:** without disabling the IOKit-daemon busy hold, the registry never quiesces, InterfaceNamer times out after 5 min, and wifid waits.

**Test:** revert only the two quiesce hunks and compare `MiniIONetworkStack` / `*QUIET*` timing.

**Prediction:** wifid stalls or is delayed by minutes.

---

## 8. Inventory

### 8.1 Repository artifacts

| Path | Role |
|---|---|
| `xnu/patches/0104-super-wifi-battery.patch` | Main port: 22 files, +4578/−58 |
| `xnu/patches/0105-super-link-fix.patch` | Link fix: 3 files, +70 |
| `shim/out/shim-boot-super.img` | Super boot image, 17,494,016 B |
| `shim/out/payload-super.bin` | XNU+ADT+args payload, 16,757,888 B |
| `shim/out/shim-boot-branch-reboot.img` | Branch reboot image, 17,723,392 B |
| `shim/out/payload-branch-reboot.bin` | Branch payload, 16,989,856 B |
| `shim/out/shim-boot-0101s0reboot.img` | Control image, 17,399,808 B |
| `shim/out/shim-boot-wifi-auto.img` | Known branch Wi-Fi image, 17,723,392 B |
| `shim/out/sweet-wlan.adt` | ADT with `/arm-io/wlan`, `flame,wcn3990` |
| `logs/xnu-wifi-boot.txt` | 8,442-line branch Wi-Fi boot |
| `logs/wland-connected.log` | 1,372-line WCN3990 bring-up/join |
| `logs/xnu-super-panic.txt` | 610-line 0104 60 Hz kernel log; misnamed; duplicate |
| `logs/xnu-0101s0reboot.txt` | Byte-identical duplicate |
| `logs/xnu-super-panic.txt.shim.txt` | Failed loader: `INITRD 855FE000`, no payload |
| `logs/xnu-wifi-boot.txt.shim.txt` | Same failed loader pattern |
| `tools/adt.py` | Read-only ADT dumper used |
| `.github/workflows/xnu.yml` | `macos-15-intel`, Xcode 16 cross-compile |

### 8.2 Root/userland artifacts referenced by the notes (not in this repo)

| Path | Role |
|---|---|
| `/var/local/bin/wland` | Mach-O arm64 Wi-Fi userland, 247,696 B |
| `/var/local/bin/netsvc` | Mach-O arm64 network service, 88,160 B |
| `/var/local/fw/modem/` | 322 files, ~80 MB, firmware/BDF |
| `/var/local/fw/rmtfs/{modemst1,modemst2,fsg,fsc}.img` | Modem file system images |
| `/System/Library/xpc/launchd.plist` | Contains `org.ios-sweet.wland` (531 jobs) |
| `/Library/Preferences/SystemConfiguration/preferences.plist` | Old plist moved to `.pre-wifi`; standard service absent |

### 8.3 WSL donor

| Path | Role |
|---|---|
| `/home/pablo/research/DC28088-wifi/wland` | 247,696 B; hash in `wifi-build.json` |
| `/home/pablo/research/DC28088-wifi/netsvc` | 88,160 B; hash in `wifi-build.json` |
| `/home/pablo/research/DC28088-wifi/wifi-build.json` | Donor commit + patch/file hashes |
| `/home/pablo/research/DC28088-wifi/SHA256SUMS` | Hash manifest |
| `/home/pablo/research/DC28088-kernel/kernel.development.sweet` | 17,565,712 B Mach-O, not source |

### 8.4 CI

| Run | Purpose | State |
|---|---|---|
| `41494548855` | 0104 build | Built (per notes) |
| `41498675277` | 0105 build | Cancelled: arm64 capacity |
| `41501352880` | 0105 on `macos-15-intel` | Queued/no runner at last record |
| `41502238106` | 0105 on `macos-latest` branch | Queued/no runner at last record |

---

## 9. Next steps

Ordered by dependency. None of these was executed here.

1. **Resolve the initrd handoff first.** Instrument the shim to print the boot header's `ramdisk_addr`, `ramdisk_size`, and the DTB `/chosen/linux,initrd-start/end`. Compare with `INITRD lo=855FE000 hi=855FE060`. Fix the DTB or the shim fallback. Do not touch 0104/0105 until `LOADER` passes.
2. **Confirm `0105` link.** Query runs `41501352880` and `41502238106`; capture the link map, undefined symbols, and kernel hash. If green, rebuild `payload-super.bin` from that exact artifact and record the hash.
3. **Boot the super image and capture a ring/log.** Required markers, in order: `flame wlan: /dev/wlan ready`, `SWEET SMMU: WLAN 0x240/0x1 -> CB4`, `exec wland`, `flame wlan: the radio is up`, `net: en0 attached`, `MiniIONetworkStack: opened by configd`, `flame wifi: en0 and the station are up`, `apple80211` scan/join, `net: the link (wcn3990) is up`, `ASSOCIATE_RESULT value 1`, `CURRENT_NETWORK answered`.
4. **Fix the network service, not the driver.** With association proven, install/create the standard `en0`/AirPort/IPv4 DHCP/IPv6 Automatic service in `preferences.plist`. Verify `SWEET NET: configd en0 add address …` and a DHCP lease. Only then judge the spinner.
5. **Capture for at least 5 minutes.** Resolve H9 (early log vs stall). Look for `exec SpringBoard`, `exec backboardd`, and nonzero `SWEET FPS` swaps.
6. **Validate battery over 30–60 minutes.** Log raw `usb`, `path`, `charger`, `subtype`, `rawCurrent`, `mv`, `ocv`, `ma`, `percent`, `fFailures`. Test on a real charger and on USB. Check the 12-failure hold and the 99% charging cap.
7. **Fix/confirm RTC.** Read PM6150 `0x6046/0x6048` twice with a delay; compare to host time. If it is unset, set it once and verify persistence. Do not let a wrong 1971 clock break TLS silently.
8. **Check MAC stability.** Three boots, compare `FW_HELLO` address. If random, decide whether to persist a locally administered MAC in the ADT or in wland.
9. **Only then performance.** Keep the `0101`/`0102` topaz path; measure swaps/s and frame time under the super kernel with Wi-Fi up. Compare with the 0101s0 baseline, not with `0103 ca_vbl=1`.
10. **Record exact results.** Update `NOTES.md` with run IDs, image hashes, boot markers, and the observed/inferred split. This note deliberately did not edit it.

---

## 10. Questions for another AI

1. Given `INITRD lo=855FE000 hi=855FE060` but a payload at `0x5E000`, is `0x855FE000` a DTB address, an ABL `/chosen` stub, or a stale Android `initrd` property? What is the cleanest fix that does not touch the XNU payload?
2. Why do `xnu-wifi-boot.txt` and `xnu-super-panic.txt` both have a paired shim log saying “no payload” while the kernel logs are successful? Is the UFS log pull definitively reading the previous boot's `dmesg`, or can the shim boot a kernel from another path after the error?
3. Does `0105` cover every symbol the 0104 tree needs, or are there weak/optional paths (`sweet_files`, `SweetKeyStore`, `sweet_pmem`) that link but fail at runtime?
4. Is the `02:50:49:58:45:4c` MAC generated by `wland`, by the WCN3990 firmware, or by the kernel? Where is it persisted, if anywhere?
5. Does iOS 16.7.16's IO80211.framework still fall back to `SIOCS/GA80211` when `newUserClient` refuses, or does it require a user client for some paths? The 16.5 layout asserts may not cover 16.7.16.
6. Which of the REFUSED types (96, 97, 106, 115, 383, 422, 25, 365) are mandatory for Settings to tick the network, versus optional?
7. Is the spinner purely the missing `preferences.plist` service, or does wifid also require a `IO80211InterfaceRole`/`IONetworkInterface` property that `RedwoodWLAN` does not set?
8. Why does the 0104 60 Hz log show 60 s of `0 swaps` and no `exec SpringBoard`? Is that an early capture, a launchd stall, or an IOKit-quiesce regression?
9. Is the PM6150 RTC really at 1971, or is `0x6048` a different counter/epoch? What is the correct PM6150 RTC base and does iOS set it from NTP after DHCP?
10. Why does `charging=1` coexist with negative current for 40 minutes? Is the SMB5 `charger`/`path` decode wrong, or is the USB host simply underpowered?
11. Is 150 mΩ the right IR for this cell, and is the 5020 mAh count the right capacity for the Sunwoda/NVT pack? The 13-point SDAM/OCV disagreement suggests the seed is trusted more than the curve; is that correct?
12. Does `sweet-wlan.adt` need calibration/MAC properties for 16.7.16, or is the branch's “ADT MACs + AMFI trust-cache + LaunchServices rebuild” path only for wallpaper/UI?
13. If the super kernel boots, will `wland`'s auto-start compare `kern.boottime` with `/var/local/wland.boot` and exit “already started in this boot” because the RTC is wrong? The 0104 RTC fix exists precisely for this; verify it on the super image.
14. What is the intended division of labour between `sweetsmmuprobe=1`, `sweetsmmuwlan=1`, and `sweetpmem=1`? Are all three required on the super image, or can `sweetsmmuprobe` be dropped after the stream is proven?
15. Is `0105`'s `sweet_gpu_probe -> sweet_gpu_init` forwarding safe on the fast topaz path, or does it double-initialize the GPU after `sweet_ufs_init` already called the old `sweet_gpu_init`? The patch replaces the old direct call; confirm the call graph.

---

### Appendix A — Quick command index used for this note

Read-only commands, for reproducibility:

```powershell
git log -12 --format="%h %ad %s" --date=iso-strict
git apply --stat xnu/patches/0104-super-wifi-battery.patch
git apply --stat xnu/patches/0105-super-link-fix.patch
Get-FileHash shim/out/*.img,shim/out/payload-*.bin -Algorithm SHA256
python tools/adt.py dump shim/out/sweet-wlan.adt
Select-String -Path logs/xnu-wifi-boot.txt -Pattern "flame wlan|net: en0|apple80211|SWEET BATTERY|SWEET SMMU|SWEET NET:"
Select-String -Path logs/wland-connected.log -Pattern "wlfw|bridge|radio: join|stats:"
Get-Content logs/xnu-super-panic.txt.shim.txt -TotalCount 5
```

No device or write command was run.

### Appendix B — Abbreviations

| Term | Meaning |
|---|---|
| ADT | Apple Device Tree |
| AKS | Apple KeyStore |
| BCM | Bus Clock Manager (RPMh bus resource) |
| BDF | Board Data File (WCN3990 calibration) |
| BSS | Basic Service Set (an AP) |
| CE | Copy Engine (WCN3990) |
| HTT | High Throughput Transport (WCN3990 host/firmware) |
| OCV | Open-Circuit Voltage |
| PMEM | Physical Memory device (`/dev/pmem`) |
| QG | Qualcomm Fuel Gauge |
| RPMh | Resource Power Manager (hardened) |
| SDAM | Shared Direct Access Memory (PM6150 QG state) |
| SMMU | System Memory Management Unit |
| SMR/S2CR | Stream Matching Register / Stream-to-Context Register |
| WMI | Wireless Module Interface (WCN3990) |
| XNU | Darwin kernel |

<!-- END -->
