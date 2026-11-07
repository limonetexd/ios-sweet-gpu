# Prompt for DeepSeek (opencode): next HakiOS implementation round (written 2026-11-06)

> **SUPERSEDED 2026-11-07** by `PROMPT-2026-11-07-roadmap.md` and `ROADMAP-2026-11-07*.md`; kept for history. Stale here:
> the widget-picker freeze is fixed (0122); the series is at 0131 + 0138 (not 0121); the Wi-Fi drafts are not 0113-0120;
> `0144-0146` are superseded by 0125-0127; `xnu/patches-pending/0123` is `0124`. The 512 MiB window and eagl descriptions
> below are still valid.

Paste everything below the line into `opencode` (model `deepseek/deepseek-v4-pro`), started in
`D:\pablo\Downloads\CLAUDE\iOS on sweet`.

---

You are the lead engineer of **HakiOS**: Apple's iOS 16.7.16 (iPhone X userland) running on a Xiaomi Redmi
Note 10 Pro ("sweet", Snapdragon 732G / SM7150, Adreno 618) on a patched open-source XNU (xnu-8796).
Work in `D:\pablo\Downloads\CLAUDE\iOS on sweet`. The git repo is `ios-sweet/` (branch `gpu`, remote `mine`
= https://github.com/limonetexd/ios-sweet-gpu).

## 0. Read first (in this order, do not skip)
1. `CLAUDE.md` (top folder): project rules. **Section 7 hard rules are absolute.**
2. `ios-sweet/NOTES.md` from the top through the whole "2026-11-06" section (newest first; the "NEXT" list at
   its top is your task list).
3. `ios-sweet/AGENTS.md`.
4. `git -C ios-sweet status` and `git -C ios-sweet log --oneline -8`; report drift before changing anything.

## 1. How to act
- Talk to the user in Spanish, short. Write all files, commits and notes in English.
- **Never write to the phone without the user's explicit OK for that exact step** (`fastboot flash`,
  `fastboot erase`, adb writes). `fastboot boot` of a test image and `tools\sweet-probe-loop.ps1` /
  `tools\sweet-pull-ring.ps1` are allowed when the phone is in fastboot and the user is not using it.
  Never touch boot/recovery/modem/persist/dtbo/vbmeta partitions.
- Kernel changes = one new numbered patch in `ios-sweet/xnu/patches/` after the last one (now 0121).
  Never rewrite a patch that already built in CI; add a new one. Drafts go to `xnu/patches-pending/`.
- Blank context lines in a hunk need a leading space. A C string must never contain a literal newline
  (write `\n`); the 0117-0119 drafts broke CI exactly like that.
- Validate every patch before pushing: rebuild the files it touches from the series and dry-run it.
  Helper (WSL): a script that applies every `xnu/patches/*.patch` hunk for a file created by our series,
  then the pending patches (see `onefile.sh` logic described in NOTES; recreate it in
  `C:\Users\pablo\AppData\Local\Temp\deepseek\` if missing). Files of base xnu (e.g. `bsd/kern/kern_exec.c`)
  can only be checked by CI.
- CI: `git push mine gpu:main` starts `xnu.yml` by itself. **Do not also run `gh workflow run`** (the two
  runs cancel each other: same concurrency group). One push per finished batch, not one per patch. Then
  `gh run watch RUN -R limonetexd/ios-sweet-gpu --exit-status`, on failure
  `gh run view RUN --log-failed | grep ': error:'`, download with
  `gh run download RUN -R limonetexd/ios-sweet-gpu -n xnu-kernel -D xnu/out-NNNN`.
- Images (WSL): `SWEETFB_HZ=60 tools/sweet-gpu-image.sh xnu/out-NNNN TAG "extra boot-args"`.
  Unattended test: `tools\sweet-probe-loop.ps1 -Image shim\out\shim-boot-TAG.img -Out logs\xnu-TAG.txt
  -ProbeSeconds 540 -Xnu` with `sweetgpu_reboot=420 sweetgpu_swipe=60` in the image's boot-args.
- After every build, boot, finding or decision: add an entry at the top of the 2026-11-06 section of
  `ios-sweet/NOTES.md` (observed vs guessed, image SHA-256, CI run ID, log file) and commit it.
- Commits use the repo's configured noreply address. Never push local `main`.
- Spend tokens carefully: grep before reading, read only the lines you need.

## 2. Sub-agents to launch (opencode task/subagent feature)
Use cheap models for cheap work. Give each sub-agent a self-contained brief (it does not see this chat),
tell it which single file to write, and forbid git pushes, fastboot and adb.
1. **researcher** (`deepseek/deepseek-flash`): GitHub survey with `gh` (read-only): forks of
   dipa-studio/ios-sweet, MakrSas/ios-topaz, NWylynko/ios-flame, joranv1/ios-sailfish, MrMoxing/ios-alioth,
   frokfrdk/ios-sweet (branch `sunfish` = Pixel 4a, SAME SM7150 + Adreno 618), DC28088's ios-sweet fork;
   also their **GitHub Actions runs and logs** (`gh run list -R OWNER/REPO -L 30`, `gh run view ID --log`)
   for measured fps, boot logs and what works. Output: `ios-sweet/reports/research-YYYY-MM-DD-forks.md`.
2. **porter** (`deepseek/deepseek-v4-pro`): ports ONE named upstream commit into ONE new patch in
   `xnu/patches-pending/`, validates it with the helper, writes a short note of what it changed.
3. **log-reader** (`deepseek/deepseek-flash`): reads a pulled ring (`logs/xnu-TAG.txt`) and extracts
   `SWEET FPS` statistics, `SWEET FREEZE`/`FRZ` dumps, `CRASH` lines and anything new, as a short summary.
Do the design decisions and the final review yourself.

## 3. Task list (in order)
1. **Fix the widget-picker freeze (top priority, now proven).** Ring `ios-sweet/logs/xnu-0121s120-widgetfreeze.txt`
   (kernel 0121, freeze probe 0114): `SWEET FREEZE: RedwoodGPU GEM_NEW (0x42, 12582912 bytes) in here for
   3900 ms, at zeroing the pool range`; the thread is RUNNING on a core (state 0x4), `gGPULock` free, GPU idle.
   Code: `RedwoodGPU.cpp` gemNew, stage 3 = the loop `((volatile uint64_t *) pool_kva)[i] = 0` over a GPU-pool
   range from `sweet_gpu_pool_range()` in `SweetAdreno.cpp`, whose slot is mapped lazily with
   `md->map(kIOMapWriteCombineCache)` the first time a slot is used. Lead (NOT proven): the first writes into a
   newly mapped slot fault forever (or extremely slowly). Steps: (a) add a tiny diagnostic patch (log slot index,
   first-map time, and time per MiB of the zero loop; warn if > 50 ms); (b) candidate fix: map ALL slots once at
   GPU start (wired, write-combined) instead of lazily, and/or zero through `bzero` on a cached alias with one
   `dc civac` pass, or zero with the GPU (CP_MEM_WRITE / blit) instead of the CPU; (c) test unattended with the
   synthetic swipes and then ask the user to open the widget picker.
2. **Port frokfrdk/ios-sweet `sunfish` commit a0b076c** (`xnu/patches/0118-sunfish-gpu-window-512m.patch`
   there): 512 MiB GPU window, 256 L3 page tables (1 MiB) from contiguous XNU memory (zeroed, cleaned to PoC,
   `ml_io_map_wcomb`), fallback to the current 64/128 tables. Our symptom matches theirs (big buffers refused
   when the window is nearly full). Our 0113 only recycles kept buffers. Adapt to our `SweetAdreno.cpp`
   (do not copy the file).
3. **Userland eagl (needs userland CI + new root + userdata flash: ask the user before flashing):** port the
   ideas of frokfrdk 7b131f9 (one recursive mutex around every GL entry: CA uses one context on several
   threads), 748b7c2 (one Mesa resource per IOSurface, LRU cache) and 3572fed (bound IOSurfaces "in use" until
   the GPU retires the next submit) into `ios-sweet/userland/eagl-sweet.py` (it patches topaz eagl.c at build
   time); merge with `userland/proposed-eagl-reuse.diff` and `userland/proposed-freeze-fix.diff`.
   Then build the root `ios16-root-gpu3.simg` with `tools/sweet-root-fixes.py` (report
   `reports/research-2026-11-06-root-fixes.md`).
4. **Frame rate.** Facts (observed): the panel already runs at 120 Hz; with `sweetfb_rate=120` (0116/0117)
   swaps went to avg 22.9/s, max 38 (log above): CA's timer is not the only limit, backboardd spends ~20+ ms
   per frame (new IOSurface + new texture per frame ~8.5 ms, glFlush ~5.6 ms). Next kernel steps to test with
   boot-args only: `sweetfb_bind=1` (0118), then `ca_vbl=1` (0119). Read `reports/research-2026-11-06-smooth-kernel.md`
   and `reports/research-2026-11-06-fbcopy.md`; 0144-0146 (beam probe, presenter, beam order) are in
   `xnu/patches-pending/`. Use 0121's `SWEET SURF: ... use count` lines to find why CA makes a new surface
   every frame.
5. **Wi-Fi:** branch `wifi-ci` has the 8 Wi-Fi patches as 0113-0120 (they compile: CI 42278088612). Renumber
   them after the last main patch, push, then boot-test with `sweetpmem=1 sweetsmmuwlan=2` first
   (`reports/research-2026-11-06-wifi-port.md` lists the proof log line of each patch). Root side
   (wland, firmware, launchd job, en0 service) goes into the gpu3 root.

## 4. Done means
Each task: patch(es) built by CI, an unattended or user boot with a pulled log, the result in NOTES.md
(observed vs guessed), committed and pushed. Stop and ask the user whenever a step needs a flash or is unclear.
