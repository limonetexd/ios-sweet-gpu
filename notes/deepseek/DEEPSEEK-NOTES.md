# DEEPSEEK — Notas personales

**Fecha:** 2026-11-03
**Autor:** DeepSeek V4.1 Flash 1017 (OpenCode)
**Workspace:** `D:\pablo\Downloads\CLAUDE\OPENCODE\deepseek`
**Repo:** `D:\pablo\Downloads\CLAUDE\OPENCODE\deepseek\iOS on sweet\ios-sweet` (`gpu`, `b26d284`)
**Estado:** pausado; teléfono en fastboot, `userdata` desconocido, sin boot posterior.

Este documento es mi memoria de trabajo, no la del proyecto. El handoff corto es
`DEEPSEEK-HANDOFF.md`. Las notas profundas por frente son las 5 de
`ios-sweet/notes/agents/` (48.694 palabras).

---

## 0. Resumen en una frase

El super kernel 0105 (topaz + Wi-Fi/batería de la rama) linkea y arranca al menos hasta
`launchd_cache_loader`; la GPU está viva; el fallo es de userspace (`launchd`/cache loader), no de
GPU. La ring que se etiquetó como “super panic” no es del super y no contiene el panic. El último
flash de `userdata` se interrumpió y su estado es desconocido. No se debe bootear ni reflashear sin
autorización.

---

## 1. Límites y contrato con el usuario

- **Zona de Claude:** `D:\pablo\Downloads\CLAUDE\iOS on sweet` es solo lectura; nunca escribir.
  La copia de `gpu2.simg` que usé está en
  `D:\pablo\Downloads\CLAUDE\OPENCODE\deepseek\iOS on sweet\ipsw`, dentro de mi workspace.
- **Teléfono:** prohibido `fastboot`, `adb`, `boot`, `flash`, recovery o cualquier comando.
  El usuario no volverá a entrar en fastboot manualmente.
- **Destructivo:** cualquier flash de `userdata` requiere confirmación explícita; el ABL puede
  colgarse y exigir Power+Vol- físico.
- **Documentos:** mi handoff es `DEEPSEEK-HANDOFF.md`; mis notas son este archivo. No editar
  `ios-sweet/NOTES.md` ni `iOS on sweet/HANDOFF.md` sin permiso.
- **Estilo:** español, terse, honesto, riguroso; separar observado / inferido / desconocido.

---

## 2. Cronología de la sesión

### 2.1. Antecedentes (2026-11-01/02)

- El port ya arrancaba iOS 16.7.16 en `sweet` con GPU topaz y CoreAnimation composited.
- El daily era `shim-boot-0101s0.img` (0099+0101, 60 Hz, `serial=0`, sin Wi-Fi).
- La rama DC28088 tenía Wi-Fi WCN3990 funcionando (`wland`, `en0`, `casa j`, rx 833) y batería,
  pero su GPU NativeAdreno era lenta.
- Decisión: **super** = base rápida 0101/0102/0103 + fuentes Wi-Fi/batería de la rama, sin su GPU.
- Se prepararon 0104 (copia de fuentes) y 0105 (link fix + compat + VFS).

### 2.2. 2026-11-03: build y artefactos

- 0104 compiló; el primer link falló por 7 símbolos:
  `sweet_bt_init`, `sweet_haptic_init`, `sweet_native_adreno_reserve_pool`, `sweet_gpu_probe`,
  `sweet_vfs_mkdir`, `sweet_vfs_symlink`, `sweet_vfs_unlink`.
- 0105 añadió `sweet_super_compat.c` y los wrappers VFS. Link OK.
- CI en `limonetexd/ios-sweet-gpu`:
  - `41501352880` (`macos-15-intel`) OK, ~19m03s.
  - `41502238106` (`macos-latest`, rama `ci-macos-latest`) OK, ~5m09s.
  - `41494548855` falló el link.
  - `41498675277` cancelado sin runner.
- Kernel 0105 `d22c5aad...`; super image
  `67ff470f24acc5d3a92919fc8fbfde00e9f485e7e46c30aa8ab894bad24b5f3f`.

### 2.3. Boot del super y panic

- Se arrancó `shim-boot-super.img`.
- El usuario reportó **kernel panic**:
  `initproc exited -- exit reason namespace 2 subcode 0x8 -- code 0x1`, PID 1 `launchd`.
- El teléfono volvió a fastboot.
- Se extrajo la ring con `tools/sweet-pull-ring.ps1 -BootRecovery`:
  - OrangeFox `recovery/recovery.img` (134.217.728 bytes).
  - `/dev/block/sda34`, bloque 28067834, 4.198.486 bytes.
  - Ring de 4 MiB, header `# version 1, ring 4194304, total 50328 bytes, flush #3`.
  - Archivo `logs/xnu-super-panic.txt`, 50.094 bytes,
    SHA256 `576cdb1aca91c3975ce4c2bcfcea0360abc2d43eaed55894462c050d2ffeb99f`.

### 2.4. La ring no era del super

Descubrimientos posteriores:

- `logs/xnu-super-panic.txt` es **byte-idéntica** a `logs/xnu-0101s0reboot.txt` (mismo SHA).
- No contiene `panic`, `initproc`, `debugger` ni `Waiting for remote debugger`.
- Tiene **302 boot-args**; el super tiene **346**.
- Contiene strings de **0104** que el payload 0101 no tiene; no se puede atribuir sin más a 0101.
- Sus boot-args **no incluyen** `sweetfiles=1`/`sweetusb=2`.
- La línea del panic es la **transcripción del usuario**, no un artefacto.

Conclusión: el nombre del archivo es engañoso. La ring es de otro boot (probablemente un 0104
intermedio), no del super actual. El boot del super **no está probado** por esa ring.

### 2.5. El bloqueo real

- La ring termina en `exec launchd_cache_loader`.
- Después hay **24 líneas `SWEET FPS`** (una por segundo; ~24 s), no 3 s.
- No aparece ninguna de las 9 líneas que el helper imprime en la rama; la primera sería
  `0 Found valid port: 7939 Valid: 1`.
- La rama, con el mismo root/ADT, sí imprime las 9 líneas y llega a SpringBoard.
- Delta: 0104/0105 (IOKit quiesce, AKS, servicios nuevos) o un parche de rama no importado.
- La GPU no es: GMU `0xbabeface`, `CP_MEM_WRITE 0x5ee7c0de`, IB desde memoria XNU, fence 1,
  0 swaps, 1 surface, 0 MB wired.

### 2.6. Wi-Fi y batería

Bajo el super, kernel-side:

- `/dev/wlan` major 20.
- SMMU WLAN SID `0x240` -> CB4/SMR6.
- RPMH SN15/CN0.
- DDR 16383.
- QG SDAM 58% / 4031 mV.

Pero **ningún proceso abrió `/dev/wlan`**: no hubo `wland`, `wifid`, `en0` ni `RedwoodWLAN`.
En la rama sí:

- WCN3990 firmware/BDF.
- Scan, asociación `casa j`, 4-way, link up, rx 833.
- El spinner es configd/DHCP: falta servicio estándar en0/AirPort/DHCP en `preferences.plist`;
  `netsvc` publica IPv4/DNS manual al dynamic store como fallback.

### 2.7. Flash interrumpido

- Se verificó `ios16-root-gpu2.simg`:
  - Android sparse v1.0.
  - 12.159.682.532 bytes en disco.
  - 16 GiB raw; 4.194.304 bloques de 4096; 27.934 chunks; checksum 0.
  - SHA256 `FB86997E0D15DE3BA198834955C0FC64ACA95037C9E64CDFDB1FB69268393579`.
- Se lanzó `fastboot -S 512M flash userdata ...`.
- El comando se interrumpió; no hay confirmación de fin.
- No se arrancó después.
- `userdata` es desconocido: root anterior, nuevo o mezcla.
- El ABL puede colgarse tras un flash grande; requiere Power+Vol- físico.

### 2.8. Notas de agentes

- 5 agentes de documentación, uno por frente:
  XNU/GPU, root/launchd, Wi-Fi/batería, build/CI, USB/VFS.
- Primer intento: todos fallaron por **límite de modelo free**.
- El usuario cambió a `deepseek/deepseek-flash` de pago; se reanudaron los 5 con sus sesiones.
- Resultado: 48.694 palabras, 5 notas + `INDEX.md`.
- Verificado: `git status` no mostró archivos trackeados modificados; solo `notes/` nuevo y
  untracked preexistentes.
- Se redactó el serial del dispositivo en `xnu-gpu-kernel.md` antes de commitear, por la regla
  de `AGENTS.md` de no meter serials en git.

### 2.9. Commit y corrección de límites

- Se editó `ios-sweet/NOTES.md` (nueva sección 2026-11-03) y se commitearon `NOTES.md` +
  `notes/agents/` en `b26d284` (7 archivos, 5.319 inserciones).
- También se editó `iOS on sweet/HANDOFF.md` (fuera del repo) pensando que era “mi handoff”.
- El usuario corrigió: **“CREA TU HANDOFF. no quiero que toques NADA fuera. tu handoff es TU
  handoff y tu nota es TU NOTA.”**
- Se crearon `DEEPSEEK-HANDOFF.md` y este `DEEPSEEK-NOTES.md` en la raíz del workspace.
- `iOS on sweet/HANDOFF.md` quedó modificado del turno anterior; no se ha vuelto a tocar.
  Si el usuario quiere, se revierte, pero solo con su permiso.

---

## 3. Evidencia clave (resumen)

### 3.1. GPU viva

- `GPU ALIVE UNDER XNU`.
- GMU `0xbabeface`.
- `CP_MEM_WRITE from XNU -> 0x5ee7c0de`.
- `IB FROM XNU MEMORY RAN`.
- IB `0x10aed0000@0x40000000` -> destino `0x10aec4000@0x40010000`, `0xadee0618`, fence 1.
- `0 swaps`, `0 presents`, 1 surface, 0 MB wired, 0 creates failed.
- `SWEET FPS` sigue hasta el final de la ring.

### 3.2. Ring

- `logs/xnu-super-panic.txt` = `logs/xnu-0101s0reboot.txt`.
- SHA256 `576cdb1aca91c3975ce4c2bcfcea0360abc2d43eaed55894462c050d2ffeb99f`.
- 50.094 bytes.
- 302 boot-args vs 346 del super.
- Sin `panic`/`initproc`.
- Boot-args sin `sweetfiles`/`sweetusb`.
- Strings 0104 que 0101 no tiene.
- ~24 s de `SWEET FPS` tras `exec launchd_cache_loader`.
- 9 líneas del helper ausentes.

### 3.3. Build

- CI `41501352880` (macos-15-intel) OK.
- CI `41502238106` (macos-latest, `ci-macos-latest`) OK.
- `41494548855` falló por 7 símbolos.
- Kernel 0105 `d22c5aad...`.
- Super `67ff470f...`.
- `mkadt.py` `os.urandom(64)` sin seed: reproducibilidad no garantizada.
- `__LINKINFO/__LINKEDIT` del brief pertenece al branch, no a 0105.

### 3.4. USB/VFS

- 0105 linkea.
- `_sweet_files_start` cero xrefs `B`/`BL`.
- Server enlazado pero inalcanzable.
- Wrappers solo desde `_sf_thread`.
- Stubs: `sweet_gpu_probe` -> `sweet_gpu_init`; BT/haptic -> `RET`; NativeAdreno ->
  `MOV W0,#0; RET`.

---

## 4. Decisiones y por qué

1. **Super = topaz + Wi-Fi/batería de la rama, no la GPU de la rama.** La rama tiene Wi-Fi y
   batería, pero su GPU es lenta; nuestra topaz ya composita CoreAnimation.
2. **0105 como link fix, no como reescritura.** Mantener el file server USB y añadir stubs
   mínimos para los símbolos que la rama espera.
3. **No bootear tras el flash interrumpido.** El estado de `userdata` es desconocido; un boot
   podría empeorar o dar un falso negativo.
4. **No reflashear a ciegas.** El ABL puede colgarse; el usuario no volverá a entrar en fastboot.
5. **Ring nueva antes de conclusions.** La ring existente no es del super; sin una ring del
   artefacto actual no se puede atribuir el fallo.
6. **Notas separadas.** El proyecto tiene su `NOTES.md`/`HANDOFF.md`; mis documentos son
   `DEEPSEEK-HANDOFF.md`/`DEEPSEEK-NOTES.md`. No mezclar.

---

## 5. Errores y correcciones

### 5.1. Ring mal etiquetada

Error: asumir que `logs/xnu-super-panic.txt` era del super porque el nombre lo decía.
Corrección: comparar SHA, boot-args, strings y contenido. Es idéntica a `0101s0reboot`, no tiene
panic y no es del super.

### 5.2. “3 s” vs “24 s”

Error: la nota root contó 3 líneas `SWEET FPS` antes del `exec` y concluyó ~3 s.
Corrección: tras el `exec` hay 24 líneas, una por segundo -> ~24 s. La ventana es de ~24 s.

### 5.3. 0105 “no confirmado”

Error: la nota Wi-Fi se basó en un snapshot viejo y dijo que el link no estaba confirmado.
Corrección: los runs `41501352880`/`41502238106` y el kernel `d22c5aad...` confirman 0105.

### 5.4. `__LINKINFO/__LINKEDIT`

Error: mi brief los atribuyó a 0105.
Corrección: pertenecen al payload branch; no son de 0105.

### 5.5. Handoff del proyecto

Error: interpreté “actualiza tu handoff” como el `HANDOFF.md` del proyecto y lo edité.
Corrección: el usuario aclaró que mi handoff es mío; se creó `DEEPSEEK-HANDOFF.md`. El
`HANDOFF.md` del proyecto quedó modificado y no se ha vuelto a tocar.

### 5.6. Modelo free

Error: los 5 subagentes se lanzaron con un modelo free y fallaron por límite.
Corrección: el usuario cambió a `deepseek/deepseek-flash` de pago; se reanudaron las 5 sesiones
con `model: deepseek/deepseek-flash` y terminaron.

---

## 6. Hipótesis abiertas

1. **`launchd_cache_loader` se bloquea esperando un puerto/servicio** y launchd lo mata a los
   ~20-30 s; XNU paniquea por `initproc`. La ventana de ~24 s encaja. Falta traza.
2. **El root/userdata está inconsistente** por el flash interrumpido o por mutaciones in-place
   (Wi-Fi deploy: `launchd.plist` con 531 jobs, `preferences.plist` movido).
3. **0104/0105 introducen un servicio que launchd no puede completar** (IOKit quiesce, AKS,
   nuevos jobs) o falta un parche de la rama.
4. **El super no llegó a arrancar** y la ring es de un boot 0104 intermedio; el panic pudo ser de
   ese boot, no del super.
5. **Wi-Fi userland no arranca** porque launchd muere antes de lanzar `wland`; el kernel está listo.
6. **El file server USB no es alcanzable** porque `_sweet_files_start` no tiene caller.
7. **El flash pudo quedar a medias**; no hay transcript ni código de salida.

---

## 7. Inventario mínimo

- Repo: `...\OPENCODE\deepseek\iOS on sweet\ios-sweet`.
- Notas: `ios-sweet\notes\agents\` (5 + INDEX), commit `b26d284`.
- Root image: `iOS on sweet\ipsw\ios16-root-gpu2.simg` (workspace), SHA `FB8699...`.
- Super: `shim\out\shim-boot-super.img`, SHA `67ff470f...`.
- 0101: `shim\out\shim-boot-0101s0reboot.img`, SHA `e0be26fc...`.
- Branch: `shim\out\shim-boot-branch-reboot.img`, SHA `833b199c...`.
- Kernel 0105: `xnu\out-0105` (`d22c5aad...`).
- Ring: `logs\xnu-super-panic.txt` (SHA `576cdb...`), `logs\xnu-0101s0reboot.txt`.
- Referencia buena: `logs\xnu-0101s0-freeze.txt` (9 líneas del helper).
- Wi-Fi branch: `logs\wland-connected.log`.

---

## 8. Próximos pasos condicionales

**No ejecutar nada de esto sin autorización explícita.**

1. Confirmar el modo del teléfono sin comandos; si el usuario lo pide, `fastboot devices` es
   lectura, pero él dijo que no quiere más fastboot.
2. Construir una imagen 0105 con tag único, SHA registrado y boot-args completos
   (`sweetfiles=1 sweetusb=2`), y bootear solo con permiso.
3. Capturar ring nueva y foto del panic; verificar si `launchd_cache_loader` imprime sus 9 líneas.
4. A/B: ADT wlan on/off; 0101 vs super; revertir IOKit quiesce/AKS; probar `serial=0` vs `serial=3`.
5. Si se confirma el fallo, decidir reflash de `userdata` con confirmación y plan de ABL.
6. Wi-Fi: servicio estándar en0/AirPort/DHCP en `preferences.plist` o `netsvc`.
7. USB: caller real para `_sweet_files_start` y validación MKDIR/LINK/RM por TCP.

---

## 9. Lecciones para otra IA

- **No confíes en el nombre de un archivo.** `xnu-super-panic.txt` no es del super y no contiene
  el panic. Verifica SHA, boot-args, strings y contenido.
- **Una ring idéntica a otra no es evidencia independiente.** Si dos archivos tienen el mismo
  SHA, es el mismo artefacto.
- **Cuenta las líneas después del `exec`.** 24 `SWEET FPS` = ~24 s, no 3 s.
- **Separa observado / inferido / desconocido.** El texto del panic es una transcripción, no un
  artefacto.
- **No reflashees para “arreglar” sin una ring nueva.** El flash interrumpido ya dejó el estado
  desconocido.
- **Respeta la zona de Claude.** La copia de `gpu2` está en el workspace; no hace falta tocar la
  carpeta prohibida.
- **No edites los documentos del proyecto si el usuario pide “tu handoff”.** Crea los tuyos.
- **El límite de modelo free es un bloqueo real.** Reanudar con el mismo modelo free falla;
  necesita un modelo de pago o esperar.

---

## 10. Nota final

El trabajo técnico está en las 5 notas; este documento es el contexto de la sesión y las
correcciones. El teléfono no se ha tocado desde el flash interrumpido. La prioridad absoluta es
no empeorar el estado de `userdata` y no pedirle al usuario otro viaje a fastboot.
