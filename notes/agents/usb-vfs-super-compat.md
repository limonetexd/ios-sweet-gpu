# 0105 super-compat / VFS / USB file server: technical note for another AI

**Scope:** the `0105-super-link-fix.patch` front of the iOS 16.7.16 (XNU 8796.141.3) port to the
Redmi Note 10 Pro (`sweet`, SM7150): the seven-symbol link failure, the `sweet_super_compat.c`
stubs, the three kernel VFS wrappers, and the `sweet_files.c` USB file server that consumes them.

**Status in one line:** the link fix is real and is present in the checked-in kernel artifact, but
the USB file server entry point is never called in that artifact, so the VFS wrappers are linked
but not reachable at runtime; the only file named as a super boot log is byte-identical to a
different `0101s0` log and its boot arguments do not enable the file server.

**Evidence convention used throughout:**

- **[O] observed** — read directly from a file, hash, symbol table, disassembly, or command output
  in this repository.
- **[I] inferred** — follows from observed facts plus source semantics, but was not executed.
- **[U] unknown / unverified** — no local evidence, or evidence is contradictory.

This investigation was read-only. No phone command (`fastboot`, `adb`, boot, flash), no code edit,
no `NOTES.md`/`HANDOFF.md` edit, no commit/push, and no access to
`D:\pablo\Downloads\CLAUDE\iOS on sweet` was performed. The only file written is this note.

---

## 0. Five things the next AI should know first

1. **0105 is a link-time patch, not a feature patch.** It adds 37 lines of stubs and 32 lines of
   VFS wrappers. It does not add a caller for the file server. [O]
2. **The kernel artifact proves the symbols exist.** `xnu/out-0105/kernel.development.sweet`
   contains `_sweet_vfs_mkdir`, `_sweet_vfs_symlink`, `_sweet_vfs_unlink`, the four compat
   entries, `_sweet_files_start`, and `_sf_thread` at the addresses listed below. [O]
3. **`_sweet_files_start` has zero direct callers.** A scan of every ARM64 `B`/`BL` instruction in
   `__TEXT` and `__TEXT_EXEC` found no branch to `0xfffffe00079563b4`; no source hunk in 0104/0105
   calls it. The only reachable code that calls the three VFS wrappers is `_sf_thread`, which cannot
   run unless `_sweet_files_start` runs. [O] for the branch scan; [I] for "therefore unreachable".
4. **The named super log is not independent evidence.** `logs/xnu-super-panic.txt` and
   `logs/xnu-0101s0reboot.txt` have the same SHA-256 (`576cdb1a…`) and the same 50,094 bytes. The
   log's boot args omit `sweetfiles=1`, `sweetusb=2`, and `sweetgpu_reboot=120`, while the
   `payload-super.bin` command line contains all three. The log also contains no panic text. [O]
5. **The VFS wrappers are semantically plausible but not runtime-validated.** They call internal
   XNU VFS functions with `vfs_context_kernel()`, `AT_FDCWD`, and `UIO_SYSSPACE`; the important
   unknowns are the kernel context's cred, `current_proc()`/`fd_cmask` inside a kernel thread, cwd
   for relative paths, and unlink's swap/busy-file behavior. [I]/[U]

---

## 1. Scope, status, and method

### 1.1 What this note covers

This note covers only the 0105 compatibility front:

- the seven symbols that made the 0104 super build fail at link time;
- the exact contents and semantics of `bsd/dev/sweet_super_compat.c`;
- the exact contents and semantics of `sweet_vfs_mkdir`, `sweet_vfs_symlink`, and
  `sweet_vfs_unlink` added at the end of `bsd/vfs/vfs_syscalls.c`;
- how those wrappers interact with XNU's `mkdir1at`, `symlinkat_internal`, `unlink1`, `nameiat`,
  and `vfs_context_kernel`;
- the `sweet_files.c` server that calls the wrappers;
- the static evidence in `xnu/out-0105`, `shim/out/payload-super.bin`, and
  `shim/out/shim-boot-super.img`;
- the limits of the available runtime log.

It does **not** cover the Wi-Fi/BT/battery port in detail, the topaz/Redwood GPU implementation, the
userland installation flow, or the HFS/APFS root layout. Those are referenced only where they
affect 0105.

### 1.2 Status table

| Area | Status | Evidence |
|---|---|---|
| 0104 first link | Failed with seven undefined symbols, per project notes; raw link log not found locally | [O] `NOTES.md` / `HANDOFF.md`; [U] raw CI log |
| 0105 patch applies after 0104 | Recorded as applying cleanly; 92-line patch committed as `771481a` | [O] git |
| Compat symbols defined | Present in linked kernel symbol table | [O] Mach-O `LC_SYMTAB` |
| VFS wrappers defined | Present at `0xfffffe000753d184`, `…d23c`, `…d270` | [O] Mach-O |
| Kernel loads | Not proven for 0105; the named log is a duplicate of 0101s0 | [U] |
| GPU stub forwarding | `sweet_gpu_probe` is a single `B` to `sweet_gpu_init` | [O] disassembly |
| BT/haptic stubs | Each is a single `RET` | [O] disassembly |
| NativeAdreno reserve | `MOV W0,#0; RET`; caller casts result to `void` | [O] source + disassembly |
| File server caller | No `B`/`BL` to `_sweet_files_start`; not called by `_sweet_usb_probe` | [O] scan |
| File server runtime | Never validated; log lacks `sweetfiles=1` and has no `SWEET FILES:` line | [O] log |
| VFS wrappers runtime | Never validated; only `_sf_thread` calls them | [O] xref scan |
| Panic quoted by the user | Not present in any local log searched | [U] |

### 1.3 Method

The investigation used:

- `git log`, `git show`, and the committed patch files;
- exact reads of the patch hunks and the upstream XNU 8796.141.3 source for the callees;
- a read-only Python Mach-O parser over `kernel.development.sweet` to list segments, symbols, and
  addresses;
- a read-only ARM64 opcode scan over `__TEXT`/`__TEXT_EXEC` to find `B`/`BL` cross-references;
- a read-only parser for the custom `SWEETXNU` payload header;
- SHA-256 hashing of the kernel, payload, image, and both suspicious logs;
- `Select-String` over `logs/xnu-super-panic.txt` for boot args, USB, GPU, UFS, launchd, and panic
  strings.

No compiler, linker, disassembler binary, phone, or write-capable script was used. The instruction
decoding below is manual from the 32-bit words, cross-checked against the source patch.

---

## 2. Chronology

The project history matters because 0105 is a reaction to a specific 0104 link failure, and because
the artifact timestamps show that the runtime log was produced after the super image was built.

| When (local/UTC as stated) | Event | Evidence | Status |
|---|---|---|---|
| 2026-11-02 | 0096d is the known-good fast topaz build (~25 fps); 0101/0102 add vsync tuple and Accessibility-pref fix | `HANDOFF.md` | [O] project record |
| 2026-11-02 | Wi-Fi works on the DC28088 branch kernel + this root; super plan is to merge branch Wi-Fi/battery onto the fast topaz tree | `HANDOFF.md` | [O] project record |
| 2026-11-02 | 0104 (`5639176`) copies branch Wi-Fi/battery source, `sweet_files.c`, `sweet_ufs.c` hooks; deliberately excludes branch NativeAdreno | `0104-super-wifi-battery.patch`; `NOTES.md` | [O] |
| 2026-11-02 | 0104 CI `41494548855`; first link fails on exactly seven symbols | `NOTES.md` “Super link fix 0105”; `HANDOFF.md` | [O] notes; [U] raw log |
| 2026-11-02 | 0105 (`771481a`) adds `sweet_super_compat.c` and the three wrappers; patch is 92 lines | git show | [O] |
| 2026-11-02 | 0105 CI `41498675277` is cancelled because no macOS arm64 runner is acquired; retry `41501352880` (`macos-15-intel`) is queued; at 18:38 UTC both queues are empty | `NOTES.md`; commits `61c27e9`, `e1ce648` | [O] project record |
| 2026-11-03 18:24:41 | `xnu/out-0105/kernel.development.sweet` exists, 17,382,896 bytes, SHA-256 `d22c5aad…` | file metadata + hash | [O] |
| 2026-11-03 18:24:46 | `shim/out/payload-super.bin` exists, 16,757,888 bytes, SHA-256 `8201e7de…` | file metadata + hash | [O] |
| 2026-11-03 18:24:51 | `shim/out/shim-boot-super.img` exists, 17,494,016 bytes, SHA-256 `67ff470f…`; `check-super/` extracted | file metadata + hash | [O] |
| 2026-11-03 18:28:37 | `logs/xnu-super-panic.txt` written, 50,094 bytes | file metadata | [O] |
| 2026-11-03 18:29:51 | `payload-0101s0reboot.bin` written | directory listing | [O] |
| 2026-11-03 18:32:21 | `logs/xnu-0101s0reboot.txt` written; byte-identical to the “super” log | hash | [O] |

### 2.1 The 0104 → 0105 sequence in prose

0104 was an integration patch. It copied the branch's Wi-Fi/battery/UFS/file-server source onto the
fast 0101/0102 tree, but it did not copy the branch's Bluetooth driver, haptic driver, NativeAdreno
GPU stack, or the branch's VFS helper functions. The copied `sweet_ufs.c` still contained the
branch's initialization block:

```c
(void)sweet_native_adreno_reserve_pool();
sweet_pmem_init();
sweet_rpmh_ddr_raise();
sweet_smmu_probe_start();
sweet_haptic_init();
sweet_bt_init();
flame_wlan_init();
sweet_keys_init();
sweet_touch_init();
sweet_gpu_probe();
sweet_usb_probe();
```

The copied `sweet_files.c` still declared and called:

```c
extern int sweet_vfs_mkdir(const char *path, int mode);
extern int sweet_vfs_symlink(const char *target, const char *link);
extern int sweet_vfs_unlink(const char *path);
```

Those seven names had no definitions in the fast tree, so the link failed. 0105 supplied the seven
definitions: four in a new `sweet_super_compat.c`, three at the end of `vfs_syscalls.c`.

This is why the patch is small. It is not a redesign; it is a compatibility veneer that lets the
branch-derived UFS and file-server objects link against the fast tree.

### 2.2 What the dates do and do not prove

The 0105 kernel artifact, payload, and image were all created within ten seconds of each other on
2026-11-03 18:24. The payload's ten non-empty segments are byte-identical to the corresponding
segments in `kernel.development.sweet` (SHA-256 per segment; see §5.4). That is strong evidence that
`payload-super.bin` was packed from this exact kernel. [O]

The image was created at 18:24:51; the “super panic” log was written at 18:28:37. The timing is
compatible with a boot attempt, but the content is not: it is byte-identical to a later
`0101s0reboot` log, and its boot args lack the file-server args that are present in the payload.
Therefore the timing does not prove that the super image booted. [O]/[I]

The CI run that produced `out-0105` is not recorded in `NOTES.md` or `HANDOFF.md`. The notes end
with `41501352880` queued; the artifact exists, so some build succeeded, but attributing it to a
specific run would be invention. [U]

---

## 3. The link fix and the seven symbols

### 3.1 Why exactly seven symbols

The seven undefined symbols were not random. Each came from a specific copied translation unit:

| # | Symbol | Caller in 0104 | Why it was missing | 0105 fix |
|---|---|---|---|---|
| 1 | `sweet_bt_init` | `sweet_ufs.c` UFS init block | `bsd/dev/sweet_bt.c` from the branch was not copied/built | Empty function |
| 2 | `sweet_haptic_init` | `sweet_ufs.c` UFS init block | `bsd/dev/sweet_haptic.c` not copied/built | Empty function |
| 3 | `sweet_native_adreno_reserve_pool` | `sweet_ufs.c` UFS init block | Branch NativeAdreno stack deliberately excluded in favor of topaz | `return 0` |
| 4 | `sweet_gpu_probe` | `sweet_ufs.c` UFS init block, replacing old `sweet_gpu_init()` | Fast tree exports `sweet_gpu_init`, not the branch's `sweet_gpu_probe` | Forward to `sweet_gpu_init` |
| 5 | `sweet_vfs_mkdir` | `sweet_files.c` `MKDIR` handler | Branch's VFS helper was not copied | Wrapper around `mkdir1at` |
| 6 | `sweet_vfs_symlink` | `sweet_files.c` `LINK` handler | Same | Wrapper around `symlinkat_internal` |
| 7 | `sweet_vfs_unlink` | `sweet_files.c` `RM` handler | Same | Wrapper around `unlink1` |

The count is exactly seven because the other branch functions called by the copied UFS code were
provided by 0104 itself (`sweet_pmem_init`, `sweet_rpmh_ddr_raise`, `sweet_smmu_probe_start`,
`flame_wlan_init`) or already existed in the fast tree. `sweet_files_start` was not undefined
because 0104 adds its definition in the same patch that adds the file. [I, from the patch contents]

The missing symbols were declared `extern` at their call sites, so the compiler had enough
information to emit calls; the failure was at link time, not compile time. That is why the patch
could fix it without touching the callers. [O]

### 3.2 What 0105 adds

`0105-super-link-fix.patch` is 92 lines:

1. one line in `bsd/conf/files`:
   ```text
   bsd/dev/sweet_super_compat.c	standard
   ```
2. a new 37-line `bsd/dev/sweet_super_compat.c`, guarded by
   `#if defined(ARM64_BOARD_CONFIG_SWEET)`;
3. 32 lines appended to `bsd/vfs/vfs_syscalls.c` after `fs_snapshot`, also guarded by
   `ARM64_BOARD_CONFIG_SWEET`.

The guard matters: without `ARM64_BOARD_CONFIG_SWEET`, neither the stubs nor the wrappers exist and
the seven symbols would still be undefined. The built `sweet` target defines it, which is why the
symbols are present in `out-0105`. [I, strongly supported by the symbol table]

### 3.3 Exact symbol addresses in the linked kernel

Read from `xnu/out-0105/kernel.development.sweet` (Mach-O, `LC_SYMTAB`, 71,376 symbols). Addresses
are unslid kernel VAs.

| Symbol | Address | Size/shape | Role |
|---|---:|---|---|
| `_sweet_vfs_mkdir` | `0xfffffe000753d184` | wrapper, ~0xb8 bytes to next symbol | `mkdir1at` |
| `_sweet_vfs_symlink` | `0xfffffe000753d23c` | wrapper, ~0x34 bytes to next | `symlinkat_internal` |
| `_sweet_vfs_unlink` | `0xfffffe000753d270` | wrapper | `unlink1` |
| `_sweet_gpu_probe` | `0xfffffe0007957198` | 4 bytes, one `B` | tail branch to `_sweet_gpu_init` |
| `_sweet_bt_init` | `0xfffffe000795719c` | 4 bytes, `RET` | no-op |
| `_sweet_haptic_init` | `0xfffffe00079571a0` | 4 bytes, `RET` | no-op |
| `_sweet_native_adreno_reserve_pool` | `0xfffffe00079571a4` | 8 bytes, `MOV W0,#0; RET` | returns 0 |
| `_sweet_gpu_init` | `0xfffffe00074f9e98` | existing fast GPU init | target of probe |
| `_sweet_files_start` | `0xfffffe00079563b4` | file-server entry | **no callers** |
| `_sf_thread` | `0xfffffe0007956410` | server thread | calls wrappers |
| `_mkdir1at` | `0xfffffe0007537670` | XNU internal | callee |
| `_symlinkat_internal` | `0xfffffe0007531b50` | XNU internal | callee |
| `_unlink1` | `0xfffffe0007531f3c` | XNU internal, 3-line forwarder | callee |
| `_unlinkat_internal` | `0xfffffe0007531f54` | XNU internal | actual unlink |
| `_nameiat` | `0xfffffe000752e9ac` | XNU path resolution | callee |
| `_vfs_context_kernel` | `0xfffffe000754a714` | XNU context | callee |

The presence of these symbols is the strongest static proof that 0105 was compiled into this kernel.
It does **not** prove that any of the new code ran. [O]/[I]

### 3.4 Build provenance and payload match

`xnu/out-0105/SHA256SUMS`:

```text
d22c5aadf208b5e0347f487fdcb7b83d487a37d06af2b623ed9f675d9b7c1793  kernel.development.sweet
```

`shim/out/payload-super.bin` (custom `SWEETXNU` header):

```text
magic=SWEETXNU version=1 nsegs=10
virt_base=fffffe0006000000
entry=fffffe0007494488
adt_off=ff81e0 adt_size=32a0
kernel_end=fffffe000851c000
phys_base=100000000 mem_size=ecb00000
```

Per-segment SHA-256 comparison between the kernel Mach-O and the payload:

```text
__TEXT            vm=fffffe0007004000  MATCH
__DATA_CONST      vm=fffffe0007168000  MATCH
__TEXT_EXEC       vm=fffffe00072ec000  MATCH
__KLD             vm=fffffe0007b50000  MATCH
__LASTDATA_CONST  vm=fffffe0007b54000  MATCH
__KLDDATA         vm=fffffe0007b58000  MATCH
__DATA            vm=fffffe0007b5c000  MATCH
__BOOTDATA        vm=fffffe00080c4000  MATCH
__LINKINFO        vm=fffffe0008110000  MATCH
__LINKEDIT        vm=fffffe000815c000  MATCH
```

This is why comparing whole-file hashes is misleading: `payload-super.bin` has a different overall
SHA-256 (`8201e7de…`) because of the `SWEETXNU` header, segment packing, and chained-fixup
rewriting, but its loadable segment contents match the kernel. [O]

`shim/out/check-super/header.txt` confirms the image composition:

```text
kernel_size: 380928
kernel_addr: 0x8000
ramdisk_size: 16757888
ramdisk_addr: 0x1000000
page_size: 4096
header_version: 2
cmdline: console=null
```

`check-super/ramdisk` has SHA-256 `8201e7de…`, i.e. it is `payload-super.bin`. The 380,928-byte
`kernel` is the shim, not XNU. `shim-boot-super.img` is therefore a shim + the super payload. [O]

### 3.5 What link success does and does not prove

It proves:

- the seven externs now have definitions;
- the new file was included in `bsd/conf/files`;
- the wrappers compiled against the same XNU internal prototypes as the rest of `vfs_syscalls.c`;
- the resulting kernel has the symbols at fixed addresses;
- the payload was packed from that kernel.

It does not prove:

- that `sweet_files_start` is called;
- that the USB interface comes up;
- that `vfs_context_kernel()` is safe for these operations inside `sf_thread`;
- that `mkdir`/`symlink`/`unlink` succeed on the HFS root;
- that the stubs behave like the branch drivers;
- that the super image boots or reaches launchd.

Those are all separate questions. The rest of this note separates them.

---

## 4. Stubs and wrappers, line by line

### 4.1 `bsd/dev/sweet_super_compat.c` — exact contents

The file is 37 lines. The whole body, with annotations:

```c
#if defined(ARM64_BOARD_CONFIG_SWEET)
#include <sys/param.h>
#include <sys/systm.h>

void sweet_gpu_init(void);

void
sweet_gpu_probe(void)
{
	sweet_gpu_init();
}

void
sweet_bt_init(void)
{
}

void
sweet_haptic_init(void)
{
}

int
sweet_native_adreno_reserve_pool(void)
{
	return 0;
}
#endif /* ARM64_BOARD_CONFIG_SWEET */
```

Line-by-line:

- **`#if defined(ARM64_BOARD_CONFIG_SWEET)`** — the file compiles only for the sweet board. If the
  build system ever compiles this file for a different board, all seven symbols remain unresolved
  for sweet callers. [O]
- **`#include <sys/param.h>` / `<sys/systm.h>`** — minimal kernel headers. No VFS, no IOKit, no
  branch headers; this is deliberately independent of the branch. [O]
- **`void sweet_gpu_init(void);`** — forward declaration of the fast-tree GPU entry point. It is
  declared, not defined here. [O]
- **`sweet_gpu_probe`** — one call, no return value. The compiled body is a single ARM64 `B`
  instruction, not a `BL`, because the compiler tail-call-optimized the void-to-void call. The word
  at `0xfffffe0007957198` is `0x17ee8b40`, which decodes to a branch to `0xfffffe00074f9e98`
  (`_sweet_gpu_init`). [O]
- **`sweet_bt_init`** — empty. The compiled body is `0xd65f03c0` (`RET`). There is no log, no error,
  no hardware access. [O]
- **`sweet_haptic_init`** — empty, also a single `RET`. [O]
- **`sweet_native_adreno_reserve_pool`** — `return 0`; compiled as `0x52800000` (`MOV W0,#0`)
  followed by `RET`. The caller in `sweet_ufs.c` is `(void)sweet_native_adreno_reserve_pool();`, so
  the value is ignored. [O]

**Semantic consequence:** these are not implementations of the branch interfaces. They are
link-time placeholders. If a caller depends on side effects (BT UART setup, haptic power rail,
Adreno owned-BO pool), those side effects do not happen. The return value of the Adreno function is
currently irrelevant, but that could change if future code starts checking it. [I]

### 4.2 `sweet_gpu_probe` ordering change

The 0104 diff is not a pure symbol substitution. It moves the GPU call:

```diff
 	sweet_keys_init();
 	sweet_touch_init();
+	sweet_gpu_probe();
 	sweet_usb_probe();
-	sweet_gpu_init();
```

In the older 0082 order, GPU init ran **after** `sweet_usb_probe()`. In 0104/0105, the forwarded
`sweet_gpu_init()` runs **before** `sweet_usb_probe()`. That is a real behavioral change. The log
happens to print USB lines before GPU lines, but that log is not trustworthy for 0105 (§5.5), so the
ordering effect is unvalidated. [O] diff; [U] runtime effect.

Possible reasons the branch order is this way: the branch's `sweet_gpu_probe` may need to run before
USB to hand off the GPU/display, or the branch's UFS init block may simply have evolved separately.
No rationale is recorded in the patch. [U]

### 4.3 `sweet_vfs_mkdir` — exact contents

```c
int
sweet_vfs_mkdir(const char *path, int mode)
{
	struct vnode_attr va;
	VATTR_INIT(&va);
	VATTR_SET(&va, va_mode, mode & ACCESSPERMS);
	return mkdir1at(vfs_context_kernel(), CAST_USER_ADDR_T(path), &va, AT_FDCWD, UIO_SYSSPACE);
}
```

Line-by-line:

- **`struct vnode_attr va;`** — stack-allocated attribute block. `mkdir1at` consumes it during the
  call; no lifetime issue. [O]
- **`VATTR_INIT(&va);`** — zeroes the attribute structure and initializes its bitmap. [O]
- **`VATTR_SET(&va, va_mode, mode & ACCESSPERMS);`** — sets only `va_mode`. `ACCESSPERMS` is
  `0777`; this strips setuid/setgid/sticky and any type bits. It does **not** apply
  `~p->p_fd.fd_cmask`. Compare with XNU's `mkdir` syscall, which does
  `(uap->mode & ACCESSPERMS) & ~p->p_fd.fd_cmask`. The wrapper therefore ignores umask at this
  level. [O] source; [I] whether any lower layer re-applies cmask.
- **`mkdir1at(vfs_context_kernel(), ...)`** — kernel context, not the caller's user context. The
  wrapper is only callable from kernel code; there is no `copyin`. [O]
- **`CAST_USER_ADDR_T(path)`** — casts the kernel pointer to `user_addr_t` for the prototype. With
  `UIO_SYSSPACE`, the callee treats it as a kernel address and does not call `copyinstr`. [O]
- **`&va`** — `mkdir1at` will set `va_type = VDIR` and call `vn_authorize_mkdir`/`vn_create`. [O]
- **`AT_FDCWD`** — relative paths use the context process's current directory. [O] source; [U]
  which process/cwd that is inside `sf_thread`.
- **`UIO_SYSSPACE`** — no user-space copy; path must be a valid NUL-terminated kernel string for
  the duration of the call. `sweet_files.c` passes a pointer into its `line`/`arg1` buffer, which
  remains valid during the synchronous call. [O]
- **Return** — `mkdir1at` returns an errno; `EEXIST` is handled by the server (mapped to success),
  other errors are sent to the client. [O]

### 4.4 `sweet_vfs_symlink` — exact contents

```c
int
sweet_vfs_symlink(const char *target, const char *link)
{
	return symlinkat_internal(vfs_context_kernel(), CAST_USER_ADDR_T(target), AT_FDCWD,
	           CAST_USER_ADDR_T(link), UIO_SYSSPACE);
}
```

Line-by-line:

- **Argument order is `target`, then `link`.** The server's protocol is `LINK <target> <path>`;
  `sweet_files.c` calls `sweet_vfs_symlink(arg1, arg2)`. This matches the wrapper: `target` is the
  contents of the symlink, `link` is the new directory entry. [O]
- **`vfs_context_kernel()`** — kernel credentials/context. [O]
- **`CAST_USER_ADDR_T(target)`** — first argument of `symlinkat_internal` is `path_data`, the
  symlink target string. [O]
- **`AT_FDCWD`** — relative link path resolves against the context cwd. [O]/[U]
- **`CAST_USER_ADDR_T(link)`** — the new link path. [O]
- **`UIO_SYSSPACE`** — both strings are kernel pointers; `symlinkat_internal` does not copy them in
  when `segflg` is sysspace. [O]
- **Return** — errno from `symlinkat_internal`. `EEXIST` is not special-cased by the server for
  `LINK`; the client sees `ERR 17`. [O]

Inside `symlinkat_internal`, the mode is not supplied by the wrapper:

```c
p = vfs_context_proc(ctx);
VATTR_INIT(&va);
VATTR_SET(&va, va_type, VLNK);
VATTR_SET(&va, va_mode, ACCESSPERMS & ~p->p_fd.fd_cmask);
```

So the symlink mode depends on `vfs_context_proc(ctx)->p_fd.fd_cmask`. With a kernel context whose
`vc_thread` is NULL, `vfs_context_proc()` falls back to `current_proc()`. If `current_proc()` is
`kernproc`, the cmask is whatever `kernproc` has (likely 0); if it is NULL, this dereference is a
panic. This is one of the most important unknowns. [O] source; [U] runtime.

### 4.5 `sweet_vfs_unlink` — exact contents

```c
int
sweet_vfs_unlink(const char *path)
{
	return unlink1(vfs_context_kernel(), NULLVP, CAST_USER_ADDR_T(path), UIO_SYSSPACE, 0);
}
```

Line-by-line:

- **`vfs_context_kernel()`** — kernel context. The unlink code has a special case: swap vnodes
  cannot be unlinked by non-kernel contexts, but **can** be unlinked by the kernel context. [O]
- **`NULLVP`** — no starting directory vnode. `unlinkat_internal` therefore does not set `USEDVP`
  and resolves the path from `AT_FDCWD`. [O]
- **`CAST_USER_ADDR_T(path)`** — kernel pointer; `UIO_SYSSPACE` means no copyin. [O]
- **`0` unlink flags** — no `VNODE_REMOVE_NODELETEBUSY`, no `VNODE_REMOVE_SKIP_NAMESPACE_EVENT`,
  no `VNODE_REMOVE_NO_AUDIT_PATH`. This is POSIX-style unlink, not Carbon delete. [O]
- **Return** — errno from `unlink1` → `unlinkat_internal`. [O]

`unlink1` itself is only:

```c
int
unlink1(vfs_context_t ctx, vnode_t start_dvp, user_addr_t path_arg,
    enum uio_seg segflg, int unlink_flags)
{
	return unlinkat_internal(ctx, AT_FDCWD, start_dvp, path_arg, segflg,
	           unlink_flags);
}
```

So the wrapper's effective call is:

```c
unlinkat_internal(vfs_context_kernel(), AT_FDCWD, NULLVP,
    (user_addr_t)path, UIO_SYSSPACE, 0);
```

### 4.6 Callee semantics that matter

#### `mkdir1at`

From XNU 8796.141.3 `bsd/vfs/vfs_syscalls.c`:

```c
NDINIT(&nd, CREATE, OP_MKDIR, LOCKPARENT | AUDITVNPATH1, segflg, path, ctx);
nd.ni_cnd.cn_flags |= WILLBEDIR;
nd.ni_flag = NAMEI_COMPOUNDMKDIR;
...
error = nameiat(&nd, fd);
...
VATTR_SET(vap, va_type, VDIR);
...
error = vn_authorize_mkdir(dvp, &nd.ni_cnd, vap, ctx, NULL);
...
error = vn_create(dvp, &vp, &nd, vap, 0, 0, NULL, ctx);
```

Consequences:

- `mkdir1at` resolves the parent, checks `EEXIST`, authorizes `mkdir` on the parent, then creates
  the directory vnode.
- It sets `va_type = VDIR` itself, so the wrapper does not need to.
- It uses `vap->va_mode` as supplied. The wrapper supplies `mode & 0777`, with no `~fd_cmask`.
- The `NAMEI_COMPOUNDMKDIR` path is the modern compound-VNOP path; an `EKEEPLOOKING` result loops
  back through `nameiat`.
- `EEXIST` is returned before authorization when the target already exists; the server maps that to
  success for `MKDIR`. [O]

#### `symlinkat_internal`

```c
if (UIO_SEG_IS_USER_SPACE(segflg)) {
    path = zalloc(ZV_NAMEI);
    error = copyinstr(path_data, path, MAXPATHLEN, &dummy);
} else {
    path = (char *)path_data;
}
...
NDINIT(&nd, CREATE, OP_SYMLINK, LOCKPARENT | AUDITVNPATH1, segflg, link, ctx);
error = nameiat(&nd, fd);
...
p = vfs_context_proc(ctx);
VATTR_INIT(&va);
VATTR_SET(&va, va_type, VLNK);
VATTR_SET(&va, va_mode, ACCESSPERMS & ~p->p_fd.fd_cmask);
...
error = mac_vnode_check_create(ctx, dvp, &nd.ni_cnd, &va);
...
error = vnode_authorize(dvp, NULL, KAUTH_VNODE_ADD_FILE, ctx);
...
error = vnode_authattr_new(dvp, &va, 0, ctx);
...
error = VNOP_SYMLINK(dvp, &vp, &nd.ni_cnd, &va, path, ctx);
```

Consequences:

- With `UIO_SYSSPACE`, the target string is **not** copied or length-checked by `copyinstr`; it is
  used directly. `namei` handles the link path, but the target length is the filesystem's problem.
- `vfs_context_proc(ctx)` is called unconditionally for `fd_cmask`; this is the panic-risk line.
- `vnode_authorize` checks `KAUTH_VNODE_ADD_FILE` on the parent.
- `vnode_authattr_new` fills ownership/default attributes; `VNOP_SYMLINK` creates the link.
- `EEXIST` is returned if the link path exists. [O]

#### `unlinkat_internal` / `unlink1`

```c
cn_flags = LOCKPARENT;
if (!(unlink_flags & VNODE_REMOVE_NO_AUDIT_PATH)) cn_flags |= AUDITVNPATH1;
if (start_dvp) cn_flags |= USEDVP;
...
NDINIT(ndp, DELETE, OP_UNLINK, cn_flags, segflg, path_arg, ctx);
ndp->ni_dvp = start_dvp;
ndp->ni_flag |= NAMEI_COMPOUNDREMOVE;
...
error = nameiat(ndp, fd);
...
if ((vp->v_flag & VROOT) || (dvp->v_mount != vp->v_mount)) {
    error = EBUSY;
    goto out;
}
...
if (vnode_isswap(vp) && (ctx != vfs_context_kernel())) {
    error = EPERM;
    ...
}
...
error = vn_authorize_unlink(dvp, vp, cnp, ctx, NULL);
```

Consequences:

- `VROOT` (mount root) and cross-mount unlinks are refused with `EBUSY`.
- Swap vnodes are protected only for non-kernel contexts; `sweet_vfs_unlink` uses the kernel
  context, so it bypasses that protection. [O]
- With `unlink_flags = 0`, there is no busy-file refusal flag. POSIX unlink can remove an open file;
  the server can remove files that userland still has open.
- No `rmdir`: a directory target will fail in the filesystem's `VNOP_REMOVE` (typically `EPERM` or
  `EISDIR`), not recursively delete. [I]
- `vn_authorize_unlink` is still called; root credentials do not skip KAUTH entirely. [O]

#### `nameiat` and `AT_FDCWD`

```c
if ((dirfd != AT_FDCWD) && !(NAMEI_CONTLOOKUP) && !(USEDVP)) {
    ...
    error = vnode_getfromfd(cn_context, dirfd, &dvp_at);
    ...
    ndp->ni_dvp = dvp_at;
    ndp->ni_cnd.cn_flags |= USEDVP;
    error = namei(ndp);
    ...
}
return namei(ndp);
```

With `AT_FDCWD`, `nameiat` goes straight to `namei`. Relative paths therefore use the cwd of the
process returned by `vfs_context_proc(ctx)`. For `vfs_context_kernel()`, that is
`current_proc()` because the context's `vc_thread` is NULL. [O] source; [U] which proc/cwd.

### 4.7 `vfs_context_kernel()` semantics

From `bsd/vfs/kpi_vfs.c` (XNU 8796.141.3):

```c
vfs_context_t
vfs_context_kernel(void)
{
	return &vfs_context0;
}

proc_t
vfs_context_proc(vfs_context_t ctx)
{
	proc_t proc = NULL;
	thread_t t;
	if (ctx != NULL && (t = VFS_CONTEXT_GET_THREAD(ctx)) != NULL) {
		proc = (proc_t)get_bsdthreadtask_info(t);
	}
	return proc == NULL ? current_proc() : proc;
}

kauth_cred_t
vfs_context_ucred(vfs_context_t ctx)
{
	return ctx->vc_ucred;
}

int
vfs_context_iskernel(vfs_context_t ctx)
{
	return ctx == &vfs_context0;
}
```

So:

- `vfs_context_kernel()` is not "the current thread's context"; it is a static `vfs_context0`.
- `vfs_context_proc()` on it falls back to `current_proc()`.
- `vfs_context_ucred()` returns `vfs_context0.vc_ucred` directly.
- `vfs_context_iskernel()` is pointer identity against `vfs_context0`.

The symbol `_vfs_context0` is at `0xfffffe000721ef78` in `__DATA_CONST`. The bytes at that location
are zero in this file (a prebound/chained-fixup slot); the runtime value was not captured. Therefore the exact
`vc_ucred` (NOCRED vs a real root cred) is **unknown** from this artifact alone. [O] symbol;
[U] initializer.

This matters because `sweet_files.c` passes `vfs_context_ucred(ctx)` into `vn_rdwr` for both PUT and
GET. If that is `NOCRED`, the I/O credential path may behave differently or assert. It also matters
for `symlinkat_internal`'s `p->p_fd.fd_cmask`. [I]/[U]

### 4.8 Call graph observed in the linked kernel

A scan of all `B`/`BL` instructions in `__TEXT` and `__TEXT_EXEC` found:

```text
TARGET sweet_files_start  xrefs 0
TARGET sweet_vfs_mkdir     xrefs 1   fffffe0007957040 in _sf_thread+0xc30
TARGET sweet_vfs_symlink   xrefs 1   fffffe0007956bc0 in _sf_thread+0x7b0
TARGET sweet_vfs_unlink    xrefs 1   fffffe0007957054 in _sf_thread+0xc44
TARGET sweet_gpu_probe     xrefs 1   fffffe00074f0dc0 in _sweet_ufs_rootdev+0x6e8
TARGET sweet_bt_init       xrefs 1   fffffe00074f0db0 in _sweet_ufs_rootdev+0x6d8
TARGET sweet_haptic_init   xrefs 1   fffffe00074f0dac in _sweet_ufs_rootdev+0x6d4
TARGET sweet_native_adreno_reserve_pool xrefs 1 fffffe00074f0d9c in _sweet_ufs_rootdev+0x6c4
TARGET sweet_gpu_init      xrefs 0   (tail branch from _sweet_gpu_probe)
```

Interpretation:

- Every wrapper has exactly one caller: `_sf_thread`. There are no other kernel callers. They are
  global symbols, so future code could call them, but nothing does today. [O]
- The four compat entries have exactly one caller each, all in the inlined/renamed
  `_sweet_ufs_rootdev` body. The old `sweet_gpu_init()` call is gone; `sweet_gpu_probe()` replaced
  it. [O]
- `_sweet_files_start` has no caller. `_sweet_usb_probe` was disassembled to its `RET` and contains
  no branch to it. [O]

The only caveat is an indirect call through a computed function pointer, which a `B`/`BL` scan
cannot see. The source has no such assignment, and the file-server code has no constructor or
exported callback registration. The practical conclusion is that the server is dead code in this
build. [I, high confidence]

---

## 5. Raw evidence

This section records the exact observations, so another AI does not have to re-derive them.

### 5.1 Commit and patch

```text
$ git log --oneline -8
e1ce648 notes: both macOS runner queues still empty at 18:38Z; leave runs queued
61c27e9 notes: arm64 runner capacity cancelled 0105; retry on macos-15-intel (run 41501352880)
34e3a8f ci: use macos-15-intel (arm64 hosted capacity unavailable); same Xcode 16, cross-compiles the arm64 kernel
9222114 notes: 0105 super link fix and Wi-Fi service/spinner notes
771481a xnu 0105: super link fix - compat stubs (BT/haptic/NativeAdreno, gpu_probe->sweet_gpu_init) and VFS wrappers for the USB file server
ede4419 notes: super patch 0104 (Wi-Fi+battery on fast topaz kernel) CI 41494548855; watcher builds shim-boot-super
5639176 xnu 0104: super build - Wi-Fi WCN3990 (PMEM/RPMh/SMMU, wland en0/Apple80211) and battery from the DC28088 branch, on our fast topaz GPU
```

```text
$ git show --stat --oneline 771481a
771481a xnu 0105: super link fix - compat stubs (BT/haptic/NativeAdreno, gpu_probe->sweet_gpu_init) and VFS wrappers for the USB file server
 xnu/patches/0105-super-link-fix.patch | 92 +++++++++++++++++++++++++++++++++++++
 1 file changed, 92 insertions(+)
```

The commit adds only the patch file. The built kernel is a separate local artifact, not committed.
[O]

### 5.2 Hashes

```text
D22C5AADF208B5E0347F487FDCB7B83D487A37D06AF2B623ED9F675D9B7C1793  xnu/out-0105/kernel.development.sweet
8201E7DE7B17B39AF59142F23CACDEFD4A93B73A5F3811B9D7809AA24F6D7BFE  shim/out/payload-super.bin
67FF470F24ACC5D3A92919FC8FBFDE00E9F485E7E46C30AA8AB894BAD24B5F3F  shim/out/shim-boot-super.img
576CDB1ACA91C3975CE4C2BCFCEA0360ABC2D43EAED55894462C050D2FFEB99F  logs/xnu-super-panic.txt
576CDB1ACA91C3975CE4C2BCFCEA0360ABC2D43EAED55894462C050D2FFEB99F  logs/xnu-0101s0reboot.txt
```

The last two lines are the important integrity finding. The “super panic” log is byte-for-byte the
same file as the `0101s0reboot` log. [O]

### 5.3 Kernel segment layout

From the Mach-O load commands:

```text
__TEXT           vmaddr=fffffe0007004000 vmsize=00164000 fileoff=00000000
__DATA_CONST     vmaddr=fffffe0007168000 vmsize=00184000 fileoff=00164000
__TEXT_EXEC      vmaddr=fffffe00072ec000 vmsize=00864000 fileoff=002e8000
__KLD            vmaddr=fffffe0007b50000 vmsize=00004000 fileoff=00b4c000
__LASTDATA_CONST vmaddr=fffffe0007b54000 vmsize=00004000 fileoff=00b50000
__LAST           vmaddr=fffffe0007b58000 vmsize=00000000 fileoff=00000000
__KLDDATA        vmaddr=fffffe0007b58000 vmsize=00004000 fileoff=00b54000
__DATA           vmaddr=fffffe0007b5c000 vmsize=00568000 fileoff=00b58000
__BOOTDATA       vmaddr=fffffe00080c4000 vmsize=0004c000 fileoff=00ba0000
__LINKINFO       vmaddr=fffffe0008110000 vmsize=0004c000 fileoff=00bec000
__CTF            vmaddr=fffffe000815c000 vmsize=00000000 fileoff=00c38000
__LINKEDIT       vmaddr=fffffe000815c000 vmsize=003c0000 fileoff=00cd4000
```

Note the discrepancy with the user-supplied linkinfo values (`__LINKINFO 0xfffffe0008170000
0x4c000; __LINKEDIT 0xfffffe00081bc000 0x3cc000`). The values above are parsed from this exact
artifact; the user-supplied values were not reproduced. They may come from a different build or be
approximate. [O] parse; [U] provenance of the other values.

### 5.4 Payload header and segments

```text
magic='SWEETXNU' version=1 nsegs=10
virt_base=fffffe0006000000 entry=fffffe0007494488
adt_off=ff81e0 adt_size=32a0
kernel_end=fffffe000851c000 phys_base=100000000 mem_size=ecb00000
seg[0] vmaddr=fffffe0007004000 vmsize=00164000 file_off=000003e8 file_size=00164000
seg[1] vmaddr=fffffe0007168000 vmsize=00184000 file_off=001643f0 file_size=00184000
seg[2] vmaddr=fffffe00072ec000 vmsize=00864000 file_off=002e83f0 file_size=00864000
seg[3] vmaddr=fffffe0007b50000 vmsize=00004000 file_off=00b4c3f0 file_size=00004000
seg[4] vmaddr=fffffe0007b54000 vmsize=00004000 file_off=00b503f0 file_size=00004000
seg[5] vmaddr=fffffe0007b58000 vmsize=00004000 file_off=00b543f0 file_size=00004000
seg[6] vmaddr=fffffe0007b5c000 vmsize=00568000 file_off=00b583f0 file_size=00048000
seg[7] vmaddr=fffffe00080c4000 vmsize=0004c000 file_off=00ba03f0 file_size=0004c000
seg[8] vmaddr=fffffe0008110000 vmsize=0004c000 file_off=00bec3f0 file_size=0004c000
seg[9] vmaddr=fffffe000815c000 vmsize=003c0000 file_off=00c383f0 file_size=003bfdf0
```

The payload's kernel command line (`cmdline[608]` at offset `0x48`) is:

```text
debug=0xc serial=0 cpus=8 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0
unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1
launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=60 sweetgpu=2 sweetpmem=1
sweetsmmuprobe=1 sweetsmmuwlan=1 sweetwifi=1 sweetfiles=1 sweetusb=2 sweetgpu_reboot=120
```

This is the command line that would be passed to the 0105 kernel if the image were booted. It
contains `sweetfiles=1`. [O]

### 5.5 The “super panic” log

`logs/xnu-super-panic.txt` has 610 lines. The relevant lines:

```text
152  SWEET UFS: "userdata" on LUN 0: first block 0x2b8c00, 109643 MiB, read-write, DMA at 0x1045c0000
211  SWEET USB: GDSC usb30_prim 0xf8222000 (on)
219  SWEET USB: DWC3 GSNPSID 0x5533320a GCTL 0x00112000 ...
223  BSD root: ufsroot0, major 1, minor 0
328  com.apple.xpc.launchd|... boot-args = debug=0xc serial=0 cpus=8 keepsyms=1
     -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1
     wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1
     sweetfb_noconsole=1 sweetfb_hz=60 sweetgpu=2 sweetpmem=1 sweetsmmuprobe=1 sweetsmmuwlan=1 sweetwifi=1
403  SWEET GPU: cx gdsc 0xf8222000 gx gdsc 0xf8222000
406  SWEET GPU: CP_MEM_WRITE from XNU -> 0x5ee7c0de ... *** GPU ALIVE UNDER XNU ***
408  SWEET GPU: Adreno 618 handed to RedwoodGPU (wptr 30 rptr 30 rbbm 00000001)
584  com.apple.xpc.launchd|... (launchd_cache_loader) <Notice>: Doing boot task
586  exec launchd_cache_loader
610  SWEET FPS: 0 swaps in 1001 ms ... 1 surfaces, 0 zombies, 0 MB wired, 0 creates failed
```

Observations:

- The boot args at line 328 **omit** `sweetfiles=1`, `sweetusb=2`, and `sweetgpu_reboot=120`.
  The payload command line contains all three. Therefore this log was not produced by
  `payload-super.bin` as packed. [O]
- There is no `SWEET FILES: listening on tcp 2223` line. If the file server had started, that line
  is printed unconditionally after bind/listen. [O] source; [O] absence in log.
- There is no panic line. Searches for `panic`, `initproc`, and the quoted
  `initproc exited -- exit reason namespace 2 subcode 0x8 -- code 0x1` found nothing in this or
  other local logs. The filename is therefore misleading. [O]
- The log ends while `launchd_cache_loader` is running, followed by repeated `SWEET FPS` lines. It
  does not show a crash or an orderly shutdown. [O]
- The file is byte-identical to `xnu-0101s0reboot.txt`. The simplest explanation is that the probe
  read a stale ring buffer or copied the same log twice, not that 0105 produced it. [I]

The shim log is also not a kernel log:

```text
SHIM sweet milestone 4: xnu loader
LOADER no SWEETXNU payload
PLOG ufs=00000000
REBOOT pon spare=00000004 rc=00000000
...
GPU probe done, back to fastboot in 10 s
```

It records a GPU probe from the shim/fastboot side, not the kernel file server. `LOADER no SWEETXNU
payload` indicates the shim did not find a payload in that particular boot path. [O] This is another
reason not to treat the pair as a valid 0105 boot record.

### 5.6 File-server source facts

From `0104-super-wifi-battery.patch`:

- `sweet_files.c` is 355 lines. [O]
- It is enabled only by `sweetfiles=1`:
  ```c
  int on = 0;
  PE_parse_boot_argn("sweetfiles", &on, sizeof(on));
  if (!on) return;
  ```
- It binds `192.168.7.2:2223` (`htons(2223)`, `htonl(0xc0a80702)`). [O]
- It refuses peers outside `192.168.7.0/24`:
  ```c
  if (peer.sin_family != AF_INET ||
      (ntohl(peer.sin_addr.s_addr) & 0xffffff00u) != 0xc0a80700u) { ... }
  ```
- It calls the wrappers at:
  ```c
  err = sweet_vfs_mkdir(arg1, arg2 ? (int)strtoul(arg2, NULL, 8) : 0755);
  err = sweet_vfs_symlink(arg1, arg2);
  err = sweet_vfs_unlink(arg1);
  ```
- It starts via `sweet_files_start()` → `kernel_thread_start(sf_thread, NULL, &thread)`. [O]
- The comments say “Started with the USB gadget (sweet_usb.c) when the interface comes up.” [O]
  But no 0104/0105 hunk adds that call, and the linked kernel has no branch to
  `_sweet_files_start`. [O]

### 5.7 Xref scan method and limits

The scan:

1. parses `LC_SEGMENT_64` to get `__TEXT`/`__TEXT_EXEC` VM ranges and file offsets;
2. reads every aligned 32-bit word;
3. selects `B` (`opcode & 0xFC000000 == 0x14000000`) and `BL` (`0x94000000`);
4. decodes the signed 26-bit immediate and computes `PC + imm*4`;
5. maps the target to the nearest symbol.

It found zero `B`/`BL` to `_sweet_files_start`. It also found exactly one xref for each VFS wrapper,
all inside `_sf_thread`. It cannot see a call through a function pointer computed at runtime; the
source contains no such registration, and the file-server code has no constructor. [O]/[I]

---

## 6. Observed vs inferred vs unknown

### 6.1 Observed

These are direct reads, not interpretations:

- 0105 is a 92-line patch committed as `771481a`; it adds one `bsd/conf/files` line, a 37-line
  compat file, and 32 lines of VFS wrappers. [O]
- `sweet_super_compat.c` defines `sweet_gpu_probe`, `sweet_bt_init`, `sweet_haptic_init`, and
  `sweet_native_adreno_reserve_pool` under `ARM64_BOARD_CONFIG_SWEET`. [O]
- `out-0105/kernel.development.sweet` contains all seven new symbols plus `_sweet_files_start` and
  `_sf_thread`. [O]
- `sweet_gpu_probe` compiles to a single `B` to `sweet_gpu_init`; BT/haptic compile to `RET`;
  NativeAdreno compiles to `MOV W0,#0; RET`. [O]
- `sweet_files_start` has zero `B`/`BL` xrefs; each VFS wrapper has exactly one, in `_sf_thread`.
  [O]
- `payload-super.bin` has ten segments whose contents match `out-0105`'s kernel segments; its
  command line includes `sweetfiles=1 sweetusb=2 sweetgpu_reboot=120`. [O]
- `shim-boot-super.img` contains the shim (380,928 bytes) and `payload-super.bin` as its ramdisk;
  `check-super/ramdisk` hash equals `payload-super.bin`. [O]
- `xnu-super-panic.txt` has the same SHA-256 as `xnu-0101s0reboot.txt`; its boot args omit the
  file-server args; it has no `SWEET FILES:` and no panic text. [O]
- The project notes record seven undefined symbols and the CI runner cancellation; the raw link log
  and the successful 0105 CI run ID are not in the local tree. [O] notes; [U] raw log/run ID.

### 6.2 Inferred

These are strong conclusions from the observations:

- **0104 failed at link because the copied branch code outran its copied implementations.** The
  seven symbols map cleanly to the branch UFS and file-server call sites. [I, high]
- **0105 fixes the link but does not make the file server reachable.** With no caller of
  `sweet_files_start` and no other caller of the wrappers, the server thread never starts in this
  build. [I, high; caveat: indirect call not observed]
- **The named super log is not evidence for 0105.** Its hash duplicate and boot-arg mismatch are
  sufficient to reject it as an independent 0105 boot record. [I, high]
- **The wrappers would use kernel credentials, not the USB client's credentials.** They pass
  `vfs_context_kernel()`; `vfs_context_iskernel()` is true. Authorization is against root/kernel,
  not against a user. [I, high]
- **`mkdir` ignores umask at the wrapper level.** XNU's syscall does `& ~fd_cmask`; the wrapper does
  not. Unless `vn_create` re-applies it (not observed), a requested `0777` directory can be created
  `0777`. [I, medium]
- **`sweet_gpu_init()` now runs earlier relative to USB probe.** The diff moved the call. The
  runtime effect is unknown. [I, high for the order; U for effect]
- **The no-op BT/haptic stubs are acceptable only because the super boot args do not request those
  drivers.** If `sweetbt=1` or `sweethaptic=1` is passed, the kernel will silently do nothing. [I]

### 6.3 Unknown

These are the questions that block a confident runtime claim:

- Which CI run produced `out-0105`? The notes end with `41501352880` queued; the artifact exists but
  no run ID is attached. [U]
- What is `vfs_context0.vc_ucred` at runtime: `NOCRED`, `kernproc`'s cred, or a root cred? [U]
- What does `current_proc()` return inside an `sf_thread` created by `kernel_thread_start` on this
  arm64 XNU? Is `p_fd` valid? Is `fd_cmask` initialized? [U]
- What is `kernproc`'s cwd when `sweet_files_start` would run? Does a relative path resolve to `/`,
  to `/var/root`, or fail? [U]
- Does `vn_create`/`vnode_authattr_new` apply any additional umask or default-mode logic after
  `mkdir1at` receives `va_mode`? [U]
- Does `symlinkat_internal` reject or truncate a target longer than `MAXPATHLEN` when
  `UIO_SYSSPACE` is used? [U]
- Is there an indirect/kext caller of `sweet_files_start` outside the scanned `__TEXT`/`__TEXT_EXEC`
  branches? No source evidence, but not mathematically excluded. [U]
- Did the super image ever reach launchd? The only candidate log is a duplicate and ends at
  `launchd_cache_loader`. [U]
- What produced the quoted `initproc exited -- exit reason namespace 2 subcode 0x8 -- code 0x1`
  panic? It is not in any local log. [U]
- Did `sweet_gpu_probe`/`sweet_gpu_init` actually run under 0105, and did the GPU handoff succeed?
  The log shows GPU lines, but the log is not attributable to 0105. [U]
- Did BT/haptic/NativeAdreno stubs get called in the super boot? The UFS code calls them
  unconditionally, but the log is not trustworthy and there are no stub logs. [U]
- Does HFS preserve symlink mode/ownership as set by `symlinkat_internal`, or ignore it? [U]
- Does the file server's `PUT` of a signed binary preserve everything iOS needs (xattrs, resource
  forks, code signature)? `PUT` writes data only and sets mode/owner; no xattr copy. [I]/[U]

### 6.4 What would change the conclusions

- A valid 0105 boot log with `sweetfiles=1` and `SWEET FILES: listening on tcp 2223` would prove the
  caller exists in a different image or that the scan missed an indirect path.
- A disassembly of `sweet_usb_probe` in the exact booted image showing a `BL` to
  `_sweet_files_start` would refute the dead-code conclusion.
- A runtime dump of `vfs_context0` and `current_proc()` would resolve the cred/cwd/cmask questions.
- A successful `MKDIR`/`LINK`/`RM` over TCP with errno 0 would validate the wrappers.
- A panic in `symlinkat_internal` at the `fd_cmask` load would confirm the NULL-proc risk.

---

## 7. Risks

### 7.1 Critical: the file server is linked but unreachable

This is the largest risk and the one most likely to waste another AI's time.

- `sweet_files_start()` is defined and exported at `0xfffffe00079563b4`. [O]
- No `B`/`BL` in the kernel targets it. [O]
- `_sweet_usb_probe` ends in `RET` and does not call it. [O]
- The 0104 patch does not modify `sweet_usb.c`; the 0105 patch does not either. [O]
- The only callers of the three wrappers are inside `_sf_thread`, which only runs after
  `sweet_files_start`. [O]

Therefore, booting `shim-boot-super.img` with `sweetfiles=1` will not start the server **unless**
some code outside the checked-in patch set calls `sweet_files_start`. The comment in
`sweet_files.c` claims it is started by `sweet_usb.c`, but that hunk is absent. This is an
integration gap, not a link error. [I, high]

The fix is not part of this read-only note, but the shape is obvious: add a call after the USB
interface is up (in the branch's `sweet_usb.c`), or call it from the UFS/USB probe path behind
`sweetfiles=1`. That call must be added and tested; merely having the symbol is not enough. [I]

### 7.2 No-op stubs can hide real initialization requirements

- `sweet_bt_init()` and `sweet_haptic_init()` return immediately. If the branch's UFS init expects
  them to power rails, configure QUP SEs, or register IOKit services, those side effects are gone.
  The super boot args in the payload do not include `sweetbt=1` or `sweethaptic=1`, so the current
  image does not request them; a future image that does will fail silently. [O]/[I]
- `sweet_native_adreno_reserve_pool()` returns 0. The current caller ignores the result
  (`(void)`), so the value is harmless now. If future code checks it, 0 may mean "success" or
  "no pool"; the semantics are not documented. [O]/[U]
- `sweet_gpu_probe()` forwards to `sweet_gpu_init()` but cannot report failure because both are
  `void`. If GPU init fails, UFS init still returns 0 and boot continues into a broken display
  path. [O]/[I]
- The stubs are compiled only under `ARM64_BOARD_CONFIG_SWEET`. A build that forgets the define
  reverts to the original seven-symbol link failure. [O]

### 7.3 VFS context, credentials, cwd, and `fd_cmask`

- `vfs_context_kernel()` returns a static context, not the current thread's context. Its
  `vfs_context_proc()` falls back to `current_proc()`. Inside a `kernel_thread_start` thread, that
  may be `kernproc` or NULL. `symlinkat_internal` unconditionally dereferences
  `p->p_fd.fd_cmask`; a NULL `p` is a panic. [O] source; [U] runtime.
- `vfs_context_ucred()` returns `vfs_context0.vc_ucred` directly. The exact runtime cred is
  unknown. `vn_rdwr` receives it for PUT/GET; a sentinel cred could assert or behave differently.
  [O] source; [U] runtime.
- `AT_FDCWD` relative paths use the context process's cwd. If the kernel thread's cwd is not `/`,
  a client sending `PUT relative/path` writes relative to an unexpected directory. [O]/[U]
- The wrappers do not jail paths. Absolute paths are passed straight to `namei`; `..` components are
  allowed. The server is root and can write anywhere the VFS permits. [O]
- `mkdir1at`/`symlinkat_internal`/`unlink1` use `LOCKPARENT` but the path is resolved twice in some
  cases (e.g., symlink retry after create); concurrent renames can change the parent between
  resolution and operation. This is the usual path-based TOCTOU, amplified by a network service.
  [I]

### 7.4 Mode and ownership inconsistencies

| Operation | Mode applied | Owner | Notes |
|---|---|---|---|
| `MKDIR` | `mode & 0777` in wrapper; no `~fd_cmask` | default from `vn_create`/`vnode_authattr_new` | Setuid/setgid/sticky stripped; umask ignored at wrapper level |
| `LINK` (symlink) | `0777 & ~fd_cmask` inside `symlinkat_internal` | default | `fd_cmask` from `current_proc()` |
| `PUT` | `mode & 07777` in `vnode_open`, then `sf_setattr` sets `mode & 07777` | explicitly `uid=0`, `gid=0` | Preserves setuid/setgid/sticky if requested |
| `CHMOD` | `mode & 07777` in `sf_setattr` | owner unchanged | No `chown` command |

The inconsistencies are real:

- `MKDIR 07777` cannot create a sticky directory; it becomes `0777`.
- `PUT 04755` can create a setuid-root file, because `sf_put` masks with `07777` and sets owner
  root. That is a significant privilege surface on a root filesystem. [O]
- The server has no `CHOWN`, but `PUT` always sets root:wheel. [O]
- HFS may ignore some mode bits on symlinks; the effective mode is filesystem-dependent. [U]

### 7.5 Unlink scope and swap files

- `sweet_vfs_unlink` passes `unlink_flags = 0`, so it does not request `VNODE_REMOVE_NODELETEBUSY`.
  POSIX unlink can remove an open file; this is normal for a root file tool but dangerous if the
  target is in active use. [O]
- `unlinkat_internal` refuses `VROOT` and cross-mount deletes with `EBUSY`, so it cannot delete a
  mount root. [O]
- Swap vnodes are protected only when `ctx != vfs_context_kernel()`. The wrapper uses the kernel
  context, so it bypasses that protection. A client can `RM` a swap file if it knows the path.
  [O]
- There is no `RMDIR`; a directory `RM` will fail at `VNOP_REMOVE`. There is no recursive delete.
  [I]
- There is no `RENAME`, so installs that need atomic replace must delete then write, leaving a
  window with no file. `PUT` truncates in place, which is not atomic. [O]/[I]

### 7.6 Missing operations

The protocol supports only:

```text
PUT, GET, MKDIR, LINK (symlink), RM, CHMOD, SYNC
```

Missing operations that a real installer may need:

- `RMDIR` (empty directory removal);
- `RENAME`/atomic replace;
- `CHOWN`/`CHGRP`;
- `UTIMES`;
- `STAT`/`LIST`/`READDIR`;
- hard links;
- `TRUNCATE`/append;
- xattr/resource-fork/ACL copy;
- recursive mkdir/remove.

The absence is not a bug in 0105, but it limits what can be validated and what the server can
install. The existing userland deployment used repeated `PUT` for 322 files; that works for plain
files, not for directories with metadata. [O] notes; [I]

### 7.7 Protocol parser and framing

- `sf_line` reads one byte at a time until `\n` or `max-1` (1099) bytes. If a client sends a line
  longer than 1099 bytes without a newline, `sf_line` returns success with a truncated line and
  leaves the rest in the socket. The next request then starts mid-line: protocol desync. [O]
- `sf_handle` copies the `PUT` path into `char a[512]` and rejects if the token is `>= 512`; other
  commands use `arg1` directly, up to ~1090 bytes. `namei` will return `ENAMETOOLONG` for paths over
  `MAXPATHLEN`, but the target string for `LINK` has no explicit length check. [O]
- The parser does not reject embedded NUL bytes. `sf_line` terminates at the newline and writes
  `line[n]=0`; an embedded NUL truncates the C string, so a request can name a shorter path than
  the bytes suggest. For a local root tool this is primarily a correctness issue. [O]/[I]
- `PUT` parsing is positional: `PUT <path> <mode-octal> <size>`. If the mode field is missing, the
  size is parsed as octal mode and `sf_dec` sees the remaining text; the result is likely `EINVAL`
  or a zero-size write, not a clear protocol error. [O]
- `sf_reply` uses `snprintf` into 48 bytes; the largest `OK <uint64>` is well under that, so no
  truncation. It ignores send errors. [O]

### 7.8 Lifecycle and concurrency

- `sf_thread` allocates `sf_buf = kalloc_data(64K, Z_WAITOK)` once and never frees it. The thread
  never exits, so this is a permanent 64K allocation, not a leak per request. [O]
- `kalloc_data` is not checked for NULL. `Z_WAITOK` is allowed to sleep, but a NULL return would
  make `sf_recv_all` write to NULL. [O]/[I]
- `sf_thread` loops forever: if `socket`/`bind`/`listen` fails, it sleeps 1 s and retries; if
  `accept` fails, it sleeps 100 ms and retries. A second `sweet_files_start` would create a second
  thread that can never bind and spins forever. [O]
- The server handles one connection at a time on the accept thread. A slow client blocks all other
  clients. There is no timeout on `sf_recv_all`/`sf_line`; a half-open connection can hang the
  server. [O]
- `sf_put` receives the entire declared size even after a write error, discarding the rest, then
  closes. This avoids desync but leaves a partial file with no rollback. [O]
- `sf_get` reads `vnode_size` once and sends exactly that many bytes. If the file grows during the
  read, the extra bytes are not sent; if it shrinks, the short read leaves the client waiting for
  the original size. [O]/[I]

### 7.9 Security and authentication

- The only access control is the peer IPv4 subnet `192.168.7.0/24` and the bind address
  `192.168.7.2`. There is no password, token, TLS, or per-request authentication. [O]
- The bind is to one address, which normally limits reachability to the USB Ethernet interface.
  But any host that can source a `192.168.7.x` address on that link (or spoof one) can connect.
  [O]/[I]
- The operations are root-equivalent: write anywhere, chmod, symlink, unlink. A compromised host
  on the USB link can replace system binaries or launchd plists. [O]
- `PUT` sets owner root:wheel. A client can install a setuid-root binary (`PUT ... 04755 ...`).
  This is intentional for the installer, but it means the network service is a root execution
  surface. [O]
- There is no audit trail beyond `printf("SWEET FILES: ...")` lines on the kernel console. [O]

### 7.10 Filesystem and code-signing semantics

- `PUT` writes file data with `vn_rdwr`; it does not copy xattrs, resource forks, ACLs, or code
  signature blobs stored outside the Mach-O. On iOS, a signed binary's signature is usually in the
  Mach-O, but launchd jobs/plists and some assets rely on metadata. [I]
- `sf_setattr` sets `va_mode` and optionally `va_uid`/`va_gid`; it does not set `va_acl` or
  `va_xattr`. [O]
- `LINK` creates a symlink with a mode derived from `fd_cmask`; HFS may ignore symlink modes. [U]
- The root is HFS (the log says `hfs, local, journaled, noatime`). HFS has different case/normalization
  and metadata behavior than APFS; a path that works on the host may normalize differently. [O] log;
  [I] implications.
- `SYNC` calls `sync(kernproc, NULL, &rv)`, which flushes all filesystems. It does not fsync a
  specific file; a `PUT` followed by `SYNC` is the intended durability sequence. [O]

### 7.11 Error handling and observability

- `sweet_files.c` logs every command and errno, but only to the kernel console. If serial is off,
  the ring may be the only record. [O]
- `sf_reply` ignores send errors; the server continues after a client disconnect. [O]
- `sf_put` returns the first error but may leave a partial file. `sf_get` may have already sent
  `OK <size>` before a read error; the client sees a truncated body, not an `ERR` line. [O]
- The VFS wrappers return raw errno values; the client sees `ERR 13`, `ERR 17`, etc. There is no
  mapping to human-readable messages. [O]
- The stubs produce no logs, so a missing BT/haptic/GPU init is invisible except by its downstream
  effects. [O]

### 7.12 Link-time ABI risk

- The wrappers are declared `extern` in `sweet_files.c` and defined in `vfs_syscalls.c` without a
  shared header. If either signature changes, the compiler will not catch it across translation
  units; the link will still succeed if the symbol name matches, and the call will corrupt
  arguments at runtime. [O]
- `CAST_USER_ADDR_T(path)` hides the pointer type. A future change from `const char *` to a struct
  or a different address space would compile but be wrong. [O]
- The compat file declares `void sweet_gpu_init(void);` manually. If the real prototype changes,
  the compiler will not see the mismatch. [O]

---

## 8. Inventory

### 8.1 Source and patches

| Path | Size / lines | Purpose | Status |
|---|---:|---|---|
| `xnu/patches/0105-super-link-fix.patch` | 92 lines | The 0105 change: conf line, compat file, VFS wrappers | [O] committed `771481a` |
| `xnu/patches/0104-super-wifi-battery.patch` | large; `sweet_files.c` at lines 2216–2575 | Copied branch Wi-Fi/battery/UFS/file-server source | [O] committed `5639176` |
| `bsd/dev/sweet_super_compat.c` (in patch) | 37 lines | Four stubs | [O] patch content |
| `bsd/vfs/vfs_syscalls.c` (in patch) | +32 lines | Three wrappers | [O] patch content |
| `bsd/dev/sweet_files.c` (in patch) | 355 lines | TCP file server | [O] patch content |
| `bsd/conf/files` (in patch) | +2 lines total | Adds `sweet_files.c`, `sweet_super_compat.c` | [O] |
| `tools/mkpayload.py` | ~200 lines | Packs kernel + ADT into `SWEETXNU` payload, rewrites chained fixups | [O] |
| `tools/flame-files.py` (host side, referenced) | not read | Client for the server | [U] |

### 8.2 Build artifacts

| Path | Size | SHA-256 | Notes |
|---|---:|---|---|
| `xnu/out-0105/kernel.development.sweet` | 17,382,896 | `d22c5aad…` | Mach-O kernel with 0105 symbols |
| `xnu/out-0105/kernel.development.sweet.link/kernel.development.sweet.exp` | 195,612 | — | Export list; includes `_vfs_context_kernel` |
| `xnu/out-0105/kernel.development.sweet.link/kernel.development.sweet.linkarguments` | 2,555 | — | Link file list |
| `shim/out/payload-super.bin` | 16,757,888 | `8201e7de…` | 10-segment `SWEETXNU` payload |
| `shim/out/shim-boot-super.img` | 17,494,016 | `67ff470f…` | Android boot image: shim + payload |
| `shim/out/check-super/kernel` | 380,928 | `94e447f7…` | Shim kernel extracted from image |
| `shim/out/check-super/ramdisk` | 16,757,888 | `8201e7de…` | Equals `payload-super.bin` |
| `shim/out/check-super/header.txt` | 362 | — | Image header summary |
| `shim/out/check-super/dtb` | 346,902 | — | DTB extracted from image |

### 8.3 Logs

| Path | Size | SHA-256 | Notes |
|---|---:|---|---|
| `logs/xnu-super-panic.txt` | 50,094 | `576cdb1a…` | Duplicate of `xnu-0101s0reboot.txt`; no panic; boot args lack `sweetfiles=1` |
| `logs/xnu-super-panic.txt.shim.txt` | 6,040 | — | Shim GPU probe log; `LOADER no SWEETXNU payload` |
| `logs/xnu-0101s0reboot.txt` | 50,094 | `576cdb1a…` | The identical twin |
| `logs/xnu-0101s0reboot.txt.shim.txt` | 6,040 | — | Same shim log |
| `logs/xnu-wifi-boot.txt` | 575,997 | — | Branch Wi-Fi boot reference, not 0105 |
| `logs/wland-connected.log` | 111,945 | — | Wi-Fi proof, not 0105 |

### 8.4 Symbols to look up

```text
_sweet_vfs_mkdir                    0xfffffe000753d184
_sweet_vfs_symlink                  0xfffffe000753d23c
_sweet_vfs_unlink                   0xfffffe000753d270
_sweet_gpu_probe                    0xfffffe0007957198
_sweet_bt_init                      0xfffffe000795719c
_sweet_haptic_init                  0xfffffe00079571a0
_sweet_native_adreno_reserve_pool   0xfffffe00079571a4
_sweet_gpu_init                     0xfffffe00074f9e98
_sweet_files_start                  0xfffffe00079563b4
_sf_thread                          0xfffffe0007956410
_mkdir1at                           0xfffffe0007537670
_symlinkat_internal                 0xfffffe0007531b50
_unlink1                            0xfffffe0007531f3c
_unlinkat_internal                  0xfffffe0007531f54
_nameiat                            0xfffffe000752e9ac
_vfs_context_kernel                 0xfffffe000754a714
```

### 8.5 Where to look next

- For the missing caller: search the branch `sweet_usb.c` for `sweet_files_start` in the DC28088
  tree, and compare with the fast tree's `sweet_usb.c`. The 0104 patch did not touch it.
- For `vfs_context0`: inspect `bsd/vfs/kpi_vfs.c` and the definition of `vfs_context0` in the
  upstream tree; the definition was not in the files fetched here.
- For `current_proc()`/`kernproc`: inspect `osfmk/kern/thread.c` `kernel_thread_start` and
  `bsd/kern/kern_proc.c` `current_proc`; the exact uthread/proc relationship was not resolved.
- For umask: inspect `vn_create`/`vnode_authattr_new_internal` in `vfs_subr.c`.
- For the real boot: capture a fresh ring from a boot whose args include `sweetfiles=1`, and verify
  the kernel hash/tag before trusting it.

---

## 9. Possible validation

### 9.1 Static validation (no phone)

These checks can be done on the repository and artifacts:

1. **Patch application:** apply 0104 then 0105 to a clean tree; confirm no hunk failures and that
   `bsd/conf/files` has both entries.
2. **Compile guard:** build with `ARM64_BOARD_CONFIG_SWEET` defined; confirm `sweet_super_compat.o`
   and `vfs_syscalls.o` contain the symbols. Build without it and confirm the seven symbols are
   absent (expected, but shows the guard works).
3. **Signature check:** compile with `-Werror=implicit-function-declaration` and
   `-Werror=incompatible-pointer-types`; the manual externs should still compile, but a header would
   be better.
4. **Symbol table:** assert the addresses/symbols in §3.3. A script can fail if
   `_sweet_files_start` is missing or if any wrapper is missing.
5. **Call-graph scan:** assert zero `B`/`BL` to `_sweet_files_start` in the current build (this is
   the regression test for the dead-code finding). Assert one xref per wrapper from `_sf_thread`.
6. **Payload consistency:** assert each payload segment hash equals the kernel segment hash; assert
   the payload cmdline contains `sweetfiles=1`, `sweetusb=2`, and `sweetgpu_reboot=`.
7. **Image consistency:** assert `check-super/ramdisk` hash equals `payload-super.bin`; assert the
   image header sizes.
8. **Log provenance:** assert `xnu-super-panic.txt` is not byte-identical to any other log before
   using it as evidence. Add a build tag or boot-arg echo to future logs.

### 9.2 Runtime validation (phone; NOT performed here)

The following must be done by someone with the phone and explicit permission. It is listed as a
plan, not as a claim.

**Preconditions:**

- Boot `shim-boot-super.img` (SHA `67ff470f…`) or rebuild from the same kernel/payload.
- Capture the *entire* console ring, not a truncated tail.
- Confirm the boot args line contains `sweetfiles=1 sweetusb=2 sweetgpu_reboot=120`.
- Confirm the kernel is 0105 (symbols or a build tag), not 0101s0.

**Server start:**

- Look for `SWEET FILES: listening on tcp 2223`.
- If absent, check whether `sweet_files_start` is called. This is the expected failure in the
  current artifact.
- If present, verify the bind address is `192.168.7.2:2223` and the interface is `ue0`.

**Host setup:**

- USB Ethernet gadget enumerated (usbip/cdc_ether), host `192.168.7.1/24`.
- `nc 192.168.7.2 2223` or `tools/flame-files.py`.
- No Wi-Fi route to `192.168.7.0/24` that could bypass the USB link.

**Functional matrix:**

| Test | Request | Expected | What it proves |
|---|---|---|---|
| Ping server | connect | accept | bind/listen |
| Mkdir | `MKDIR /var/tmp/sweet-a 0755` | `OK` | wrapper + `mkdir1at` |
| Mkdir existing | repeat | `OK` (EEXIST mapped) | EEXIST handling |
| Mkdir nested | `MKDIR /var/tmp/sweet-a/b 0755` | `OK` | parent resolution |
| Mkdir mode | `MKDIR /var/tmp/sweet-b 0777` then stat | mode 0777 or 0755 | umask behavior |
| Mkdir sticky | `MKDIR /var/tmp/sweet-c 01777` | mode 0777, no sticky | `ACCESSPERMS` mask |
| Symlink | `LINK /var/tmp/sweet-a /var/tmp/sweet-l` | `OK`; `readlink` target | arg order + wrapper |
| Symlink existing | repeat | `ERR 17` | EEXIST |
| Unlink file | `RM /var/tmp/sweet-a/file` | `OK` | `unlink1` |
| Unlink dir | `RM /var/tmp/sweet-a` | `ERR` (EPERM/EISDIR) | no rmdir |
| Unlink missing | `RM /var/tmp/nope` | `ERR 2` | errno |
| Put/get | `PUT` 1 MB random, `GET`, compare | byte-identical | `vn_rdwr` + cred |
| Put setuid | `PUT ... 04755`, stat | mode 4755, owner root | root install surface |
| Chmod | `CHMOD ... 0600`, stat | 0600 | `sf_setattr` |
| Sync | `SYNC` | `OK` | `sync(kernproc, …)` |
| Subnet refusal | connect from 192.168.8.x | refused/close | peer check |
| Long path | 1100-byte path | `ERR 63` or clean error | parser/namei |
| Long line | 2000 bytes no newline | clean error, no desync | `sf_line` |
| Partial PUT | disconnect mid-body | server recovers next connection | `sf_put` error path |
| Concurrent | two connections | serialized, no crash | single-thread accept |
| Repeated start | call start twice | second bind fails; no panic | lifecycle |

**Crash/robustness tests:**

- `MKDIR`/`LINK`/`RM` with relative paths (`foo`, `../foo`) to see cwd.
- `LINK` with a 4 KB target to see target-length behavior.
- `RM` of an open file, a swap file (if safe), and a mount root (should `EBUSY`).
- `PUT` to a read-only filesystem/path to see error propagation.
- `PUT` with `mode=07777`, `mode=0`, `mode=0100000`.
- `GET` a file that changes size during transfer.
- Kill the client mid-`GET`/`PUT`; check server stays alive.
- Check kernel memory after 1000 requests: `sf_buf` is one allocation, but vnode refs/leaks may
  show.

**Observability:**

- Add (outside this note) a boot-time self-test behind `sweetfiles_selftest=1` that calls
  `sweet_vfs_mkdir`, `sweet_vfs_symlink`, `sweet_vfs_unlink` directly before USB is up. This
  isolates VFS behavior from the dead entry point.
- Log the context proc, cwd, `fd_cmask`, and cred at first call. This answers §6.3.
- Add a version/build tag to the kernel and echo it in the boot log.

### 9.3 Acceptance criteria

A minimal 0105 acceptance gate:

- [ ] Kernel contains all seven symbols at the expected addresses.
- [ ] Boot log shows the exact super cmdline including `sweetfiles=1`.
- [ ] `SWEET FILES: listening on tcp 2223` appears.
- [ ] `MKDIR`, `LINK`, `RM`, `PUT`, `GET`, `CHMOD`, `SYNC` each return expected results.
- [ ] No panic in `symlinkat_internal` (fd_cmask), `vn_rdwr` (cred), or `unlink1` (swap).
- [ ] Logs are unique (hash differs from 0101s0) and tagged with the kernel build.

Until these pass, 0105 should be described as “linked, not runtime-validated.” [I]

---

## 10. Questions for another AI

These are the questions that would most efficiently unblock the next step. They are ordered by
impact.

1. **Where is `sweet_files_start()` supposed to be called?** The comment says `sweet_usb.c` when the
   interface comes up, but 0104/0105 add no such hunk and the 0105 kernel has zero `B`/`BL` xrefs to
   `0xfffffe00079563b4`. Show the exact branch/fast-tree `sweet_usb.c` line or confirm the call is
   missing.
2. **Is the 0105 artifact actually the one in `payload-super.bin`?** The segment hashes match, but
   the CI run ID is missing. Can you identify the run from the artifact metadata or rebuild log?
3. **What is `vfs_context0.vc_ucred` at runtime?** Is it `NOCRED`, `kernproc`'s cred, or a root
   cred? Does `vn_rdwr(..., vfs_context_ucred(vfs_context_kernel()), ...)` accept it?
4. **What does `current_proc()` return inside a `kernel_thread_start` thread on arm64 XNU
   8796.141.3?** Is `p_fd` valid, and is `p_fd.fd_cmask` safe to dereference in
   `symlinkat_internal`?
5. **What is `kernproc`'s cwd when the USB probe runs?** Do relative paths in `MKDIR`/`LINK`/`RM`
   resolve to `/`, to `/var/root`, or fail?
6. **Does `vn_create`/`vnode_authattr_new` apply umask after `mkdir1at` receives `va_mode`?** If
   not, `sweet_vfs_mkdir` ignores umask and `MKDIR 0777` creates 0777 regardless of the process
   cmask.
7. **Should `sweet_vfs_unlink` pass `VNODE_REMOVE_NODELETEBUSY`?** What semantics does the branch
   file server intend: POSIX unlink of open files, or Carbon “busy files cannot be deleted”?
8. **Is deleting swap files via the kernel context acceptable?** `unlinkat_internal` explicitly
   exempts `vfs_context_kernel()` from the `VSWAP` EPERM check. Should the wrapper add a guard?
9. **Does `symlinkat_internal` validate the target length with `UIO_SYSSPACE`?** What happens with a
   4 KB target: `ENAMETOOLONG`, truncation, or a filesystem error?
10. **Why is `logs/xnu-super-panic.txt` byte-identical to `logs/xnu-0101s0reboot.txt`?** Was the
    ring copied twice, or did the probe read a stale buffer? Is there a lost super log elsewhere?
11. **Did any 0105 boot reach launchd?** The only candidate log ends at `launchd_cache_loader` and
    has no panic text. What was the actual failure mode (watchdog, panic, hang, fastboot return)?
12. **Is `sweet_gpu_probe` → `sweet_gpu_init` idempotent?** It is a tail branch; if another path
    calls `sweet_gpu_init` too, is double init safe? The xref scan shows no direct second call, but
    a bootloader/kext path could differ.
13. **Are the BT/haptic no-ops acceptable for the super image?** The payload does not pass
    `sweetbt=1`/`sweethaptic=1`, but a future image might. Should the stubs log a warning or return
    an error?
14. **What should `sweet_native_adreno_reserve_pool` return?** The current caller ignores it, but
    the branch semantics may be “0 = success” or “0 = no pool.” Is a negative errno more correct?
15. **Does `PUT` preserve everything iOS needs for a signed binary/launchd plist?** It writes data
    and sets mode/owner only; no xattrs/resource forks/ACLs. If not, what is the minimum metadata
    the installer must restore?
16. **Can the VFS wrappers be tested without USB?** A boot-time self-test behind a new boot arg
    would isolate `vfs_context_kernel`/cwd/cmask from the missing `sweet_files_start` caller. Is
    there an existing test hook in the branch tree?
17. **Is the `__LINKINFO`/`__LINKEDIT` address discrepancy meaningful?** This artifact has
    `__LINKINFO 0xfffffe0008110000` and `__LINKEDIT 0xfffffe000815c000`; the user-supplied values
    were `0xfffffe0008170000`/`0xfffffe00081bc000`. Which build are those from?

---

## Appendix A. Minimal source map

For quick navigation:

- `0105-super-link-fix.patch:1-9` — `bsd/conf/files` addition.
- `0105-super-link-fix.patch:10-52` — `sweet_super_compat.c`.
- `0105-super-link-fix.patch:53-92` — VFS wrappers.
- `0104-super-wifi-battery.patch:2216-2575` — `sweet_files.c`.
- `0104-super-wifi-battery.patch:4107-4147` — `sweet_ufs.c` hook block and GPU call move.
- XNU `bsd/vfs/vfs_syscalls.c` — `symlinkat_internal` (line ~5792), `unlinkat_internal`
  (~5985), `unlink1` (~6267), `mkdir1at` (~9719), `nameiat` (~3975).
- XNU `bsd/vfs/kpi_vfs.c` — `vfs_context_proc` (~1352), `vfs_context_kernel` (~1576),
  `vfs_context_ucred` (~1599), `vfs_context_iskernel` (~1615).

## Appendix B. Terms

- **VFS** — virtual file system layer; `vnode`, `namei`, `vnode_attr`, `vn_create`, `VNOP_*`.
- **`vfs_context_t`** — credential/thread context passed to VFS operations. `vfs_context_kernel()`
  is the kernel's static context.
- **`vfs_context0`** — the static object returned by `vfs_context_kernel()`; its `vc_thread` is
  NULL and its `vc_ucred` is the open question.
- **`AT_FDCWD`** — “use the current working directory” for relative paths.
- **`UIO_SYSSPACE`** — the buffer is in kernel address space; no `copyin`/`copyout`.
- **`NAMEI_COMPOUNDMKDIR` / `NAMEI_COMPOUNDREMOVE`** — XNU namei flags that let the filesystem
  perform the final create/remove as part of the lookup, reducing races.
- **`ACCESSPERMS`** — `0777` (rwx for user/group/other).
- **`fd_cmask`** — per-process file-creation mask (umask), stored in `struct filedesc`.
- **`VROOT`** — vnode flag marking the root of a mounted filesystem; unlink refuses it.
- **`VSWAP`** — vnode flag for swap files; unlink protects it unless the context is the kernel.

<!-- END -->
