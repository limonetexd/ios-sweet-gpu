# Agent notes index — 2026-11-03

Five read-only documentation agents, **48.694 words** total. These are raw working notes, not a
single source of truth: each file carries its own evidence labels (`OBS` / `INF` / `DESC` or
equivalent). Read this index first, then the specific note.

| File | Words | Scope | Core finding |
|---|---:|---|---|
| `xnu-gpu-kernel.md` | 9.723 | XNU/GPU/kernel bring-up, shim, ADT, boot image, SMMU/RPMH | GPU is alive and idle; the panic is not GPU. The ring labeled “super” is not from the current super artifact. |
| `root-launchd-panic.md` | 9.847 | Root, sparse image, `userdata` flash, `launchd`, panic forensics | The failure is in userspace (`launchd`/`launchd_cache_loader`), not HFS+ metadata. Ring does not contain the panic line. |
| `wifi-battery-branch.md` | 9.187 | DC28088 branch, WCN3990/`wland`/`netsvc`, configd/DHCP, battery | Wi-Fi works on the branch (firmware/BDF, association, rx 833); the spinner is configd/DHCP. Battery reads from QG SDAM. |
| `build-ci-artifacts.md` | 9.693 | CI, artifact download, `mkpayload`, boot image v2, hashes, reproducibility | CI runs are in `limonetexd/ios-sweet-gpu`; 0105 succeeded; byte-for-byte reproduction is blocked by `mkadt.py` (`os.urandom(64)`). |
| `usb-vfs-super-compat.md` | 10.244 | 0105 link fix, `sweet_super_compat.c`, VFS wrappers, `sweet_files` | 0105 links, but `_sweet_files_start` has zero `B`/`BL` xrefs: the USB file server is linked but unreachable. |

## Cross-cutting facts

1. **GPU is not the panic.** Ring evidence: GMU `0xbabeface`, `CP_MEM_WRITE 0x5ee7c0de`,
   `IB FROM XNU MEMORY RAN`, fence 1; then 0 swaps/0 presents, 1 surface, 0 MB wired.
   Kernel and GPU stay alive.
2. **The “super panic” ring is mislabeled.** `logs/xnu-super-panic.txt` is byte-identical to
   `logs/xnu-0101s0reboot.txt` (SHA256
   `576cdb1aca91c3975ce4c2bcfcea0360abc2d43eaed55894462c050d2ffeb99f`). It contains no panic
   line, has 302 boot-args vs 346 for the super, and contains 0104 strings that the 0101 payload
   does not have. Its boot-args lack `sweetfiles=1`/`sweetusb=2`. The panic text
   `initproc exited -- exit reason namespace 2 subcode 0x8 -- code 0x1` is the user's
   transcription, not an artifact.
3. **Blocker is `launchd`/`launchd_cache_loader`.** After `exec launchd_cache_loader` the ring
   has ~24 one-second `SWEET FPS` lines (~24 s), not 3 s, and none of the 9 lines the helper
   prints on the branch. The branch, with the same root/ADT, prints them and reaches
   SpringBoard. The delta is 0104/0105 (IOKit quiesce, AKS, new services) or a missing branch
   patch — not GPU.
4. **Wi-Fi/battery kernel-side ready; userland not reached under the super.** `/dev/wlan`
   major 20, SMMU WLAN SID `0x240` -> CB4/SMR6, RPMH SN15/CN0, DDR 16383, QG SDAM 58% /
   4031 mV. Under the super, no process opened `/dev/wlan`: no `wland`, `wifid`, `en0`,
   `RedwoodWLAN`. On the branch: WCN3990 firmware/BDF, scan, `casa j` association, link up,
   rx 833. Spinner = configd/DHCP (standard en0/AirPort/DHCP service in `preferences.plist`;
   `netsvc` fallback).
5. **0105 build confirmed.** Runs `41501352880` (macos-15-intel) and `41502238106`
   (macos-latest, branch `ci-macos-latest`) succeeded in `limonetexd/ios-sweet-gpu`;
   `41494548855` failed the link on 7 symbols. Kernel 0105 `d22c5aad...`; super image
   `67ff470f24acc5d3a92919fc8fbfde00e9f485e7e46c30aa8ab894bad24b5f3f`.
   `mkadt.py` uses `os.urandom(64)` without a seed, so byte-for-byte reproducibility is not
   guaranteed. The `__LINKINFO/__LINKEDIT` pair in the original brief belongs to the branch
   payload, not to 0105.
6. **USB/VFS.** 0105 links, but `_sweet_files_start` has zero `B`/`BL` xrefs; the server is
   linked but unreachable and the wrappers are only called by `_sf_thread`. Stubs:
   `sweet_gpu_probe` -> `sweet_gpu_init`; BT/haptic -> `RET`; NativeAdreno -> `MOV W0,#0; RET`.

## Errata / conflicts between notes

- `wifi-battery-branch.md` says the 0105 link was not confirmed. `build-ci-artifacts.md` proves
  it was, with run IDs and hashes. **Build note wins.**
- `root-launchd-panic.md` says ~3 s of silence after the `exec`; `xnu-gpu-kernel.md` says ~23 s.
  The ring has 24 `SWEET FPS` lines after `exec launchd_cache_loader` -> ~24 s. **XNU note wins;
  the root note's 3 s is wrong.**
- `xnu-gpu-kernel.md` names the repo `dipa-studio/ios-sweet`; `build-ci-artifacts.md` shows the
  real runs in `limonetexd/ios-sweet-gpu`. Treat the build note as authoritative for CI.
- `root-launchd-panic.md` says there was no new CI/commit for 2026-11-03; the build note
  documents the successful 0105 runs. This is a stale snapshot, not a contradiction of fact.

## Provenance and constraints

- All five agents were restricted to `D:\pablo\Downloads\CLAUDE\OPENCODE\deepseek\iOS on sweet`
  (workspace) and read-only access to the WSL research trees. No phone commands (`fastboot`,
  `adb`, `boot`, `flash`) were allowed.
- No tracked file was modified by the agents: `git status` shows only `notes/` as new, plus
  pre-existing untracked files. `NOTES.md` and `HANDOFF.md` were not edited by the agents.
- The `gpu2.simg` copy used is the workspace copy
  `OPENCODE/deepseek/iOS on sweet/ipsw/ios16-root-gpu2.simg`, **not** the Claude folder. Its
  SHA256 is `FB86997E0D15DE3BA198834955C0FC64ACA95037C9E64CDFDB1FB69268393579`
  (12.159.682.532 bytes); verified independently.
- Device serials are omitted from this index.
