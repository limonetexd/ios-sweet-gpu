# Phase M1 — Port the Metal driver as the primary GPU path (auto-run)

Lead engineer. Read `CLAUDE.md`, `PROJECT_STATE.md`, "Metal assessment" in `GPU_DECISION.md`. **User decision 2026-11-08: Metal is the primary path. Port the driver.** This overrides the R1/R2/R3 gate for choosing the path; it does not remove the safety rules.

**Allowed without asking:** `fastboot boot` test images, REA under `REA_SAFE_PROTOCOL.md`, GitHub CI when local building is not enough, commits and non-force pushes on `gpu`, subagents for lists and builds.

**Still needs the user's yes in the session:** flashing or erasing any named partition, including `userdata`. Files added to the booted root are additive and removable; take a list of what was added.

**Standing:** every image auto-returns to fastboot (`sweetgpu_reboot=N`, confirmed in the payload); verify codename and image hash before boot; no guessed Adreno registers or packets; no code from unlicensed sources (DC28088, ios-topaz); keep GL buildable and selectable, and tag the known-good commit, until Metal passes the same tests; a compile or one boot is never `verified-working`.

**Work directory:** `~/Developer/ios-sweet-work/metal` (donor `a79ff07`, tools, shader corpus).

**Steps, one rung at a time:**

1. `tools/metal-build.sh`: reproducible host tools and iOS outputs from the pinned donor and Mesa, outside git.
2. Shader gaps: QuartzCore `fixed_frag_lph_cph`/`_cpf`, VideoToolbox bitcast and `air.get_null_texture_2d`. Patches on the pinned donor, written here.
3. Kernel patch, next free number: boot-arg `sweetmetal=1` publishes `MetalPluginName`/`MetalPluginClassName` on `IOAcceleratorES`. `check-patch.py`, apply on a scratch tree, `reviewer` subagent.
4. Build kernel (CI if needed), image with auto-return, install files with no partition flash.
5. Device ladder, stopping at the first failure to diagnose: discovery, compute, triangle, CoreAnimation, then Safari video.

**Record** each rung in `TEST_LOG.md`. **Stop** when a rung needs a flash or the user's physical help, or context reaches 70%. Then handoff and new `NEXT_PROMPT.md`.
