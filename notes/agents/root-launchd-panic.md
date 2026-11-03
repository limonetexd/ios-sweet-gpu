# Nota forense: root, userdata, launchd y panic en sweet

**Ámbito:** `ios-sweet` — Redmi Note 10 Pro (`sweet`, SM7150), usuario iOS 16.7.16 (20H392, iPhone X), kernel XNU 8796.141.3, root HFS+ sintético en la partición `userdata`.
**Fecha del análisis:** 2026-11-03.
**Modo:** solo lectura. No se ejecutó ningún comando de fastboot, adb, boot, flash o recovery; no se tocó el teléfono, el código, `NOTES.md`, `HANDOFF.md` ni la carpeta `D:\pablo\Downloads\CLAUDE\iOS on sweet`. La única escritura es este archivo.

**Etiquetas de evidencia:**

| Etiqueta | Significado |
|---|---|
| `OBS` | Leído directamente en un artefacto del workspace (log, imagen, script, git). |
| `INF` | Inferencia con mecanismo explícito; puede ser falsa si falla una premisa. |
| `DESC` | Desconocido, no verificado o solo reportado por el usuario, sin artefacto que lo respalde. |

Cada afirmación relevante lleva fuente (`NOTES.md:línea`, `logs/archivo:línea`, `HANDOFF.md:línea`, ruta de script). Las líneas de `NOTES.md` corresponden a la copia de 210.905 bytes con mtime 2026-11-02 19:38; las de los logs, a la copia exacta indicada.

---

## 1. Veredicto operativo

1. **El panic es de espacio de usuario, no de GPU ni del kernel.** El self-test de GPU terminó: `CP_MEM_WRITE from XNU -> 0x5ee7c0de`, la IB corrió (`IB FROM XNU MEMORY RAN`, `fence 1 done 1`) y el hilo de estadísticas siguió imprimiendo `SWEET FPS` con `0 swaps`, `GPU 0 ms pending (fence 1)` hasta el final del ring (`logs/xnu-super-panic.txt:403-407`, `:587-589`). No hay assert de kernel, fault de SMMU/GPU, ni línea térmica.
2. **El que muere es `launchd` (PID 1), no un daemon cualquiera.** El texto reportado es `initproc exited ...`; `initproc` es `launchd`. El ring, sin embargo, **no contiene la línea del panic**: termina en `exec launchd_cache_loader` más tres tics de `SWEET FPS` (`:586-589`). La única fuente del texto es la transcripción humana; no hay foto, core ni `.ips` en el workspace.
3. **El fallo ocurre en el arranque de `launchd_cache_loader` o en el manejo que hace `launchd` de esa boot task, no en el parseo del plist.** En los arranques buenos, el helper imprime nueve líneas inmediatamente después de `exec launchd_cache_loader`; la primera es `0 Found valid port: 7939 Valid: 1`. En el ring del panic no hay **ninguna** de las nueve, y pasan ~3 s de tics del kernel antes de que el ring se corte (`logs/xnu-0101s0-freeze.txt:519-530` vs `logs/xnu-super-panic.txt:586-589`). Si el helper hubiera llegado a abrir `/System/Library/xpc/launchd.plist`, la primera línea ya debería estar.
4. **El root del teléfono no es el `.simg` de referencia.** El root se modificó en caliente en los boots `rw` y, sobre todo, la deploy de Wi-Fi del 2026-11-02 escribió `/System/Library/xpc/launchd.plist` (job `org.ios-sweet.wland`, 531 jobs) y movió `preferences.plist` sin reflash (`NOTES.md:174-183`). Cualquier comparación con `gpu2.simg` mide “cuánto se desvió el teléfono”, no “si el root es factory”.
5. **El estado actual de `userdata` es desconocido.** El flash de `gpu2` del 2026-11-01 está documentado como hecho (`HANDOFF.md:18`), pero el intento de reflash que el usuario describe como interrumpido no tiene transcript, no tiene log y no tiene código de salida. No se puede afirmar ni que terminó ni que quedó a medias. La ring es contenido de *un* boot; no es un inventario del disco actual.
6. **No hay evidencia de corrupción estructural de HFS+.** El volumen montó (`hfs: mounted iOSRoot on device b(1, 0)`), el journal se replayó hasta `6875648` y terminó (`journal replay done`), y no hay `hfs_mark_inconsistent`, `hfs_swap_BTNode` ni errores de I/O en el ring (`logs/xnu-super-panic.txt:227-229`). Eso **no** descarta corrupción de datos dentro de archivos: el metadata puede estar sano y el contenido de un archivo concreto puede ser viejo, nuevo o mezcla de ambos.
7. **La hipótesis más económica no es “kernel nuevo roto”, sino “root/userdata inconsistente o plist/helper desviados”.** El boot usó argumentos de la familia 0101/0102 + Wi-Fi (`serial=0`, `sweetfb_hz=60`, `sweetgpu=2`, `sweetpmem=1`, `sweetsmmuprobe=1`, `sweetsmmuwlan=1`, `sweetwifi=1`), sin `sweetusb`/`sweetfiles` (`:328`). 0101s0 había booteado y funcionado el 2026-11-02 (`NOTES.md:166-167`). No hay commit ni CI nuevo para el 2026-11-03 (`git log`: último `e1ce648`, 2026-11-02 19:38).
8. **El siguiente paso seguro es host-side + lectura read-only, no un boot ni un reflash a ciegas.** Primero: verificar el `.simg`, mapear los chunks que contienen `launchd.plist`, el helper y la ring; después: leer del teléfono, por recovery y sin escribir, esos mismos rangos y comparar SHA256. Solo si no coinciden se justifica un reflash completo.

**Resumen en una frase:** el kernel y la GPU estaban vivos; `launchd` murió justo cuando iba a recibir el cache de arranque; el sospechoso principal es el estado del root/userdata (flash parcial o mutación in-place), no el driver gráfico ni una regresión de 0101/0102.

---

## 2. Cronología y separación de dos estados

### 2.1. Cronología mínima verificable

| Fecha/hora | Evento | Evidencia | Estado |
|---|---|---|---|
| 2026-10-15 … 10-17 | Construcción del root iOS 16, flashes v1–v12, primeros `launchd`, AMFI, keybag, HFS journal. | `NOTES.md:447-528` | `OBS` |
| 2026-11-01 23:26 | mtime de `ipsw/ios16-root-gpu2.simg` (12.159.682.532 bytes). | `Get-ChildItem ipsw` | `OBS` |
| 2026-11-01 | “Phone userdata holds root `ipsw/ios16-root-gpu2.simg` (flashed 2026-11-01)”. | `HANDOFF.md:18` | `OBS` (documentado; sin transcript) |
| 2026-11-02 | Boots 0102 (`sweetfix=1`) y 0101s0; Wi-Fi WCN3990; deploy por `sweet_files`; 0104/0105 a CI. | `NOTES.md:102-215`, `HANDOFF.md:93-133` | `OBS` |
| 2026-11-02 18:29–19:38 | CI 0105 sin runner macOS; runs 41501352880 y 41502238106 en cola; último commit `e1ce648`. | `git log`, `NOTES.md:216-222` | `OBS` |
| 2026-11-03 18:24 | mtime del directorio `xnu/` (posible build/artefacto local, no confirmado). | `Get-ChildItem` | `OBS` |
| 2026-11-03 18:28:37 | Se escribe `logs/xnu-super-panic.txt` (50.094 bytes). | mtime | `OBS` |
| 2026-11-03 18:32:21 | Se escribe `logs/xnu-0101s0reboot.txt` (50.094 bytes), byte-idéntico al anterior. | SHA256 | `OBS` |
| 2026-11-03 (hora desconocida) | Intento de reflash de `gpu2` “interrumpido”, sin log ni estado final. | reporte del usuario | `DESC` |
| 2026-11-03 (orden desconocido) | ¿El reflash fue antes o después de la ring? No hay evidencia. | — | `DESC` |

### 2.2. Los dos estados que hay que no confundir

**Estado A — el boot que escribió la ring.** Es el estado del root *en el momento* en que `launchd` arrancó, ejecutó nueve boot tasks y murió en la décima. La ring prueba que en ese momento: HFS montó, el journal se replayó, `/sbin/launchd` se cargó, se creó el bootstrap port, se ejecutaron `mount`, `seputil`, `dirs_cleaner`, `xpcroleaccountd`, `init_featureflags`, `auearlyboot`, `tzinit`, `FinishRestoreFromBackup`, `finish_demo_restore`, `sysstatuscheck`, `prng_seedctl` y se hizo `exec launchd_cache_loader`. También prueba que el kernel siguió vivo al menos ~3 s después.

**Estado B — el contenido actual de `userdata`.** Es lo que hay hoy en la partición, después de cualquier escritura posterior: boots `rw`, journal replay, keybag, preferencias, deploy de Wi-Fi, y el intento de reflash. **La ring no describe el Estado B.** La ring se escribe en los últimos 1.025 bloques de 4 KiB de `userdata` (bloque `0x1d7d3fa`, 4.100 KiB; `logs/xnu-super-panic.txt:153`). Un flash completo de `gpu2` reescribe también esa zona; un flash interrumpido antes del chunk 24 la deja intacta. Por eso:

- Si la ring se pudo leer coherente **después** del reflash, el reflash no llegó al final de la partición (o se leyó antes). Eso acota el progreso del flash a “< últimos 4,1 MiB”, pero no dice nada de los chunks intermedios.
- Si el reflash ocurrió **después** de la ring, la ring es pre-flash y describe el root que falló, no el que hay ahora.
- Si el reflash ocurrió **antes** de la ring, la ring describe un root parcialmente reescrito; el fallo podría ser consecuencia directa del flash.

No hay forma de decidir el orden con los artefactos actuales. Es la primera pregunta que hay que resolver (§10).

### 2.3. Por qué la ring no contiene el panic

La ring es un buffer circular de 4 MiB en `userdata`; el hilo de `sweet_ufs.c` vuelca los bloques nuevos y el header cada ~1 s y hace `SYNCHRONIZE CACHE` (`NOTES.md:410`). Un panic que ocurre **después** del último flush no entra en la ring: queda en pantalla, en el framebuffer o en el buffer del kernel que ya no se vuelca. La ring termina con tres `SWEET FPS` consecutivos, es decir, ~3 s después de `exec launchd_cache_loader`; el panic es posterior a esos tres tics y anterior al siguiente flush. No hay `panic`, `initproc`, `debugger` ni `Waiting for remote debugger` en las 610 líneas. La frase del usuario es, por tanto, la **única** evidencia textual del panic, y no está verificada contra el artefacto.

---

## 3. Mecánica del sparse v1.0 y del `-S 512M`

### 3.1. Header verificado de `gpu2.simg`

Leído en `ipsw/ios16-root-gpu2.simg` (copia del workspace, no la carpeta de Claude):

```
magic       0xed26ff3a   (Android sparse)
version     1.0
file_hdr_sz 28
chunk_hdr_sz 12
blk_sz      4096
total_blks  4194304      -> 17.179.869.184 bytes = 16 GiB exactos
total_chunks 27934
checksum    0x00000000   (no calculado por img2simg)
file_bytes  12.159.682.532
```

`gpu1.simg` tiene el mismo header (misma versión, mismo `blk_sz`, mismo `total_blks`, mismos 27.934 chunks, checksum 0) y el mismo tamaño de archivo; cambia el contenido (gpu2 es el root con blit GPU/eagl). El header no prueba integridad: el checksum del formato está a cero y nadie ha comparado el contenido completo contra el teléfono.

### 3.2. Tipos de chunk y qué significa “flash completo”

El formato Android sparse usa chunks de 12 bytes de header:

| Tipo | Valor | Contenido | Efecto en el flash |
|---|---|---|---|
| `RAW` | `0xCAC1` | `chunk_sz` bloques de datos literales | Se envían y escriben. |
| `FILL` | `0xCAC2` | 4 bytes de relleno repetidos | El bootloader escribe el patrón; `img2simg` lo usa para regiones cero. |
| `DONTCARE` | `0xCAC3` | sin datos | El bootloader puede **no escribir**; queda lo que hubiera. |
| `CRC32` | `0xCAC4` | 4 bytes de checksum | Metadato; no escribe datos. |

`img2simg` convierte un raw HFS+ de 16 GiB en 27.934 chunks y 12,16 GB de archivo. Los bloques cero se convierten en `FILL` o `DONTCARE`; el resto en `RAW`. En un flash **completo**, el bootloader recorre todos los chunks en orden y escribe los `RAW`/`FILL`; los `DONTCARE` pueden quedar sin tocar. En un flash **interrumpido**, el bootloader se detiene en un chunk arbitrario: los anteriores están escritos, los posteriores no, y el chunk de corte puede estar a medias.

### 3.3. Por qué `-S 512M` produce 24 descargas

`fastboot -S 512M` limita cada transferencia a 512 MiB. Los logs completos de `gpu1` y del root base muestran exactamente 24 descargas:

```
Sending sparse 'userdata' 1/24 (518156 KB)  OKAY [ 13.815s]
Writing 'userdata'                          OKAY [  0.000s]
...
Sending sparse 'userdata' 24/24 (230990 KB) OKAY [  6.347s]
Writing 'userdata'                          OKAY [  0.000s]
Finished. Total time: 334.501s
exit 0
```

(`flash-userdata-gpu1.log:1-51`; `flash-userdata.log:1-51` es el flash base, 24/24, 333,057 s, chunk 1 de 518.160 KB y chunk 24 de 216.872 KB.)

Cada `Sending ... OKAY` es una transferencia USB; cada `Writing ... OKAY` es la escritura en UFS. **No hay checkpoint persistente, no hay reanudación y no hay verificación de contenido.** Si el cable, el host o el ABL fallan en la descarga 15, el estado es: chunks 1–14 escritos, chunk 15 parcial o no escrito, chunks 16–24 sin escribir. `fastboot` no deja un marcador en la partición que diga “hasta aquí llegué”.

### 3.4. Dónde caen los archivos críticos

El root es HFS+ con journal. El volumen tiene 4.194.304 bloques de 4 KiB (16 GiB), pero el `.simg` solo transporta 12,16 GB porque el resto son ceros/rellenos. Los archivos críticos no están todos al principio:

- **Volumen header / metadata / catálogo / journal:** bloques bajos y zona de journal (~6,4–6,9 MiB de journal según el replay: `from 6396416 to 6724096`, extra hasta `6875648`; `logs/xnu-super-panic.txt:225-227`). Si el flash se corta antes de esta zona, HFS no monta; si se corta después, el metadata puede quedar coherente.
- **`/sbin/launchd`:** binario de sistema, en la zona de sistema; probablemente en los primeros GB.
- **`/usr/libexec/launchd_cache_loader`:** helper pequeño; su ubicación exacta no está mapeada en los artefactos. Puede caer en cualquier chunk según el layout del HFS.
- **`/System/Library/xpc/launchd.plist`:** ~1,4 MB; en las versiones v5–v8 se documentó contiguo en el offset de imagen `0x1e025f000` (~7,5 GiB), 195 bloques (`NOTES.md:409`, `:447`). Está en la **mitad tardía** del stream, sobre el chunk 15–16 de 24. Es un punto de corte plausible.
- **`dyld_shared_cache_arm64.*` (44 subcaches):** varios GB; cruzan muchos chunks. El ring muestra 42 mapas “not in trust cache” (`:281-323`) más la línea de servicio `SWEET: trust caches unavailable` (`:58`), es decir, el cache se mapeó; no prueba que todas las páginas estén íntegras.

Consecuencia: un corte en el chunk 15 puede dejar el volumen header, el catálogo y `launchd` nuevos, pero el plist y/o el helper viejos o mezclados. HFS monta, `launchd` arranca, las boot tasks tempranas pasan, y el fallo aparece exactamente en la primera tarea que lee el plist: `launchd_cache_loader`. Es el patrón que se observa.

### 3.5. Lo que no se puede afirmar del flash

- **No hay transcript del flash de `gpu2` ni del reflash interrumpido.** Los únicos logs completos son `flash-userdata.log` (base, 31/10) y `flash-userdata-gpu1.log` (gpu1, 01/11). No hay un `flash-userdata-gpu2.log` ni un log del intento del 03/11.
- **No hay código de salida, ni “24/24”, ni “Finished”, ni `fastboot getvar` posterior.** El `getvar` está además prohibido en la práctica porque el ABL se cuelga tras flashes grandes (`NOTES.md:487`, `HANDOFF.md:24`).
- **No hay SHA256 del `.simg` en el repo ni del contenido del teléfono.** El checksum sparse es 0. La comparación `.simg` vs teléfono nunca se hizo.

---

## 4. Procedimiento de flash/recovery y manejo del ABL

Esta sección documenta el procedimiento **histórico** para que otro agente no lo improvise. No se ejecutó nada en esta sesión.

### 4.1. Flash de `userdata` (destructivo, requiere confirmación explícita)

```text
fastboot -S 512M flash userdata ipsw/ios16-root-gpu2.simg
```

- El `.simg` debe ser el sparse, no el raw: un flash raw de 16 GiB fue matado por `earlyoom` a 2,6 GB de RSS (`NOTES.md:487`); el sparse es el único camino viable.
- `-S 512M` es obligatorio por el límite de descarga del ABL (768 MiB; `max-download-size: 805306368`, `NOTES.md:496`).
- El flash tarda ~333–335 s con 24/24 `OKAY` en los logs completos. Un tiempo mucho menor, un `FAILED`, un `Sending` eterno o un corte de USB significan flash incompleto.
- **No reutilizar el mismo `.simg` como “verificación”**: un segundo flash completo es la única forma de garantizar que todos los chunks se reescribieron; un flash parcial no se reanuda.

### 4.2. ABL colgado después del flash

El patrón documentado: tras un flash grande, el ABL queda en `Sending...` o `reboot bootloader` expira; el usuario reentra a fastboot con **Power + Vol−** (`NOTES.md:454`, `:487`; `HANDOFF.md:24`). Reglas:

- **Nunca** emitir otro comando contra un ABL colgado. Esperar, desconectar, Power+Vol−, y verificar que el dispositivo vuelve a fastboot.
- **Nunca** `fastboot getvar` después de un flash grande: es el comando que más veces colgó el ABL.
- **Nunca** asumir que el flash terminó porque el host volvió al prompt; el ABL puede haber cortado la última transferencia.

### 4.3. Recovery y extracción de la ring

`tools/sweet-pull-ring.ps1` (leído completo):

```text
fastboot boot recovery/recovery.img          # OrangeFox temporal, no flasheado
adb get-state                                 # espera recovery/device/sideload
adb shell readlink -f /dev/block/by-name/userdata
adb shell blockdev --getsize64 <dev>
adb exec-out dd if=<dev> bs=4096 skip=<blocks-1025> count=1025 > area.bin
adb exec-out dd if=<dev> bs=4096 skip=<skip-32> count=32 > shim.bin
adb reboot bootloader
python3 tools/sweet-log.py area.bin out.txt
```

- `tail = 1025` bloques de 4 KiB = 4.100 KiB; `skip = blocks - 1025`. La ring vive en los últimos 1.025 bloques de `userdata`.
- El shim log se lee 32 bloques antes (`skip - 32`), con magic `0x52505753` (`SWRP`) y longitud en el offset 12; se guarda como `out.shim.txt`.
- `tools/sweet-log.py` lee el header `SWEETLOG` (`<8sIIQQ`: magic, version, ring size, total, seq), toma `data[4096:4096+size]`, y si `total > size` rota; luego `decode('utf-8','replace').replace('\r','')`. Por eso el `.txt` de 50.094 bytes corresponde a 50.328 bytes de ring menos 234 `\r`.
- **Recovery no tiene hfsplus** (`NOTES.md:409`): no se puede montar el root desde OrangeFox; solo `dd` de bloques raw. `fsck.hfsplus` y `mount -t hfsplus` se hacen en el host sobre una copia.
- **No tocar “Format Data”, “Factory reset” ni “Wipe”**: destruyen el root y la ring.

### 4.4. Imagen de recovery

`recovery/recovery.img`: 134.217.728 bytes, SHA256 `91B1B7BC78D5B7499AFF608F6A98F9E9A7F44021595648216ABDABCF3DD25666`, OrangeFox R12.0_2. Es un boot temporal (`fastboot boot`), no se flashea. El kernel de recovery no tiene hfsplus; solo sirve para `dd` y para el shell.

### 4.5. El “reboot 0101s0” que no booteó

`logs/xnu-0101s0reboot.txt` se escribió 3 min 44 s después del panic y es **byte-idéntico** (`SHA256 576CDB1A...`, 50.094 bytes). Eso significa una de cuatro cosas:

1. El boot nunca se envió (el usuario solo renombró/copió el archivo).
2. El boot se envió pero el ABL estaba colgado y no cargó nada.
3. El kernel cargó pero no llegó a inicializar `sweet_ufs` en modo escritura (la ring se escribe después de `SWEET LOG: console log to the last 4100 KiB`, `:153`), así que no actualizó la zona.
4. El kernel cargó una imagen sin el parche 0047 (ring persistente) o con `ufsrw=0`, y no escribió.

En cualquiera de los cuatro casos, **no es evidencia de que el panic sea reproducible ni de que el root esté sano**. El `.shim.txt` asociado es aún menos útil: 6.040 bytes, SHA256 `3703A528...`, idéntico al de `xnu-wifi-boot.txt`; su contenido termina en `GPU probe done, back to fastboot in 10 s` y dice `LOADER no SWEETXNU payload`, `PLOG ufs=00000000`. Es un log de un probe de GPU viejo, no del boot del panic. El script lo copia del área de scratch del shim, que no se reescribió.

---

## 5. Mecánica del panic

### 5.1. El código de XNU que produce el mensaje

En `xnu-8796.141.3`, `bsd/kern/kern_exit.c`, `proc_prepareexit()` llama a `proc_handle_critical_exit()` para `initproc` o para procesos con `POSIX_SPAWN_PANIC_ON_EXIT`:

```c
if (p->p_crash_behavior != 0 || p == initproc) {
    proc_handle_critical_exit(p, rv);
}
```

`proc_handle_critical_exit()` hace, para `initproc`:

```c
char *exit_reason_desc = exit_reason_get_string_desc(p->p_exit_reason);
...
printf("pid %d exited -- exit reason namespace %d subcode 0x%llx, description %s\n", ...);
...
proc_crash_coredump(p);
sync(p, (void *)NULL, (int *)NULL);
...
panic_with_options(0, NULL, DEBUGGER_OPTION_INITPROC_PANIC,
    "%s %s -- exit reason namespace %d subcode 0x%llx description: %." LAUNCHD_PANIC_REASON_STRING_MAXLEN "s",
    ((proc_getcsflags(p) & CS_KILLED) ? "CS_KILLED" : ""),
    prefix_str, p->p_exit_reason->osr_namespace, p->p_exit_reason->osr_code,
    exit_reason_desc ? exit_reason_desc : "none");
```

(`proc_should_trigger_panic()` devuelve verdadero si `p == initproc` o si el proceso tiene `POSIX_SPAWN_PANIC_ON_EXIT`; `prefix_str` es `"initproc exited"` si `initproc_spawned` ya está puesto, o `"initproc failed to start"` si no.)

Consecuencias:

- **El panic no es un assert del kernel ni un watchdog de hardware.** Es una decisión de política: “si PID 1 sale, panic”.
- **El namespace y el subcode vienen del `exit_reason` de `launchd`.** `bsd/sys/reason.h` define `OS_REASON_SIGNAL = 2`; para ese namespace, `osr_code` es el número de señal (`os_reason_create(OS_REASON_SIGNAL, signum)`). Por tanto `subcode 0x8` = señal 8 = `SIGFPE` en Darwin, **si el texto es literal**.
- El prefijo puede llevar `CS_KILLED` si el proceso fue matado por code signing; el texto reportado no lo incluye.

### 5.2. Precedentes que calibran la lectura

| Caso | Texto observado | Namespace/subcode | Lectura |
|---|---|---|---|
| Boot 0027 (2026-10-15) | `pid 1 exited -- exit reason namespace 2 subcode 0xa` | 2 / `0xa` | `SIGBUS`; el `sp` no estaba alineado al entrar al binario estático (`NOTES.md:502`). |
| Boot 0041u (2026-10-16) | `watchdogd[113] exited ... namespace 2 subcode 5` | 2 / `5` | `SIGTRAP`; `_os_crash` deliberado de watchdogd (`NOTES.md:452`). |
| Boot 0038e (2026-10-16) | `launchd_cache_loader[22] exited ... namespace 7 subcode 0x1` | 7 / `1` | `OS_REASON_LIBXPC`, código 1; `abort: Unable to find AMFI` (`NOTES.md:454`). |
| Boot 0029u (2026-10-15) | `namespace 9 code 0xe` | 9 / `14` | `OS_REASON_EXEC` / `EXEC_EXIT_REASON_WRONG_PLATFORM` (`NOTES.md:487`). |
| **Panic actual (reportado)** | `initproc exited -- exit reason namespace 2 subcode 0x8 -- code 0x1` | 2 / `0x8` | `SIGFPE` si es literal; `-- code 0x1` no pertenece al formato de XNU. |

La tabla confirma que el proyecto ya ha visto namespace 2 con subcode = señal (0xa = SIGBUS, 0x5 = SIGTRAP). También confirma que el texto exacto importa: el caso AMFI nombra al **helper** (`launchd_cache_loader[22]`), no a `initproc`. En el caso actual, el prefijo reportado es `initproc exited`, que es `launchd` (PID 1).

### 5.3. La anomalía `SIGFPE`

`SIGFPE` (8) es una señal rara en arm64:

- No hay trap de división entera por cero en arm64: `udiv`/`sdiv` por cero devuelve 0, no genera excepción.
- Las excepciones de coma flotante están deshabilitadas por defecto (`FPCR` con traps off); un `fdiv` por cero da infinito/NaN, no SIGFPE.
- `abort()` produce `SIGABRT` (6); `__assert_rtn`/`os_crash` producen `SIGABRT`/`SIGTRAP` (6/5); `__builtin_trap` en arm64 emite `brk #1` y produce `SIGTRAP` (5).
- Un `SIGFPE` “espontáneo” en `launchd` requeriría una instrucción o un `raise(SIGFPE)` explícito, o una transcripción incorrecta.

Por eso hay dos lecturas del texto:

**R1 — literal.** `launchd` (PID 1) recibió `SIGFPE` y el kernel paniqueó por política. El origen sería una ruta de código de `launchd`/libxpc que ejecuta una operación arithmetic trap o un `raise`, o una corrupción de instrucciones que acaba en una excepción aritmética. No hay mecanismo obvio en los artefactos.

**R2 — compuesta/misread.** El usuario combinó dos líneas: el fallo de la boot task (código de salida 1, o señal 8) y el panic de `initproc`. El `-- code 0x1` no existe en el formato de `panic_with_options` de XNU 8796 (`... description: %s`), lo que apoya que la cadena no es literal. En este caso, el helper pudo salir con señal 8, y `launchd` pudo paniquear por la política de boot task, pero el panic imprimiría `launchd_cache_loader[pid] exited`, no `initproc exited`.

**R3 — el texto es de otro boot.** La ring no lo contiene; la frase pudo leerse en pantalla de un boot anterior o de una imagen distinta. No hay forma de correlacionar la frase con las 610 líneas.

La nota no elige R1/R2/R3 como hecho. Lo que sí se puede afirmar: **el ring termina antes del panic, no hay `CRASH launchd_cache_loader` (parche 0043) en la ring, y el kernel seguía vivo 3 s después del `exec`**. Si el helper hubiera muerto por señal, el parche 0043 debería haber impreso `CRASH launchd_cache_loader[...]` antes del panic (para un proceso no-init); no está. Eso favorece que el que murió fue `launchd` (R1) o que el helper nunca llegó a ejecutarse.

### 5.4. Lo que el kernel no hizo

- No hubo `panic: ...` de HFS, APFS, SMMU, GPU, AKS, watchdog ni lock.
- No hubo `hfs_mark_inconsistent` ni `hfs_swap_BTNode` (el precedente de corrupción HFS de 0041u sí los tenía; `NOTES.md:452`).
- No hubo `SWEET WDT` ni `watchdogd` en el ring; `wdt_test=no_user_checkin` está en boot-args (`:328`).
- No hubo `CRASH` de ningún daemon.
- El GPU self-test se completó y el hilo de FPS siguió; el fallo es posterior a la inicialización gráfica.

---

## 6. `launchd_cache_loader` y las nueve líneas ausentes

### 6.1. Qué hace el helper

Es una boot task de `launchd` (no un daemon permanente). Su trabajo, inferido de los logs y de `NOTES.md:454`:

1. Encontrar el bootstrap port de `launchd` (en los logs, `7939`; en otros boots, `2563`).
2. Leer `/System/Library/xpc/launchd.plist` y su `.sig` (o usar el cache “unsecure” si `launchd_unsecure_cache=1`).
3. Validar la firma contra AMFI (`AppleMobileFileIntegrity`, selector 6) o saltarla.
4. Serializar el plist y enviarlo al puerto de `launchd` (`Trying to send bytes to launchd: 7939 16384`, `Sending validated cache to launchd`, `Cache sent to launchd successfully`).
5. `launchd` recibe el cache, imprime su UUID y `Early boot complete. Continuing system boot.`; luego `exec xpcproxy` y `exec SpringBoard`.

En el caso AMFI de 0038e, el helper abortó con `Unable to find AMFI` y el panic fue `launchd_cache_loader[22] exited -- exit reason namespace 7 subcode 0x1` (`NOTES.md:454`). En el caso actual **no** hay `Unable to find AMFI`, y `launchd_unsecure_cache=1` está en boot-args; el punto de fallo es anterior o distinto.

### 6.2. La secuencia buena, literal

De `logs/xnu-0101s0-freeze.txt:519-530`:

```text
exec launchd_cache_loader
0 Found valid port: 7939 Valid: 1
1 Found valid port: 0 Valid: 0
2 Found valid port: 0 Valid: 0
Using default cache paths
Code: /System/Library/xpc/launchd.plist Sig: /System/Library/xpc/launchd.plist.sig
Using unsecure cache: /System/Library/xpc/launchd.plist
Trying to send bytes to launchd: 7939 16384
Sending validated cache to launchd
Cache sent to launchd successfully
com.apple.xpc.launchd|... <Notice>: launchd UUID: 5C15DB07-B3BC-3DF3-B62F-3E498B993B8E
com.apple.xpc.launchd|... (boot) <Notice>: Early boot complete. Continuing system boot.
exec xpcproxy
...
exec SpringBoard
```

Las nueve líneas del helper aparecen **inmediatamente** después del `exec`: la línea de launchd que anuncia la boot task tiene timestamp `16:01:45.361270`, y el helper no interpone una espera visible (sus `printf` no llevan timestamp propio). No hay una pausa de segundos entre `exec` y `0 Found valid port`.

### 6.3. La secuencia del panic, literal

De `logs/xnu-super-panic.txt:584-589`:

```text
com.apple.xpc.launchd|1969-12-31 16:00:45.086321 (launchd_cache_loader) <Notice>: Doing boot task
[System Event] [865661843] [INFO] [Subsystem: launchd] [Event: launchd_cache_loader] Doing boot task
exec launchd_cache_loader
SWEET FPS: 0 swaps in 1000 ms ... GPU 0 ms pending (fence 1) ...
SWEET FPS: 0 swaps in 1001 ms ... GPU 0 ms pending (fence 1) ...
SWEET FPS: 0 swaps in 1001 ms ... GPU 0 ms pending (fence 1) ...
```

No hay `0 Found valid port`, no hay `Using default cache paths`, no hay `Cache sent`, no hay UUID, no hay `Early boot complete`, no hay `exec xpcproxy`. El ring se corta ~3 s después.

### 6.4. Qué puede explicar la ausencia

| Explicación | Mecanismo | A favor | En contra |
|---|---|---|---|
| **E1. El helper no llega a `main`** | `exec` carga un Mach-O corrupto o le falta una dependencia (libSystem/dyld cache); dyld falla antes del primer `printf`. | El `exec` se imprimió (parche 0042) pero no hay ninguna línea; el helper es pequeño y puede estar en un chunk no escrito. | dyld normalmente imprime un error (“Library not loaded…”); no hay error en la ring. |
| **E2. El helper queda bloqueado en el port lookup** | `bootstrap_look_up` no responde; el helper espera; `launchd` muere por otra razón a los 3 s. | La primera línea es precisamente el resultado del lookup; si está bloqueado, no imprime. | El lookup era instantáneo en todos los boots buenos; un bloqueo de 3 s es anómalo pero posible si el bootstrap port está roto. |
| **E3. El stdout del job ya no va al console** | La deploy de Wi-Fi reescribió `launchd.plist`; el job `launchd_cache_loader` perdió `StandardOutPath`/`StandardErrorPath` o cambió su configuración. | El plist se modificó in-place (`NOTES.md:174-183`); el helper podría estar corriendo y enviando el cache sin que sus `printf` lleguen a la ring. | En los logs buenos las líneas del helper aparecen sin que se documente un `StandardOutPath` explícito para ese job; el console es el default de las boot tasks. |
| **E4. `launchd` muere antes de que el helper arranque** | `launchd` recibe una señal (SIGFPE) al despachar la boot task; el hijo ni se ejecuta o queda huérfano. | El panic reportado es `initproc exited`; no hay `CRASH` del helper. | No hay mecanismo claro de SIGFPE en `launchd`; el texto puede ser compuesto. |
| **E5. El plist está corrupto y el helper aborta** | El helper abre el plist, falla el parseo y sale con error. | El plist está en la zona tardía del flash y fue reescrito por Wi-Fi. | La primera línea (port) es anterior a la lectura del plist; si el orden de `printf` refleja el código, debería estar. Además el helper imprimiría un error de parseo, no silencio. |

**La explicación más consistente con el artefacto es E1/E4 combinadas:** el helper no imprime porque no llega a `main` (o `launchd` muere antes de que corra), y el panic es de `launchd`. E2/E3 son alternativas que solo se distinguen mirando el plist y el binario; E5 es la menos probable por el orden de impresión, salvo que el helper imprima la primera línea **después** de leer el plist (no verificable sin el fuente, que no es público desde iOS 8; `libxpc` es closed source).

### 6.5. El detalle que más discrimina

En los boots buenos, el helper tarda **0 ms** entre `exec` y `0 Found valid port`. En el panic, pasan **3 s** sin línea. Si el helper estuviera simplemente lento, el kernel seguiría vivo y la ring seguiría creciendo; el panic ocurre en esa ventana. Eso descarta un timeout largo de boot task (serían decenas de segundos) y favorece una muerte abrupta por señal o un fallo de `exec`/dyld. También descarta que el problema sea “el plist tarda en parsearse”: el parseo ocurre después de la primera línea.

---

## 7. Tabla observado / inferido / desconocido

| # | Hecho | Evidencia | Estado | Confianza |
|---|---|---|---|---|
| 1 | Ring de 50.094 bytes, 610 líneas, 0 CR, 610 LF. El decode de `sweet-log.py` reportó 50.328 bytes de ring y `flush #3` (no re-verificado en esta sesión: el `.bin` de la extracción no se conservó). | `logs/xnu-super-panic.txt`; `sweet-log.py:23`; reporte de extracción | `OBS` | Media-Alta |
| 2 | SHA256 de la ring: `576CDB1ACA91C3975CE4C2BCFCEA0360ABC2D43EAED55894462C050D2FFEB99F`. | `Get-FileHash` | `OBS` | Alta |
| 3 | `xnu-0101s0reboot.txt` es byte-idéntico a la ring del panic. | SHA256 | `OBS` | Alta |
| 4 | Los `.shim.txt` del panic, reboot y wifi-boot son idénticos (6.040 bytes, SHA `3703A528...`), con `GPU probe done, back to fastboot in 10 s`. | `Get-FileHash`, contenido | `OBS` | Alta |
| 5 | Boot-args: `debug=0xc serial=0 cpus=8 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=60 sweetgpu=2 sweetpmem=1 sweetsmmuprobe=1 sweetsmmuwlan=1 sweetwifi=1`. | `logs/xnu-super-panic.txt:328` | `OBS` | Alta |
| 6 | HFS montó `iOSRoot`, journal replay `from 6396416 to 6724096`, extra hasta `6875648`, `journal replay done`. | `:225-229` | `OBS` | Alta |
| 7 | `SWEET: root volume is not authenticated (error 25); continuing unsealed`. | `:229` | `OBS` | Alta |
| 8 | GPU self-test: `CP_MEM_WRITE ... 0x5ee7c0de`, IB corrió, fence 1. | `:403-407` | `OBS` | Alta |
| 9 | `MKB_INIT: mount is with NO CPROTECT:0x1480d000 on (/private/var/)`; `does not support Data Protection`; `Unable to set /private/var//tmp to class D`. | `:416-424` | `OBS` | Alta |
| 10 | `UMD_INIT: ... APFSNativeDevice`; `BOOTEDUSER is:501`; personas 99/199/100/1000/200. | `:427-527` | `OBS` | Alta |
| 11 | `dirs_cleaner`: `dc_reset: /tmp: Invalid argument`, `/var/run: Invalid argument`. | `:528-531` | `OBS` | Alta |
| 12 | `prng_seedctl`: `kern.prng.user_reseed_count: (-1) (2) No such file or directory`; `failed to load virtual random: (-147) (-536870212)`. | `:579-583` | `OBS` | Alta |
| 13 | Última línea de launchd: `exec launchd_cache_loader`; después, 3 `SWEET FPS` y fin. | `:584-589` | `OBS` | Alta |
| 14 | En el boot bueno, el helper imprime 9 líneas inmediatamente y luego `launchd UUID`/`Early boot complete`/`SpringBoard`. | `logs/xnu-0101s0-freeze.txt:519-530` | `OBS` | Alta |
| 15 | El panic no está en la ring; no hay `panic`, `initproc`, `CRASH` ni `debugger`. | búsqueda en 610 líneas | `OBS` | Alta |
| 16 | `gpu2.simg`: sparse v1.0, 4.096 B/bloque, 4.194.304 bloques, 27.934 chunks, checksum 0, 12.159.682.532 bytes, 16 GiB raw. | header leído | `OBS` | Alta |
| 17 | `gpu1.simg` tiene el mismo header y tamaño; el contenido difiere. | header leído | `OBS` | Alta |
| 18 | `recovery.img`: 134.217.728 bytes, SHA `91B1B7BC...`, OrangeFox R12.0_2. | hash/stat | `OBS` | Alta |
| 19 | `userdata` empieza en bloque `0x2b8c00`, 109.643 MiB; ring en bloque `0x1d7d3fa`, 4.100 KiB. | `logs/xnu-super-panic.txt:152-153` | `OBS` | Alta |
| 20 | `gpu2` fue flasheado el 2026-11-01 según HANDOFF; no hay log de ese flash. | `HANDOFF.md:18`; `ls logs` | `OBS`/`DESC` | Media |
| 21 | El reflash “interrumpido” no tiene transcript, exit code ni estado final. | reporte del usuario | `DESC` | Baja |
| 22 | El root del teléfono fue modificado in-place por la deploy de Wi-Fi (plist de 531 jobs, `preferences.plist` movido). | `NOTES.md:174-183` | `OBS` | Alta |
| 23 | El boot del panic usó argumentos de Wi-Fi (`sweetwifi=1`, etc.) pero no `sweetusb`/`sweetfiles`; no es el image super completo. | `:328` vs `HANDOFF.md:128-129` | `INF` | Media |
| 24 | El kernel del boot del panic no está identificado por hash/CI; los args encajan con 0101s0/0102 + Wi-Fi. | `:328`, `git log` | `DESC`/`INF` | Media |
| 25 | El texto `-- code 0x1` no pertenece al formato de XNU 8796; la cadena puede ser compuesta. | `kern_exit.c:1828-1831` | `INF` | Alta |
| 26 | `SIGFPE` es señal 8; namespace 2 = `OS_REASON_SIGNAL`; el subcode es la señal. | `reason.h`; precedentes 0xa/0x5 | `OBS` | Alta |
| 27 | No hay `CRASH launchd_cache_loader` en la ring; el parche 0043 lo imprimiría para un hijo que muere por señal. | `NOTES.md:447`; ring | `INF` | Media-Alta |
| 28 | El kernel estaba vivo ~3 s después del `exec`; el panic es posterior al último flush. | `:586-589`; `NOTES.md:410` | `OBS`/`INF` | Alta |
| 29 | No hay `.ips`, core ni foto del panic en el workspace. | `ls`, búsqueda | `OBS` | Alta |
| 30 | El root “limpio” solo puede definirse como el `.simg` de referencia, no como un root factory. | `HANDOFF.md:18`, `NOTES.md:237` | `INF` | Alta |

---

## 8. Hipótesis ordenadas

Las hipótesis no son mutuamente excluyentes: H1 (flash parcial) puede causar H2 (plist desviado) y H3 (helper corrupto). El orden es por probabilidad **antes** de mirar el teléfono, no por gravedad.

### H1. El `userdata` está en un estado mezcla por un flash sparse interrumpido (prior 0,35)

**Mecanismo:** el flash de `gpu2` (o un reflash posterior) se cortó en el chunk N. Los chunks 1..N-1 son nuevos; N puede estar a medias; N+1..24 son viejos (del root anterior en el teléfono). El volumen HFS+ sigue montando porque el header, el catálogo y el journal cayeron en chunks escritos, pero un archivo de la zona tardía (plist, helper, dyld subcache) quedó viejo o mezclado.

**A favor:**
- El fallo está exactamente en la primera boot task que lee un archivo grande de la zona tardía (`launchd.plist`, offset ~7,5 GiB; `NOTES.md:447`).
- El HFS monta y el journal replay termina: no es corrupción estructural, es corrupción de contenido.
- No hay `hfs_mark_inconsistent` ni errores de I/O.
- El flash sparse no es atómico ni reanudable (§3); un corte de USB/ABL es el modo de fallo documentado del proyecto (`NOTES.md:454`, `:487`).
- El root del teléfono ya estaba desviado por la deploy de Wi-Fi; un flash posterior puede haber mezclado versiones.

**En contra:**
- No hay transcript del flash; no se sabe si se cortó.
- El helper no imprime **nada**, ni siquiera la primera línea de port; un plist corrupto no explicaría la ausencia de esa línea (salvo que el orden de impresión sea distinto).
- HFS no reporta corrupción; un flash parcial en la zona del plist podría haber dejado un archivo con bytes viejos/nuevos pero HFS no lo detecta (no hay checksums por archivo).

**Test:** comparar los bloques del plist, del helper y de la ring contra `gpu2.simg` (§10). Si el plist o el helper no coinciden, H1 gana.

### H2. La deploy de Wi-Fi reescribió `launchd.plist` y dejó una configuración inválida para el cache loader (prior 0,25)

**Mecanismo:** el 2026-11-02 se instaló `org.ios-sweet.wland` y se movió `preferences.plist` sin reflash, editando `/System/Library/xpc/launchd.plist` (531 jobs). Un plist reescrito con `plistlib`/`patch-launchd-plist.py` puede cambiar el orden de las claves, el `StandardOutPath` del job, o el tamaño/extents del archivo. El helper lee el plist, pero si el job ya no tiene el stdout al console, sus `printf` no aparecen en la ring; si el plist tiene un job malformado, el cache loader puede fallar al serializarlo.

**A favor:**
- El plist es el archivo que el helper consume y el que se modificó in-place.
- La deploy fue el último cambio conocido del root antes del panic.
- El fallo es exactamente en `launchd_cache_loader`.
- Si el stdout del job cambió, la ausencia de las 9 líneas no prueba que el helper no corrió (E3).

**En contra:**
- En los boots buenos, el helper imprime sin que se documente un `StandardOutPath` explícito; el console es el default de las boot tasks.
- Un plist malformado normalmente produce un error de parseo, no un SIGFPE de `launchd`.
- El boot del panic pudo ser anterior a la deploy (no hay orden temporal exacto).

**Test:** extraer el plist del teléfono y del `gpu2`; `plutil -lint`/`plistlib`; comparar el job `launchd_cache_loader`, el número de jobs, el `StandardOutPath` y el SHA256. Ver §10.

### H3. El binario del helper o el dyld shared cache están corruptos/incompletos (prior 0,15)

**Mecanismo:** `launchd_cache_loader` vive en `/usr/libexec` y depende de libSystem/dyld cache. Si su Mach-O está truncado, o si una página del subcache que necesita está en un chunk no escrito, dyld falla antes de `main`; el `exec` se imprime pero no hay ninguna línea del helper. `launchd` podría morir por la boot task fallida.

**A favor:**
- Explica el silencio total del helper mejor que un plist corrupto.
- El helper es pequeño y puede caer en un chunk tardío.
- El ring muestra 43 mapas “not in trust cache”; el cache se mapea, pero no se verifica cada página.

**En contra:**
- dyld normalmente imprime “Library not loaded” o un error de código de firma; no hay error en la ring.
- Si el helper muere por señal, el parche 0043 debería imprimir `CRASH launchd_cache_loader`; no está.
- El `exec` del kernel no garantiza que el binario se haya cargado, pero un fallo de dyld suele dejar rastro.

**Test:** hash del helper y de los subcaches en el teléfono vs `gpu2`; `otool -l`/`codesign` en el host; comparar el `LC_UUID` con el que aparece en los logs, si aparece.

### H4. Regresión del kernel/boot image (0105 super, 0102 sweetfix, o una mezcla local) (prior 0,10)

**Mecanismo:** el boot usó un kernel nuevo (0104/0105 con Wi-Fi) o una imagen local no commiteada; un cambio en el scheduler, en el bootstrap port, en `posix_spawn` o en la política de boot tasks hace que `launchd` muera al despachar el cache loader.

**A favor:**
- Los boot-args incluyen `sweetpmem=1 sweetsmmuprobe=1 sweetsmmuwlan=1 sweetwifi=1`, que son de la familia super (0104/0105), no de 0101s0 puro.
- 0105 nunca tuvo CI completado (runner outage; `NOTES.md:216-222`); si se construyó localmente, es un binario no validado.
- El `xnu/` mtime del 2026-11-03 18:24 sugiere actividad local.

**En contra:**
- Los args **no** incluyen `sweetusb=2`/`sweetfiles=1`, que son parte del image super completo (`HANDOFF.md:128-129`); pueden ser args inertes añadidos a 0101s0.
- No hay commit nuevo después de `e1ce648` (2026-11-02 19:38); el kernel del 03/11 no está en git.
- 0101s0 había booteado y funcionado el 02/11; el fallo es en userspace, no en un assert del kernel.
- El GPU y el kernel siguen vivos; no hay un `panic` de kernel distinto del de initproc.

**Test:** identificar el binario exacto del boot (hash del kernel en el image, `load_init_program`/`Darwin Kernel Version`, CI run). Si es 0101s0, H4 baja mucho; si es un 0105 local, H4 sube.

### H5. El texto del panic es compuesto o de otro boot; el fallo real es una boot task que sale con código 1 (prior 0,10)

**Mecanismo:** el helper o `launchd` imprime una línea de error con `-- code 0x1` (código de salida de la boot task) y el kernel paniquea por `initproc` con otra línea; el usuario las combinó. El `SIGFPE` no es real.

**A favor:**
- El formato reportado no coincide con `kern_exit.c:1828-1831` (`description:`, no `-- code`).
- La ring no contiene el texto; la transcripción es la única fuente.
- El caso AMFI ya mostró un panic que nombra al helper, no a `initproc`; es fácil confundir las dos líneas.

**En contra:**
- El usuario reportó explícitamente `initproc exited` y `pid 1`; no es una paráfrasis obvia.
- Aun si el texto es compuesto, el hecho físico (ring cortada en cache loader, 3 s de kernel vivo) sigue necesitando explicación.

**Test:** obtener la foto/video de la pantalla del panic; leer el `panic` string completo. Es la evidencia más barata y la que más discrimina.

### H6. Otra causa (hardware, potencia, térmica, corrupción de RAM) (prior 0,05)

**Mecanismo:** un evento de hardware (reset parcial, caída de tensión, error de RAM) corrompe el estado de `launchd` y produce una señal rara.

**A favor:**
- `SIGFPE` es raro; un event de hardware podría explicarlo.
- El proyecto ya vio resets externos (watchdog Qualcomm/TZ; `NOTES.md:480`).

**En contra:**
- No hay líneas térmicas, de PMIC, de watchdog ni de reset en la ring.
- El GPU y el kernel siguen funcionando; un evento de hardware tan selectivo es improbable.
- El patrón es reproducible en el mismo punto (cache loader), lo que apunta a software/datos, no a hardware aleatorio.

**Test:** repetir el boot con el mismo root y ver si el fallo es determinista; revisar `dmesg`/PMIC si hay un kernel de diagnóstico.

### 8.1. Prior combinado y regla de decisión

| Hipótesis | Prior | Se confirma si… | Se refuta si… |
|---|---|---|---|
| H1 flash parcial | 0,35 | bloques del plist/helper/ring no coinciden con `gpu2` | todos los bloques comparados coinciden |
| H2 plist Wi-Fi | 0,25 | plist inválido, job cambiado o SHA distinto | plist válido e idéntico al de un boot bueno |
| H3 helper/dyld | 0,15 | helper/subcache truncado o SHA distinto | helper y subcaches coinciden y dyld no reporta error |
| H4 kernel nuevo | 0,10 | el image no es 0101s0/0102 y el fallo se reproduce con él | el image es 0101s0 y el fallo persiste con el mismo binario |
| H5 texto compuesto | 0,10 | la foto muestra otra cosa | la foto confirma `initproc ... SIGFPE` |
| H6 hardware | 0,05 | fallo aleatorio, líneas de PMIC/reset | fallo determinista en el mismo punto |

La regla es: **primero distinguir H1 de H4/H5 con Comparación de bloques + foto del panic**; después, si el root coincide, atacar H2/H3 con hashes del plist/helper.

---

## 9. Inventario, intentos fallidos y límites de lo afirmable

### 9.1. Inventario de artefactos

| Artefacto | Tamaño / SHA256 | Uso | Estado |
|---|---|---|---|
| `logs/xnu-super-panic.txt` | 50.094 B; `576CDB1A...B99F` | Ring primaria del boot del panic. | `OBS` |
| `logs/xnu-super-panic.txt.shim.txt` | 6.040 B; `3703A528...7CFD` | Shim scratch; contenido de GPU probe viejo. | `OBS` (stale) |
| `logs/xnu-0101s0reboot.txt` | 50.094 B; mismo SHA | Duplicado byte-idéntico; reboot no-op. | `OBS` |
| `logs/xnu-0101s0reboot.txt.shim.txt` | 6.040 B; mismo SHA | Stale. | `OBS` |
| `logs/xnu-0101s0-freeze.txt` | 352.741 B | Secuencia buena del cache loader. | `OBS` |
| `logs/xnu-0102-freeze.txt` | 348.752 B | Otra secuencia buena. | `OBS` |
| `logs/xnu-0103p.txt` | 557.479 B | `ca_vbl=1`, peor FPS; no usar. | `OBS` |
| `logs/xnu-wifi-boot.txt` | 575.997 B | Boot Wi-Fi; shim idéntico al stale. | `OBS` |
| `ipsw/ios16-root-gpu2.simg` | 12.159.682.532 B; sparse v1.0; 27.934 chunks | Root de referencia del 2026-11-01. | `OBS` (header) |
| `ipsw/ios16-root-gpu1.simg` | 12.159.682.532 B; mismo header | Root previo. | `OBS` (header) |
| `ipsw/ios16-root.simg` | 12.145.242.424 B | Root base. | `OBS` |
| `ipsw/dmg/087-86698-044.dmg` | 4.730.814.044 B | OS dmg. | `OBS` |
| `ipsw/dmg/087-86593-047.dmg` | 2.743.074.816 B | SystemOS dmg. | `OBS` |
| `ipsw/dmg/087-86715-047.dmg` | 10.485.760 B | AppOS dmg. | `OBS` |
| `recovery/recovery.img` | 134.217.728 B; `91B1B7BC...25666` | OrangeFox temporal. | `OBS` |
| `flash-userdata.log` | 3.374 B; 24/24; 333,057 s | Flash base. | `OBS` |
| `flash-userdata-gpu1.log` | 3.374 B; 24/24; 334,501 s | Flash gpu1. | `OBS` |
| `tools/sweet-pull-ring.ps1` | 2.773 B | Procedimiento de extracción. | `OBS` |
| `tools/sweet-log.py` | 1.090 B | Decode de la ring. | `OBS` |
| `tools/sparsediff.py` | 2.459 B | Comparación sparse. | `OBS` |
| `xnu/patches/0101..0105` | — | Estado del kernel. | `OBS` |
| `HANDOFF.md` | 12.426 B | Estado del 2026-11-02. | `OBS` |
| `NOTES.md` | 210.905 B | Historia y recetas. | `OBS` |

**SHA256 de `gpu2.simg`:** `FB86997E0D15DE3BA198834955C0FC64ACA95037C9E64CDFDB1FB69268393579`, calculado en esta sesión sobre la copia del workspace (`ipsw/ios16-root-gpu2.simg`, 12.159.682.532 bytes). No se calculó el SHA del contenido del teléfono; por tanto este hash identifica el ejemplar host, no el Estado B.

### 9.2. Intentos fallidos y callejones sin salida

1. **`xnu-0101s0reboot.txt` no es un boot nuevo.** Es el mismo archivo (mismo SHA) que el panic; no prueba reproducibilidad. El nombre sugiere un intento de reboot, pero el contenido no cambió.
2. **El `.shim.txt` no es del boot del panic.** Es el mismo que el de `xnu-wifi-boot.txt`; termina en `GPU probe done, back to fastboot in 10 s`. `LOADER no SWEETXNU payload` y `PLOG ufs=00000000` indican que el scratch no corresponde al image booteado o que el shim no llegó a la fase de kernel.
3. **No hay línea de panic en la ring.** El parche 0047 no puede volcar lo que pasa después del último flush; el panic queda en pantalla. Buscar `panic`, `initproc`, `debugger` en las 610 líneas no da nada.
4. **No hay `.ips` ni core.** El parche 0039 desactiva el coredump por defecto en SWEET (`NOTES.md:454`); el caso AMFI generó un core de 2,7 GB, pero el panic actual no dejó core en el workspace.
5. **No hay log del flash de `gpu2` ni del reflash.** Los únicos logs completos son base y gpu1. Sin el transcript no se sabe el último chunk `OKAY`.
6. **No hay árbol de XNU local.** `research/` solo tiene `gpu-sweet` e `ipsw-x`; para simbolizar un crash de userspace haría falta el dyld cache y un core, que no existen.
7. **No hay `HANDOFF.md` dentro de `ios-sweet/`.** El `HANDOFF.md` está en el directorio padre (`iOS on sweet/HANDOFF.md`), fuera del repo, y está fechado 2026-11-02; no cubre el 03/11.
8. **El `getvar` está prohibido en la práctica.** No se puede preguntar al ABL por el estado del flash después de un flash grande sin arriesgar otro cuelgue.

### 9.3. Lo que no se puede afirmar

- **“El root está limpio.”** No: el root del teléfono fue modificado por boots `rw` y por la deploy de Wi-Fi; “limpio” solo aplica al `.simg` de referencia, y ni siquiera se ha comparado.
- **“El flash terminó.”** No hay transcript del `gpu2`/reflash; el `.simg` existe, pero eso no prueba que el teléfono lo tenga completo.
- **“El panic es reproducible.”** El único intento de reboot produjo un archivo idéntico; no hubo un segundo boot con ring nueva.
- **“Fue SIGFPE.”** Solo si la transcripción es literal; el formato no coincide con XNU y la ring no lo contiene.
- **“Fue la GPU.”** No: el self-test pasó, la IB corrió, el fence 1 está, `0 swaps` y el stats thread vivo.
- **“Fue 0105.”** No hay evidencia de que el boot usara 0105; los args encajan con 0101s0 + Wi-Fi, y no hay commit del 03/11.
- **“Un reflash lo arregla.”** Un reflash completo es la forma de volver a un baseline conocido, pero no está probado que el fallo sea del root; si es H2/H3 (plist/helper) o H4 (kernel), el reflash puede no cambiar nada.
- **“El HFS está sano.”** El metadata montó, pero no se corrió `fsck.hfsplus -n` sobre el teléfono ni sobre una copia; no hay verificación de contenido.

### 9.4. Definición operativa de “root limpio”

Para esta nota, **“root limpio” = el `.simg` de referencia construido en el host, sin mutaciones posteriores en el teléfono**. No significa “root factory de iOS”: el root es sintético (HFS+ con userland iOS 16.7.16, cryptex hard links, plist parcheado, keybag sintético, etc.). La cadena de construcción está en `NOTES.md:488` y `tools/mkiosroot.sh`; los parches de userland, en `tools/sweet-root-tweaks.py`, `tools/patch-launchd-plist.py` y las imágenes v3–v12.

El `gpu2.simg` del workspace es la referencia más cercana, pero:
- se construyó el 2026-11-01 23:26;
- se flasheó ese día según HANDOFF, sin log;
- el teléfono lo booteó el 02/11 y lo mutó con Wi-Fi;
- no hay SHA del contenido del teléfono.

Por tanto, “limpio” es una **hipótesis de trabajo**, no un hecho.

---

## 10. Árbol de decisión seguro, evidencia faltante y preguntas

### 10.1. Fase 0 — congelar

- **No bootear, no flashear, no `getvar`, no formatear.** Cualquier boot `rw` adicional muta el Estado B y puede destruir la ring o el journal que se quiere leer.
- **No usar el teléfono como banco de pruebas hasta tener la foto del panic y la comparación de bloques.** El coste de un boot es alto (15–30 min de datamigrator, riesgo de ABL colgado, riesgo de otra mutación).
- **No tocar `NOTES.md`/`HANDOFF.md` ni el código** durante la forense; la nota es el único artefacto nuevo.

### 10.2. Fase 1 — host-only, sin teléfono

1. **Verificar el `.simg`.** Header ya verificado (§3.1). Caminar la tabla de chunks: sumar `chunk_sz` de todos los chunks (RAW/FILL/DONTCARE) y comprobar que suma `total_blks`; comprobar que cada chunk cae dentro del archivo; verificar que el último chunk no está truncado. Un `.simg` truncado en el host explica un flash incompleto incluso si el teléfono hizo todo bien.
2. **Convertir a raw en un disco temporal** (16 GiB libres) o usar un lector sparse-aware. `simg2img gpu2.simg gpu2.raw` y `fsck.hfsplus -n gpu2.raw` (solo lectura). Si `fsck` reporta errores, el `.simg` de referencia no es un baseline limpio.
3. **Extraer los archivos críticos** del raw con `hfsplus`/`hfsfuse`/loop mount read-only:
   - `/System/Library/xpc/launchd.plist` y `.sig`;
   - `/usr/libexec/launchd_cache_loader`;
   - `/sbin/launchd`;
   - `/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64*` (44 archivos; al menos el principal y los que el helper necesita);
   - `/private/var/keybags/systembag.kb` (para entender el estado de MKB, no para modificarlo).
4. **Validar el plist** con `plutil -lint` (macOS) o `plistlib.load` (Python). Contar jobs; buscar `org.ios-sweet.wland`, `launchd_cache_loader`, `StandardOutPath`/`StandardErrorPath`; comparar con el plist de un boot bueno si existe una copia.
5. **Hashear** cada archivo y construir un **mapa de extents**: qué bloques de la imagen ocupan el plist, el helper y `launchd`. Identificar en qué chunk sparse (de los 27.934) y en qué descarga de 512 MiB (de las 24) cae cada uno. Ese mapa es el que se usará para leer el teléfono.
6. **Mapear la ring**: bloque `0x1d7d3fa` + 1.025; comparar con el área de la ring del `.simg` (probablemente ceros o datos viejos). Si el `.simg` tiene datos distintos en esa zona, el flash completo habría cambiado la ring; si el teléfono conserva la ring del panic, el flash no llegó al final.
7. **Documentar el SHA256** del `.simg` y de cada archivo extraído; sin esto no hay cadena de custodia.

### 10.3. Fase 2 — teléfono en read-only (solo con el usuario presente; no ejecutado aquí)

1. **Entrar a recovery** con `fastboot boot recovery/recovery.img` (temporal, no flash). Si el ABL está colgado, Power+Vol− y reintentar; no encadenar comandos.
2. **Esperar adb** y verificar `userdata` con `readlink -f /dev/block/by-name/userdata` + `blockdev --getsize64`. No montar, no escribir.
3. **Leer por `dd` solo los rangos del mapa** (volumen header, journal, plist, helper, `launchd`, ring, 1–2 MB alrededor de cada uno). No hace falta leer los 109.643 MiB completos; un `dd` completo tarda ~2 h y no aporta más que el hash global.
4. **Hashear en el host** y comparar con el mapa del `.simg`. Tres resultados posibles:
   - **Todo coincide:** el root está intacto; el fallo es de runtime (H2/H3/H4). Pasar a Fase 3.
   - **Discrepancia localizada** (solo plist/helper): restaurar esos archivos desde `gpu2` por `dd` (escritura; requiere aprobación explícita) o reflash completo. Antes de escribir, guardar una copia del estado actual.
   - **Discrepancia amplia o `fsck` con errores:** el flash fue parcial; el único baseline seguro es un reflash completo.
5. **Opcional:** leer la ring otra vez y comparar con `xnu-super-panic.txt`. Si cambió, hubo un boot posterior; si es idéntica, no.
6. **No** ejecutar `fsck.hfsplus -y` sobre el teléfono (escribe). Solo `-n` sobre una copia raw en el host.
7. **No** montar el root en read-write desde el host; HFS+ de Linux puede replayar el journal y modificar la imagen.

### 10.4. Fase 3 — boot mínimo, solo si el root coincide

Si la comparación de bloques dice que el root está intacto, el siguiente boot debe ser el más pequeño posible:

- **Image:** `shim-boot-0101s0.img` (0099+0101, 60 Hz, `serial=0`, sin `sweetfix`, sin Wi-Fi). Es el daily que funcionó el 02/11 (`NOTES.md:166-167`).
- **Args:** los de 0101s0, **sin** `sweetpmem`/`sweetsmmuprobe`/`sweetsmmuwlan`/`sweetwifi` (para descartar H4) y **sin** `sweetusb`/`sweetfiles`.
- **Auto-reboot:** `sweetgpu_reboot=1820` (30 min) o sin auto-reboot, para no cortar el datamigrator; la primera boot tras un flash tarda 15–30 min (`HANDOFF.md:19`).
- **Captura:** video de pantalla desde el primer segundo; la ring no captura el panic. Si el fallo se repite, el video da el texto exacto.
- **Después:** pull de la ring y comparación con el panic. Si el fallo desaparece, el problema era el plist/helper/kernel; si se repite, el root o el binario son los sospechosos.

### 10.5. Matriz de decisión

| Resultado de la comparación | Interpretación | Acción |
|---|---|---|
| Plist, helper, `launchd`, ring coinciden con `gpu2` | Root intacto; fallo runtime (H2/H3/H4) | Boot mínimo 0101s0; si repite, bisectar plist/helper; no reflash. |
| Solo el plist difiere | H2 (deploy Wi-Fi) | Restaurar plist desde `gpu2` (dd, aprobación) o reflash; validar con `plutil`. |
| Solo el helper difiere | H3 (binario corrupto) | Restaurar helper desde `gpu2`; verificar Mach-O/codesign; boot mínimo. |
| Ring ausente o distinta | El flash posterior la sobrescribió; Estado B ≠ A | Asumir flash parcial; reflash completo. |
| `fsck -n` con errores | H1 (corrupción estructural) | Reflash completo; no intentar reparar a mano. |
| El image no es 0101s0 | H4 (kernel nuevo) | Reboot con 0101s0; comparar. |

### 10.6. Evidencia faltante y cómo obtenerla solo con artefactos

| Evidencia | Por qué falta | Cómo obtenerla sin violar el modo read-only |
|---|---|---|
| Texto exacto del panic | La ring no lo captura; no hay foto. | Foto/video de la pantalla en el próximo boot; o leer el framebuffer si el boot queda en panic y el usuario fotografía. |
| Transcript del flash `gpu2`/reflash | No se guardó. | No recuperable del teléfono; solo el estado de los bloques (Fase 2) puede inferir hasta dónde llegó. |
| SHA del `userdata` del teléfono | Nunca se calculó. | `dd` read-only de los rangos usados + SHA; el hash global de 109.643 MiB es posible pero lento. |
| Copia del plist del teléfono | Está en el root, no en el host. | `dd` de los extents del plist (mapa de Fase 1) + `plutil`/`plistlib`. |
| Copia del helper | Igual. | `dd` de los extents del helper; `otool`/`codesign`/SHA. |
| `fsck.hfsplus -n` del teléfono | Recovery no tiene hfsplus. | `dd` de una copia raw al host y `fsck -n` (solo lectura). |
| Kernel exacto del boot | No hay hash/CI en la ring. | Comparar `Darwin Kernel Version` + `load_init_program` + boot-args con los images; si el image está en `shim/out/`, hashear el kernel. |
| Estado del ABL | No se puede `getvar`. | Observación física (pantalla) y Power+Vol−; no automatizar. |
| `launchd.plist` job table | No está en git. | Extraer del root; contar jobs; comparar con `NOTES.md:471` (532 daemons) y `NOTES.md:181` (531 jobs tras Wi-Fi). |
| Core/`.ips` | Coredump off; no hay ReportCrash. | No recuperable si no se generó; el próximo boot puede habilitar `kern.coredump=1` (decisión aparte). |

### 10.7. Preguntas para otro AI

1. **¿La ring del panic es anterior o posterior al reflash interrumpido?** ¿Hay algún timestamp interno (seq de flush, `total`, `flush #3`) que permita ordenarla contra el mtime del `.simg`/HANDOFF?
2. **¿El helper imprime `0 Found valid port` antes o después de abrir el plist?** El fuente de `launchd_cache_loader` no es público desde iOS 8; ¿se puede responder con `strings`/desensamblado del binario del `gpu2` y el orden de los format strings?
3. **¿Qué señal produce `SIGFPE` en `launchd`/libxpc en arm64?** ¿Hay un `raise(SIGFPE)` o una ruta de `abort_with_reason` que el kernel mapee a 8? ¿O el `subcode 0x8` es una lectura errónea?
4. **¿El parche 0043 imprime `CRASH` para un hijo que muere por señal antes de que el padre paniquee?** Si sí, la ausencia de `CRASH launchd_cache_loader` es evidencia fuerte de que el helper no murió; si no, no.
5. **¿El boot del panic usó 0101s0, 0102 o un 0105 local?** Los args encajan con 0101s0 + Wi-Fi; ¿hay un `shim-boot-super.img` con ese cmdline en `shim/out/` y cuál es su SHA?
6. **¿La deploy de Wi-Fi reescribió el plist completo o solo añadió un job?** ¿Se conservó el `StandardOutPath` de `launchd_cache_loader`? ¿El plist tiene 531 o 532 jobs?
7. **¿El `gpu2.simg` del workspace es byte-idéntico al que se flasheó?** ¿Existe otra copia con otro SHA (por ejemplo, en el árbol de trabajo original del host)? Comparar contra el hash `FB86997E...3579` de §9.1.
8. **¿El flash de `gpu2` del 01/11 se completó?** HANDOFF dice que sí, pero no hay log; ¿el teléfono booteó 0102 el 02/11 sobre ese root? Si sí, el flash de 01/11 terminó y el problema es posterior.
9. **¿Qué contiene la zona de la ring en `gpu2.simg`?** Si son ceros, un flash completo la habría borrado; el hecho de que la ring del panic sobreviva acota el flash a < últimos 4,1 MiB.
10. **¿El `launchd.plist` del teléfono es válido?** ¿`plutil -lint` pasa? ¿El job de cache loader tiene `ProgramArguments` y `StandardOutPath`?
11. **¿El helper y `launchd` tienen el mismo SHA que en `gpu2`?** Si no, ¿la diferencia está en el primer bloque (corrupto) o en todo el archivo (versión distinta)?
12. **¿El journal de HFS contiene transacciones del boot del panic?** El replay terminó en `6875648`; ¿hay transacciones posteriores sin commit que puedan mostrar la última escritura?
13. **¿El `SIGFPE` es determinista?** Un solo boot adicional con el mismo root y video respondería; ¿vale el coste (15–30 min, riesgo de ABL)?
14. **¿Qué baseline es más seguro: reflash completo de `gpu2` o restaurar solo plist/helper?** Depende de la comparación de bloques; no decidir antes.
15. **¿Hay algún artefacto de CI del 03/11 (run, artifact, kernel) que no esté en git?** El `xnu/` mtime 18:24 sugiere actividad; revisar `xnu/out-*`, `shim/out/*.img` y logs de shell.

### 10.8. Cierre: qué cambiaría el veredicto

- **Cambia a H1 (flash parcial):** discrepancia de bloques en plist/helper/ring, o `fsck -n` con errores, o un transcript que muestre <24/24.
- **Cambia a H2 (plist Wi-Fi):** plist inválido o job de cache loader sin stdout, con el resto del root intacto.
- **Cambia a H3 (helper/dyld):** helper truncado o subcache con páginas cero, con el plist válido.
- **Cambia a H4 (kernel):** el image del boot no es 0101s0/0102 y el fallo se reproduce con ese kernel en un root verificado.
- **Cambia a H5 (texto compuesto):** la foto muestra un panic distinto o una línea de boot task con `code 1`.
- **Cambia a H6 (hardware):** el fallo es aleatorio, con líneas de PMIC/reset/térmicas, y no se correlaciona con un archivo.

Mientras no haya foto del panic ni comparación de bloques, la afirmación defendible es la del §1: **kernel y GPU vivos; `launchd` muerto en el cache loader; root/userdata no verificados; flash de estado desconocido; siguiente paso read-only.**

---

**Fin de la nota.** No se ejecutaron comandos de teléfono; no se modificó código, `NOTES.md`, `HANDOFF.md` ni artefactos fuera de este archivo.
