# Spec 0016: `-commit` returns before the GPU fence (pipelined frame)

Status: spec only, no code. Owner: next implementation agent. Needs a userland build and a
`userdata` flash to test (`tools/metal-flash-test.sh`).

## Why

At 1125x2436 a frame is **8.9 ms of thread CPU + 16.9 ms of GPU wait, strictly serial**
(`logs/xnu-0163n.txt`: wall/cb 26.56, cpu/cb 9.42, `3771 waits of 17212 us`, 29 swaps in the best
second). The CPU cannot start frame N+1 until the GPU has finished frame N, because
`-[RedwoodMetalCommandBuffer commit]` pays the one `rwa_finish` before it releases `_work`
(`redwoodmetal.m` 5200-5352, patch 0011).

If the fence moves off the committing thread, a frame costs `max(CPU, GPU)`, not the sum: 16.9 ms
at the current clock, i.e. ~58 swaps/s at 60 Hz — still marginal (one tick is 16.67 ms), so expect
"most seconds 55-59, some 30", not a clean 60. The GPU clock is already at the top the GMU accepts
(`SWEET GPU: gfx3d cfg 0x101 dcvs perf 0x30000006 return 0` = level 6, 650 MHz), so there is no
clock margin to add; a smaller GPU frame is the next lever after this one, not part of it.

## What is true today (read in the sources)

- `commit` replays the recorded draws under `rw_lib_lock()`, with `rwa_set_deferred_wait(device, 1)`,
  then pays exactly one `mesa.finish`, sets the deferred wait back to 0, releases `_work`, returns
  the queue slot and delivers handlers (`redwoodDeliverHandlers`).
- `_work` holds everything a frame names (`retainReferences`); it may only be dropped after the
  fence. The comment above `[_work removeAllObjects]` names the crash that rule prevents: releasing
  on another thread while this one is inside a draw.
- `-waitUntilCompleted` is the driver's fence and sets `RW_CB_COMPLETED`. `-waitUntilScheduled` is
  empty. Handlers are delivered from `commit`; backboardd sets a completion queue, so they run on
  that queue via `dispatch_async`.
- The metal library has no lock: every entry serialises through `rw_lib_lock()`.
- CA calls `commitAndWaitUntilSubmitted` (`METAL_FINDINGS.md`), i.e. it asks for "submitted", not
  "completed". The current driver answers with "completed", which is stricter than CA asked for.
- CA allocates a new 13.9 MB drawable surface every frame and frees the last, so the frame's render
  target is not reused the next frame. App-owned resources (textures, buffers) are subject to
  Metal's own rule: the app must not write a resource the GPU is still reading.

## Design (depth 1, no new thread in v1)

1. New library entry `rwa_flush(struct rwa_device *)`: submit the queued work and return the
   library's own fence value without waiting (`pipe->flush`, i.e. the first half of `rwa_finish`).
   Implemented in `air_metal.c` beside `rwa_finish` (0011's `rwa_set_deferred_wait` is the model).
2. `commit`: as today up to the end of the replay. Then, instead of `mesa.finish`:
   - if the queue has a pending *previous* buffer, pay its fence first (`mesa.finish`, which also
     covers our new submission — freedreno has one batch, so waiting here is correct and cheap);
     release that buffer's `_work` and deliver its handlers;
   - `mesa.flush` this buffer's work, keep `_work`, set `RW_CB_SCHEDULED`, deliver scheduled
     handlers, and park the buffer on the queue's in-flight list.
3. `-waitUntilCompleted` keeps its meaning: pay the fence of this buffer (and of anything before it
   on the same queue), release `_work`, deliver completed handlers.
4. `-dealloc` (and the queue's teardown) pays any fence still pending, so the last frame of an app
   is not left half-executed.
5. Ordering: the library lock is taken per step, never held across a wait that another thread could
   need... **or** the finish stays under the same lock as today; decide with the reviewer. Today the
   whole commit runs under the lock; keeping that for the flush keeps the "one commit inside
   `rwa_render_draw`" crash fixed (xnu-0160vA line 4447).
6. Boot-arg `sweetmetal_commitwait=1` keeps today's behaviour (fence inside commit) so one image can
   A/B the change without a second flash.

## Invariants that must not break

- No resource named by a frame is released, rewritten or destroyed before that frame's fence.
- One `mesa.finish` per command buffer at most, and every buffer gets exactly one.
- A failed draw still fails the buffer with the library's sentence and still returns the queue slot.
- `_work` is dropped on the thread that paid the fence, never on the completion queue.
- A queue slot is not returned before the work is submitted (it may be returned before the fence).
- No handler runs before the state it is promised.

## Test plan

1. Host: `air_metal_test` (`--draw`, `--draw-scissor`, `--clear`, `--draw-ubo`) — unchanged pass.
   New case: two command buffers committed back to back, then `waitUntilCompleted` on the first:
   the second must not start before the first is submitted; both pictures correct.
2. `metaltest` self-test on the device, item 21 plus a new item: N commits without waiting for
   completion, one `waitUntilCompleted` at the end, measure commits/s against the current build.
3. Device, one boot per configuration, `sweetmetal_passlog=1`:
   - `sweetmetal_commitwait=1` (control) vs unset (new): expect wall/cb 25.6 -> about 17-18 ms and
     `waits` to move off the commit path; check `SMMU gfsr`, `fault address`, `THE GPU DID NOT
     FINISH`, `CRASH backboardd` are empty.
   - Then `sweet-subs-per-swap.py` for the swap rate, and the user looks at the screen (tearing,
     missing frames, stale content are the failure modes to look for).
4. Rollback: the pre-flash root snapshot (`work1-pre*.raw`) plus the current image; the change is one
   plug-in and one library file, both in `metal-build/pay/`.

## Risks

- A resource read by the GPU being rewritten by the app for the *next* frame is invisible to us: the
  depth-1 pipeline makes it possible where today it cannot happen. This is Metal-legal (the app must
  synchronise), but iOS userland has code written against a synchronous driver. The safety valve is
  the `sweetmetal_commitwait=1` boot-arg and the fact that CA allocates a new drawable every frame.
- A missed fence reports "completed" (silent corruption) — the acceptance test is the picture, not
  only the log.
- This is userland, not the kernel: a bad build crashes backboardd (0161wA did), it does not brick
  the phone. Recovery is the old root image, as with every earlier metal flash.

## Not in this spec

The remaining GPU-side cut (a cheaper frame than 16.9 ms), the 750x1624 path (0163 fixed the strip;
the picture is nearest-scaled and the user asked for native), and B1 (a new 13.9 MB surface a frame).
