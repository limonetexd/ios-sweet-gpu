# XNU / topaz GPU / kernel bring-up en sweet (iOS 16.7.16, 20H392) — nota para otra IA

**Ámbito:** `D:\pablo\Downloads\CLAUDE\OPENCODE\deepseek\iOS on sweet\ios-sweet` (repo `dipa-studio/ios-sweet`, shadow local sin remoto configurado). Device `sweet` = Redmi Note 10 Pro, SM7150, serial `[redacted]` (dato del brief; no re-verificado aquí). Objetivo del frente: un único kernel XNU con GPU topaz rápida + Wi-Fi WCN3990 + batería real (la “super” image).

**Método:** solo lectura sobre el workspace y sobre `\\wsl.localhost\Ubuntu\home\pablo\research` (cat/ls/grep/find). No se ejecutó `fastboot`, `adb`, `boot`, `flash`, recovery ni ningún comando contra el teléfono. No se editó código, `NOTES.md`, `HANDOFF.md` ni nada fuera de este archivo. **`HANDOFF.md` no existe en `ios-sweet/`**: el único handoff dentro del repo es `NOTES.md` (210.905 B, mtime 2026-11-02 19:38:44); el `HANDOFF.md` que citan las notas hermanas está en el directorio padre `iOS on sweet/`, que está prohibido para este agente y **no se ha leído**. Todo lo que sigue se apoya en artefactos del workspace y en el donor WSL.

**Etiquetas:** `[OBS]` leído directamente en un artefacto; `[INF]` inferencia con mecanismo explícito; `[DESC]` desconocido, no verificado o solo reportado por el usuario. Las líneas de `NOTES.md` corresponden a la copia de 210.905 B; las de los logs, a la copia exacta indicada. Las líneas de los parches son las del archivo `.patch` completo (no las del árbol XNU).

---

## 1. Alcance y estado

### 1.1. Qué cubre este frente

Cubre la cadena de arranque propia del port, no el root de iOS:

1. **Shim** (`shim/`): bootloader mínimo que ABL carga como “kernel” de un `boot.img` v2, con MMU y caches apagadas, que trae la GPU Adreno 618 si se compila con `SHIM_GPUBOOT`, prepara el payload `SWEETXNU` (kernel Mach-O + ADT) y salta a XNU como si fuera iBoot.
2. **Payload** (`tools/mkpayload.py`): contenedor `SWEETXNU` v1 con segmentos ya rebasados (chained fixups resueltos), ADT y `boot_args`.
3. **ADT** (`shim/out/sweet-wlan.adt`, `sweet-gpupool.adt`, `tools/mkadt.py`, `tools/adt.py`): device tree estilo Apple que XNU consume; en la super se añade `/arm-io/wlan`.
4. **Kernel** (`xnu/patches/0104-super-wifi-battery.patch`, `0105-super-link-fix.patch`, artefactos `xnu/out-0105/`): kernel 8796.141.3 con topaz/RedwoodGPU y los drivers Wi-Fi/batería importados de la rama DC28088.
5. **Presentación**: `SweetFramebuffer`/AppleCLCD y el monitor `SWEET FPS` (0097); el estado `0 swaps, 1 surface, fence 1`.

No cubre: el root HFS+, el `launchd.plist` de 531 jobs, el deploy de `wland`/firmware, ni la forensic del flash. Eso está en `notes/agents/root-launchd-panic.md` (nota hermana) y `notes/agents/wifi-battery-branch.md`; esta nota las cita cuando hace falta y **corrige** dos puntos de la primera (procedencia de la ring y ventana de 23 s, §4.7 y §6.5).

### 1.2. Estado en una tabla

| Capacidad | Estado | Evidencia | Etiqueta |
|---|---|---|---|
| Shim carga, GPU probe, salto a XNU | Funciona en las imágenes 0082g→0102/0104 | `logs/xnu-super-panic.txt:403-409`; `shim/shim.c:384-412` | `[OBS]` |
| GPU topaz bajo XNU | **Viva**: GMU 0xbabeface, RBBM 1, CP_MEM_WRITE desde XNU, IB desde memoria XNU, fence 1 | `logs/xnu-super-panic.txt:403-409` | `[OBS]` |
| Display AppleCLCD | Registrado, 1080x2400 stride 4320 en 0x9c000000, presentado como 1125x2436; vsync 60 Hz | `:75-77`, `:107` | `[OBS]` |
| CoreAnimation / backboardd | **No arrancó** en la ring super: 0 swaps, 0 presents, 1 surface | `:107-609` | `[OBS]` |
| Wi-Fi kernel side | `/dev/wlan` (major 20), SMMU WLAN SID 0x240→CB4, RPMh SN15/CN0 | `:155-208`, `:400` | `[OBS]` |
| Wi-Fi userland | No: no hay `open /dev/wlan`, ni `en0`, ni `RedwoodWLAN`, ni `wifid`, ni `wland` en la ring | búsqueda en 609 líneas | `[OBS]` |
| Batería real | QG SDAM seed 58%, 4031 mV, 240 mA, external=1 charging=1 | `:103-106` | `[OBS]` |
| launchd | Arranca y ejecuta boot tasks hasta `launchd_cache_loader`; después 23 s de FPS y fin de ring | `:234-586`, `:587-609` | `[OBS]` |
| Panic `initproc exited` | Reportado por el usuario; **no está en la ring** | sin artefacto | `[DESC]` |
| Super image actual (`67ff470f…`) booteada | **No probado**: la ring no coincide con sus args; el `.shim.txt` es de un probe viejo | §4.7 | `[INF]` |

### 1.3. Veredicto operativo (lo que otro agente debe asumir)

1. **La GPU no es el bloqueo.** El self-test terminó antes de `launchd`; después no hay ninguna submission (0 swaps, 0 presents, `GPU 0 ms pending (fence 1)`). Un fallo de GPU tendría namespace `OS_REASON_GPUPANIC` (6) o un fault de SMMU/GPU en el log; no hay ni uno.
2. **El Wi-Fi tampoco es el bloqueo directo.** El kernel llegó a crear `/dev/wlan` y a programar el stream SMMU del WCN3990, pero **ningún proceso abrió `/dev/wlan`**: no hay línea de `flame_wlan: open`, ni `en0`, ni `RedwoodWLAN`, ni `wifid`. El fallo es anterior a que el Wi-Fi userland toque el hardware.
3. **El bloqueo es `launchd`/`launchd_cache_loader`.** El ring se corta justo después de `exec launchd_cache_loader`, sin ninguna de las nueve líneas que el helper imprime en un boot bueno (`0 Found valid port…`, `Using default cache paths`, `Cache sent…`, `Early boot complete`). Pasan 23 tics de 1 s antes del corte; el kernel sigue vivo y el hilo de FPS sigue imprimiendo.
4. **La procedencia de la ring es dudosa.** `logs/xnu-super-panic.txt` es byte-idéntico a `logs/xnu-0101s0reboot.txt` (SHA256 `576cdb1a…`), pero contiene strings que **solo existen en 0104** (`flame wlan: /dev/wlan`, `SWEET PMEM`, `SWEET SMMU: WLAN`, `SWEET BATTERY: seed`) y el payload de 0101 no las tiene. Además, sus boot-args (302 caracteres) no son los del `payload-super.bin` actual (346 caracteres). La ring es de **algún boot super anterior**, no del artefacto actual ni de 0101; el `.shim.txt` es un residuo de un probe-only y no describe el boot.
5. **El siguiente paso no es tocar la GPU.** Es (a) hacer que la imagen actual bootee de verdad con una ring nueva y un tag único, y (b) aislar qué cambio de 0104/0105 hace que `launchd_cache_loader` no imprima. Los tests A/B están en §9.

### 1.4. Corrección a las notas previas

La nota `root-launchd-panic.md` afirma que “los args encajan con 0101s0 + Wi-Fi” y que la ventana es de ~3 s. Ambas cosas son incorrectas con los artefactos actuales:

- **Args:** el payload `payload-0101s0reboot.bin` no contiene `flame wlan`, `SWEET PMEM`, `SWEET SMMU: WLAN` ni `SWEET BATTERY: seed`; su kernel tiene 0 ocurrencias de esos strings. El kernel de la ring sí las tiene. Por tanto la ring **no** puede ser del payload 0101; es de un kernel con 0104 (probablemente un super build previo con 302 chars de cmdline).
- **Ventana:** contando las líneas `SWEET FPS` posteriores a `exec launchd_cache_loader` (`:587-609`) hay **23** líneas de ~1000-1001 ms, no 3. La ventana de silencio es de ~23 s, compatible con un timeout de boot task de 20-30 s, no con una muerte instantánea.

La nota hermana `wifi-battery-branch.md` afirma que el shim “miró 0x855FE000 y no el payload” y que eso bloquea la super. Eso sale del `.shim.txt`, que es un log de **probe-only** (`plog`) y no se reescribe en las imágenes `SHIM_GPUBOOT`: en `shim/shim.c` el bloque `#ifdef SHIM_GPUPROBE` que llama `plog_init()` está **después** de `loader_boot()`, y `loader_boot()` no retorna. Por tanto el scratch del shim conserva el último probe y no prueba nada del boot XNU actual. El “initrd handoff” es un falso positivo; no lo persigas sin una ring nueva que lo confirme.

---

## 2. Cronología

### 2.1. Build / CI / artefactos

Fechas locales del workspace (Europe/Madrid, +0100/+0200 según el archivo). Los IDs de CI son los del brief y `NOTES.md:199-222`; `gh` ya no puede consultarlos (HTTP 404 con el repo actual), así que **no se re-verificaron en esta sesión**.

| Fecha/hora | Hecho | Evidencia | Etiqueta |
|---|---|---|---|
| 2026-10-15…11-01 | Port XNU, display, IOSurface, topaz, 0082g primera GPU bajo XNU, 0083 RedwoodGPU, 0096d ~25 fps | `NOTES.md:295-311`, `:43-56` | `[OBS]` |
| 2026-11-02 15:50:42 | `shim/out/sweet-wlan.adt` (12.960 B) | mtime; `tools/adt.py dump` | `[OBS]` |
| 2026-11-02 18:47:59 | commit `5639176` “xnu 0104: super build…” | `git log` | `[OBS]` |
| 2026-11-02 18:48:37 | commit `ede4419` notes; CI 0104 = `41494548855` | `git log`, `NOTES.md:199` | `[OBS]`/`[DESC]` |
| 2026-11-02 19:14:28 | commit `771481a` “xnu 0105: super link fix…” | `git log` | `[OBS]` |
| 2026-11-02 19:14:06 | mtime `0105-super-link-fix.patch` (2.515 B) | `Get-Item` | `[OBS]` |
| 2026-11-02 19:16:58 | commit `9222114` notes 0105 | `git log` | `[OBS]` |
| 2026-11-02 19:31:12 | commit `34e3a8f` CI `macos-15-intel` | `git log` | `[OBS]` |
| 2026-11-02 19:32:48 | commit `61c27e9` notes runner cancelado | `git log` | `[OBS]` |
| 2026-11-02 19:38:44 | commit `e1ce648` (HEAD de `main` en esta copia) | `git log` | `[OBS]` |
| 2026-11-02 18:29→19:38 | CI 0105 `41498675277` cancelado por capacidad arm64; `41501352880` (`macos-15-intel`) y `41502238106` (`ci-macos-latest`) en cola | `NOTES.md:216-222` | `[OBS]` |
| 2026-11-03 18:24:41 | `xnu/out-0105/kernel.development.sweet` (17.382.896 B) | mtime | `[OBS]` |
| 2026-11-03 18:24:46 | `shim/out/payload-super.bin` (16.757.888 B) | mtime | `[OBS]` |
| 2026-11-03 18:24:51 | `shim/out/shim-boot-super.img` (17.494.016 B, SHA `67ff470f…`) | mtime/SHA | `[OBS]` |
| 2026-11-03 18:28:37 | `logs/xnu-super-panic.txt` (50.094 B) | mtime | `[OBS]` |
| 2026-11-03 18:29:51/55 | `payload-0101s0reboot.bin` / `shim-boot-0101s0reboot.img` | mtime | `[OBS]` |
| 2026-11-03 18:32:21 | `logs/xnu-0101s0reboot.txt` (mismo SHA que la ring “super”) | SHA | `[OBS]` |
| 2026-11-03 18:35:10-14 | `payload-branch-reboot.bin` / `shim-boot-branch-reboot.img` (SHA `833b199c…`) | mtime/SHA | `[OBS]` |
| 2026-11-03 (hora desconocida) | Reflash de `gpu2` “interrumpido”, sin log ni exit code | reporte del usuario | `[DESC]` |
| 2026-11-03 (posterior) | CI `41501352880` OK; `41502238106` OK (según brief) | brief | `[DESC]` |

### 2.2. Cronología interna del boot que escribió la ring

Los timestamps de launchd son época+uptime (1969-12-31 16:00:xx en PST), no la hora real; el calendario del kernel se puso a 1971 por el RTC (§4.5). Lo que importa es el orden y los deltas.

| Línea | Evento | Delta |
|---|---|---|
| `:52` | `iBoot version: sweet-shim` | t=0 |
| `:68-97` | CPUs 0-7, PSCI CPU_ON, SGI1 | primeros ms |
| `:75-77` | modos 1125x2436@60, IOAcceleratorES vacío, AppleCLCD 1080x2400@0x9c000000 | <1 s |
| `:80` | RTC: 53.464.448 s (1971-09-11), boottime igual | ~1 s |
| `:103-106` | batería QG SDAM 58%, 4031 mV, 240 mA | ~1 s |
| `:152-154` | UFS `userdata` 109.643 MiB, ring en `0x1d7d3fa`, `/dev/pmem` | ~2 s |
| `:155-206` | RPMH: RSC, cmd-db, MC0/SH0/ACV/SN15/CN0, DDR 16383 | ~2-3 s |
| `:208` | `flame wlan: /dev/wlan ready (major 20)` | ~3 s |
| `:223-229` | BSD root `ufsroot0`, journal replay, HFS `iOSRoot`, unsealed | ~3 s |
| `:234` | `exec launchd` | ~3 s |
| `:237-279` | libignition, `ignition_level=1`, dylib cache | ~3 s |
| `:281-323` | 43 mapas del dyld shared cache “not in trust cache” | ~3 s |
| `:325-328` | launchd hello; boot-args (302 chars) | 16:00:39.845 |
| `:333-424` | mount, seputil, obliterator, MSU, fips, keybag | 16:00:39.86→40.54 |
| `:426-527` | usermanagerd, personas 99/199/100/1000/200 | 16:00:40.54 |
| `:528-568` | dirs_cleaner, xpcroleaccountd, featureflags, auearlyboot, tzinit, FinishRestore | 16:00:40.7→41.0 |
| `:575-583` | finish_demo_restore, sysstatuscheck, prng_seedctl (falla `virtual random`) | 16:00:45.04→45.08 |
| `:586` | `exec launchd_cache_loader` | 16:00:45.086 |
| `:587-609` | 23 × `SWEET FPS: 0 swaps…` | 16:00:45→16:01:08 aprox. |
| — | panic reportado (no en ring) | después del último flush |

**Dato clave:** en el boot bueno de la rama (`logs/xnu-wifi-boot.txt:663-676`) el helper imprime sus nueve líneas y launchd dice `Early boot complete` **0,3 s** después del `exec`; en la ring super hay **23 s** de silencio. Eso no es “tardó un poco”: es un timeout o un bloqueo.

### 2.3. Qué prueban y qué no prueban las fechas

- Prueban que el kernel `out-0105` se descargó/compiló el 03/11 a las 18:24 y que el payload/imagen super se construyeron 5-10 s después.
- **No** prueban que `shim-boot-super.img` se haya booteado: la ring no lleva sus args y el `.shim.txt` es de probe. El boot de las 18:28 pudo fallar antes de XNU (ABL/DTB) y dejar la ring anterior.
- **No** prueban que el panic sea del 03/11: la ring pudo escribirse en un boot super anterior (02/11 o 03/11 por la mañana) con el mismo kernel 0104/0105 y args más cortos.
- El commit de docs `34e3a8f`/`61c27e9` es del 02/11; no hay commit nuevo el 03/11. El binario `out-0105` del 03/11 no está en git (solo el patch).

---

## 3. Arquitectura

### 3.1. Cadena de arranque

```
ABL (Xiaomi bootloader)
  └─ boot.img v2 (mkbootimg, header_version=2)
       ├─ kernel   = shim/out/Image        (shim.elf -> binary, link 0, MMU off)
       ├─ ramdisk  = payload SWEETXNU      (kernel + ADT + boot_args; 16 MB)
       ├─ dtb      = dtb/boot_unpacked/dtb (stock sweet DTB; ABL lo parchea)
       └─ cmdline  = "console=null"        (irrelevante: el shim usa el payload)
            ↓
        shim_main(dtb)
          ├─ SHIM_GPUBOOT: gpuprobe_run()   (CX/GX, GMU, HFI, SMMU, CP, zap, IB)
          └─ loader_boot(dtb)
               ├─ lee /chosen linux,initrd-start/end
               ├─ valida "SWEETXNU" v1
               ├─ copia segmentos a phys_base + (vmaddr - virt_base)
               ├─ coloca ADT y boot_args detrás de kernel_end
               └─ salta a entry_va con x0 = boot_args PA, MMU/caches off
                    ↓
                 XNU (mach_kernel, DEVELOPMENT, MACHINE_CONFIG=SWEET)
```

El shim **no** usa el header de Android para localizar el ramdisk: usa la propiedad `linux,initrd-start` del DTB que ABL pasa en `x0`. Eso es un punto frágil conocido (si ABL deja un valor viejo, el shim no encuentra el payload). No confundir con el `.shim.txt` viejo (§1.4).

### 3.2. Shim: archivos y contrato

| Archivo | Rol | Líneas clave |
|---|---|---|
| `shim/start.S` | entry, stack, salto a C, `secondary_entry` | — |
| `shim/shim.c` | main, GIC/PSCI, SMP, `gpuprobe_run`/`loader_boot` | `:375-412` |
| `shim/loader.c` | “iBoot”: payload, segmentos, ADT, `boot_args`, jump | `:79-146` |
| `shim/mmu.c` | mapas 16K, identidad, MMU on/off | — |
| `shim/fdt.c` | lectura de `/chosen` del DTB | — |
| `shim/gpuprobe.c` | bring-up Adreno 618 (43.704 B) | `:28-1317` |
| `shim/gpufw.S` | firmware GMU embebido (`a618_gmu.bin`) | — |
| `shim/plog.c` | log de probe en userdata (solo `SHIM_GPUPROBE`) | `:20-346` |
| `shim/ufs.c` | probe UFS (sin payload) | — |
| `shim/console.c/.h` | consola framebuffer/serial | — |
| `shim/build.sh` | compila, linka, `mkbootimg` v2 | `:1-40` |

`build.sh` usa `aarch64-linux-gnu-gcc -O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector`; comprueba que no haya relocaciones `ABS64` (solo `start.o` puede tener direcciones absolutas); linka `-T shim.ld -Wl,-N`, `objcopy -O binary`, y rellena a `_end` para que `.bss`/stacks existan como ceros. Luego:

```bash
mkbootimg --header_version 2 --kernel out/Image --ramdisk out/ramdisk.bin \
  --dtb ../dtb/boot_unpacked/dtb --base 0 --kernel_offset 0x8000 \
  --ramdisk_offset 0x1000000 --tags_offset 0x100 --dtb_offset 0x1f00000 \
  --pagesize 4096 --os_version 17.0.0 --os_patch_level 2035-06 \
  --cmdline "console=null" -o out/shim-boot.img
```

El `--cmdline "console=null"` es deliberado: la consola real la maneja el shim/XNU; el `boot_args.CommandLine` sale del payload.

### 3.3. Payload `SWEETXNU` y `mkpayload.py`

Layout little-endian (cabecera de 0x2a8 + tabla de segmentos):

```
0x000  char  magic[8] = "SWEETXNU"
0x008  u32   version = 1, nsegs
0x010  u64   virt_base      VA que mapea a phys_base
0x018  u64   entry_va       LC_UNIXTHREAD pc
0x020  u64   adt_off, adt_size
0x030  u64   kernel_end_va  fin del segmento más alto, alineado 16K
0x038  u64   phys_base      RAM gestionada por XNU (= ADT dram-base)
0x040  u64   mem_size       (= ADT dram-size)
0x048  char  cmdline[608]
0x2a8  seg[nsegs] { u64 vmaddr, vmsize, file_off, file_size }
```

`mkpayload.py`:

- Parsea el Mach-O (`LC_SEGMENT_64`, `LC_UNIXTHREAD`, `LC_DYLD_CHAINED_FIXUPS`).
- **Resuelve los chained fixups** a VA planos; no admite binds (`imports_count == 0`). El kernel se linka PIE con `LC_DYLD_CHAINED_FIXUPS` y nadie más (ni kmutil ni iBoot) los resuelve.
- `virt_base = __TEXT.vmaddr & ~(32 MiB - 1)` para que el bloque L2 de 16K que empieza en el mach header caiga exacto en `phys_base`.
- `phys_base`/`mem_size` salen del ADT (`/chosen/dram-base`, `/chosen/dram-size`), no de una constante.
- `kernel_end` = max(vmaddr+vmsize) alineado a 16K; el ADT se coloca ahí y `boot_args` en la página 16K siguiente.
- No hay ramdisk de root en estas imágenes (`--ramdisk` no se usa); el root es `ufsroot0` en `userdata`.

`loader.c` valida `magic`, `version`, alineación, y que el payload no solape `[phys_base, phys_base+mem_size]`. Copia con `copy64` (MMU off: Device memory, solo accesos alineados de 8 bytes), cero el BSS, escribe:

```c
ba->Revision = 2; ba->Version = 2;
ba->virtBase = p->virt_base; ba->physBase = p->phys_base; ba->memSize = p->mem_size;
ba->topOfKernelData = ba_pa + 16K;
ba->Video = { FB_BASE, 1, FB_STRIDE, FB_W, FB_H, 32 };
ba->deviceTreeP = adt_pa - (phys_base - virt_base);  // VA, MMU on
ba->deviceTreeLength = adt_size;
ba->CommandLine[608] = p->cmdline;
ba->memSizeActual = p->mem_size;
```

y salta con `dsb sy; ic iallu; dsb sy; isb`.

### 3.4. `boot.img` v2 y `unpack_bootv2.py`

Header Android estándar: `ANDROID!`, `kernel_size/addr`, `ramdisk_size/addr`, `second`, `tags`, `page_size`, `header_version`, `os_version`; para v1/v2, `recovery_dtbo` en 1632 y `dtb_size/dtb_addr` en 1648. `unpack_bootv2.py` separa `kernel`, `ramdisk`, `second`, `recovery_dtbo`, `dtb` y escribe `header.txt`. No verifica firmas ni hashes; solo estructura.

Verificación hecha en esta sesión (sin escribir): los tres `ramdisk_size` coinciden **exactamente** con el tamaño del payload y el ramdisk empieza por `SWEETXNU`:

| Imagen | `ramdisk_size` | payload | primer bloque |
|---|---:|---:|---|
| `shim-boot-super.img` | `0xffb480` = 16.757.888 | `payload-super.bin` 16.757.888 | `SWEETXNU` en off 0 |
| `shim-boot-0101s0reboot.img` | `0xfe43a0` = 16.663.456 | `payload-0101s0reboot.bin` 16.663.456 | `SWEETXNU` en off 0 |
| `shim-boot-branch-reboot.img` | `0x1033ea0` = 16.989.856 | `payload-branch-reboot.bin` 16.989.856 | `SWEETXNU` en off 0 |

Además, los segmentos del payload coinciden byte a byte con el kernel de `xnu/out-0105`, `xnu/out-0101` y `DC28088-kernel`, respectivamente (§4.3).

### 3.5. GPU handoff: `SHIM_GPUBOOT` y `gpuprobe.c`

Con `-DSHIM_GPUBOOT`, `shim_main` llama `gpuprobe_run(&stage)` **antes** de `loader_boot`. `gpuprobe.c` hace, en orden (nombres y valores de `logs/xnu-super-panic.txt.shim.txt` y `logs/xnu-wifi-boot.txt.shim.txt`):

1. **Relojes GPUCC / GDSC:** CX GDSC `0xf8222000`, GX `0xf8222000`; `gcc halted=0x6`; GMUCLK `cx_gmu=0x4221`, `cxo=0x1`; PLL0 locked `mode=0xD0800005`, `user=0x7`.
2. **SMMU del GPU:** `nsmr=5`, `ncb=5`; CB0/CB1 tables en 0x1f0000000; SID 5 (GMU) con SMR `0x80000005`, `sctlr=0x67`, `s2cr=0`, `cbar=0x1f301`; SID 0 (GPU) CB1; **regla del hypervisor:** el SMMU Adreno solo acepta SMRs para los SIDs exactos del DT con mask 0 (GMU 5, GPU 0). Un SMR enmascarado lee 0 y el GMU nunca llega a DDR (reset del SoC); escrituras de fault-type S2CR también resetean. CB registers son libres.
3. **RPMh/BCM DDR:** `mc0=0x50000`, `sh0=0x5003c`, `acv=0x5000c`, `memnoc=0x221`, `dvm=1`; PDC/RSC desde cmd-db: `gfx.lvl=0x30050` (no el 0x30090 de Linux); RSC ACK timeout, pero PDC `0x80000001`; el ACK del RSC nunca llega y es inofensivo (igual que A640/ios-flame).
4. **GMU:** firmware `a618_gmu.bin` en ITCM (0x8000 B), CM3 start, `INIT_RESULT=0xBABEFACE`, `fsr=0x400`; BOOT_SLUMBER OOB, SPTPRAC `0x28`, HFI v1: INIT, FW_VERSION `0x10110000`, PERF_TABLE v1, BW_TABLE a618, TEST; GPU_SET OOB → GX on.
5. **DCVS:** perf idx 4, 430 MHz; `gfx3d cfg was=0 now=0x101`; PLL0 `L=0x2C`, `frac=0xCAAA`, `mode=0xD1000005`.
6. **CP:** `a630_sqe.fw` (0x7D84 B), CP start `status=0x00C00015`, ME_INIT idle `rptr=9`, zap `a615_zap` vía SCM PAS 13 (región 0x97715000), `CP_SET_SECURE_MODE 0`, `CP_MEM_WRITE` a `0xCAFEF00D`.
7. **Paint:** 5 batches (rptr 0x44C→0xFFF) pintan un gradiente de 500 filas en el framebuffer de ABL; `FB band word=0xFF7FC880`.

El handoff deja el ring en `wptr=rptr` y publica la GPU para XNU. `sweet_gpu.c` (boot-arg `sweetgpu=2`) vuelve a comprobar GMU/RBBM y ejecuta un IB **en memoria de XNU** (§4.4).

### 3.6. `SHIM_GPUPROBE` vs `SHIM_GPUBOOT`

| Flag | Efecto | Cuándo se usa |
|---|---|---|
| `-DSHIM_GPUPROBE` | Activa `gpuprobe.c` y `plog.c`; el bloque de `shim.c` **después** de `loader_boot` inicializa `plog`, guarda el log en userdata, arma watchdog, vuelve a fastboot | Imágenes de diagnóstico sin payload (probe 1-4, `sweet-probe-loop.ps1`) |
| `-DSHIM_GPUBOOT` | Llama `gpuprobe_run` y **continúa** a `loader_boot`; no inicializa `plog` | Imágenes que bootean XNU (`SHIM_CFLAGS="-DSHIM_GPUPROBE -DSHIM_GPUBOOT"` en `tools/sweet-gpu-image.sh:16`) |
| Ambos | El bloque `GPUPROBE` es código muerto porque `loader_boot` no retorna | Todas las imágenes XNU actuales |

Consecuencia práctica: **el `.shim.txt` de un boot XNU no se actualiza**. El scratch `plog` solo lo escribe el modo probe-only. Todos los `.shim.txt` recientes tienen SHA `3703a528…` y terminan en `GPU probe done, back to fastboot in 10 s`; son el mismo probe viejo. No sirven para diagnosticar el boot actual.

### 3.7. ADT: `sweet-wlan.adt`

`tools/adt.py dump` y `Compare-Object` contra `sweet-gpupool.adt` dan **solo dos diferencias**:

```text
random-seed = <...>            # distinto en cada build
+ wlan {                       # bajo /arm-io
+   AAPL,phandle = 0x18
+   device_type = 'wlan'
+   compatible = 'flame,wcn3990'
+ }
```

No hay `reg`, `interrupts`, `local-mac-address`, `mac-address` ni `address`. El nodo no describe hardware al kernel; su función es **hacer que launchd cargue `com.apple.wifid`**: el job de wifid tiene `_LimitLoadToDeviceTree = wlan` (documentado en el donor `DC28088_ios-sweet/tools/adt-add-wlan.py:2-7`). Sin el nodo, wifid no es elegible; con el nodo, sí. El kernel no hace match contra `/arm-io/wlan` (en 0104, `RedwoodWLAN` se cuelga de `IOService::getPlatform()`, no del nodo); el radio lo lleva `wland` en userland vía `/dev/wlan`. El `product/wifi-chipset='4357'` ya estaba en el ADT base, no es específico del nodo.

`/chosen` del ADT: `dram-base=0x100000000`, `dram-size=0xecb00000`, `unique-chip-id=0x5357454554000001`, `chip-id=0x8015`, `display-scale=3`, `crypto-hash-method=sha2-384`, `certificate-security-mode=1`, `effective-security-mode-sep=1`. El `gpupool` añade el pool de GPU fuera de la RAM de XNU (`0x1ecb00000-0x1fcb00000`, 256 MiB) y las tablas del shim en `0x1f0000000`.

### 3.8. Composición del kernel super

El kernel super es **nuestro árbol 0101/0102/0103 + 0104 + 0105**, no la rama DC28088 completa. La pila de parches se aplica en orden; 0104 aplica después de 0103 y 0105 después de 0104. 0102 (`sweetfix=1`) y 0103 (`ca_vbl=1`) están compilados pero **inertes** con los args del super (no se pasan). 0099/0100 (share BGRA/guard rows) también están inertes sin CoreAnimation.

Payload `payload-super.bin` (10 segmentos, `nsegs=10`):

| # | Segmento | vmaddr | vmsize | file size |
|---|---|---:|---:|---:|
| 0 | `__TEXT` | `0xfffffe0007004000` | `0x164000` | `0x164000` |
| 1 | `__DATA_CONST` | `0xfffffe0007168000` | `0x184000` | `0x184000` |
| 2 | `__TEXT_EXEC` | `0xfffffe00072ec000` | `0x864000` | `0x864000` |
| 3 | `__KLD` | `0xfffffe0007b50000` | `0x4000` | `0x4000` |
| 4 | `__LASTDATA_CONST` | `0xfffffe0007b54000` | `0x4000` | `0x4000` |
| 5 | `__KLDDATA` | `0xfffffe0007b58000` | `0x4000` | `0x4000` |
| 6 | `__DATA` | `0xfffffe0007b5c000` | `0x568000` | `0x48000` |
| 7 | `__BOOTDATA` | `0xfffffe00080c4000` | `0x4c000` | `0x4c000` |
| 8 | `__LINKINFO` | `0xfffffe0008110000` | `0x4c000` | `0x4c000` |
| 9 | `__LINKEDIT` | `0xfffffe000815c000` | `0x3c0000` | `0x3bfdf0` |

Cabecera: `virt_base=0xfffffe0006000000`, `entry=0xfffffe0007494488`, `adt_off=0xff81e0`, `adt_size=12.960`, `kernel_end=0xfffffe000851c000`, `phys_base=0x100000000`, `mem_size=0xecb00000`, payload 16.757.888 B.

Tamaños comparados:

| Kernel | Archivo | `__TEXT_EXEC` | `kernel_end` | entry |
|---|---:|---:|---|---|
| 0101 | 17.272.256 | `0x858000` | `0xfffffe00084d8000` | `0xfffffe0007490488` |
| 0105/super | 17.382.896 | `0x864000` | `0xfffffe000851c000` | `0xfffffe0007494488` |
| branch DC28088 | 17.565.712 | `0x888000` | `0xfffffe0008588000` | `0xfffffe00074a1488` |

0104 añade **4.578 líneas y borra 58 en 22 archivos**; 0105 añade **70 líneas en 3 archivos**. El crecimiento de `__TEXT_EXEC` de 0101 a 0105 es 48 KiB; `__DATA` vmsize crece 192 KiB; `kernel_end` +272 KiB.

### 3.9. Qué tocan 0104 y 0105 (archivo por archivo)

**0104 — `0104-super-wifi-battery.patch` (179.108 B)**

| Archivo | Líneas +/- | Qué hace | Relación con GPU |
|---|---:|---|---|
| `bsd/conf/files` | +7 | añade `sweet_pmem.c`, `flame_wlan.c`, `redwood_*`, `sweet_files.c` | ninguna |
| `bsd/dev/flame_wlan.c` | +442 | `/dev/wlan`: protocolo `fw_hdr`, cola de 64 mensajes, `scan/join/leave/transmit`, hooks de RX/link; `wland` en userland | ninguna |
| `bsd/dev/flame_sta.c` | +242 | estación (topaz `sta.c`): `flame_wlan_*`, `redwood_sta` API, `MiniIONetworkStackStart` | ninguna |
| `bsd/dev/redwood_net.c` | +376 | `en0` con la KPI de ifnet, framing Ethernet, `RedwoodWLANStart` cuando el link sube | ninguna |
| `bsd/dev/redwood_sta.c` | +371 | máquina de estados station (`IDLE/SCAN/JOINED`), PMK, `redwood_sta_*` | ninguna |
| `bsd/dev/redwood_apple80211.c` | +739 | ioctls `SIOCSA80211=0x802869c8` / `SIOCGA80211=0xc02869c9`, tipos de wifid | ninguna |
| `bsd/dev/sweet_pmem.c` | +417 | `/dev/pmem` (major 19), `ml_io_map` de ventanas físicas, `sweet_pmem_probe_read`, `PMEM_RPMH` | ninguna (solo lectura de registros) |
| `bsd/dev/sweet_rpmh.c` | +889/-33 | lookup multi-entrada, read ACK, ARC probe/read/require/raise, BCM vote, vreg set, `sweet_rpmh_ddr_raise`, probe SMMU apps, **WLAN SID 0x240**, dump MDSS | ninguna (votos DDR/relojes) |
| `bsd/dev/sweet_spmi.c` | +4/-2 | permite QG SDAM (0xb640) al battery | ninguna |
| `bsd/dev/sweet_ufs.c` | +16/-2 | en `sweet_ufs_init`: `native_adreno_reserve_pool`, `sweet_pmem_init`, `ddr_raise`, `smmu_probe_start`, `haptic`, `bt`, `flame_wlan_init`, y `sweet_gpu_probe()` en vez de `sweet_gpu_init()` | **orden de init**; el GPU sigue siendo topaz |
| `bsd/dev/sweet_files.c` | +355 | servidor TCP 192.168.7.2:2223 (PUT/GET/MKDIR/LINK/RM/CHMOD/SYNC) sobre USB ECM | ninguna |
| `bsd/sys/flame_wlan.h` | +69 | protocolo `/dev/wlan` | ninguna |
| `bsd/sys/redwood_net.h` | +63 | API de link (TX/RX/up) | ninguna |
| `bsd/sys/redwood_sta.h` | +122 | API station/Apple80211 | ninguna |
| `bsd/sys/redwood_input.h` | +5 | tipos de input | ninguna |
| `iokit/Kernel/IOService.cpp` | +2 | en `iokitDaemonLaunched`, **no** hace `adjustBusy(-1)` en SWEET | ninguna |
| `iokit/Kernel/IOStartIOKit.cpp` | +9 | `if (false)` en vez de `OSKext::iokitDaemonAvailable()`: no retiene el registry busy | ninguna |
| `iokit/Kernel/arm/MiniIONetworkStack.cpp` | +114 | `IONetworkStack` en `IOResources`, user client que rechaza naming; configd espera `*QUIET*` | ninguna |
| `iokit/Kernel/arm/RedwoodWLAN.cpp` | +137 | `IO80211Controller` + `RedwoodWLAN` (IONetworkInterface) con `IO80211InterfaceRole=Infrastructure`, `IOInterfaceName=en0`, MAC, `IOBuiltin`; `newUserClient` devuelve unsupported para forzar el path IOCTL | ninguna |
| `iokit/Kernel/arm/SweetBattery.cpp` | +148/-12 | QG/SMB5 real, SDAM seed, coulomb counting, IR drop 150 mΩ, poll 5 s, hold 12 fallos | ninguna |
| `iokit/Kernel/arm/SweetKeyStore.cpp` | +49/-9 | `SWEET_AKS_LOCK_STATE 0x4`, `sls 0`, `kAKSWrapKey`/`kAKSUnwrapKey` (HackiOS), logging por selector | ninguna |
| `iokit/conf/files.arm64` | +2 | añade `RedwoodWLAN.cpp` y `SweetBattery`/`SweetKeyStore` según config | ninguna |

**0105 — `0105-super-link-fix.patch` (2.515 B)**

| Archivo | Líneas | Qué hace |
|---|---:|---|
| `bsd/conf/files` | +1 | añade `sweet_super_compat.c` |
| `bsd/dev/sweet_super_compat.c` | +37 | `sweet_gpu_probe()` → `sweet_gpu_init()`; `sweet_bt_init()`/`sweet_haptic_init()` no-op; `sweet_native_adreno_reserve_pool()` → 0 |
| `bsd/vfs/vfs_syscalls.c` | +32 | `sweet_vfs_mkdir/symlink/unlink` con `vfs_context_kernel()`, `mkdir1at`, `symlinkat_internal`, `unlink1` para `sweet_files.c` |

**Lo que 0104 NO toca:** `SweetAdreno.cpp`, `RedwoodGPU.cpp`, `SweetFramebuffer.cpp`, `SweetSurface.*`, `sweet_gpu.c`, `topaz`/Mesa, `RedwoodGPU` userland. La GPU sigue siendo la pila topaz rápida. La única línea “GPU” de 0105 es el forwarding `sweet_gpu_probe → sweet_gpu_init`; no cambia el driver.

### 3.10. RPMh / PMEM / SMMU / WLAN / batería: mecánica

- **RPMh**: `sweet_rpmh.c` mapea `0x18220000` (RSC) y `0x18220d00` (TCS). El `cmd-db` lo localiza en `0x85f20000` (tamaño `0x1078`, magic `0xc0330db`). Resuelve `MC0` (`0x50000`, slave 5, aux 8@0x838), `SH0` (`0x5003c`, aux 0x850), `ACV` (`0x5000c`, aux 0x960), `SN15` (`0x5007c`, aux 0x928), `CN0` (`0x500a8`, aux 0x940). Escribe en TCS0, espera `done=1`, `irq=0x1`, `idle=0x1`, `status0=0x10101`; el ACK por IRQ no se usa (polling). El voto DDR es `MC0=0x3fff`, `SH0=0x3fff`, `ACV=(0,8)`; el log imprime los **return codes** 0, no los valores.
- **PMEM**: `/dev/pmem` permite a userland (`wland`) leer/escribir ventanas físicas (MSA/CE) sin `ml_io_map` desde el kernel; en el boot super no se abrió. El probe `sweet_pmem_probe_read(0x15000020)` se usa para validar el SMMU apps.
- **SMMU apps**: `sCR0=0x230406`, `ID0=0x4c017e4f`, `ID1=0x6000003d`, `ID2=0x5555` → 79 SMRs, 61 context banks. `sweet_smmu_wlan_stream` busca un SMR libre y un CB libre, escribe `CBA2R=1` (AArch64), `CBAR=0x1f000`, `SCTLR=0xe0` (M=0: translation off, fault reporting), `S2CR=cb` (type 0: el SMR apunta al bank, pero M=0 deja el bank en bypass), `SMR=(1<<31)|(mask<<16)|SID`. WLAN SID `0x240`, mask `1` → SMR6/CB4. MDSS SID `0x800`, mask `0x440` → SMR5/CB3; `SCTLR=0xe0` (M=0) y `TTBR0=0`, así que **el scanout usa direcciones físicas** (la copia de CPU a `0x9c000000` es consistente).
- **WLAN**: el kernel no habla con el WCN3990; `flame_wlan.c` expone `/dev/wlan` y `wland` (userland) hace PMEM/RPMh/firmware/CE/WMI/HTT. El kernel solo programa el stream SMMU y crea `en0` cuando el link sube. El ADT `wlan` hace elegible a `wifid`; `RedwoodWLAN.cpp` publica los servicios que `wifid`/configd buscan.
- **Batería**: `SweetBattery` lee QG SDAM (0xb640), SMB5 (0x4805/0x48c2), seed desde SDAM (`sdam[6]!=0 && sdam[7]<=100`), estima OCV con caída IR (`ma*150/1000`), cuenta coulombios (`ma*ms/180720`), corrige 2%/poll en reposo, publica `IOPMPowerSource`. El poll es 5 s; 12 fallos seguidos → fallback estático 100%.

### 3.11. Presentación y monitor

- `SweetFramebuffer` publica `AppleCLCD` en `/arm-io/disp0`, 1080x2400 stride 4320 en `0x9c000000`, `presented as 1125x2436`, modos 1125x2436@60, y un `IOAcceleratorES` vacío para que `CAMetalContextCreate` no espere 30 s.
- `SWEET FPS` (0097) imprime cada segundo: swaps, presents, vsync timer, GPU pending/fence, surfaces, zombies, wired MB, creates failed.
- En la ring super: 1 surface (la default del panel), 0 zombies, 0 MB wired, 0 creates failed, fence 1, `GPU 0 ms pending`, vsync 17-25 ms. Es el estado **inicializado pero nunca usado**: no hay backboardd, no hay CA, no hay swap.

---

## 4. Evidencia cruda

### 4.1. Comandos y hashes (read-only)

```powershell
Get-FileHash shim\out\shim-boot-super.img,shim\out\shim-boot-0101s0reboot.img,shim\out\shim-boot-branch-reboot.img,
  shim\out\payload-super.bin,shim\out\payload-0101s0reboot.bin,shim\out\payload-branch-reboot.bin,
  xnu\out-0105\kernel.development.sweet,xnu\out-0101\kernel.development.sweet -Algorithm SHA256
```

Salida (lowercase, tal cual):

```
67ff470f24acc5d3a92919fc8fbfde00e9f485e7e46c30aa8ab894bad24b5f3f  shim-boot-super.img
e0be26fca701c96c5862b579f14b58a31a36a560f82df1f5300d127e28a7949c  shim-boot-0101s0reboot.img
833b199ce8124dd9ebb36af0a1a17e3d03d3a483a5b88a860daa7080146821f9  shim-boot-branch-reboot.img
8201e7de7b17b39af59142f23cacdefd4a93b73a5f3811b9d7809aa24f6d7bfe  payload-super.bin
b1a21ba8194636a0bceb54b1394f2ceb24c13b0c584c959875e211ff422efafe  payload-0101s0reboot.bin
ff6fef0409ed9eece33ab8c6c75e7739bd632cfdac7c1c9fe3d35ab39e42584f  payload-branch-reboot.bin
d22c5aadf208b5e0347f487fdcb7b83d487a37d06af2b623ed9f675d9b7c1793  xnu/out-0105/kernel.development.sweet
d2bbc4dc3c3089efa26b9551d6ed602fee9d43a9aae13c9cbcc2399576fd68c5  xnu/out-0101/kernel.development.sweet
```

Tamaños:

```text
shim-boot-super.img          17.494.016
shim-boot-0101s0reboot.img   17.399.808
shim-boot-branch-reboot.img  17.723.392
payload-super.bin            16.757.888
payload-0101s0reboot.bin     16.663.456
payload-branch-reboot.bin    16.989.856
out-0105 kernel              17.382.896
out-0101 kernel              17.272.256
DC28088-kernel               17.565.712
```

Parches/ADTs:

```text
8cc3eafa489f5ae4161e3e8f66d0aa9c625d2d1ddf8f94dbc97a3426f1e17673  0104-super-wifi-battery.patch (179.108 B)
88f89b2304eab26a5dcf1bcbe30a5bf1ec30c3400d60207f1538828af0ca2376  0105-super-link-fix.patch (2.515 B)
994c8cac2a3070f5b6a6a27b8731c72b0f78c11cddfa70c57e07cc4f2316db5f  sweet-wlan.adt (12.960 B)
a8f78c1a84cabfc759662ca96f7677d84dedd3094e24e61e4d16eeb2f88454ae  sweet-gpupool.adt (12.772 B)
```

### 4.2. Cabeceras de payload (salida literal del parser en memoria)

```text
payload-super.bin 16.757.888
  magic b'SWEETXNU' ver 1 nsegs 10
  virt_base 0xfffffe0006000000 entry 0xfffffe0007494488
  adt_off 0xff81e0 adt_size 12960 kernel_end 0xfffffe000851c000
  phys_base 0x100000000 mem_size 0xecb00000
  cmdline: debug=0xc serial=0 cpus=8 keepsyms=1 -enable_kprintf_spam -noprogress
    rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1
    wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1
    sweetfb_noconsole=1 sweetfb_hz=60 sweetgpu=2 sweetpmem=1 sweetsmmuprobe=1
    sweetsmmuwlan=1 sweetwifi=1 sweetfiles=1 sweetusb=2 sweetgpu_reboot=120

payload-0101s0reboot.bin 16.663.456
  virt_base 0xfffffe0006000000 entry 0xfffffe0007490488
  adt_off 0xfe11b0 adt_size 12772 kernel_end 0xfffffe00084d8000
  cmdline: ... sweetfb_hz=60 sweetgpu=2 sweetgpu_reboot=90

payload-branch-reboot.bin 16.989.856
  virt_base 0xfffffe0006000000 entry 0xfffffe00074a1488
  adt_off 0x1030c00 adt_size 12960 kernel_end 0xfffffe0008588000
  cmdline: ... sweetfb_hz=30 sweetgpu=2 sweetusb=2 sweetfiles=1 sweetpmem=1
    sweetsmmuprobe=1 sweetsmmuwlan=1 sweetwifi=1 sweetgpu_reboot=120
```

**Discrepancia crítica:** los args del `payload-super.bin` actual tienen **346 caracteres**; la línea `boot-args` de la ring tiene **302** y termina en `sweetwifi=1` (sin `sweetfiles`, `sweetusb`, `sweetgpu_reboot`). No es truncamiento de launchd: el log de la rama imprime 346 caracteres completos (`logs/xnu-wifi-boot.txt:419`). Por tanto la ring es de un build super **anterior** al payload actual, con el mismo núcleo 0104/0105 y menos args. [INF]

### 4.3. Los segmentos del payload son el kernel exacto

Comparación SHA256 por segmento (payload vs kernel file), primeros 16 hex:

```text
payload-super.bin vs xnu/out-0105/kernel.development.sweet
  __TEXT           7b29c5172dd2b427  MATCH
  __DATA_CONST     ac2bf221c4c448c0  MATCH
  __TEXT_EXEC      1b65e3882383db6a  MATCH
  __KLD            29cd8e6baedcea73  MATCH
  __LASTDATA_CONST c26820e8331a75ef  MATCH
  __KLDDATA        ae89bf83bbdf6fe8  MATCH
  __DATA           d2057d1f331743b0  MATCH
  __BOOTDATA       094d14209deb3c47  MATCH
  __LINKINFO       a52e7e60f0c8dcac  MATCH
  __LINKEDIT       fead62181bff46d1  MATCH

payload-0101s0reboot.bin vs xnu/out-0101/kernel.development.sweet
  __TEXT           5c99ae01fd6f8a25  MATCH
  __TEXT_EXEC      37b096179e69ffd9  MATCH
  ... (todos MATCH)

payload-branch-reboot.bin vs DC28088-kernel/kernel.development.sweet
  __TEXT           c8592aa27d66      MATCH
  __TEXT_EXEC      530a7cec456f      MATCH
  ... (todos MATCH)
```

Esto prueba que las tres imágenes son reproducibles desde sus kernels/ADTs, y que el `payload-super.bin` actual **sí** es `out-0105` + `sweet-wlan.adt`. No prueba que esa imagen se haya booteado.

### 4.4. GPU viva: extracto literal

`logs/xnu-super-panic.txt:403-409`:

```text
SWEET GPU: cx gdsc 0xf8222000 gx gdsc 0xf8222000
SWEET GPU: gfx3d cfg 0x101 dcvs perf 0x30000006 return 0
SWEET GPU: gmu init 0xbabeface rbbm 0x1 sqe base 0x10000000 rptr 0x10 wptr 0x10
SWEET GPU: CP_MEM_WRITE from XNU -> 0x5ee7c0de rptr 0x15 status 0x1 *** GPU ALIVE UNDER XNU ***
SWEET GPU: selftest: ib 10aed0000@40000000 dst 10aec4000@40010000 fence 1 done 1 dst adee0618 *** IB FROM XNU MEMORY RAN ***
SWEET GPU: Adreno 618 handed to RedwoodGPU (wptr 30 rptr 30 rbbm 00000001)
SWEET GPU: adreno start -> 0
```

Lectura:

- `cx/gx gdsc=0xf8222000`: ambos rails leídos on (el mismo valor es el registro de GDSC; no distingue CX/GX, pero el driver lo usa como “on”).
- `gfx3d cfg 0x101`: el bloque GFX3D está encendido y el `gfx3d` clock configurado; `dcvs perf 0x30000006` es el voto de perf (índice 4/430 MHz según la serie 0099).
- `gmu init 0xbabeface`: `INIT_RESULT` del GMU; `rbbm 1`: `RBBM_STATUS`; `sqe base 0x10000000`, `rptr/wptr 0x10`: ring del CP en la base que dejó el shim.
- `CP_MEM_WRITE ... 0x5ee7c0de rptr 0x15 status 0x1`: XNU **añadió** un comando al ring que el shim dejó y el CP lo ejecutó (rptr avanzó de 0x10 a 0x15).
- `selftest ib 10aed0000@40000000`: IB construida en memoria **de XNU** (física `0x10aed0000`), mapeada en GPU VA `0x40000000`; `dst 10aec4000@40010000`: buffer destino en otra página de XNU (VA `0x40010000`); `fence 1 done 1 dst adee0618`: el CP escribió `0xadee0618` y el fence 1 se completó. Esto valida page tables del GPU SMMU, privilegio de ring/IB y el mecanismo de fence.
- `handed to RedwoodGPU (wptr 30 rptr 30)`: el ring del shim está drenado; `adreno start -> 0`: `RedwoodGPU::start` OK.

**Lo que no prueba:** que la GPU funcione bajo carga (Mesa/eagl/backboardd). En este boot no hubo ninguna submission después del selftest: `0 swaps`, `0 presents`, `GPU 0 ms pending (fence 1)`, `1 surfaces`, `0 MB wired`. La GPU quedó idle.

### 4.5. RPMh, SMMU y batería: extractos

RPMh (`:155-206`):

```text
SWEET RPMH: rsc=0x18220000 tcs=0x18220d00 DRV=2 id=0x10100 solver=0x4010100 config=0x80008104 TCS=8 ncpt=16
SWEET RPMH: cmd-db locator=0xc3f000c pa=0x85f20000 size=0x1078
SWEET RPMH: cmd-db version=0x1 magic=0xc0330db checksum=0 flags=0
SWEET RPMH: MC0 addr=0x50000 slave=5 aux=8@0x838 version=0x1000 priority=0x1540010:0
SWEET RPMH: TCS0 done=1 irq=0x1 idle=0x1 control=0x1010000 status0=0x10101
SWEET RPMH: BCM MC0 addr=0x50000 vote 0x6fffffff -> 0
...
SWEET DDR: memory bandwidth vote 16383: MC0 0, SH0 0, ACV 0
...
SWEET SMMU: votes SN15=0 CN0=0
```

SMMU (`:396-402`):

```text
SWEET SMMU: sCR0=0x230406
SWEET SMMU: ID0=0x4c017e4f ID1=0x6000003d ID2=0x5555: 79 SMRs, 61 context banks
SWEET SMMU: pmem-path ID0=0x4c017e4f
SWEET SMMU: WLAN 0x240/0x1 -> CB4 via SMR6: SMR 0x80010240 S2CR 0x4 SCTLR 0xe0 CBAR 0x1f000 -> ok
SWEET SMMU: MDSS SMR5 0x84400800 S2CR 0x3 -> CB3 CBAR 0x1f000 CBA2R 0x1 SCTLR 0xe0 TTBR0 000000000 TCR 0 TCR2 0x34077 MAIR 0,0 FSR 0x400 FAR 0x111c5bf9df3bd
SWEET SMMU: MDSS 0x800/0x440: 1 matching SMRs
```

Batería (`:103-106`):

```text
SWEET BATTERY: QG SDAM b640: 00 01 4f 00 04 00 01 3a 39 01 00 00 54 3b 43 00
SWEET BATTERY: seed 58% from QG SDAM (curve 60%)
SWEET BATTERY: 58% (curve 60%) 4031mV ocv 3995mV 240mA external=1 charging=1 full=0
SWEET BATTERY: PM6150 / estimated SOC, 58% 4031mV external=1 charging=1
```

RTC (`:80`):

```text
SWEET RTC: calendar set from the PM6150 RTC: 53464448 s (boot time now 53464448)
```

`53464448` s desde epoch = 1971-09-11, no 2026. El guard de 0104 solo rechaza `<86400` y `now>978307200` (2001) antes de leer; acepta 1971. La rama tiene el mismo comportamiento (`logs/xnu-wifi-boot.txt:84`: 53.371.308 s) y bootea, así que **no es la causa del panic**, pero invalida timestamps de launchd/cache y la lógica de “already started in this boot” de wland.

### 4.6. `launchd_cache_loader`: bueno vs super

Bueno (rama, `logs/xnu-wifi-boot.txt:663-676`):

```text
exec launchd_cache_loader
0 Found valid port: 2563 Valid: 1
1 Found valid port: 0 Valid: 0
2 Found valid port: 0 Valid: 0
Using default cache paths
Code: /System/Library/xpc/launchd.plist Sig: /System/Library/xpc/launchd.plist.sig
Using unsecure cache: /System/Library/xpc/launchd.plist
Trying to send bytes to launchd: 2563 16384
Sending validated cache to launchd
Cache sent to launchd successfully
com.apple.xpc.launchd|... <Notice>: launchd UUID: 5C15DB07-B3BC-3DF3-B62F-3E498B993B8E
com.apple.xpc.launchd|... (boot) <Notice>: Early boot complete. Continuing system boot.
exec xpcproxy
...
exec SpringBoard
```

Super (`logs/xnu-super-panic.txt:584-589`):

```text
com.apple.xpc.launchd|1969-12-31 16:00:45.086321 (launchd_cache_loader) <Notice>: Doing boot task
[System Event] [865661843] [INFO] [Subsystem: launchd] [Event: launchd_cache_loader] Doing boot task
exec launchd_cache_loader
SWEET FPS: 0 swaps in 1000 ms ... GPU 0 ms pending (fence 1); 1 surfaces ...
SWEET FPS: 0 swaps in 1001 ms ... GPU 0 ms pending (fence 1); 1 surfaces ...
SWEET FPS: 0 swaps in 1001 ms ... GPU 0 ms pending (fence 1); 1 surfaces ...
```

No hay `0 Found valid port`, ni `Using default cache paths`, ni `Cache sent`, ni UUID, ni `Early boot complete`, ni `xpcproxy`, ni `SpringBoard`. La ring sigue 23 líneas más (~23 s). El helper **no imprimió ni su primera línea**. Eso es el hecho más discriminante de todo el frente.

### 4.7. Procedencia de la ring (por qué no se puede confiar en el nombre)

1. `logs/xnu-super-panic.txt` y `logs/xnu-0101s0reboot.txt` son byte-idénticos: 50.094 B, SHA256 `576cdb1aca91c3975ce4c2bcfcea0360abc2d43eaed55894462c050d2ffeb99f`.
2. La ring contiene `flame wlan: /dev/wlan ready` (`:208`), `SWEET PMEM` (`:154`), `SWEET SMMU: WLAN` (`:400`), `SWEET BATTERY: seed` (`:104`). Esas strings **no existen** en `xnu/out-0101/kernel.development.sweet` (0 ocurrencias) ni en `payload-0101s0reboot.bin`; sí en `out-0105` y `payload-super.bin`.
3. Los args de la ring son 302 chars; el `payload-super.bin` actual tiene 346 (con `sweetfiles=1 sweetusb=2 sweetgpu_reboot=120`). El log de la rama imprime 346 sin truncar. Por tanto la ring es de un **super build anterior** con menos args, no del `shim-boot-super.img` actual.
4. El `.shim.txt` (6.040 B, SHA `3703a528…`) es idéntico a todos los `.shim.txt` recientes y contiene `LOADER no SWEETXNU payload`, `PLOG ufs=00000000`, `GPU probe done, back to fastboot in 10 s`. Es un log de **probe-only** (`SHIM_GPUPROBE` sin payload), no de un boot XNU; el bloque `plog` de `shim.c` está después de `loader_boot` y no se ejecuta en `SHIM_GPUBOOT`. No describe el boot.
5. Conclusión: la ring es de **algún** boot que cargó un kernel 0104/0105 y llegó a launchd; el nombre “super-panic” es una etiqueta, no una prueba de que el artefacto `67ff470f…` se haya booteado. La frase del panic es del usuario, no del artefacto.

### 4.8. Kernel strings: topaz vs NativeAdreno

Conteo de bytes en los payloads/kernels (Python, sin escribir):

| String | 0101 | 0105/super | branch |
|---|---:|---:|---:|
| `SWEET GPU: CP_MEM_WRITE` | 1 | 1 | 0 |
| `IB FROM XNU MEMORY` | 1 | 1 | 0 |
| `SWEET GPU: adreno start` | 1 | 1 | 0 |
| `NativeAdreno` | 0 | 0 | 257 |
| `flame wlan: /dev/wlan` | 0 | 1 | 1 |
| `SWEET SMMU: WLAN` | 0 | 4 | 4 |
| `SWEET PMEM` | 0 | 9 | 9 |
| `RedwoodWLAN` | 0 | 32 | 32 |
| `SWEET BATTERY: seed` | 0 | 1 | 1 |
| `MiniIONetworkStack` | 0 | 5 | 5 |

Esto demuestra que el super **no** arrastró NativeAdreno y que la rama **no** tiene el selftest topaz. La rama usa NativeAdreno (257 referencias) y su GPU es la que en nuestro root daba “red clock / CPU-like” (`NOTES.md:186-187`).

---

## 5. Observado vs inferido vs desconocido

### 5.1. Observado (artefacto)

| # | Hecho | Fuente |
|---|---|---|
| O1 | Ring 50.094 B, 609 líneas (Measure-Object), SHA `576cdb1a…`; 64 líneas `SWEET FPS` | `logs/xnu-super-panic.txt`; `Get-FileHash` |
| O2 | `xnu-0101s0reboot.txt` idéntico byte a byte | SHA |
| O3 | Todos los `.shim.txt` recientes idénticos, con `LOADER no SWEETXNU payload` | SHA/contenido |
| O4 | Boot-args de la ring: 302 chars, Hz 60, `sweetgpu=2 sweetpmem=1 sweetsmmuprobe=1 sweetsmmuwlan=1 sweetwifi=1`, sin usb/files/reboot | `:328` |
| O5 | Payload super actual: 346 chars, con usb/files/reboot | parser del payload |
| O6 | GPU selftest completo, IB desde XNU, fence 1 | `:403-409` |
| O7 | CPU 8/8, SGI1, PSCI OK | `:69-97` |
| O8 | AppleCLCD 1080x2400 stride 4320 @0x9c000000, presentado 1125x2436 | `:75-77` |
| O9 | `/dev/pmem` major 19, `/dev/wlan` major 20 | `:154`, `:208` |
| O10 | RPMh MC0/SH0/ACV/SN15/CN0, DDR 16383 | `:155-206` |
| O11 | SMMU 79 SMR/61 CB; WLAN CB4/SMR6; MDSS CB3 | `:396-402` |
| O12 | Batería 58% seed SDAM, 4031 mV, 240 mA | `:103-106` |
| O13 | RTC 53.464.448 s (1971) | `:80` |
| O14 | launchd llega a `exec launchd_cache_loader`; 23 FPS después; sin líneas del helper | `:586-609` |
| O15 | 0104: 4.578 inserciones/58 borrados/22 archivos; 0105: 70/0/3 | diffstat del patch |
| O16 | Payloads = kernels out-0105/out-0101/DC28088 (segmentos MATCH) | §4.3 |
| O17 | ADT wlan = gpupool + nodo `/arm-io/wlan` + random seed | `adt.py dump`/`Compare-Object` |
| O18 | Super kernel no tiene `NativeAdreno`; branch sí (257) | strings |

### 5.2. Inferido (mecanismo explícito)

| # | Inferencia | Base | Fuerza |
|---|---|---|---|
| I1 | La ring es de un super build anterior, no del artefacto actual | args 302 vs 346 + strings 0104 | Alta |
| I2 | El `.shim.txt` no es de este boot | `plog` solo en `SHIM_GPUPROBE`; hash idéntico | Alta |
| I3 | El panic no es de GPU | selftest OK; 0 submissions después; namespace reportado no es GPUPANIC | Alta |
| I4 | El panic no es de Wi-Fi directo | `/dev/wlan` no se abrió; no wland/wifid/en0 | Alta |
| I5 | `launchd_cache_loader` se bloquea antes de su primera línea | 23 s sin `Found valid port`; el bueno lo imprime en 0 ms | Alta |
| I6 | La ventana de 23 s es compatible con timeout de boot task, no con muerte instantánea | 23 × 1 s; `code 0x1` reportado | Media |
| I7 | El nodo wlan cambia el job set de launchd (wifid elegible) | donor `adt-add-wlan.py:2-7` | Alta |
| I8 | El nodo wlan **solo** no explica el fallo, porque la rama con el mismo nodo/root bootea | `xnu-wifi-boot.txt:663-676` | Alta |
| I9 | El delta real es 0104/0105 vs la rama completa (o una diferencia de base) | super = 0101 base + 0104/0105; rama = full DC28088 | Alta |
| I10 | El RTC 1971 no es la causa (la rama lo tiene y bootea), pero puede amplificar timestamps/cache | `xnu-wifi-boot.txt:84` | Media |
| I11 | El topaz está inicializado pero no ejercitado bajo CA | 0 swaps/0 presents/1 surface | Alta |
| I12 | El Wi-Fi kernel-side está listo pero el userland no arrancó | `/dev/wlan` creado; sin open/en0 | Alta |

### 5.3. Desconocido (no verificado)

| # | Desconocido | Por qué importa |
|---|---|---|
| D1 | Si `shim-boot-super.img` (SHA `67ff…`) bootea y reproduce el fallo | La ring actual no lo prueba; el `.shim.txt` no sirve |
| D2 | El kernel exacto que escribió la ring (hash/CI) | Solo sabemos “0104/0105-like” por strings |
| D3 | El texto literal del panic | Solo reporte humano; no está en la ring; el formato `-- code 0x1` no coincide con `kern_exit.c` de 8796 |
| D4 | Si el helper murió, hangueó o nunca llegó a `main` | No hay `CRASH launchd_cache_loader` ni línea del helper |
| D5 | Qué syscall/port/IPC usa el helper antes de `Found valid port` | `launchd_cache_loader` es closed source; no hay traza |
| D6 | Si launchd salió por SIGFPE, exit(1) o timeout | namespace 2/subcode 8 sugiere señal 8; `code 0x1` sugiere exit 1; no cuadra |
| D7 | Si el root actual es el mismo que el del boot de la ring | La ring no inventaría el disco; el root se mutó in-place |
| D8 | Si el fallo se reproduce con el kernel super actual y args completos | No hay boot documentado |
| D9 | Si la rama tiene un parche requerido que el super no importó (0121, 0155, 0167/0177/0178, 0179…) | La rama bootea; el super no |
| D10 | Si el AKS 0x4/sls 0 o el wrap/unwrap cambian el estado que ve launchd | keybagd sí funcionó; launchd no se trazó |
| D11 | Si el `sweet_smmu_probe_thread` o el poll de batería (5 s) interfieren con launchd | Coincidencia temporal; no hay traza |
| D12 | El epoch correcto del RTC PM6150 | 1971 es implausible; la rama lo acepta |

---

## 6. Intentos fallidos y callejones sin salida

1. **0104 primer link (CI 41494548855):** falló con exactamente siete undefined: `sweet_bt_init`, `sweet_haptic_init`, `sweet_native_adreno_reserve_pool`, `sweet_gpu_probe`, `sweet_vfs_mkdir`, `sweet_vfs_symlink`, `sweet_vfs_unlink`. Se resolvió con 0105 (`sweet_super_compat.c` + wrappers VFS). [OBS] `NOTES.md:208-214`.
2. **CI 41498675277 (0105) cancelado:** runner macOS arm64 sin capacidad; se cambió a `macos-15-intel` (mismo Xcode 16, cross-compila arm64). [OBS] `NOTES.md:216-222`, `.github/workflows/xnu.yml:37-41`.
3. **Branch Metal bundle en el root topaz:** `SweetMetal2.bundle` + `CA_FORCE_TIMER=1` en backboardd → UI glitcheada (líneas verdes, sin blur), el scan de Wi-Fi se paró; revertido. [OBS] `NOTES.md:190-194`.
4. **Branch kernel + root topaz:** Wi-Fi + batería, pero GPU NativeAdreno lenta (“red clock”, CPU-like); no sirve para el objetivo. [OBS] `NOTES.md:186-187`.
5. **`0101s0reboot` “control”:** su log es byte-idéntico a la ring super; no hubo ring nueva. El boot no escribió la zona (no llegó a XNU, no llegó a UFS rw, o el ABL estaba colgado). No es evidencia de reproducibilidad. [OBS] SHA.
6. **`.shim.txt` como diagnóstico:** todos idénticos; `LOADER no SWEETXNU payload` es de un probe-only con ramdisk vacío, no del boot actual. Perseguir el “initrd handoff” con este archivo es un falso positivo. [INF] `shim/shim.c:398-412`, `shim/plog.c:20`.
7. **Interpretar `0 swaps` como fallo de display:** no; backboardd nunca arrancó. El display está registrado y el vsync corre. [OBS]/[INF].
8. **Interpretar la ring como “0101s0 + Wi-Fi”:** el kernel 0101 no contiene los strings 0104; la ring no puede ser de ese payload. [OBS] strings.
9. **`0103 ca_vbl=1`:** peor FPS (6,82 vs 17,19 swaps/s); descartado; no tiene relación con este frente. [OBS] `NOTES.md:160-167`.
10. **`gh run view`:** HTTP 404 con el repo actual; los IDs de CI no se pudieron re-verificar. No asumir que el artefacto local `out-0105` vino de ese run solo por el nombre. [OBS] comando.
11. **`HANDOFF.md`:** no está en `ios-sweet/`; el de la carpeta padre está prohibido. No se pudo leer. [OBS] `Test-Path`/listado.

---

## 7. Hipótesis abiertas

| ID | Hipótesis (prior) | Mecanismo | A favor / en contra | Test decisivo |
|---|---|---|---|---|
| **H1** | `launchd_cache_loader` se bloquea en un timeout de boot task (0,40) | El helper no llega a `Found valid port`; espera un puerto/servicio. A los ~20-30 s launchd considera la task fallida y sale 1; XNU paniquea por `initproc`. La ventana de 23 s encaja. | **+** 23 s sin líneas; el helper bueno imprime en 0 ms; `code 0x1`. **−** sin traza; namespace 2/subcode 8 no encaja con un timeout limpio. | Ring nueva con `sweetiolog=launchd_cache_loader,launchd` y `sweetsample=...`; `serial=3` 60 s; foto del panic. |
| **H2** | El cambio IOKit quiesce/busy de 0104 rompe el bootstrap (0,20) | `IOStartIOKit.cpp` ya no retiene el registry (`if (false)`); `IOService.cpp` no hace `adjustBusy(-1)`. Busy count desbalanceado o registry “quiet” demasiado pronto → `waitForService`/quiesce cuelga. | **+** el fallo ocurre al publicar servicios; 0104 toca ese código; la rama tiene 0123/0136 y funciona. **−** el helper imprime la primera línea antes de IOKit (probable); no hay traza de `getBusyState`. | Revertir el bloque IOKit de 0104 (volver a `OSKext::iokitDaemonAvailable()` + `adjustBusy(-1)`), mismo root/ADT/args. |
| **H3** | Falta un parche de la rama que el super no importó (0,15) | La rama completa bootea con el mismo root/ADT; el super es un subconjunto. Un parche no importado (0121 trust-cache/ExtensionKit, 0155 skywalk, 0167/0177/0178 scheduler, 0179 latency) sería necesario para el cache loader. | **+** mismo root/nodo bootea en la rama; el super carece de ~20 parches. **−** casi todos son GPU/display/perf; 0121 es el único de userland temprano. | Diff rama vs super; boot del super + 0121; luego + 0155; aislar el mínimo. |
| **H4** | AKS 0x4/sls 0 o wrap/unwrap alteran a launchd (0,10) | 0104 cambia `SWEET_AKS_LOCK_STATE` 0x6→0x4, `sls` 3→0 y añade wrap/unwrap. Si launchd consulta AKS y ve “locked” o un blob distinto, espera o trap. | **+** 0104 toca AKS; keybagd corre antes; namespace 2/subcode 8 podría ser un trap de userland. **−** keybagd sel 0/14 = 0; la rama tiene lo mismo y bootea. | Kernel con 0x6/sls 3 y otro con wrap/unwrap off. |
| **H5** | El poll de batería (5 s) o el hilo SMMU compiten con launchd (0,05) | Timer de batería cada 5 s (SPMI) + hilo SMMU a 1 s (`ml_io_map`/TLB). Un lock de SPMI/IOPMPowerSource podría bloquear a launchd a los ~20 s. | **+** la ventana coincide con ~4 polls; el super añade el poll de 5 s. **−** la rama bootea con el mismo poll; no hay fallo SPMI. | `sweetbattery=0` y `sweetsmmuprobe=0`, en boots separados. |
| **H6** | El nodo `/arm-io/wlan` hace cargar wifid y el cache loader se atasca (0,05) | Sin nodo wifid no es elegible; con nodo launchd debe incluirlo en el cache. Si el binario/plist de wifid falta o el cache se reconstruye mal, el helper falla. | **+** único cambio de ADT; el fallo es en el cache loader. **−** la rama con el mismo nodo/root bootea y ejecuta wifid. | Super + `sweet-gpupool.adt` vs super + `sweet-wlan.adt`, misma ring/tag. |
| **H7** | El texto del panic es compuesto o de otro boot (0,05) | El usuario combinó la línea de la boot task (`code 0x1`) con el panic de initproc; `-- code 0x1` no pertenece al formato de `panic_with_options` de 8796 (`... description: %s`). | **+** la ring no contiene el texto; el formato no coincide; el caso AMFI ya nombró al helper. **−** el usuario reporta `initproc exited` explícito. | Foto/video del panic; comparar con `kern_exit.c` del build. |
| **H8** | El kernel super actual ni siquiera booteó (0,05) | El boot de las 18:28 falló antes de XNU (ABL/DTB/initrd); la ring es de un boot anterior y el “panic” es de ese boot. | **+** args 302 vs 346; `.shim.txt` viejo; no hay ring nueva. **−** la ring contiene 0104 y llega a launchd. | Boot del artefacto actual con tag único y ring nueva. |

### 7.1. Regla de decisión

1. Primero **H8/H1**: ring nueva del artefacto actual (tag en cmdline, SHA registrado). Sin eso, todo lo demás es arqueología.
2. Si se reproduce el silencio de `launchd_cache_loader`: **H1/H2/H3** con A/B de IOKit, AKS y parches de rama.
3. Si la ring nueva pasa el cache loader y llega a SpringBoard: el “panic” era de la imagen vieja y el frente GPU/Wi-Fi sigue.
4. H4/H5/H6 solo después de descartar H2/H3; son baratos con boot-args, pero menos probables.

---

## 8. Inventario de archivos

### 8.1. Kernel / parches

| Archivo | Tamaño | SHA256 (si aplica) | Rol |
|---|---:|---|---|
| `xnu/patches/0104-super-wifi-battery.patch` | 179.108 | `8cc3eafa…e17673` | Wi-Fi/batería/PMEM/RPMH/SMMU/IOKit |
| `xnu/patches/0105-super-link-fix.patch` | 2.515 | `88f89b23…ca2376` | compat GPU/BT/haptic + VFS |
| `xnu/out-0105/kernel.development.sweet` | 17.382.896 | `d22c5aad…7c1793` | kernel super |
| `xnu/out-0101/kernel.development.sweet` | 17.272.256 | `d2bbc4dc…fd68c5` | kernel daily |
| `xnu/out-0105/SHA256SUMS` | 91 | — | hash del kernel |
| `xnu/out-0101/SHA256SUMS` | 91 | — | hash del kernel |
| `.github/workflows/xnu.yml` | — | — | build macOS 13.5/SWEET/DEVELOPMENT, `macos-15-intel` |
| `xnu/README.md` | 594 | — | build/provenance |

### 8.2. Imágenes / payloads / ADT

| Archivo | Tamaño | SHA256 | Rol |
|---|---:|---|---|
| `shim/out/shim-boot-super.img` | 17.494.016 | `67ff470f…b5f3f` | super actual (no probado) |
| `shim/out/payload-super.bin` | 16.757.888 | `8201e7de…d7bfe` | out-0105 + sweet-wlan |
| `shim/out/shim-boot-0101s0reboot.img` | 17.399.808 | `e0be26fc…a7949c` | daily 0101 |
| `shim/out/payload-0101s0reboot.bin` | 16.663.456 | `b1a21ba8…2efafe` | out-0101 + gpupool |
| `shim/out/shim-boot-branch-reboot.img` | 17.723.392 | `833b199c…6821f9` | rama DC28088 |
| `shim/out/payload-branch-reboot.bin` | 16.989.856 | `ff6fef04…42584f` | DC28088-kernel + sweet-wlan |
| `shim/out/sweet-wlan.adt` | 12.960 | `994c8cac…16db5f` | ADT super con `/arm-io/wlan` |
| `shim/out/sweet-gpupool.adt` | 12.772 | `a8f78c1a…8454ae` | ADT daily, pool GPU |
| `shim/out/sweet-local.adt` | 12.772 | — | copia local |
| `shim/out/check-super/` | — | — | unpack de la super |
| `shim/out/check-0101s0reboot/` | — | — | unpack del control |
| `shim/out/check-branch-reboot/` | — | — | unpack de la rama |

### 8.3. Logs

| Archivo | Tamaño | SHA256 | Uso |
|---|---:|---|---|
| `logs/xnu-super-panic.txt` | 50.094 | `576cdb1a…eb99f` | ring “super” (procedencia dudosa) |
| `logs/xnu-0101s0reboot.txt` | 50.094 | idéntico | duplicado del anterior |
| `logs/xnu-super-panic.txt.shim.txt` | 6.040 | `3703a528…` | probe-only viejo |
| `logs/xnu-0101s0reboot.txt.shim.txt` | 6.040 | idéntico | ídem |
| `logs/xnu-wifi-boot.txt` | 575.997 | — | boot rama con Wi-Fi; cache loader bueno |
| `logs/wland-connected.log` | 111.945 | — | WCN3990 join `casa j`, 833 RX |
| `logs/xnu-0101s0-freeze.txt` | 352.741 | — | cache loader bueno (hermano) |
| `logs/xnu-0102-freeze.txt` | 348.752 | — | cache loader bueno |
| `logs/xnu-0103p.txt` | 557.479 | — | `ca_vbl=1` peor; no usar |

### 8.4. Notas hermanas

| Archivo | Tamaño | Relación |
|---|---:|---|
| `notes/agents/root-launchd-panic.md` | 62.073 | root/launchd/panic; corregida en §1.4/§4.7 |
| `notes/agents/wifi-battery-branch.md` | 64.241 | Wi-Fi/batería/rama; su H1 (initrd) es falso positivo |
| `notes/agents/usb-vfs-super-compat.md` | 73.700 | 0105/VFS/USB file server |

---

## 9. Próximos pasos condicionales

> Ningún paso de esta sección se ejecutó. Son instrucciones para el agente/usuario que sí puede tocar el teléfono, con la autorización correspondiente. No usar `fastboot getvar`; no flashear sin confirmación; no reutilizar logs viejos.

### 9.1. Fase 0 — obtener evidencia válida del artefacto actual (bloqueante)

1. Añadir un **tag único** al cmdline del super, p. ej. `sweetrun=super-YYYYMMDD-HHMM`, y reconstruir con `tools/sweet-gpu-image.sh` o el watcher. El tag debe aparecer en `launchd` (`boot-args = …`) y en la ring.
2. Registrar en la nota: SHA256 del `.img`, SHA256 del kernel, cmdline completo (longitud), hora, y el resultado de `cmp` ramdisk vs payload.
3. Bootear **solo** ese artefacto; esperar 5 min (no 30 s) antes de concluir. Si no vuelve a fastboot, usar el watchdog/recovery habitual.
4. Pull de la ring; comprobar que el `boot-args` de la ring contiene el tag. Si no, la ring es vieja: **no analizarla**.
5. Foto/video del panic si ocurre; el texto completo es la evidencia que falta.

**Criterio de éxito:** ring nueva, tag presente, línea `boot-args` con 346 chars (o los que tenga el build), y o bien `exec SpringBoard`, o bien el punto exacto de bloqueo.

### 9.2. Fase 1 — A/B del nodo wlan y del kernel

| Test | Imagen | ADT | Args | Qué discrimina |
|---|---|---|---|---|
| T1 | super actual | `sweet-wlan.adt` | completos | baseline; ¿reproduce? |
| T2 | super actual | `sweet-gpupool.adt` (sin wlan) | completos | ¿el nodo wlan/ job wifid es el trigger? |
| T3 | 0101 actual | `sweet-wlan.adt` | `sweetgpu=2 sweetfb_hz=60` | ¿0104 es necesario para el fallo? |
| T4 | super actual | `sweet-wlan.adt` | `sweetwifi=0 sweetsmmuprobe=0 sweetsmmuwlan=0 sweetpmem=0` | ¿el bring-up Wi-Fi/SMMU/PMEM interfiere? |
| T5 | super actual | `sweet-wlan.adt` | `sweetbattery=0` | ¿el poll de batería interfiere? |
| T6 | super actual | `sweet-wlan.adt` | `sweetgpu=0` | ¿el init topaz interfiere? (poco probable) |

**Predicciones:**
- Si T2 bootea y T1 no: el nodo wlan (job wifid) es condición; el fix es hacer wifid no bloqueante o retrasar su carga.
- Si T3 bootea y T1 no: 0104 es condición; bisectar 0104 (IOKit vs AKS vs drivers).
- Si T4 bootea: el bring-up Wi-Fi/SMMU/PMEM es condición; probar cada flag por separado.
- Si T5 bootea: el poll de batería es condición; revisar el lock SPMI.
- Si T6 bootea: el init topaz es condición (raro; el mismo init funciona en 0101).

### 9.3. Fase 2 — bisectar 0104 si T1 falla y T2/T3 no discriminan

Orden propuesto (cada uno un kernel CI, un boot):

1. **IOKit**: revertir `IOStartIOKit.cpp` (`if (false)` → `OSKext::iokitDaemonAvailable()`) y `IOService.cpp` (`adjustBusy(-1)` restaurado). Mantener drivers Wi-Fi/batería.
2. **AKS**: restaurar `SWEET_AKS_LOCK_STATE 0x6` y `sls 3`; desactivar wrap/unwrap.
3. **SMMU/PMEM**: compilar sin `sweet_smmu_probe_start`/`sweet_pmem_init` (o con flags 0).
4. **Batería**: volver al poll de 30 s / static 100%.
5. **MiniIONetworkStack/RedwoodWLAN**: compilar sin publicar los servicios (solo `/dev/wlan`), para ver si el registry/IOKit es el problema.
6. **Rama**: importar 0121 (trust cache) o 0155 (skywalk) al super, uno por uno.

**Diagnóstico barato antes de cada build:** `sweetiolog=launchd_cache_loader,launchd` (0049) para ver qué servicios abre el helper; `sweetnull=launchd_cache_loader,launchd` (0048) para su stderr; `sweetsample=launchd_cache_loader,launchd` (0054/0055) para stacks si se cuelga (ajustar el primer sample; el default es 90 s, demasiado tarde).

### 9.4. Fase 3 — si el cache loader pasa

Si T1 o un bisect llega a `Early boot complete` y `exec SpringBoard`:
1. Medir `SWEET FPS`/swaps/presents; confirmar que backboardd abre AppleCLCD y que hay superficies.
2. Verificar el path Wi-Fi: `exec wland`, `flame wlan: open`, `en0`, `RedwoodWLAN`, `wifid`, `configd`, `bridge: join`.
3. Si el Wi-Fi asocia pero no hay DHCP, instalar el servicio estándar en `preferences.plist` (en0/AirPort/IPv4 DHCP/IPv6 Automatic), como en la rama (`NOTES.md:223-227`).
4. Si el GPU topaz no rinde bajo CA, volver al frente de superficies/eagl (0099/0100, rows 64B, glblit), no al kernel.

### 9.5. Fase 4 — higiene de artefactos

1. Renombrar `logs/xnu-super-panic.txt` a `logs/xnu-0104-unknown-provenance.txt` (o dejar una nota `README` en `logs/`) para que nadie lo cite como “el panic del super actual”. No editar `NOTES.md`; sí se puede añadir un `.md` en `logs/` si el dueño lo autoriza.
2. Archivar los `.shim.txt` viejos y dejar de generarlos en boots XNU (o hacer que `plog` se escriba también en `SHIM_GPUBOOT` antes del salto, con un magic distinto).
3. Añadir al `mkpayload.py`/`shim` un `sweetrun` tag automático (hash corto + timestamp) para que cada ring sea autoidentificable. Es la única forma de evitar la ambigüedad actual.

---

## 10. Preguntas para otra IA

1. **¿Qué syscall/port es el primero de `launchd_cache_loader` antes de `Found valid port`?** ¿`bootstrap_look_up`, lectura del plist o un `mach_msg` al cache port? ¿Hay timeout de 20/30 s en libxpc/launchd para una boot task? ¿Qué son “2563” y “7939” (nombre de servicio, `mach_port_name_t` o fd)?
2. **¿Cuál es el texto literal del panic y su formato?** `namespace 2` = `OS_REASON_SIGNAL`; `subcode 0x8` = señal 8 (SIGFPE) si el campo es `osr_code`. Pero `-- code 0x1` no aparece en `panic_with_options` de `kern_exit.c` (8796): ¿frase compuesta, kernel distinto o `code` = `rv`? ¿Qué ruta de launchd/libxpc emite SIGFPE en arm64?
3. **¿De qué boot es la ring?** Los strings son 0104/0105, pero los args son 302 chars (sin `sweetfiles/sweetusb/reboot`) y el payload actual tiene 346. ¿Existe un `kernel.development.sweet` con esos args en `out-*`/CI? ¿Se puede identificar por `LC_UUID` o por el `Darwin Kernel Version`?
4. **¿El nodo `/arm-io/wlan` cambia el job set/hash del launchd cache?** ¿`launchd_cache_loader` reconstruye el cache al cambiar el device tree? Si sí, ¿qué job (`com.apple.wifid`, `org.ios-sweet.wland`) puede hacer fallar la reconstrucción?
5. **¿El quiesce de IOKit de 0104 (`if (false)`, sin `adjustBusy(-1)`) deja el busy count desbalanceado o el registry “quiet” antes de tiempo?** ¿Puede el helper esperar `*QUIET*` y colgarse? ¿La rama usa 0123/0136 con una semántica distinta?
6. **¿El AKS 0x4/sls 0 y el wrap/unwrap son correctos para 16.7.16?** La rama bootea con ellos; el super también los tiene. ¿Hay una consulta de launchd antes de `Found valid port` que los interprete como “locked”?
7. **¿Qué parches de la rama no están en el super y afectan early launchd?** 0121 (trust cache/ExtensionKit), 0155 (skywalk privileges), 0167/0177/0178 (scheduler/affinity), 0179 (latency). ¿Alguno toca `posix_spawn`, bootstrap ports, Mach IPC o `IOService::waitForService`?
8. **¿El RTC PM6150 es un contador desde fabricación o desde epoch?** 53.464.448 s = 1971; la rama lo acepta y bootea, pero wland compara `/var/local/wland.boot`. ¿Cuál es el epoch correcto y cómo se fija en Android?
9. **¿El hilo SMMU (1 s) o el poll de batería (5 s) pueden tomar un lock que launchd necesita?** ¿Hay contención en `rh_lock`, `sweet_spmi` o `ml_io_map`? ¿La GPU topaz tiene algún worker que pueda bloquearse tras el selftest (fence 1, 0 swaps)?
10. **¿Cuál es el mínimo de args para reproducir el fallo?** ¿Basta el set de 302 chars (`sweetgpu=2 sweetpmem=1 sweetsmmuprobe=1 sweetsmmuwlan=1 sweetwifi=1`) o hacen falta `sweetusb/sweetfiles/reboot`? ¿Se puede obtener ring nueva sin reflash o con `ufsrw=0`?
11. **¿El `HANDOFF.md` de la carpeta padre (prohibido para este agente) tiene el estado del reflash y del root que esta nota no puede leer?** Si otro agente tiene acceso, debe cruzar ese estado con la ring; aquí no se pudo.

---

<!-- END -->
