# Spec 0016: `-commit` returns before the GPU fence (pipelined frame)

Status: implementing as `userland/metal/0016-commit-no-wait.patch` (built, host-proven, not yet on the
phone: needs a `userdata` flash). The design below was written before the code; where the code
differs, "As built" at the end says how and why.

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

## As built (2026-11-14)

`userland/metal/0016-commit-no-wait.patch`, 4 files, 17 hunks:

- **`rwa_flush`** (`air_metal.c`, `air_metal.h`): `pipe->flush` and the fence is dropped, not kept.
  A submission nobody waits on cannot be certified by a fence nobody keeps, and freedreno's flush
  submits on this thread and leaves the last fence in the context, so the next `rwa_finish` -- which
  flushes again and, with nothing new queued, reuses that fence -- waits for exactly this work.
  This is why no per-buffer fence handle was needed, which was design step 1's open question.
- **`-commit`**: with the new default (no `sweetmetal_commitwait=1`) it takes the queue's one
  pending buffer, pays its fence *before* the replay (design step 2 said after; before is what makes
  the wait cover the previous frame only -- paid after, the replay's own draws are already queued
  and the wait would cover them too, which is the serial frame this change exists to remove), then
  replays, then `mesa.flush` instead of `mesa.finish`, parks itself as pending and keeps `_work`.
- **`-redwoodPayFenceLocked` / `-redwoodPayFence`**: the one place a fence is paid. Idempotent, so
  the three callers (`-commit`, `-waitUntilCompleted`, the queue's `-dealloc`) cannot pay twice.
  It sets Completed only after the fence, releases `_work` there, and fails the buffer with the
  library's sentence when the GPU did not finish.
- **`-addCompletedHandler:`** after a commit no longer assumes the fence is paid (it is not, under
  0016): it pays first, then delivers. `-addScheduledHandler:` is unchanged -- "submitted" is true.
- **Queue**: `_pending`, retained, one buffer. The cycle queue->pending->queue (the buffer retains
  its queue) is broken by the next commit's take or by the queue's `-dealloc`, and in between it is
  one frame. A queue cannot reach `-dealloc` with a pending buffer while the cycle holds, so that
  path is the order for a future that breaks the cycle another way rather than a live one.

Proof, host softpipe: `air_metal_test --draw-deferred dw.metallib` (its 0011 case now calls
`rwa_flush` before its single `rwa_finish` when deferred) -- per draw PASS, deferred PASS, same
bytes PASS, 0 checks failed; `--clear` 0 cases failed. Shaders: `tools/air/dw.metal` (one function
per compilation: a metallib holds one LLVM module per function and the library takes the module's
own entry point). The whole patch set re-applies to the pinned donor in name order and reproduces
the working tree byte for byte.

Rollback: the plug-in and the library only (`metal-build/pay/`), one `userdata` flash each way; the
kernel and the iOS root are untouched by this change.
