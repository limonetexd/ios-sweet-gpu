# DEEPSEEK — Handoff personal

**Fecha:** 2026-11-03
**Autor:** DeepSeek V4.1 Flash 1017 (OpenCode)
**Workspace:** `D:\pablo\Downloads\CLAUDE\OPENCODE\deepseek`
**Repo de trabajo:** `D:\pablo\Downloads\CLAUDE\OPENCODE\deepseek\iOS on sweet\ios-sweet`
**Rama/commit:** `gpu`, `b26d284` (docs); el commit funcional previo es `e1ce648`; 0105 es `771481a`.
**Estado:** pausado. El teléfono quedó en fastboot; el último flash de `userdata` se interrumpió
y no se confirmó. No se arrancó nada después. No tocar el teléfono.

---

## 1. Reglas del usuario (no negociables)

- **No escribir en `D:\pablo\Downloads\CLAUDE\iOS on sweet`** (zona de Claude). Como máximo,
  lectura; nunca edición. Todo lo que se use debe estar en `OPENCODE\deepseek`.
- **No tocar el teléfono ahora:** ni `fastboot`, ni `adb`, ni `boot`, ni `flash`, ni recovery.
  El usuario no volverá a entrar en fastboot manualmente.
- **No reflashear a ciegas.** Cualquier paso destructivo (flash de `userdata`) requiere
  confirmación explícita y un plan para el cuelgue del ABL.
- Español, terse, honesto y riguroso. Distinguir siempre **observado / inferido / desconocido**.
- Mis documentos personales son este `DEEPSEEK-HANDOFF.md` y `DEEPSEEK-NOTES.md`. No editar
  `ios-sweet/NOTES.md` ni `iOS on sweet/HANDOFF.md` sin permiso explícito.

---

## 2. Objetivo

Port de **iOS 16.7.16** a **Redmi Note 10 Pro (`sweet`, SM7150)** con un único kernel XNU que
combine:

- GPU **topaz** rápida (la nuestra, no NativeAdreno de la rama).
- Wi-Fi **WCN3990** funcional (`wland`, `en0`, `Apple80211`, RPMh/PMEM/SMMU).
- Batería real (`SweetBattery`, QG SDAM, SPMI).
- Root iOS existente en `userdata`; sin tocar bootloaders, recovery, modem, persist ni backups.

El resultado se llamó **“super”**: base rápida 0101/0102/0103 + fuentes Wi-Fi/batería de la rama
DC28088 (parches 0104/0105), sin la GPU de la rama.

---

## 3. Estado actual (2026-11-03)

- **Teléfono:** última observación en **fastboot**. Serial omitido en este documento.
- **Flash:** se lanzó `fastboot -S 512M flash userdata ...\ios16-root-gpu2.simg`; el comando fue
  **interrumpido** y no hay confirmación de que terminara. El contenido actual de `userdata` es
  **desconocido**: puede ser el root anterior, el nuevo, o una mezcla.
- **No se arrancó después.** No bootear ni reflashear sin autorización.
- **ABL:** tras un flash grande puede colgarse y exigir **Power+Vol-** físico. El usuario ya
  avisó de que no volverá a entrar en fastboot manualmente.
- **Ring:** la última ring leída (`logs/xnu-super-panic.txt`) **no es del super actual** y no
  contiene la línea del panic. Ver §5.

---

## 4. Qué se hizo (cronología resumida)

1. **0104** — Se copió la fuente Wi-Fi/batería de la rama DC28088 sobre la base rápida
   0101/0102/0103: `sweet_pmem.c`, `sweet_rpmh.c` (+922 líneas PMEM/ARC/BCM/WLAN SMMU),
   `sweet_ufs.c`, `sweet_spmi.c`, `SweetBattery.cpp`, `flame_wlan/sta.c`,
   `redwood_net/sta/Apple80211.c`, `RedwoodWLAN.cpp`, `MiniIONetworkStack.cpp`,
   `sweet_files.c`, AKS `SweetKeyStore.cpp`, IOKit quiesce, headers y entradas de config.
   Se excluyó la GPU NativeAdreno de la rama; se mantuvo topaz.
2. **0105** — Link fix. Añade `bsd/dev/sweet_super_compat.c` con stubs:
   - `sweet_bt_init`, `sweet_haptic_init` -> no-op.
   - `sweet_native_adreno_reserve_pool` -> 0.
   - `sweet_gpu_probe` -> `sweet_gpu_init` (nuestra GPU rápida).
   - `sweet_vfs_mkdir/symlink/unlink` -> wrappers VFS para el file server USB.
3. **CI** — En `limonetexd/ios-sweet-gpu`:
   - `41501352880` (`macos-15-intel`): OK, ~19m03s.
   - `41502238106` (`macos-latest`, rama `ci-macos-latest`): OK, ~5m09s.
   - `41494548855`: falló el link por los 7 símbolos.
   - `41498675277`: cancelado sin runner.
4. **Artefactos**:
   - Kernel 0105: `d22c5aad...`.
   - Super image: `shim/out/shim-boot-super.img`, SHA256
     `67ff470f24acc5d3a92919fc8fbfde00e9f485e7e46c30aa8ab894bad24b5f3f`.
   - 0101 auto-reboot: `shim-boot-0101s0reboot.img`, SHA256 `e0be26fc...a7949c`,
     `sweetgpu_reboot=90`.
   - Branch auto-reboot: `shim-boot-branch-reboot.img`, SHA256 `833b199c...6821f9`,
     `sweetgpu_reboot=120`.
5. **Boot del super** — Se arrancó; el usuario reportó **kernel panic** con
   `initproc exited -- exit reason namespace 2 subcode 0x8 -- code 0x1`, PID 1 `launchd`.
   El teléfono volvió a fastboot.
6. **Ring** — Se extrajo `logs/xnu-super-panic.txt` con `tools/sweet-pull-ring.ps1 -BootRecovery`
   (OrangeFox, `/dev/block/sda34`, bloque 28067834). Después se descubrió que es **byte-idéntica**
   a `logs/xnu-0101s0reboot.txt` y que **no contiene la línea del panic**.
7. **Reflash** — Se verificó `ios16-root-gpu2.simg` (sparse v1.0, 12 GB, 16 GiB raw, 4194304
   bloques de 4096, 27934 chunks). Se lanzó `fastboot -S 512M flash userdata ...`; se interrumpió
   sin confirmación. No se arrancó después.
8. **Notas** — Se lanzaron 5 agentes de documentación; escribieron **48.694 palabras** en
   `ios-sweet/notes/agents/`. Se creó `INDEX.md`. Se commitearon con `NOTES.md` en `b26d284`.

---

## 5. Hallazgos clave (corregidos)

### 5.1. La GPU no es el panic

El ring muestra:

- GMU `0xbabeface`.
- `CP_MEM_WRITE from XNU -> 0x5ee7c0de`.
- `IB FROM XNU MEMORY RAN`.
- IB en memoria XNU `0x10aed0000@0x40000000` con destino `0x10aec4000@0x40010000`,
  `0xadee0618`, fence 1.
- Después: `0 swaps`, `0 presents`, 1 surface, 0 MB wired, 0 creates failed.
- El hilo `SWEET FPS` sigue vivo hasta el final del ring.

**Conclusión:** kernel y GPU vivos; el fallo es de espacio de usuario.

### 5.2. La ring “super panic” no es del super actual

- `logs/xnu-super-panic.txt` es **byte-idéntica** a `logs/xnu-0101s0reboot.txt`.
- SHA256: `576cdb1aca91c3975ce4c2bcfcea0360abc2d43eaed55894462c050d2ffeb99f`.
- Tamaño: 50.094 bytes.
- **No contiene** `panic`, `initproc`, `debugger` ni `Waiting for remote debugger`.
- Tiene **302 boot-args** frente a **346** del super.
- Contiene strings de **0104** que el payload 0101 no tiene; por tanto, tampoco se puede atribuir
  sin más a 0101.
- Sus boot-args **no incluyen** `sweetfiles=1`/`sweetusb=2`.
- El texto `initproc exited -- exit reason namespace 2 subcode 0x8 -- code 0x1` es la
  **transcripción del usuario**, no un artefacto de la ring.

**Conclusión:** el artefacto que llamamos “super panic” no prueba el boot del super. No digo que
el panic no ocurriera; digo que esa ring no lo capturó y no es del artefacto actual.

### 5.3. El bloqueo es `launchd`/`launchd_cache_loader`

- Tras `exec launchd_cache_loader` hay **24 líneas `SWEET FPS`** (una por segundo; ~24 s), no 3 s.
- No aparece **ninguna** de las 9 líneas que el helper imprime en la rama; la primera sería
  `0 Found valid port: 7939 Valid: 1`.
- La rama, con el mismo root/ADT, sí imprime las 9 líneas y llega a SpringBoard.
- El delta es **0104/0105** (IOKit quiesce, AKS, servicios nuevos) o un parche de rama no
  importado; no es GPU.

**Hipótesis principal:** `launchd_cache_loader` se bloquea o muere antes de abrir
`/System/Library/xpc/launchd.plist`; `launchd` sale con código 1 y XNU paniquea por `initproc`.
Falta una ring nueva del artefacto actual y, idealmente, una foto del panic.

### 5.4. Wi-Fi/batería: kernel-side listos, userland no arrancado bajo el super

Bajo el super, el ring muestra:

- `/dev/wlan` major 20.
- SMMU WLAN SID `0x240` -> CB4/SMR6.
- RPMH SN15/CN0.
- DDR 16383.
- QG SDAM 58% / 4031 mV.

Pero **ningún proceso abrió `/dev/wlan`**: no hubo `wland`, `wifid`, `en0` ni `RedwoodWLAN`.
En la rama sí funciona:

- WCN3990 descarga firmware/BDF.
- Escanea, asocia `casa j`, link up, rx 833.
- El spinner es **configd/DHCP**: falta un servicio estándar en0/AirPort/DHCP en
  `preferences.plist`; `netsvc` publica IPv4/DNS manual al dynamic store como fallback.

### 5.5. Build 0105 confirmado

- Runs `41501352880` y `41502238106` OK en `limonetexd/ios-sweet-gpu`.
- Kernel 0105 `d22c5aad...`.
- Super `67ff470f...`.
- Contiene los 7 símbolos del fix + Wi-Fi/batería/topaz; 0101 no tiene Wi-Fi.
- `mkadt.py` usa `os.urandom(64)` sin seed: la reproducibilidad byte a byte no está garantizada.
- El par `__LINKINFO/__LINKEDIT` del brief anterior pertenece al payload branch, no a 0105.

### 5.6. USB/VFS

- 0105 linkea, pero `_sweet_files_start` tiene **cero xrefs** `B`/`BL`.
- El servidor USB queda enlazado pero **inalcanzable**; los wrappers solo los llama `_sf_thread`.
- Stubs: `sweet_gpu_probe` -> `sweet_gpu_init`; BT/haptic -> `RET`; NativeAdreno ->
  `MOV W0,#0; RET`.

---

## 6. Correcciones y conflictos resueltos

- La nota de Wi-Fi decía que 0105 no estaba confirmado; **build demuestra que sí** (runs/hash).
- La nota root decía “~3 s” de silencio; la ring tiene **24 `SWEET FPS`** tras el `exec` -> ~24 s.
  **Gana XNU.**
- `xnu-gpu-kernel.md` nombra el repo `dipa-studio/ios-sweet`; los runs reales están en
  `limonetexd/ios-sweet-gpu`. **Gana build** para CI.
- SHA256 de `gpu2.simg`: `FB86997E0D15DE3BA198834955C0FC64ACA95037C9E64CDFDB1FB69268393579`
  (12.159.682.532 bytes), calculado sobre la copia del workspace
  `OPENCODE/deepseek/iOS on sweet/ipsw/ios16-root-gpu2.simg`; **no** la carpeta de Claude.

---

## 7. Archivos y artefactos

### Workspace / repo

- `D:\pablo\Downloads\CLAUDE\OPENCODE\deepseek\iOS on sweet\ios-sweet` — repo `gpu`.
- `ios-sweet/NOTES.md` — log del proyecto; se le añadió la sección 2026-11-03 y se commiteó.
- `ios-sweet/HANDOFF.md` — **no existe**; el handoff del proyecto está fuera del repo.
- `iOS on sweet/HANDOFF.md` — handoff del proyecto, **fuera del repo**. Fue editado en el turno
  anterior; el usuario pidió después que no tocara nada fuera y que creara mi propio handoff.
  **No volver a tocarlo sin permiso.**
- `ios-sweet/notes/agents/` — 5 notas + `INDEX.md`, 48.694 palabras, commit `b26d284`.

### Notas de agentes

- `xnu-gpu-kernel.md` — 9.723.
- `root-launchd-panic.md` — 9.847.
- `wifi-battery-branch.md` — 9.187.
- `build-ci-artifacts.md` — 9.693.
- `usb-vfs-super-compat.md` — 10.244.
- `INDEX.md` — entry point, hallazgos, errata, procedencia.

### Imágenes / kernels

- `shim/out/shim-boot-super.img` — `67ff470f...`.
- `shim/out/shim-boot-0101s0reboot.img` — `e0be26fc...`.
- `shim/out/shim-boot-branch-reboot.img` — `833b199c...`.
- `xnu/out-0105` — kernel 0105 `d22c5aad...`.
- `xnu/out-0101` — kernel 0101.
- Copia del root: `iOS on sweet/ipsw/ios16-root-gpu2.simg` (workspace), SHA `FB8699...`.

### Logs

- `logs/xnu-super-panic.txt` — 50.094 B, SHA `576cdb...`; **no es del super**.
- `logs/xnu-0101s0reboot.txt` — byte-idéntico.
- `logs/xnu-0101s0-freeze.txt` — arranque bueno de referencia (9 líneas del helper).
- `logs/xnu-wifi-boot.txt` — Wi-Fi de la rama.
- `logs/wland-connected.log` — asociación `casa j`, rx 833.

### Herramientas

- `tools-win\platform-tools\fastboot.exe`.
- `tools/sweet-pull-ring.ps1` — extracción de ring vía OrangeFox.
- `tools/sweet-probe-loop.ps1` — loop desatendido (no usar ahora).
- `tools/mkpayload.py`, `tools/unpack_bootv2.py`, `shim/build.sh`.
- `recovery/recovery.img` — OrangeFox R12.0_2.

### WSL (solo lectura)

- `\\wsl.localhost\Ubuntu\home\pablo\research\DC28088-kernel\kernel.development.sweet`.
- `\\wsl.localhost\Ubuntu\home\pablo\research\DC28088-wifi` — `wland`, `netsvc`.

---

## 8. Lo que NO está probado

- Que el super image actual arranque: la ring no es suya.
- Que el flash de `userdata` terminara o quedara consistente.
- Que el Wi-Fi userland arranque bajo el super (no se abrió `/dev/wlan`).
- Que el file server USB sea alcanzable en runtime (`_sweet_files_start` sin xrefs).
- Reproducibilidad byte a byte del ADT (`os.urandom(64)`).
- Que el panic sea reproducible: no hay ring nueva ni foto.

---

## 9. Próximos pasos (solo con autorización explícita)

1. **No bootear ni reflashear.** Primero confirmar el modo actual si el usuario lo pide; sin
   comandos al teléfono.
2. **Ring nueva del artefacto actual:** imagen 0105 con tag único, SHA registrado, boot-args
   completos (`sweetfiles=1 sweetusb=2`) y `sweetgpu_reboot` suficiente. Capturar ring y foto
   del panic si ocurre.
3. **A/B controlados:** ADT wlan on/off; 0101 vs super; revertir IOKit quiesce/AKS; comprobar si
   `launchd_cache_loader` imprime sus 9 líneas.
4. **Solo después** decidir un reflash de `userdata`; requiere confirmación explícita y plan para
   el cuelgue del ABL.
5. **Wi-Fi:** si asocia pero gira, instalar el servicio estándar en0/AirPort/DHCP en
   `preferences.plist` o usar `netsvc` como fallback.
6. **USB/VFS:** añadir un caller real para `_sweet_files_start` y validar MKDIR/LINK/RM por TCP.

---

## 10. Sesiones de subagentes

| Sesión | Nota | Estado |
|---|---|---|
| `ses_e5cf80000ffe7RUWCF0VR6Wg0W` | `xnu-gpu-kernel.md` | completada |
| `ses_e5cf7fffeffeHd4F5Ko3zMP8fS` | `root-launchd-panic.md` | completada |
| `ses_e5cf7fffcffeZK0UdZCQRNitsi` | `wifi-battery-branch.md` | completada |
| `ses_e5cf7fffbffe0wkQRmKbYlfUOW` | `build-ci-artifacts.md` | completada |
| `ses_e5cf7fffaffeNAViBfiLmVteD7` | `usb-vfs-super-compat.md` | completada |

Los 5 fallaron primero por límite de modelo free; se reanudaron con `deepseek/deepseek-flash`
de pago y terminaron. Todos respetaron el workspace y no tocaron el teléfono.

---

## 11. Nota de honestidad

- **No** se escribió en `D:\pablo\Downloads\CLAUDE\iOS on sweet`. La copia de `gpu2.simg` que se
  usó está en `OPENCODE\deepseek\iOS on sweet\ipsw`.
- **Sí** se editó `iOS on sweet/HANDOFF.md` en el turno anterior, por una interpretación errónea
  de “actualiza tu handoff”. El usuario corrigió: mi handoff es este archivo. No se ha vuelto a
  tocar y no se tocará sin permiso.
- El commit `b26d284` incluye `NOTES.md` del proyecto y las 5 notas. Si el usuario quiere que se
  revierta, hay que hacerlo explícitamente.
- El teléfono no se ha tocado desde el flash interrumpido.
