> State 2026-11-14 (end of the investigation phase):
> - **CORRECTION (user photos): 750x1624 draws only a strip at the top of the screen. Every 750x1624 number below is invalid. Never build with `SWEET_SCALE=2`. The valid baseline is 0168s60: 1125x2436, `wall/cb 26.1`, `cpu/cb 9.3`, `flush 986 us/sub`, best second 29, faults 0.**
> - Phone: in fastboot. Root `work1.raw` + payload 0001-0015. Nothing was flashed in this phase; every boot was `fastboot boot` (RAM only).
> - Best result: 0168z60 = 750x1624 + `sweetmetal_fddebug=sysmem` + `sweetfb_hz=60`: 9.6 ms a command buffer, best second 57 swaps, 0 faults. 0168zM (+ `SWEET_CPUMAX=1`): 9.15 ms, best second 59. One boot each, `partially-working`. Sustained 60 is NOT reached: 5 to 8 frames in each fast second take two ticks.
> - At 1125x2436 a frame is 26 ms: 30 a second is the ceiling there.
> - The 60 Hz fault is a GMEM restore over-fetch on a 281x609 surface, not the refresh rate. The sysmem flag avoids it. Always boot with `sweetmetal_fddebug=sysmem`.
> - Kernel patch 0162 (commit 16e1259) is pushed; CI run 43588677901 was still building. Boot-args `gpu_pagelist=1`, `sweet_surfclear_ms=0`, both off by default, never booted.
> - Read first: `docs/agent-progress/FPS_INVESTIGATION.md` (sections 6 and 7), then the last four sections of `TEST_LOG.md`.
> - Trap: image builds need `PATH=$HOME/Developer/ios-sweet-work/bin:$PATH`. Without it the script silently copies the old image. Check that the printed sha256 is new and that `rg -a -o 'NAME=[^ ]*' IMAGE` shows every boot-arg you added.
> - Summary of a log: `tools/sweet-boot-summary.sh TAG`.

# Phase A (any agent, including a small model): two RAM boots of kernel 0162

This phase runs fixed commands and copies numbers. It changes no source file.

## Rules for this phase. Stop and report if any is not met.

1. Do not edit any file except `docs/agent-progress/TEST_LOG.md` (append only) and this file's "Results" section.
2. Do not run `fastboot flash`, `fastboot erase`, `fastboot oem`, `adb push`, `git reset`, `git clean`, `git checkout --`, `git stash`, `git push --force`. The only device command is `tools/sweet-boot-test.sh`.
3. Do not invent a number. Every number written comes from the output of `tools/sweet-boot-summary.sh`. If a field is empty, write "empty".
4. Do not explain a result. Write the numbers. The lead decides what they mean.
5. If a command prints an error, or the output differs from "Expected" below, stop. Copy the last 10 lines of output into "Results". Do not try a fix.
6. If `sweet-boot-test.sh` exits 3, the phone did not come back. Stop. Tell the user: hold Power + Volume-down.
7. One boot at a time. Do not start the second before the first is recorded.

## Steps

```bash
cd ~/Developer/ios-sweet && export PATH=$HOME/Developer/ios-sweet-work/bin:$PATH
gh run view 43588677901 --json status,conclusion
```

Expected: `"conclusion":"success"`. If `failure`: stop, paste `gh run view 43588677901 --log-failed | tail -30` into "Results". If `in_progress`: wait, ask again later.

```bash
mkdir -p ~/Developer/ios-sweet-work/kernel-0162 && gh run download 43588677901 -n xnu-kernel -D ~/Developer/ios-sweet-work/kernel-0162
ls ~/Developer/ios-sweet-work/kernel-0162
```

Expected: a file `kernel.development.sweet`. If the artifact name is refused, run `gh run view 43588677901` to list artifact names, and stop if none holds that file.

Boot 1 (`gpu_pagelist=1`):

```bash
A="sweetgpu_reboot=300 sweetmetal=1 metal_profile=1 sweetmetal_procs=* sweetnull=backboardd,SpringBoard,metaltest sweetmetal_passlog=1 sweetgpu_swipe=90 sweetmetal_fddebug=sysmem"
SWEETFB_HZ=60 bash tools/sweet-gpu-image.sh ~/Developer/ios-sweet-work/kernel-0162 0169pl "$A gpu_pagelist=1"
rg -a -o 'gpu_pagelist=1|sweetgpu_reboot=300|sweetfb_hz=60' shim/out/shim-boot-0169pl.img | sort -u
bash tools/sweet-boot-test.sh shim/out/shim-boot-0169pl.img 0169pl 420
bash tools/sweet-boot-summary.sh 0169pl
```

Expected: `RAMDISK MATCH`; the three boot-args listed; `fastboot ok`; the summary shows `page lists kept`.

Boot 2 (adds `sweet_surfclear_ms=0`): the same four commands with tag `0169sc` and `"$A gpu_pagelist=1 sweet_surfclear_ms=0"`. Expected in the summary: `cleared 0 ms after`.

Append one row for each boot to `TEST_LOG.md`, in the form of the 0168z60 row, with the summary's numbers. Label both `experimental`.

## How to judge (mechanical)

Compare with 0168s60: `wall/cb 26.1`, `cpu/cb 9.3`, `flush 986 us/sub`, faults 0. Boot 0169pl of this phase was already run once at 750x1624 by the lead and is invalid: run it again at full size under tag `0169pf`, and boot 2 as `0169sf`.

- "Better" means: gfsr, notfinish and arena all empty or 0, no `CRASH backboardd` or `CRASH SpringBoard`, AND `wall/cb` lower by 0.5 ms or more.
- Anything else is "not better". Write which condition failed.
- Do not change any default. Do not write a patch. A "better" result is a line in "Results" for the lead.

## Results (fill in)

- CI: `43588677901` success (commit `16e1259`). Kernel `kernel.development.sweet` sha256 `a4ef071f...`, carries `gpu_pagelist` and `sweet_surfclear_ms`. Both images `RAMDISK MATCH`, every added boot-arg present in the image.
- 0169pl: Run as `0169pf` (full size 1125x2436, as line 60 of the phase asks). Image `shim-boot-0169pf.img` `ecdc6358...`, args A + `gpu_pagelist=1`. Summary: gfsr empty, notfinish empty, arena empty, no backboardd or SpringBoard crash; `page lists kept for the walk before a submission (gpu_pagelist)`; `cleared 40 ms after`; **wall/cb 27.56 ms**, cpu/cb 15.80 ms, flush 1251 us/sub, waits 1909 of 12076 us, best second 36, 82 active s (20.1/s), peak 55.6 C. Not better: `wall/cb` is 1.46 ms higher than 0168s60's 26.1. `logs/xnu-0169pf.txt`.
- 0169sc: Run as `0169sf`. Image `shim-boot-0169sf.img` `e6c4fff9...`, args A + `gpu_pagelist=1 sweet_surfclear_ms=0`. Summary: gfsr empty, notfinish empty, arena empty, no backboardd or SpringBoard crash; `cleared 0 ms after`; `page lists kept ... (gpu_pagelist)`; **wall/cb 24.44 ms**, cpu/cb 9.01 ms, flush 957 us/sub, waits 4483 of 15544 us, best second 42, 203 active s (20.9/s), peak 55.6 C. Better: `wall/cb` is 1.66 ms lower than 0168s60's 26.1. `logs/xnu-0169sf.txt`.
- Note for the lead: batches per command buffer differ (0169pf 17.7, 0169sf 7.1), and `first cleans` differ (2122 of 12712 MB vs 893 of 293 MB), so the two boots are not the same workload. One boot each.

# Phase B (lead model only: Fable or Opus)

Not for a small model: these touch memory lifetime, the kernel, or the root image.

1. Decide from Phase A whether 0162's options become defaults in the test image script.
2. Find why 750x1624 shows only a strip (size, sysmem at that size, or the present path). Read-only first; no boot at that size without the user's go-ahead.
2b. After every boot of a new configuration the user confirms the picture before any number is recorded as a result.
3. Commit returns before the GPU wait (`FPS_INVESTIGATION.md` section 7 item 5). Written spec first, `opus-impl`, `reviewer`, host tests, then a flash with the user's typed yes.
4. Over-fetch fix in the kernel (item 6), so the sysmem flag is not needed.
5. A thermal cap before `SWEET_CPUMAX=1` is used outside a test.

Not in these phases: widgets, glyphs, masks, Control Centre.
