# Build, CI, artefactos y reproducibilidad — iOS 16.7.16 en sweet

**Ámbito:** pipeline XNU, workflows/runners, matriz CI, descarga de artefactos, boot image v2, `tools/mkpayload.py`, `tools/unpack_bootv2.py`, `shim/build.sh`, flags, verificación, hashes, reconstrucción de las imágenes 0101/super/branch, fallos, integridad y riesgos de reproducibilidad.

**Fecha de este informe:** 2026-11-03 (hora local UTC+1; las horas de GitHub Actions se citan en UTC).

**Fuentes leídas:** `NOTES.md` (749 líneas), `HANDOFF.md` (no existe en el workspace), `.github/workflows/xnu.yml`, `.github/workflows/userland.yml`, `tools/mkpayload.py`, `tools/unpack_bootv2.py`, `tools/mkadt.py`, `tools/sweet-gpu-image.sh`, `shim/build.sh`, `shim/loader.c`, `shim/start.S`, `shim/gpufw.S`, `shim/shim.ld`, `xnu/README.md`, `xnu/patches/` (105 patches trackeados + 3 scripts), `xnu/out-0105/`, `xnu/out-0101/`, `shim/out/`, `dtb/boot_unpacked/`, `research/gpu-sweet/`, `research/ipsw-x/`, `git log/show/diff` y la API pública de GitHub Actions.

**Restricciones respetadas:** no se ejecutó ningún comando contra el teléfono (ni `fastboot`, ni `adb`, ni `boot`, ni `flash`), no se editó código, `NOTES.md` ni `HANDOFF.md`, no se hicieron commits/push, no se accedió a `D:\pablo\Downloads\CLAUDE\iOS on sweet`, y no se escribió fuera de este archivo. No se ejecutaron builds ni scripts que escriban; los hashes y estructuras se obtuvieron con lectura directa (`Get-FileHash`, `sha256sum`, `cmp`, `readelf`, `file`, parseo Python en memoria).

**Convención de honestidad:** cada afirmación va marcada como observada, inferida o desconocida cuando no es obvia. “Observado” significa que lo vi en un archivo, hash, API o salida de herramienta. “Inferido” significa que se deduce de esos datos pero no se ejecutó el paso. “Desconocido” significa que no hay evidencia suficiente.

---

## 1. Alcance y estado

### 1.1 Estado del frente build/CI

| Elemento | Estado | Evidencia |
|---|---|---|
| Kernel 0105 (super: Wi-Fi + batería + topaz GPU) | CI OK; artefacto descargado; imagen `shim-boot-super.img` construida | API run `41501352880`, `conclusion: success`; `xnu/out-0105/kernel.development.sweet` SHA256 `d22c5aad...`; imagen SHA256 `67ff470f...` |
| Kernel 0101 (base rápida topaz, sin Wi-Fi) | Artefacto local; imagen reboot reconstruida | `xnu/out-0101/kernel.development.sweet` SHA256 `d2bbc4dc...`; imagen `e0be26fc...` |
| Kernel branch (DC28088, NativeAdreno + wland) | Solo sobrevive dentro de `payload-branch-reboot.bin`; no hay `kernel.*` local | UUID `c09f67e0...`; banner `xnu-8796.141.3`; payload SHA256 `ff6fef04...` |
| Imagen branch reboot | Construida; idéntica a la imagen Wi-Fi auto salvo 2 bytes de cmdline | `cmp` de payloads: 2 bytes; `cmp` de imágenes: 21 bytes |
| Workflow principal | Migrado a `macos-15-intel` en `34e3a8f`; run OK | API: label `macos-15-intel`, runner `1000000061`, build 19m03s |
| Workflow paralelo `macos-latest` | Rama `ci-macos-latest`, run OK; artefacto NO descargado | API: run `41502238106`, label `macos-latest`, build 5m09s |
| `HANDOFF.md` | No existe en el workspace | `Get-ChildItem -Recurse -Filter HANDOFF.md` sin resultados; el handoff activo está en `NOTES.md` |

### 1.2 Qué cambia respecto al brief

Tres correcciones importantes, todas con evidencia:

1. **El repositorio real de los runs recientes no es `dipa-studio/ios-sweet`.** La API devuelve 404 para `https://api.github.com/repos/dipa-studio/ios-sweet/actions/runs/41501352880`, y 200 para `https://api.github.com/repos/limonetexd/ios-sweet-gpu/actions/runs/41501352880`. El remoto `mine` del workspace es `https://github.com/limonetexd/ios-sweet-gpu.git`; `origin` es `dipa-studio/ios-sweet`. El artifact `xnu-kernel` de 0105 se descargó del repo `limonetexd/ios-sweet-gpu`. `xnu/README.md` y `NOTES.md:357` todavía dicen `-R dipa-studio/ios-sweet`, lo cual es incorrecto para estos runs.

2. **El par `__LINKINFO 0xfffffe0008170000 0x4c000` / `__LINKEDIT 0xfffffe00081bc000 0x3cc000` no es del kernel 0105.** Corresponde a `payload-branch-reboot.bin` (segmentos 8 y 9). El kernel 0105 tiene `__LINKINFO 0xfffffe0008110000 0x4c000` y `__LINKEDIT 0xfffffe000815c000 0x3c0000`. El kernel 0101 tiene `__LINKINFO 0xfffffe00080d0000 0x4c000` y `__LINKEDIT 0xfffffe000811c000 0x3bc000`.

3. **El run 41501352880 construyó el árbol de `34e3a8f`, no el de `771481a`.** `771481a` es el commit que añade `0105-super-link-fix.patch`; `34e3a8f` es el commit posterior que cambia el runner a `macos-15-intel`. GitHub reporta `head_sha: 34e3a8f...`, y ese árbol contiene el patch 0105. El kernel descargado contiene los siete símbolos del fix (ver §4.3), así que el patch sí se aplicó y enlazó.

### 1.3 Qué NO está verificado aquí

- No se arrancó ninguna imagen en el teléfono. Todo lo que se dice de “bootea”, “Wi-Fi funciona”, “GPU” o “batería” proviene de `NOTES.md`/handoff, no de una prueba de este informe.
- No se descargó el artefacto del run `41502238106` (`macos-latest`); solo se inspeccionó su metadata. No hay hash de kernel ni UUID de esa build.
- No se leyó el log completo de CI (no se descargó el zip de logs); solo la metadata de runs/jobs/artifacts de la API y los archivos locales.
- No se ejecutó `mkpayload.py`, `build.sh`, `mkbootimg` ni `unpack_bootv2.py`; las estructuras se parsearon en memoria y los hashes se recalcularon.
- No se pudo verificar `HANDOFF.md` porque no existe en este árbol; si existe fuera del workspace, no se leyó por la restricción de zona.

---

## 2. Cronología

Horas UTC salvo que se indique “local”. La zona local del workspace es UTC+1 (archivos con mtime 18:24 local = 17:24 UTC del mismo día).

| Hora | Evento | Evidencia |
|---|---|---|
| 2026-10-15 | Origen del pipeline: `xnu.yml` construye xnu-8796 con `blacktop/darwin-xnu-build` en runner macOS; primeros runs `38638702083` etc. | `git log -- .github/workflows/xnu.yml`; `NOTES.md` |
| 2026-11-02 17:47:59 | Commit `5639176`: patch 0104 “super” (Wi-Fi WCN3990 + batería sobre topaz) | `git show 5639176 --stat`: 5059 líneas añadidas |
| 2026-11-02 17:48:04 | CI `41494548855` (run_number 34) sobre `5639176`, `macos-15`, attempt 2 | API run |
| 2026-11-02 18:04:07 | Job de 0104 arranca; `Build` falla a las 18:11:41; `Collect`/upload siguen por `if: always()` | API jobs; `NOTES.md:208-215` |
| 2026-11-02 18:14:28 | Commit `771481a`: patch 0105, fix de link con stubs BT/haptic/NativeAdreno y wrappers VFS | `git show 771481a --stat`: 92 líneas |
| 2026-11-02 18:14:32 | CI `41498675277` (run_number 35) sobre `771481a`, `macos-15` | API run |
| 2026-11-02 18:14:33 | Job creado, `runner_id: 0`, sin steps | API jobs: `steps: []` |
| 2026-11-02 18:29:35 | GitHub cancela el job por falta de runner arm64; el run queda `failure`/job `cancelled` | API; `NOTES.md:216-219` |
| 2026-11-02 18:31:12 | Commit `34e3a8f`: `runs-on: macos-15-intel` | `git show 34e3a8f` |
| 2026-11-02 18:31:16 | CI `41501352880` (run_number 36) sobre `34e3a8f`, `main` | API run |
| 2026-11-02 18:32:48 | Commit `61c27e9`: notas del outage y del retry | `git show 61c27e9` |
| 2026-11-02 18:36:43 | Commit `ced27dd` en rama `ci-macos-latest`: `runs-on: macos-latest` | `git show ced27dd` |
| 2026-11-02 18:36:47 | CI `41502238106` (run_number 37) por `workflow_dispatch`, rama `ci-macos-latest` | API run |
| 2026-11-02 18:38:44 | Commit `e1ce648`: notas “both queues still empty at 18:38Z” | `git log -1 e1ce648` |
| 2026-11-02 18:41:29 | Arranca el job Intel (10m13s de cola) | API job |
| 2026-11-02 18:41:53–19:00:56 | `Build` Intel: 19m03s | API job steps |
| 2026-11-02 18:46:53 | Arranca el job `macos-latest` (10m06s de cola) | API job |
| 2026-11-02 18:47:09–18:52:18 | `Build` `macos-latest`: 5m09s | API job steps |
| 2026-11-02 18:52:40 | Termina `41502238106`: `success` | API run |
| 2026-11-02 19:01:16–19:01:30 | `Collect` y upload de `xnu-kernel` Intel | API job steps |
| 2026-11-02 19:02:04 | Termina `41501352880`: `success`; artefacto creado 19:01:40 | API run/artifacts |
| 2026-11-03 18:24:41 local | `xnu/out-0105/` extraído (mtime); ~22.4 h después del run (19:01Z del 2) | mtime; contenido |
| 2026-11-03 18:24:46 local | `payload-super.bin` | mtime; hash |
| 2026-11-03 18:24:51 local | `shim-boot-super.img` y `check-super/` | mtime; hash |
| 2026-11-03 18:29:51–18:29:55 local | `payload-0101s0reboot.bin`, `shim-boot-0101s0reboot.img`, `check-0101s0reboot/` | mtime; hash |
| 2026-11-03 18:35:10–18:35:15 local | `payload-branch-reboot.bin`, `shim-boot-branch-reboot.img`, `check-branch-reboot/`; `shim-boot.img` y `ramdisk.bin` quedan apuntando al branch | mtime; hashes idénticos |

La cronología muestra un patrón claro: el 2 de noviembre se construyó el kernel; el 3 de noviembre se ensamblaron las imágenes localmente. El `xnu/out-0105` no es una compilación local: su `linkarguments` contiene rutas `/Users/runner/work/ios-sweet-gpu/ios-sweet-gpu/dxb/...`, lo que prueba que viene del runner de GitHub.

---

## 3. Pipeline

### 3.1 Disparadores, runner y matriz

`.github/workflows/xnu.yml`:

```yaml
on:
  workflow_dispatch:
    inputs:
      macos_version:  default "13.5"
      kernel_config:  default "DEVELOPMENT"
      machine_config: default "SWEET"
      keep_going:     default "true"
  push:
    branches: [main]
    paths:
      - "xnu/patches/**"
      - ".github/workflows/xnu.yml"

concurrency:
  group: xnu-${{ github.ref }}
  cancel-in-progress: true

env:
  DXB_REPO: https://github.com/blacktop/darwin-xnu-build
  DXB_SHA: 663906528d1cd5ea8fde7de6f16de73db9511549
  MACOS_VERSION: ${{ inputs.macos_version || '13.5' }}
  KERNEL_CONFIG: ${{ inputs.kernel_config || 'DEVELOPMENT' }}
  MACHINE_CONFIG: ${{ inputs.machine_config || 'SWEET' }}

jobs:
  build:
    runs-on: macos-15-intel
    timeout-minutes: 120
```

No hay `strategy.matrix`. Hay un solo job `build`, con cuatro inputs. La “matriz” efectiva es 1×1: `MACOS_VERSION=13.5`, `KERNEL_CONFIG=DEVELOPMENT`, `MACHINE_CONFIG=SWEET`, `keep_going=true`. Los inputs existen pero no se usan para generar combinaciones. Además, los stage scripts `0019-stage-libpthread.sh` y `0026-stage-hfs.sh` fuerzan `MACOS_VERSION=13.5` cuando `MACHINE_CONFIG=SWEET`; otras combinaciones fallan por diseño (no probadas).

El disparador `push` solo cubre `main` y solo cambios en `xnu/patches/**` o en el propio workflow. La rama `ci-macos-latest` no se dispara por push; su run `41502238106` fue `workflow_dispatch`. `concurrency` agrupa por `github.ref`, así que `main` y `ci-macos-latest` no se cancelan entre sí; dos pushes a la misma ref sí. Si se empuja dos veces seguidas a `main`, `cancel-in-progress` puede matar el primer run y dejar solo el artefacto del segundo; el commit intermedio no tendrá kernel. Además, el workflow no se dispara por cambios en `shim/**`, `tools/**`, `dtb/**` ni en los propios artefactos: la cadena de imagen no se reconstruye ni se valida en CI.

El runner es una etiqueta, no una imagen fija. `macos-15-intel` y `macos-latest` pueden cambiar de imagen/Xcode entre ejecuciones. El comentario del workflow dice que `macos-15` arm64 tiene capacidad constraint y que `macos-15-intel` tiene el mismo Xcode 16 y cross-compila arm64. Eso es una afirmación del autor, no una garantía de reproducibilidad.

`userland.yml` es otro pipeline independiente, `runs-on: macos-15`, que clona `MakrSas/ios-topaz` en `e477291...` y `oosexgang/hackios-xnu-kernel` en `a3384e0...` y ejecuta `userland/build-gpu.sh`. No construye el kernel ni las imágenes de boot; no se usó en esta cadena. Si `macos-15` arm64 vuelve a fallar por capacidad, ese workflow también queda expuesto.

### 3.2 Job `build`, paso a paso

1. **`actions/checkout@v4`**: checkout del commit que disparó el run.

2. **`Fetch build script`**:

```bash
git init -q dxb
git -C dxb fetch -q --depth 1 "$DXB_REPO" "$DXB_SHA"
git -C dxb checkout -q FETCH_HEAD
cp xnu/patches/*.patch xnu/patches/*.sh dxb/patches/
sed -i '' 's|ARCHS="x86_64 arm64e" VALID_ARCHS="x86_64 arm64e"|ARCHS="x86_64 arm64e arm64" VALID_ARCHS="x86_64 arm64e arm64"|' dxb/build.sh
grep -c 'VALID_ARCHS="x86_64 arm64e arm64"' dxb/build.sh
ls dxb/patches
```

El `sed` es necesario porque `libfirehose_kernel` se construye arm64e-only y el kernel SWEET es arm64 plano. El `grep -c` es un guard: si el `sed` no cambia nada, el step falla (aunque `grep -c` imprime 0 y sale 1). Es una dependencia frágil del texto exacto de `build.sh` de blacktop.

3. **`Deps`**:

```bash
brew install jq gum bash cmake ninja
printf '#!/bin/sh\nexit 0\n' | sudo tee /usr/local/bin/xcodes >/dev/null
sudo chmod +x /usr/local/bin/xcodes
sw_vers
ls -d /Applications/Xcode*.app
XC=$(ls -d /Applications/Xcode_*.app | sort -V | head -1)
echo "DEVELOPER_DIR=$XC/Contents/Developer" >> "$GITHUB_ENV"
sudo xcode-select -s "$XC"
xcodebuild -version
xcrun --find iig
```

`xcodes` se stubea porque `build.sh` solo comprueba que exista; Xcode ya está preinstalado. `sort -V | head -1` elige el Xcode **más antiguo** instalado, no el más nuevo. En `macos-15-intel` eso puede ser Xcode 16.0/16.1; el valor exacto no está en el archivo y no se descargó el log. `brew install` no está pinneado.

4. **`Build`**:

```bash
MAKEFLAGS: ${{ inputs.keep_going == 'false' && '' || '-k' }}
run: bash build.sh
```

Por defecto `MAKEFLAGS=-k`: `make` sigue tras errores para reportar todos los fallos de compilación en un run. El step falla igualmente si el `make` final devuelve error.

5. **`Package build tree for local compiles`** (`if: always()`): copia `Kernel.framework/PrivateHeaders/platform` y empaqueta `buildtree.tgz` con `dxb/build/xnu.obj`, `fakeroot/usr/local/include`, `xnu` y `sdk-kernel-platform`; excluye `*.o`, `*.cpo`, `*.a`, `*.dSYM`, etc. Sirve para recompilar un archivo suelto con `tools/xnu-cc.py`.

6. **Upload `xnu-buildtree`** (`if: always()`, retention 7 días).

7. **`Inspect closed KDK support libs`** (`if: always()`): `ar t`, `nm -m`, `lipo -info` de `/Library/Developer/KDKs/*/System/Library/KernelSupport/lib*.a` a `out/kdk-libs/`.

8. **`Collect`** (`if: always()`):

```bash
mkdir -p out
cp -R dxb/fakeroot/System/Library/Kernels/. out/ 2>/dev/null || true
ls -la out
(cd out && shasum -a 256 kernel.* > SHA256SUMS) || true
```

`|| true` significa que un build fallido puede producir un `out/` vacío o parcial y aun así “collect” con éxito.

9. **Upload `xnu-kernel`** (`if: always()`, `if-no-files-found: warn`). No hay comprobación de que `kernel.development.sweet` exista antes de subir. Un artefacto de 178 KB (0104) demuestra que se sube basura parcial cuando el link falla.

### 3.3 `dxb/build.sh` (blacktop) — lo que realmente hace

El script está pinneado por SHA en `DXB_SHA`, pero su comportamiento depende de red y de la versión de macOS. Resumen de lo observado en el `build.sh` de ese commit:

- `install_deps`, `setup_xcode_toolchain` (fuerza `DEVELOPER_DIR` y un PATH con el toolchain de Xcode), `choose_xnu`.
- `choose_xnu` para `MACOS_VERSION=13.5`:
  - `RELEASE_URL=https://raw.githubusercontent.com/apple-oss-distributions/distribution-macOS/macos-135/release.json`
  - `KDK_NAME='Kernel Debug Kit 13.5 build 22G74'`
  - `KDKROOT=/Library/Developer/KDKs/KDK_13.5_22G74.kdk`
  - `RC_DARWIN_KERNEL_VERSION=22.6.0`
- Si el KDK no está, lo descarga desde el manifest de `dortania/KdkSupportPkg` y lo instala con `hdiutil`/`installer`. Es una descarga de red no pinneada por hash; el nombre del KDK sí está fijado.
- `get_xnu`: lee `release.json`, obtiene el tag de `xnu` y hace `git clone --branch <tag> https://github.com/apple-oss-distributions/xnu.git`. Para 13.5 el tag es `xnu-8796.141.3`.
- `patches`: hace varios `sed` a `make_symbol_aliasing.sh`, `Libsyscall.xcconfig` y `makedefs/MakeInc.def/.cmd`; luego ejecuta los `*.sh` de `dxb/patches/` y aplica los `*.patch` con `git apply`.
- `patches` **no falla si un patch no aplica**: hace `git apply --check`; si falla, imprime `warning: Skipping patch ...` y continúa. Es el modo de fallo silencioso más importante del pipeline.
- `build_bootstrap_cmds` (mig), `build_dtrace` (ctfconvert/ctfmerge/ctfdump), `build_availabilityversions`, `xnu_headers`, `libsystem_headers`, `libsyscall_headers`, `build_libplatform`, `build_libdispatch` (libfirehose_kernel).
- `build_xnu`:

```bash
make install -j8 VERBOSE=YES \
  SDKROOT=macosx \
  TARGET_CONFIGS="DEVELOPMENT ARM64 SWEET" \
  BUILD_WERROR=0 BUILD_LTO=0 \
  KDKROOT=/Library/Developer/KDKs/KDK_13.5_22G74.kdk \
  ...
```

- `kernel_version_env` fija `KERNEL_BUILD_DATE` al commit date del tag xnu y `KERNEL_BUILD_OBJROOT` al tag. Eso hace que el banner `Darwin Kernel Version ...; runner:xnu-8796.141.3` sea estable. No garantiza que el binario sea idéntico: clang, ld, KDK y dSYM pueden cambiar.
- Salida: `dxb/fakeroot/System/Library/Kernels/kernel.development.sweet` (y `.link/`, `kdk-libs`, etc.).

### 3.4 Parches: orden, stage scripts y cobertura

En el árbol de `34e3a8f`:

- 105 archivos `*.patch` trackeados.
- 3 scripts: `0019-stage-libpthread.sh`, `0020-stage-bearssl.sh`, `0026-stage-hfs.sh`.
- `.keep`.
- En el working tree hay 107 `*.patch`: los 105 trackeados + `0098-sweet-row-align-ca.patch` y `0100-sweet-surface-guard-rows.patch`, que están **untracked** (`git status` los muestra como `??`). Por tanto no están en el checkout de CI y no pueden haber influido en `xnu/out-0105`. Además, `0099-sweet-share-bgra-aligned.patch` ya contiene el cambio de filas de 0098; 0100 es un experimento local de guard rows.

Orden de aplicación: `build.sh` ejecuta primero todos los `*.sh` en orden glob y después todos los `*.patch` en orden lexicográfico. Los stage scripts:

- `0019-stage-libpthread.sh`: exige `MACHINE_CONFIG=SWEET` y `MACOS_VERSION=13.5`; clona `apple-oss-distributions/libpthread` en el commit inmutable `a6c70ca0e544347a0377babf748f831577ec24f9`, copia `kern/private/include` a `bsd/pthread/sweet_libpthread` y aplica reemplazos textuales con conteos exactos. Si el upstream cambia, falla explícitamente.
- `0020-stage-bearssl.sh`: clona BearSSL en `7bea48e5e850ab4cafbe68d3765cdaba13a86d6f` desde `https://www.bearssl.org/git/BearSSL`; copia AES/MD5/SHA-1/SHA-2; no exige 13.5.
- `0026-stage-hfs.sh`: exige 13.5; clona `apple-oss-distributions/hfs` en `31d5ec238dfab485e78a9a30b8b92d13e8914f03`; copia `core`/`hfs_encodings`; parchea `hfs_iokit.h` para `CONFIG_PROTECT`.

Riesgos: los tags/commits son inmutables, pero la red y la disponibilidad de `bearssl.org` no. `git apply --check` puede saltar un patch sin romper el build. En 0105, la presencia de los siete símbolos del fix y de `flame_wlan_init`, `sweet_rpmh`, `sweet_pmem`, `sweet_files` y `SweetBattery` prueba que 0104/0105 sí se aplicaron; no prueba que los 105 se hayan aplicado. No se descargó el log para buscar `Skipping patch`.

### 3.5 Artefactos

Dos artefactos por run:

| Artefacto | Contenido | Retención | Tamaño observado (zip) |
|---|---|---|---|
| `xnu-kernel` | `out/` = kernel + `.link/` + `kdk-libs/` + `SHA256SUMS` | 90 días (default; `expires_at` 2027-01-31) | 61,214,967 B (Intel 0105); 66,317,484 B (`macos-latest`); 178,298 B (0104 fallido) |
| `xnu-buildtree` | `buildtree.tgz` para recompilar archivos sueltos | 7 días | 23,497,047 B (Intel 0105); 23,517,818 B (`macos-latest`) |

`xnu-kernel` no es solo el kernel: incluye el directorio `.link/` con `kernel.development.sweet.a` (138,875,280 B sin comprimir en 0105), el dSYM y `linkarguments`, además de `kdk-libs/`. Por eso el zip pesa 61 MB aunque el Mach-O sean 17 MB. El `SHA256SUMS` de dentro solo cubre `kernel.*`; no cubre `.link/` ni `kdk-libs/`.

Digests de artefactos (API):

| Run | Artefacto | Digest SHA256 del zip | Creado | Expira |
|---|---|---|---|---|
| 41501352880 | `xnu-kernel` | `7cff480a37ecbf18389e28f67326b5cad3e11454ed9949dbc4835f5541958cff` | 2026-11-02T19:01:40Z | 2027-01-31T18:31:17Z |
| 41501352880 | `xnu-buildtree` | `08e00167b52314ea621ca7ee580e6d1b69f9847236c147120df4b06f9dde741f` | 2026-11-02T19:01:20Z | 2026-11-09T19:01:06Z |
| 41502238106 | `xnu-kernel` | `e5fb6cd83ed050b7a354b3d2c1dc173bcc3552f2ea67b2f13ab7a9dcfbad5a5f` | 2026-11-02T18:52:31Z | 2027-01-31T18:36:48Z |
| 41502238106 | `xnu-buildtree` | `c3c62c6f979311508ba464d47fe9f854ca2694bfc4d272e38ee5fa16d76a0042` | 2026-11-02T18:52:24Z | 2026-11-09T18:52:22Z |
| 41494548855 | `xnu-kernel` | `2d4239a8674443874f330f99f457764316e750eeb27824844ff41fc42a87113b` | 2026-11-02T18:11:55Z | 2027-01-31T18:04:02Z |
| 41494548855 | `xnu-buildtree` | `0a4720f765a151a8c53d37778e02afdee4c9a1d4477575f3cabd2a1373e0cf8e` | 2026-11-02T18:11:51Z | 2026-11-09T18:11:48Z |

El digest del zip **no es** el hash del kernel. Para 0105, el kernel es `d22c5aad...`; el zip es `7cff480a...`. Confundirlos es un error frecuente.

### 3.6 Descarga del artefacto

Comando documentado (corregido al repo real):

```bash
gh run download 41501352880 \
  -R limonetexd/ios-sweet-gpu \
  -n xnu-kernel \
  -D xnu/out-0105
```

El comando de `xnu/README.md` (`-R dipa-studio/ios-sweet`) devuelve 404 para este run. `gh` necesita autenticación; el repo es público (`"private": false` en la API), pero la descarga de artefactos suele requerir token. El resultado observado en `xnu/out-0105`:

```
xnu/out-0105/
  kernel.development.sweet          17,382,896 B
  kernel.development.sweet.link/    (dir; kernel...a 138,875,280 B + dSYM + linkarguments)
  kdk-libs/                         (arch.txt, members.txt, nm.txt)
  SHA256SUMS                        91 B
```

`kernel.development.sweet.link/kernel.development.sweet.linkarguments` contiene rutas `/Users/runner/work/ios-sweet-gpu/ios-sweet-gpu/dxb/...`, lo que confirma que es un artefacto de CI y no una compilación local. También contiene `-arch arm64`, `-mmacosx-version-min=15.0`, `-DXNU_TARGET_OS_OSX`, `-Wl,-image_base,0xfffffe0007004000`, `-Wl,-segaddr,__PRELINK_TEXT,0xfffffe0004004000`, `-pie -static`.

Verificación:

```bash
cd xnu/out-0105
shasum -a 256 -c SHA256SUMS
# kernel.development.sweet: OK
```

### 3.7 Ensamblado local: de kernel a imagen

La cadena real es:

```
kernel Mach-O + ADT  --mkpayload.py-->  payload SWEETXNU
payload             --shim/build.sh-->  shim Image + ramdisk + mkbootimg
boot.img v2         --unpack_bootv2.py--> kernel/ramdisk/dtb/header.txt
```

`tools/sweet-gpu-image.sh` automatiza parte, pero **no** es la cadena completa para super/branch:

```bash
python3 -I tools/mkadt.py shim/out/sweet-gpupool.adt --highmem --gpupool
B="debug=0xc serial=$SER cpus=8 keepsyms=1 ... sweetfb_hz=$HZ sweetgpu=2 $EXTRA"
python3 -I tools/mkpayload.py "$K/kernel.development.sweet" \
  shim/out/sweet-gpupool.adt "shim/out/payload-$T.bin" --cmdline "$B"
(cd shim && SHIM_CFLAGS="-DSHIM_GPUPROBE -DSHIM_GPUBOOT" ./build.sh "../shim/out/payload-$T.bin" \
  2>&1 | grep -E 'warning|error' || true)
cp shim/out/shim-boot.img "shim/out/shim-boot-$T.img"
python3 -I tools/unpack_bootv2.py "shim/out/shim-boot-$T.img" "shim/out/check-$T" >/dev/null
cmp "shim/out/check-$T/ramdisk" "shim/out/payload-$T.bin" && echo RAMDISK MATCH
sha256sum "shim/out/shim-boot-$T.img"
```

Problemas del wrapper:

- El ADT está hardcodeado a `sweet-gpupool.adt`. Super y branch usan `sweet-wlan.adt`; por eso no pudieron salir de este script sin modificarlo o sin ejecutar los comandos a mano.
- `mkadt.py` **no acepta seed** y usa `os.urandom(64)`; cada ejecución cambia el ADT y, por tanto, el payload y la imagen. Es la mayor fuente de no-reproducibilidad byte a byte.
- `./build.sh ... | grep ... || true` oculta el código de salida de `build.sh` (no hay `set -o pipefail`). Si el build falla antes de `mkbootimg`, queda un `shim-boot.img` viejo; el `cmp` posterior es el único guard que detecta el payload obsoleto. No quitar ese `cmp`.
- `mkpayload.py` sí falla con `set -e` antes de tocar la imagen, porque es el primer comando de la cadena.

### 3.8 Boot image v2: estructura

Cabecera v2: 1660 bytes (`0x67c`), seguida de padding a `page_size` (4096). Campos:

| Offset | Tamaño | Campo | Valor en `shim-boot-super.img` |
|---:|---:|---|---|
| 0x000 | 8 | `magic` | `ANDROID!` |
| 0x008 | 4 | `kernel_size` | 380,928 (`0x5d000`) |
| 0x00c | 4 | `kernel_addr` | `0x8000` |
| 0x010 | 4 | `ramdisk_size` | 16,757,888 |
| 0x014 | 4 | `ramdisk_addr` | `0x1000000` |
| 0x018 | 4 | `second_size` | 0 |
| 0x01c | 4 | `second_addr` | 0 |
| 0x020 | 4 | `tags_addr` | `0x100` |
| 0x024 | 4 | `page_size` | 4096 |
| 0x028 | 4 | `header_version` | 2 |
| 0x02c | 4 | `os_version` | `0x22000236` (17.0.0 / 2035-06) |
| 0x030 | 16 | `name` | vacío |
| 0x040 | 512 | `cmdline` | `console=null` |
| 0x240 | 32 | `id` | 20 bytes SHA1-like + 12 ceros |
| 0x260 | 1024 | `extra_cmdline` | vacío |
| 0x660 | 4 | `recovery_dtbo_size` | 0 |
| 0x664 | 8 | `recovery_dtbo_offset` | 0 |
| 0x66c | 4 | `header_size` | 1660 |
| 0x670 | 4 | `dtb_size` | 346,902 |
| 0x674 | 8 | `dtb_addr` | `0x1f00000` |

Layout físico:

```
0x0000  cabecera v2 (1660 B) + padding a 4096
0x1000  kernel (shim Image, 380,928 B = 93 páginas)
0x5e000 ramdisk (payload SWEETXNU, tamaño variable, padding a página)
...     second (0), recovery_dtbo (0)
...     dtb (346,902 B, padding a página)
```

`kernel_size=380928` es exactamente 93 páginas, por eso `ramdisk_offset` es siempre `94 * 4096 = 385024` en las tres imágenes. Los offsets de dtb:

| Imagen | ramdisk_size | ramdisk pages | dtb_offset | tamaño total |
|---|---:|---:|---:|---:|
| super | 16,757,888 | 4,092 | 17,145,856 | 17,494,016 |
| 0101s0reboot | 16,663,456 | 4,069 | 17,051,648 | 17,399,808 |
| branch-reboot | 16,989,856 | 4,148 | 17,375,232 | 17,723,392 |

El `dtb` es el mismo en las tres (`29cc551e...`, 346,902 B). La cabecera declara `os_version 17.0.0 / 2035-06`, mientras que el boot.img stock del que se copió la geometría declara `0x200001aa` = 16.0.0 / 2026-10. `build.sh` dice “mirrors the stock PixelOS header”, pero solo copia base/offsets/page_size/dtb; no copia os_version ni cmdline. Es una discrepancia observada, no un error demostrado.

`id` en las tres imágenes:

```
super          c6f406d231b8af266369e526a44a6e924f8e9efe000000000000000000000000
0101s0reboot   9a4453921362aa81ae12aa3649d6269c86c31fb0000000000000000000000000
branch         3e43caaa43c53037fc2c7886ae5bfcaf7e761090000000000000000000000000
```

`mkbootimg` empaqueta `pack('32s', sha1.digest())`, por eso hay 20 bytes útiles y 12 ceros. No usé este campo como checksum: mi recomputación con el algoritmo del `mkbootimg` de WSL (`sha1` sobre kernel/ramdisk/second/recovery_dtbo/dtb + tamaños) no coincidió con el valor observado. No investigué la causa; puede ser una versión distinta de `mkbootimg` o una diferencia de orden/entrada. Para verificar, usar SHA256, no el `id`.

### 3.9 `tools/mkpayload.py`

Contrato:

```
mkpayload.py KERNEL ADT OUT [--cmdline "..."] [--ramdisk IMAGE]
```

Layout little-endian, offsets desde el inicio del payload:

| Offset | Tipo | Campo |
|---:|---|---|
| 0x000 | char[8] | `SWEETXNU` |
| 0x008 | u32 | version = 1 |
| 0x00c | u32 | nsegs |
| 0x010 | u64 | virt_base |
| 0x018 | u64 | entry_va (LC_UNIXTHREAD pc) |
| 0x020 | u64 | adt_off |
| 0x028 | u64 | adt_size |
| 0x030 | u64 | kernel_end_va (página 16K) |
| 0x038 | u64 | phys_base |
| 0x040 | u64 | mem_size |
| 0x048 | char[608] | cmdline |
| 0x2a8 | seg[nsegs] | `{u64 vmaddr, vmsize, file_off, file_size}` |

Para `nsegs=10`, la cabecera mide `0x2a8 + 32*10 = 0x3e8` (1000 B). Los datos de cada segmento empiezan en `0x3e8`, se copian desde el Mach-O y se alinean a 16 bytes; el ADT va después, también alineado a 16. El payload no es un Mach-O completo: se descartan los segmentos con `vmsize=0` (`__PRELINK_*`, `__CTF`), por eso el payload es menor que el archivo de kernel.

Cálculos:

- `virt_base = __TEXT.vmaddr & ~(0x2000000 - 1)` = `0xfffffe0007004000 & ~0x1ffffff` = `0xfffffe0006000000`.
- `kernel_end = max(vmaddr + vmsize)` alineado a `PAGE=0x4000`.
- `PHYS_BASE, MEM_SIZE = adt_dram()` desde `/chosen/dram-base` y `/chosen/dram-size`; para las tres imágenes: `0x100000000`, `0xecb00000`.
- `--ramdisk` añade un segmento más, mueve `kernel_end`, calcula `rd_pa = rd_va - virt_base + PHYS_BASE` y añade `/chosen/memory-map RAMDisk = <pa, size>`. **No se usó en estas imágenes**: el cmdline lleva `rd=ufsroot0`, no `rd=md0`. El payload no contiene un ramdisk raíz; el “ramdisk” del boot image es el payload entero.
- Chained fixups: el kernel actual no tiene `LC_DYLD_CHAINED_FIXUPS` (`parse_macho` devuelve `fixups=None`); `apply_chained_fixups` devuelve 0. El código soporta formatos 1/2/6/7/8/9/12, pero no se ejercita aquí.
- `--cmdline` se trunca a 607 bytes + NUL; el resto del campo queda a cero.

Salida esperada para super (derivada del payload, no de ejecutar el script):

```
virt_base 0xfffffe0006000000
entry     0xfffffe0007494488
adt_off   0xff81e0
adt_size  0x32a0
kernel_end 0xfffffe000851c000
phys_base 0x100000000
mem_size  0xecb00000
size      16757888
```

### 3.10 `tools/unpack_bootv2.py`

Contrato: `unpack_bootv2.py SRC OUT`. Escribe `kernel`, `ramdisk`, `second`, `recovery_dtbo` (v1+), `dtb` (v2) y `header.txt`. No valida el `header_size` ni el final del archivo; solo `assert b[:8] == b'ANDROID!'`.

Lógica:

- Lee 10 `u32` desde offset 8: `kernel_size, kernel_addr, ramdisk_size, ramdisk_addr, second_size, second_addr, tags_addr, page_size, header_version, os_version`.
- `cmdline = b[64:576].split(0)[0] + b[608:1632].split(0)[0]`; concatena sin espacio, así que si ambos campos tienen texto se pegan.
- `off = page_size`; extrae `kernel`, `ramdisk`, `second`; para v1 lee `recovery_dtbo_size/offset/header_size` en 1632/1636/1644; para v2 lee `dtb_size/dtb_addr` en 1648/1652.
- Cada parte se redondea a `page_size` para el siguiente offset.
- `header.txt` vuelca todos los campos, incluidos offsets calculados.

Salida observada para super:

```
kernel_size: 380928
kernel_addr: 0x8000
ramdisk_size: 16757888
ramdisk_addr: 0x1000000
second_size: 0
tags_addr: 0x100
page_size: 4096
header_version: 2
os_version: 0x22000236
name:
cmdline: console=null
header_size: 1660
dtb_addr: 0x1f00000
kernel_offset: 4096
ramdisk_offset: 385024
second_offset: 17145856
recovery_dtbo_offset: 17145856
dtb_offset: 17145856
```

Limitaciones: no soporta v3/v4; no comprueba que `kernel_size`/`ramdisk_size`/`dtb_size` quepan en el archivo; no verifica padding ni `id`; no conserva el `id` en `header.txt`. Es una herramienta de inspección, no de validación.

### 3.11 `shim/build.sh` y flags

`shim/build.sh`:

```bash
CC=aarch64-linux-gnu-gcc
OBJCOPY=aarch64-linux-gnu-objcopy
CFLAGS="-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align \
        -fno-stack-protector -Wall -Wextra ${SHIM_CFLAGS:-}"
for f in start.S shim.c console.c mmu.c fdt.c loader.c ufs.c gpuprobe.c plog.c gpufw.S; do
  $CC $CFLAGS -c $f -o out/${f%.*}.o
done
abs=$(readelf -r out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o \
      out/ufs.o out/gpuprobe.o out/plog.o | grep -c ABS64 || true)
[ "$abs" = 0 ] || { echo "error: $abs absolute relocations" >&2; exit 1; }
$CC $CFLAGS -static -T shim.ld -Wl,--build-id=none -Wl,--no-warn-rwx-segments -Wl,-N \
  out/start.o out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o \
  out/ufs.o out/gpuprobe.o out/plog.o out/gpufw.o -o out/shim.elf
$OBJCOPY -O binary out/shim.elf out/Image
size=$(aarch64-linux-gnu-nm out/shim.elf | awk '$3=="_end"{print strtonum("0x"$1)}')
truncate -s "$size" out/Image
if [ -n "${1:-}" ]; then cp "$1" out/ramdisk.bin; else
  (cd out && rm -rf rd && mkdir rd && cd rd && find . | cpio -o -H newc --quiet | gzip -9 > ../ramdisk.bin)
fi
mkbootimg --header_version 2 --kernel out/Image --ramdisk out/ramdisk.bin \
  --dtb ../dtb/boot_unpacked/dtb --base 0 --kernel_offset 0x8000 \
  --ramdisk_offset 0x1000000 --tags_offset 0x100 --dtb_offset 0x1f00000 \
  --pagesize 4096 --os_version 17.0.0 --os_patch_level 2035-06 \
  --cmdline "console=null" -o out/shim-boot.img
gcc -O1 -Wall -o out/host_test console.c host_test.c && ./out/host_test
ls -l out/Image out/shim-boot.img
```

`host_test` compila con el gcc del host y escribe `out/host.ppm` (7,776,017 B observados); es un side effect del build, no un input de la imagen. Si `host_test` falla después de `mkbootimg`, la imagen ya está escrita pero `build.sh` devuelve error; el wrapper puede continuar y el `cmp` decidirá si la imagen sirve.

Flags:

- `-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra`.
- `-mgeneral-regs-only` evita FP/SIMD en EL1 antes de habilitar nada; `-mstrict-align` evita accesos no alineados; `-fno-pic` permite direcciones absolutas controladas; el check `ABS64` exige que solo `start.o` (linked at 0) tenga direcciones absolutas.
- Link: `-static -T shim.ld -Wl,--build-id=none -Wl,--no-warn-rwx-segments -Wl,-N`. `-N` produce un ELF con Load RWE; `readelf -l` muestra un solo LOAD `RWE`, offset 0x1000, vaddr 0, filesz 0x1a6f8, memsz 0x4d000.
- `shim.ld`: `. = 0; .text/.rodata/.data/.bss; . += 0x8000; _stack_top; . += 8*0x1000; _end`. `_end=0x5d000`; `Image` se trunca a 380,928 B (`0x5d000`). `shim.elf` mide 117,456 B; `Image` 380,928 B.
- `SHIM_GPUPROBE`: compila `gpuprobe.c`/`plog.c` y el path de probe; incluye los firmware blobs de `shim/gpufw.S`; el probe escribe log en userdata, arma watchdog y vuelve a fastboot (`plog.c`).
- `SHIM_GPUBOOT`: en `shim_main`, ejecuta `gpuprobe_run(&stage)` antes de `loader_boot(dtb)`; deja el ring limpio para `sweet_gpu.c` (`#ifndef SHIM_GPUBOOT` evita `gpu_paint`).
- Ambos (`-DSHIM_GPUPROBE -DSHIM_GPUBOOT`): es la combinación usada para las tres imágenes; el probe trae la GPU y el loader salta a XNU.
- `SHIM_GPUBOOT` solo: handoff sin probe/log; no usado en estas imágenes.
- Sin flags: `shim_main` hace el probe UFS y resetea; no bootea XNU. Es una imagen de diagnóstico, no una imagen de boot.

`shim/gpufw.S` incluye, solo bajo `SHIM_GPUPROBE`:

```
research/gpu-sweet/fw/a618_gmu.bin   32,768 B  sha256 9ef10b2b...
research/gpu-sweet/fw/a630_sqe.fw    32,136 B  sha256 36298bd5...
research/gpu-sweet/fw/a615_zap.mdt    6,860 B  sha256 534aec7f...
research/gpu-sweet/fw/a615_zap.b02    1,984 B  sha256 61be42f0...
```

Sin esos blobs el build falla en el preprocesador/`.incbin`; no están en git (`research/` está ignorado).

Warning reportado: `gpuprobe.c:876:13: warning: 'gpu_paint' defined but not used [-Wunused-function]`. Es exactamente lo esperado con `SHIM_GPUBOOT`: `gpu_paint` se define en 876 y solo se llama en 1024 dentro de `#ifndef SHIM_GPUBOOT`. No es un error y `build.sh` no usa `-Werror`. No reproduje la compilación; la warning se cita del reporte de build y el código la explica.

### 3.12 `shim/loader.c`: contrato con el payload

El loader:

- Lee `/chosen/linux,initrd-start` y `linux,initrd-end` del DTB que pasó ABL.
- Comprueba `magic == "SWEETXNU"`, `version == 1`, `adt_off & 7 == 0`, `rd_start & 7 == 0`.
- Calcula `pa_of_va_base = phys_base - virt_base` (`0x200fa000000` para estas imágenes).
- Rechaza si `rd_end > phys_base && rd_start < phys_base + mem_size` (“ramdisk overlaps kernel memory”). Con ramdisk en `0x1000000` y kernel en `0x100000000`, no hay solape.
- Copia cada segmento a `vmaddr + pa_of_va_base`; si `vmsize > file_size`, cero el resto (BSS).
- Coloca el ADT en `kernel_end + pa_of_va_base`, y `boot_args` en la página 16K siguiente; `topOfKernelData = ba_pa + 0x4000`.
- Rellena `boot_args` Rev 2/Ver 2, `virtBase`, `physBase`, `memSize`, `topOfKernelData`, `Video` (FB_BASE `0x9c000000`, 1080×2400, stride 4320, depth 32), `deviceTreeP` como VA, `deviceTreeLength`, `CommandLine` de 608 bytes, `memSizeActual`.
- `dsb sy; ic iallu; dsb sy; isb` y salta a `entry_va + pa_of_va_base` con `x0 = ba_pa`.

Esto explica por qué el payload debe tener `adt_off` alineado a 8 y por qué el `kernel_end` del header importa: el ADT y `boot_args` se colocan justo después. Si `kernel_end` está mal, se pisa el kernel o el ADT.

---

## 4. Evidencia cruda

### 4.1 Hashes y tamaños

Obtenidos con `Get-FileHash -Algorithm SHA256` y confirmados con `sha256sum` en WSL.

| Archivo | Tamaño | SHA256 |
|---|---:|---|
| `xnu/out-0105/kernel.development.sweet` | 17,382,896 | `d22c5aadf208b5e0347f487fdcb7b83d487a37d06af2b623ed9f675d9b7c1793` |
| `xnu/out-0101/kernel.development.sweet` | 17,272,256 | `d2bbc4dc3c3089efa26b9551d6ed602fee9d43a9aae13c9cbcc2399576fd68c5` |
| `shim/out/payload-super.bin` | 16,757,888 | `8201e7de7b17b39af59142f23cacdefd4a93b73a5f3811b9d7809aa24f6d7bfe` |
| `shim/out/payload-0101s0reboot.bin` | 16,663,456 | `b1a21ba8194636a0bceb54b1394f2ceb24c13b0c584c959875e211ff422efafe` |
| `shim/out/payload-branch-reboot.bin` | 16,989,856 | `ff6fef0409ed9eece33ab8c6c75e7739bd632cfdac7c1c9fe3d35ab39e42584f` |
| `shim/out/ramdisk.bin` | 16,989,856 | `ff6fef0409ed9eece33ab8c6c75e7739bd632cfdac7c1c9fe3d35ab39e42584f` |
| `shim/out/shim-boot-super.img` | 17,494,016 | `67ff470f24acc5d3a92919fc8fbfde00e9f485e7e46c30aa8ab894bad24b5f3f` |
| `shim/out/shim-boot-0101s0reboot.img` | 17,399,808 | `e0be26fca701c96c5862b579f14b58a31a36a560f82df1f5300d127e28a7949c` |
| `shim/out/shim-boot-branch-reboot.img` | 17,723,392 | `833b199ce8124dd9ebb36af0a1a17e3d03d3a483a5b88a860daa7080146821f9` |
| `shim/out/shim-boot.img` | 17,723,392 | `833b199ce8124dd9ebb36af0a1a17e3d03d3a483a5b88a860daa7080146821f9` |
| `shim/out/Image` | 380,928 | `94e447f7d9051c8e718ae17ee8f7045c27cca2eb31baeed380ef0146bf6d617a` |
| `shim/out/shim.elf` | 117,456 | `e29ea013ffb2081cb7364cfd581ad63ab6c84a34c6c15d213717b53ef97ff094` |
| `dtb/boot_unpacked/dtb` | 346,902 | `29cc551e43c7e83a63867685fcafbb7d7f327a757c3a7b3d661878f793cf4fdd` |
| `shim/out/sweet-gpupool.adt` | 12,772 | `a8f78c1a84cabfc759662ca96f7677d84dedd3094e24e61e4d16eeb2f88454ae` |
| `shim/out/sweet-wlan.adt` | 12,960 | `994c8cac2a3070f5b6a6a27b8731c72b0f78c11cddfa70c57e07cc4f2316db5f` |
| `shim/out/sweet-local.adt` | 12,772 | `9f8d00f67d977a063affff094210d37bbc3d73b181d14e26b1ec525ae3c17dd1` |
| `research/ipsw-x/d22ap.adt` | 186,084 | `9e670987c80493bd69aba7be62e3179c04663324d9249b0973675baac175dbf1` |
| `shim/out/payload-wifi-auto.bin` | 16,989,856 | `9de589c6f528c60776d2fac871533024bf4c8d02210beff8ed1cc58326ae8586` |
| `shim/out/shim-boot-wifi-auto.img` | 17,723,392 | `f5ab5524f163879b965a5855c3a952fca1954e6457566f98b435201e8fd7fefc` |

Los `SHA256SUMS` de `xnu/out-0105` y `out-0101` coinciden con los hashes de sus kernels:

```
d22c5aadf208b5e0347f487fdcb7b83d487a37d06af2b623ed9f675d9b7c1793  kernel.development.sweet
d2bbc4dc3c3089efa26b9551d6ed602fee9d43a9aae13c9cbcc2399576fd68c5  kernel.development.sweet
```

### 4.2 API de GitHub Actions

| Run | Repo | Run # | Rama | Head | Evento | Conclusión | Runner | Inicio job | Build | Fin |
|---|---|---:|---|---|---|---|---|---|---|---|
| 41501352880 | `limonetexd/ios-sweet-gpu` | 36 | `main` | `34e3a8f` | push | success | `macos-15-intel` | 18:41:29Z | 19m03s | 19:02:04Z |
| 41502238106 | `limonetexd/ios-sweet-gpu` | 37 | `ci-macos-latest` | `ced27dd` | workflow_dispatch | success | `macos-latest` | 18:46:53Z | 5m09s | 18:52:40Z |
| 41498675277 | `limonetexd/ios-sweet-gpu` | 35 | `main` | `771481a` | push | failure | `macos-15` | 18:14:33Z | — | 18:29:35Z |
| 41494548855 | `limonetexd/ios-sweet-gpu` | 34 | `main` | `5639176` | push | failure | `macos-15` | 18:04:07Z | 7m13s (falla) | 18:12:00Z |

Detalles:

- `41501352880`: job `125469346383`, runner `1000000061`, cola 10m13s, `Build` 18:41:53–19:00:56, `Package` 19:00:56–19:01:05, upload 19:01:05–19:01:09, KDK inspect 19:01:09–19:01:16, `Collect` 19:01:16–19:01:17, upload 19:01:17–19:01:30.
- `41502238106`: job `125472370386`, runner `1000000063`, cola 10m06s, `Build` 18:47:09–18:52:18.
- `41498675277`: job `125460222235`, `runner_id: 0`, `runner_name: ""`, `steps: []`, `conclusion: cancelled`; el run global figura `failure`. Es el outage de capacidad arm64: el job nunca arrancó.
- `41494548855`: `run_attempt: 2`; job `125454493853`, runner `1000000054`; `Build` 18:04:28–18:11:41 con `conclusion: failure`; `Package`, `Inspect` y `Collect` siguen y “succeed” por `if: always()`. El artefacto `xnu-kernel` de 178,298 B es el resultado de un link fallido.

### 4.3 Kernel Mach-O

`file` (WSL):

```
xnu/out-0105/kernel.development.sweet: Mach-O 64-bit arm64 executable, flags:<NOUNDEFS|PIE>
xnu/out-0101/kernel.development.sweet: Mach-O 64-bit arm64 executable, flags:<NOUNDEFS|PIE>
```

Cabecera 0105:

```
magic 0xfeedfacf
cputype 0x100000c (CPU_TYPE_ARM64)
cpusub 0
ftype 2 (MH_EXECUTE)
ncmds 26
LC_UUID 951f3cec14553d52b85af32c4978373b
LC_BUILD_VERSION platform 1 (macOS), minos 0xf0000 (15.0), sdk 0xf0000 (15.0)
LC_SOURCE_VERSION 0
LC_UNIXTHREAD entry 0xfffffe0007494488
LC_FUNCTION_STARTS presente
LC_DYLD_CHAINED_FIXUPS ausente
```

0101:

```
LC_UUID 50c5393b1b7a39ae84fe948e4d0ca4de
entry 0xfffffe0007490488
```

Branch (parseado desde el segmento `__TEXT` del payload, offset `0x3e8`):

```
LC_UUID c09f67e0a5e439b49c1ff99371e3a633
entry 0xfffffe00074a1488
banner: Darwin Kernel Version 22.6.0: Mon Aug 14 05:06:07 UTC 2023; runner:xnu-8796.141.3
```

Segmentos 0105 (los 10 con `vmsize != 0` que copia `mkpayload`):

| Segmento | vmaddr | vmsize | fileoff | filesize |
|---|---:|---:|---:|---:|
| `__TEXT` | `0xfffffe0007004000` | `0x164000` | 0 | `0x164000` |
| `__DATA_CONST` | `0xfffffe0007168000` | `0x184000` | `0x164000` | `0x184000` |
| `__TEXT_EXEC` | `0xfffffe00072ec000` | `0x864000` | `0x2e8000` | `0x864000` |
| `__KLD` | `0xfffffe0007b50000` | `0x4000` | `0xb4c000` | `0x4000` |
| `__LASTDATA_CONST` | `0xfffffe0007b54000` | `0x4000` | `0xb50000` | `0x4000` |
| `__KLDDATA` | `0xfffffe0007b58000` | `0x4000` | `0xb54000` | `0x4000` |
| `__DATA` | `0xfffffe0007b5c000` | `0x568000` | `0xb58000` | `0x48000` |
| `__BOOTDATA` | `0xfffffe00080c4000` | `0x4c000` | `0xba0000` | `0x4c000` |
| `__LINKINFO` | `0xfffffe0008110000` | `0x4c000` | `0xbec000` | `0x4c000` |
| `__LINKEDIT` | `0xfffffe000815c000` | `0x3c0000` | `0xcd4000` | `0x3bfdf0` |

`kernel_end = __LINKEDIT.vmaddr + vmsize = 0xfffffe000851c000`.

Branch:

| Segmento | vmaddr | vmsize | filesize |
|---|---:|---:|---:|
| `__TEXT` | `0xfffffe0007004000` | `0x16c000` | `0x16c000` |
| `__TEXT_EXEC` | `0xfffffe00072f8000` | `0x888000` | `0x888000` |
| `__DATA` | `0xfffffe0007b8c000` | `0x598000` | `0x48000` |
| `__LINKINFO` | `0xfffffe0008170000` | `0x4c000` | `0x4c000` |
| `__LINKEDIT` | `0xfffffe00081bc000` | `0x3cc000` | `0x3c8810` |

`kernel_end = 0xfffffe0008588000`.

0101:

| Segmento | vmaddr | vmsize |
|---|---:|---:|
| `__TEXT` | `0xfffffe0007004000` | `0x164000` |
| `__TEXT_EXEC` | `0xfffffe00072e8000` | `0x858000` |
| `__DATA` | `0xfffffe0007b4c000` | `0x538000` |
| `__LINKINFO` | `0xfffffe00080d0000` | `0x4c000` |
| `__LINKEDIT` | `0xfffffe000811c000` | `0x3bc000` |

`kernel_end = 0xfffffe00084d8000`.

Símbolos que prueban el contenido:

- 0105 contiene: `sweet_bt_init`, `sweet_haptic_init`, `sweet_native_adreno_reserve_pool`, `sweet_gpu_probe`, `sweet_vfs_mkdir`, `sweet_vfs_symlink`, `sweet_vfs_unlink` (los siete del patch 0105), además de `flame_wlan_init`, `sweet_rpmh`, `sweet_pmem`, `sweet_files`, `SweetBattery`. No contiene `NativeAdreno`; sí `RedwoodGPU` y `sweet_gpu_init`. Es el “super” con Wi-Fi/batería y topaz, no con el stack NativeAdreno.
- 0101 **no** contiene ninguno de los siete símbolos de 0105 ni `flame_wlan_init`; sí contiene `RedwoodGPU` y `sweet_gpu_init`. Es la base rápida sin Wi-Fi.
- Branch contiene `flame_wlan_init`, `SweetBattery`, `sweet_pmem`, `sweet_rpmh`, `sweet_files`, `NativeAdreno`; **no** contiene `RedwoodGPU`. Es el kernel DC28088 con NativeAdreno/Metal, no el topaz.

### 4.4 Payloads

| Payload | size | nsegs | virt_base | entry | adt_off | adt_size | kernel_end | phys_base | mem_size |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| super | 16,757,888 | 10 | `0xfffffe0006000000` | `0xfffffe0007494488` | `0xff81e0` | `0x32a0` | `0xfffffe000851c000` | `0x100000000` | `0xecb00000` |
| 0101s0reboot | 16,663,456 | 10 | `0xfffffe0006000000` | `0xfffffe0007490488` | `0xfe11b0` | `0x31e4` | `0xfffffe00084d8000` | `0x100000000` | `0xecb00000` |
| branch-reboot | 16,989,856 | 10 | `0xfffffe0006000000` | `0xfffffe00074a1488` | `0x1030c00` | `0x32a0` | `0xfffffe0008588000` | `0x100000000` | `0xecb00000` |

Los 10 segmentos de `payload-super` tienen hash de bytes idéntico a los 10 segmentos de `out-0105`; los de `payload-0101s0reboot` son idénticos a los de `out-0101`. Eso prueba que cada payload se construyó con ese kernel, sin depender de la línea de comandos.

Los ADT embebidos son byte a byte:

| Payload | ADT SHA256 | Coincide con |
|---|---|---|
| super | `994c8cac2a3070f5b6a6a27b8731c72b0f78c11cddfa70c57e07cc4f2316db5f` | `shim/out/sweet-wlan.adt` |
| 0101s0reboot | `a8f78c1a84cabfc759662ca96f7677d84dedd3094e24e61e4d16eeb2f88454ae` | `shim/out/sweet-gpupool.adt` |
| branch-reboot | `994c8cac2a3070f5b6a6a27b8731c72b0f78c11cddfa70c57e07cc4f2316db5f` | `shim/out/sweet-wlan.adt` |

`mkpayload.py` no añade checksum al payload; la integridad se comprueba por `cmp` contra el payload esperado o por el SHA256 del archivo.

### 4.5 Cabeceras de boot

Salida de `unpack_bootv2.py` para las tres imágenes (resumida):

| Campo | super | 0101s0reboot | branch-reboot |
|---|---:|---:|---:|
| `kernel_size` | 380,928 | 380,928 | 380,928 |
| `kernel_addr` | `0x8000` | `0x8000` | `0x8000` |
| `ramdisk_size` | 16,757,888 | 16,663,456 | 16,989,856 |
| `ramdisk_addr` | `0x1000000` | `0x1000000` | `0x1000000` |
| `second_size` | 0 | 0 | 0 |
| `tags_addr` | `0x100` | `0x100` | `0x100` |
| `page_size` | 4096 | 4096 | 4096 |
| `header_version` | 2 | 2 | 2 |
| `os_version` | `0x22000236` | `0x22000236` | `0x22000236` |
| `cmdline` | `console=null` | `console=null` | `console=null` |
| `header_size` | 1660 | 1660 | 1660 |
| `dtb_addr` | `0x1f00000` | `0x1f00000` | `0x1f00000` |
| `kernel_offset` | 4096 | 4096 | 4096 |
| `ramdisk_offset` | 385,024 | 385,024 | 385,024 |
| `second_offset` | 17,145,856 | 17,051,648 | 17,375,232 |
| `dtb_offset` | 17,145,856 | 17,051,648 | 17,375,232 |

El `kernel` extraído de cada imagen es byte a byte `shim/out/Image` (`94e447f7...`); el `dtb` es byte a byte `dtb/boot_unpacked/dtb` (`29cc551e...`); el `ramdisk` es byte a byte su payload (rc 0 en los tres `cmp`). Eso cierra la cadena imagen → payload → kernel/ADT/DTB.

### 4.6 ADT: diferencia real entre gpupool y wlan

Comparación estructural completa:

```
DIFF /device-tree/arm-io/wlan
    AAPL,phandle  gpupool None  wlan 18000000
    compatible    gpupool None  wlan 666c616d652c77636e3339393000  ("flame,wcn3990")
    device_type   gpupool None  wlan 776c616e00                  ("wlan")
    name          gpupool None  wlan 776c616e00                  ("wlan")
DIFF /device-tree/chosen
    random-seed   gpupool 345e2d4c...  wlan 5754bc63...
```

Es decir: `sweet-wlan.adt` = `sweet-gpupool.adt` + nodo `arm-io/wlan` + una seed aleatoria distinta. El tamaño sube 188 B (12,772 → 12,960). El nodo wlan es lo que activa `sweetwifi=1`/`flame_wlan` en el kernel; el kernel 0105 contiene `flame_wlan_init` y el 0101 no.

La seed:

```python
# tools/mkadt.py:80,92
def build(seed=None, qemu=False, highmem=False, gpupool=False):
    ...
    seed = seed if seed is not None else os.urandom(64)
    ...
    ('random-seed', seed),
```

El CLI no expone `--seed`; `build()` acepta `seed` pero `__main__` llama `build(qemu=..., highmem=..., gpupool=...)` sin seed. Cada ejecución genera 64 bytes nuevos. Seeds observadas:

```
gpupool 345e2d4c17025fafada0225daa8674d3abce1450f84544854526492d959273c7
        8d415ccb04464ed6c288851b8764244a658e452d66839a48b83a5eaf032decfc
wlan    5754bc63acd57054b7fa2e2191d33ded11499f61ee862f983b2e5b3ed0f2149a
        a4c46bdb7cb874d8b12ebbd0ea4d1dd51b04087eccb6603e456722c71a82ad69
local   884ab3f8db849761fc23294600010003b76a7b4453d7c06e8052719113686916
        4d6b7540c53b6422a9b1932dd4bf90cd9a8c4b0248a0a52492fa0d85c663b8ed
```

Consecuencia: **la misma fuente + el mismo kernel + el mismo cmdline producen un payload/imagen distinto si se regenera el ADT**. Para reproducir byte a byte hay que conservar el `.adt` exacto o añadir una opción de seed. `sweet-local.adt` y `sweet-gpupool.adt` tienen el mismo tamaño pero distinto hash por la seed; es la prueba directa.

### 4.7 Diferencia mínima branch vs Wi-Fi auto

`payload-branch-reboot.bin` no es un kernel nuevo. Sus 10 segmentos tienen exactamente los mismos hashes que `payload-wifi.bin`, `payload-wifi-auto.bin` y `payload-wifi-native.bin`; el entry y `kernel_end` también coinciden; el ADT es el mismo (`994c8cac...`). Solo cambia el cmdline:

```
wifi-auto: ... sweetgpu_reboot=600
branch:    ... sweetgpu_reboot=120
```

`cmp -l` de los dos payloads:

```
     416  66  61
     417  60  62
```

Dos bytes (octal: `66`→`61` = `'6'`→`'1'`; `60`→`62` = `'0'`→`'2'`), es decir `600` → `120`. El resto del payload es idéntico. La imagen también difiere en 21 bytes: 19 bytes del `id` de la cabecera + los 2 bytes del cmdline. Esto demuestra dos cosas: (a) el branch es el kernel Wi-Fi de DC28088, no una compilación nueva; (b) `mkbootimg`/payload son deterministas para los mismos inputs, salvo el `id`.

### 4.8 Comandos de verificación usados

```powershell
# Windows
Get-FileHash -Algorithm SHA256 <archivo>
Get-ChildItem <dir> | ForEach-Object { ... }
```

```bash
# WSL, desde el workspace
sha256sum shim/out/shim-boot-super.img
cmp shim/out/check-super/ramdisk shim/out/payload-super.bin
cmp shim/out/check-super/kernel shim/out/Image
cmp shim/out/check-super/dtb dtb/boot_unpacked/dtb
python3 -I tools/unpack_bootv2.py shim/out/shim-boot-super.img shim/out/check-super
readelf -h shim/out/shim.elf
readelf -l shim/out/shim.elf
file shim/out/Image xnu/out-0105/kernel.development.sweet
```

Parseo del payload (solo lectura, sin escribir):

```python
import struct
b = open("shim/out/payload-super.bin","rb").read()
magic,ver,n = struct.unpack_from("<8sII", b, 0)
vb,entry,ao,asz,ke,pb,ms = struct.unpack_from("<7Q", b, 0x10)
cl = b[0x48:0x48+608].split(b"\0")[0].decode()
for i in range(n):
    va,vs,fo,fs = struct.unpack_from("<4Q", b, 0x2a8+32*i)
    print(i, hex(va), hex(vs), hex(fo), hex(fs))
```

### 4.9 Kernel y boot image stock (para comparar geometría)

`dtb/boot_unpacked/header.txt` (boot.img Android stock del que se extrajo el DTB):

```
kernel_size: 18348772
kernel_addr: 0x8000
ramdisk_size: 1570396
ramdisk_addr: 0x1000000
second_size: 0
tags_addr: 0x100
page_size: 4096
header_version: 2
os_version: 0x200001aa   # 16.0.0 / 2026-10
name:
cmdline: console=ttyMSM0,115200n8 earlycon=... androidboot.hardware=qcom ...
header_size: 1660
dtb_addr: 0x1f00000
kernel_offset: 4096
ramdisk_offset: 18354176
dtb_offset: 19927040
```

La imagen del shim mantiene `page_size`, `base`, `kernel_offset`, `ramdisk_offset`, `tags_offset`, `dtb_offset`, `header_version` y el DTB; cambia kernel/ramdisk (shim/payload), `os_version` (17.0.0/2035-06), `cmdline` (`console=null`) y `name`. Es una geometría compatible, no un clon de la cabecera stock.

---

## 5. Observado vs inferido vs desconocido

### 5.1 Observado

1. Los hashes y tamaños de §4.1, calculados dos veces (Windows/WSL) con coincidencia.
2. Los campos de cabecera de §4.5, parseados del binario y confirmados por `header.txt`.
3. Los campos de payload de §4.4, parseados del binario.
4. Los segmentos Mach-O, UUIDs, entry points, `LC_BUILD_VERSION` y banner de §4.3.
5. Los símbolos de §4.3, buscados como cadenas en el kernel; 0105 tiene los siete del fix, 0101 no; branch tiene NativeAdreno y no RedwoodGPU.
6. La metadata de runs/jobs/artifacts de la API de GitHub, incluida la diferencia de repo (`limonetexd/ios-sweet-gpu` 200 vs `dipa-studio/ios-sweet` 404).
7. El contenido de `xnu/out-0105`: kernel 17,382,896 B + `.link/` con `.a` de 138,875,280 B + `kdk-libs/` + `SHA256SUMS`; `linkarguments` con rutas `/Users/runner/work/ios-sweet-gpu/...`.
8. La diferencia branch vs wifi-auto: 2 bytes de payload, 21 de imagen, mismos 10 segmentos y mismo ADT.
9. La seed aleatoria de `mkadt.py` y las tres seeds distintas.
10. La advertencia `gpu_paint` se cita del reporte de build; el código muestra por qué (llamada solo bajo `#ifndef SHIM_GPUBOOT`).
11. `HANDOFF.md` no existe en el workspace.
12. Los 105 patches trackeados y los 2 untracked (0098/0100).

### 5.2 Inferido

1. `xnu/out-0105` se descargó con `gh run download 41501352880 -R limonetexd/ios-sweet-gpu -n xnu-kernel -D xnu/out-0105`: el contenido, el nombre y el `linkarguments` lo confirman, pero no vi el comando.
2. `payload-super` se construyó con `sweet-wlan.adt` y `payload-0101s0reboot` con `sweet-gpupool.adt`: los hashes del ADT embebido coinciden exactamente.
3. Las tres imágenes se construyeron con `SHIM_CFLAGS="-DSHIM_GPUPROBE -DSHIM_GPUBOOT"`: el `Image` embebido es el mismo en las tres y contiene el probe/handoff; no vi la línea de comandos.
4. El branch se construyó a partir del kernel Wi-Fi de DC28088: los segmentos coinciden con `payload-wifi*.bin`; `NOTES.md` atribuye Wi-Fi/batería a esa rama.
5. `macos-latest` es arm64 y por eso tarda 5m vs 19m: el tamaño del job y el comentario del workflow lo sugieren; la API solo da la etiqueta, no la arquitectura.
6. La diferencia de tamaño entre los artefactos `xnu-kernel` de Intel (61.2 MB) y `macos-latest` (66.3 MB) se debe a dSYM/compresión/toolchain, no al kernel necesariamente; no se descargó el segundo.
7. `0099` aplica aunque `0098` no esté trackeado porque el propio 0099 contiene el cambio de filas; el diff de 0099 incluye `sweet_row_align` y `sweet_rows`. 0100 no está en CI.
8. El `id` de la cabecera es un SHA1 de `mkbootimg`; el campo tiene 20 bytes útiles + 12 ceros. La recomputación no coincidió, así que la versión exacta de `mkbootimg` o su orden de inputs es distinta; no lo uso como checksum.

### 5.3 Desconocido

1. Versión exacta de Xcode, SDK, clang y ld usada en `41501352880` y `41502238106`. El workflow elige el Xcode más antiguo instalado, pero no lo registra en el artefacto.
2. Si los 105 patches se aplicaron todos; no se descargó el log para buscar `Skipping patch`.
3. Si el kernel de `macos-latest` es byte a byte distinto del de Intel; solo se comparó el tamaño del zip.
4. Commit/artefacto exacto del kernel branch. No hay `kernel.*` local; el payload es la única copia. El UUID/banner no identifican un commit.
5. Por qué el `id` de la cabecera no coincide con mi recomputación.
6. Si las imágenes bootean; no se probó en el teléfono.
7. Si `sweetgpu_reboot=90` y `120` producen exactamente el tiempo esperado; el código dice `N-20` s de espera + 12 s antes del reset, pero no se cronometró.
8. Si el kernel 0105 contiene cambios equivalentes a 0100 por otra vía; 0100 no está en el checkout de CI, así que no debería, pero no se inspeccionó el binario para probarlo.
9. Si `HANDOFF.md` existe fuera del workspace; no se buscó por la restricción de zona.
10. Si `macos-15-intel` seguirá existiendo/capacidad; el comentario del workflow dice que macos-14 se retira el 2026-11-02, pero no hay garantía para el futuro.

---

## 6. Fallos y warnings

### 6.1 Fallos CI

| Fallo | Causa | Evidencia | Lección |
|---|---|---|---|
| 0104 `41494548855` | Link con exactamente 7 undefined: `sweet_bt_init`, `sweet_haptic_init`, `sweet_native_adreno_reserve_pool`, `sweet_gpu_probe`, `sweet_vfs_mkdir/symlink/unlink` | `NOTES.md:208-215`; API `Build` failure 18:11:41 | El patch 0104 copió hooks de la rama sin los drivers; 0105 añade stubs/wrappers |
| 0105 `41498675277` | Runner arm64 (`macos-15`) nunca asignado; job cancelado sin steps | API: `runner_id: 0`, `steps: []`, cancelado 18:29:35 | Capacidad de GitHub, no código; se resuelve con `macos-15-intel` o retry |
| 0105 `41501352880` | Ninguno; success | API | El cross-compile Intel produce arm64 válido; build 19m03s |
| `41502238106` | Ninguno; success | API | `macos-latest` funciona y es mucho más rápido (5m09s) en ese momento |

### 6.2 Warning de compilación

```
gpuprobe.c:876:13: warning: 'gpu_paint' defined but not used [-Wunused-function]
```

Causa: con `-DSHIM_GPUBOOT`, la llamada `gpu_paint(c)` en `gpuprobe.c:1024` queda dentro de `#ifndef SHIM_GPUBOOT`, pero la definición en 876 no. `-Wall -Wextra` incluye `-Wunused-function`. No es error; `build.sh` no usa `-Werror`. Si se quiere limpiar, mover la definición bajo el mismo `#ifndef` o añadir `__attribute__((unused))`; no se hizo.

### 6.3 Modos de fallo silenciosos (los importantes)

1. **Patch saltado**: `git apply --check` falla → `warning: Skipping patch ...` → el build sigue. Un kernel “success” puede no contener un patch. Mitigación: descargar el log y buscar `Skipping patch`; comparar símbolos/hashes esperados.
2. **Artefacto parcial**: `Collect` y upload tienen `|| true`/`if: always()`; un link fallido sube un `xnu-kernel` de 178 KB. Presencia de artefacto ≠ éxito. Verificar `conclusion: success` y `SHA256SUMS`/tamaño.
3. **`shim-boot.img` obsoleto**: el wrapper `sweet-gpu-image.sh` hace `build.sh | grep ... || true` sin `pipefail`; si el build falla, queda el `shim-boot.img` anterior. El `cmp` de ramdisk es el guard; no omitirlo.
4. **ADT distinto**: `mkadt.py` usa `os.urandom(64)`; regenerar el ADT cambia el payload y la imagen. Si se compara un hash viejo, no coincide aunque el kernel sea el mismo.
5. **Repo equivocado**: `-R dipa-studio/ios-sweet` da 404 para los runs de `limonetexd/ios-sweet-gpu`; el `gh run download` falla o descarga otro artefacto.
6. **`rd=ufsroot0` vs `rd=md0`**: si se añade `--ramdisk` a `mkpayload`, hay que cambiar el cmdline y el ADT; no hacerlo produce un payload con un segmento extra que el kernel no usa como root.
7. **`sweetgpu_reboot` mal entendido**: el código no reinicia a los N segundos exactos. `sg_reboot_fastboot` hace `if (when > 20) sleep(when-20)` y luego 12 s, medidos desde que se ejecuta esa función, no necesariamente desde el arranque; para 90 son 70+12 s desde esa llamada, para 120 100+12 s, para 1 solo 12 s (no 1). No es un temporizador de precisión y no se cronometró en el teléfono.
8. **`serial=0`**: las imágenes usan `serial=0` para no bloquear IOLog cuando el buffer se llena; esto quita el console serial temprano. Es una decisión de diagnóstico, no un fallo.
9. **`sweetfb_hz`**: super/0101 usan 60; branch usa 30. No es solo estético: cambia el ritmo de presentación y las medidas de fps; no comparar rendimiento entre imágenes sin mirar este arg.
10. **`if-no-files-found: warn`**: si no hay kernel, el step de upload no falla; el run puede quedar “success” con un artefacto vacío. En la práctica `Collect` también `|| true`.

---

## 7. Inventario

### 7.1 Artefactos locales

| Ruta | Tamaño | SHA256 | Notas |
|---|---:|---|---|
| `xnu/out-0105/kernel.development.sweet` | 17,382,896 | `d22c5aad...` | kernel super, CI 41501352880 |
| `xnu/out-0105/kernel.development.sweet.link/` | 138,875,280 (`.a`) | — | dSYM/linkarguments; no es input de la imagen |
| `xnu/out-0105/kdk-libs/` | ~1.54 MB | — | KDK 13.5 22G74, libs arm64e |
| `xnu/out-0101/kernel.development.sweet` | 17,272,256 | `d2bbc4dc...` | kernel 0101 |
| `shim/out/Image` | 380,928 | `94e447f7...` | shim ELF → binario, embebido en las 3 imágenes |
| `shim/out/shim.elf` | 117,456 | `e29ea013...` | ELF64 aarch64, entry 0, LOAD RWE |
| `shim/out/payload-super.bin` | 16,757,888 | `8201e7de...` | kernel 0105 + wlan ADT |
| `shim/out/payload-0101s0reboot.bin` | 16,663,456 | `b1a21ba8...` | kernel 0101 + gpupool ADT |
| `shim/out/payload-branch-reboot.bin` | 16,989,856 | `ff6fef04...` | kernel branch + wlan ADT |
| `shim/out/shim-boot-super.img` | 17,494,016 | `67ff470f...` | boot v2 |
| `shim/out/shim-boot-0101s0reboot.img` | 17,399,808 | `e0be26fc...` | boot v2 |
| `shim/out/shim-boot-branch-reboot.img` | 17,723,392 | `833b199c...` | boot v2 |
| `shim/out/shim-boot.img` | 17,723,392 | `833b199c...` | salida canónica del último build = branch |
| `shim/out/ramdisk.bin` | 16,989,856 | `ff6fef04...` | copia del payload branch |
| `dtb/boot_unpacked/dtb` | 346,902 | `29cc551e...` | FDT v17, last_comp 16 |
| `shim/out/sweet-gpupool.adt` | 12,772 | `a8f78c1a...` | ADT con GPU pool, sin wlan |
| `shim/out/sweet-wlan.adt` | 12,960 | `994c8cac...` | ADT + nodo wlan |
| `shim/out/sweet-local.adt` | 12,772 | `9f8d00f6...` | otra seed; no usado en estas imágenes |
| `research/ipsw-x/d22ap.adt` | 186,084 | `9e670987...` | /product de D22AP; input de `mkadt.py` |
| `research/gpu-sweet/fw/a618_gmu.bin` | 32,768 | `9ef10b2b...` | firmware, no en git |
| `research/gpu-sweet/fw/a630_sqe.fw` | 32,136 | `36298bd5...` | firmware, no en git |
| `research/gpu-sweet/fw/a615_zap.mdt` | 6,860 | `534aec7f...` | firmware, no en git |
| `research/gpu-sweet/fw/a615_zap.b02` | 1,984 | `61be42f0...` | firmware, no en git |

### 7.2 Lo que está en git y lo que no

Trackeado:

- `xnu.yml`, `userland.yml`, `tools/*.py`, `tools/*.sh`, `shim/*.c`, `shim/*.S`, `shim/*.h`, `shim/build.sh`, `shim/shim.ld`, `xnu/patches/*.patch` (105) y `*.sh` (3).
- `dtb/` está en `.gitignore`; el DTB no está trackeado.
- `shim/out/` está ignorado; todas las imágenes/payloads son locales.
- `xnu/out-*/` está ignorado; los kernels son locales (o artefactos de GitHub).
- `research/` está ignorado; firmware, `d22ap.adt`, `gpu-sweet` no están en git.
- `logs/`, `reports/`, `recovery/`, `backup/`, `research_notes/` ignorados.
- `0098` y `0100` están untracked; no están en el checkout de CI.

### 7.3 Toolchain local observado

WSL Ubuntu:

```
aarch64-linux-gnu-gcc 15.2.0
gcc 15.2.0
Python 3.14.4
mkbootimg 1:34.0.5-12build1 (Python script, 605 líneas)
cpio (GNU cpio) 2.15
readelf/file/nm de binutils
```

`mkbootimg` genera cabecera v2, `id` de 32 bytes (20 útiles), `--os_version 17.0.0`, `--os_patch_level 2035-06`. La versión exacta importa para el `id`; el resto de la cabecera es estable.

---

## 8. Reproducción paso a paso

### 8.0 Prerrequisitos

- Linux/WSL con `aarch64-linux-gnu-gcc`, `aarch64-linux-gnu-objcopy`, `aarch64-linux-gnu-readelf`, `aarch64-linux-gnu-nm`, `mkbootimg`, `cpio`, `gzip`, `python3`.
- `dtb/boot_unpacked/dtb` (346,902 B, SHA256 `29cc551e...`). Si no está, extraerlo con `tools/unpack_bootv2.py` del boot.img stock; sin él `build.sh` falla.
- Firmware `research/gpu-sweet/fw/*` (4 blobs) si se compila con `SHIM_GPUPROBE`.
- `research/ipsw-x/d22ap.adt` (186,084 B) si se regenera el ADT; sin él `mkadt.py` avisa y omite `/product`, cambiando el ADT.
- Kernel: `xnu/out-0105/kernel.development.sweet` (super), `xnu/out-0101/...` (0101), o el branch (no disponible).

### 8.1 Reconstruir el kernel desde CI

```bash
gh run download 41501352880 \
  -R limonetexd/ios-sweet-gpu \
  -n xnu-kernel \
  -D xnu/out-0105
cd xnu/out-0105
shasum -a 256 -c SHA256SUMS
```

Comprobar que el kernel es Mach-O arm64, `LC_UUID 951f3cec...`, entry `0xfffffe0007494488`, y que contiene `sweet_bt_init`, `flame_wlan_init`, `sweet_rpmh`, `sweet_pmem`, `sweet_files`, `SweetBattery`. Si falta alguno, el artefacto no es el 0105 esperado.

### 8.2 Reconstruir `shim-boot-super.img`

```bash
# 1) payload
python3 -I tools/mkpayload.py \
  xnu/out-0105/kernel.development.sweet \
  shim/out/sweet-wlan.adt \
  shim/out/payload-super.bin \
  --cmdline "debug=0xc serial=0 cpus=8 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=60 sweetgpu=2 sweetpmem=1 sweetsmmuprobe=1 sweetsmmuwlan=1 sweetwifi=1 sweetfiles=1 sweetusb=2 sweetgpu_reboot=120"

# 2) shim + boot image
( cd shim && SHIM_CFLAGS="-DSHIM_GPUPROBE -DSHIM_GPUBOOT" ./build.sh ../shim/out/payload-super.bin )

# 3) nombre y verificación
cp shim/out/shim-boot.img shim/out/shim-boot-super.img
python3 -I tools/unpack_bootv2.py shim/out/shim-boot-super.img shim/out/check-super
cmp shim/out/check-super/ramdisk shim/out/payload-super.bin && echo RAMDISK_MATCH
sha256sum shim/out/shim-boot-super.img
```

Resultado esperado: payload `8201e7de...`, imagen `67ff470f...`, tamaño 17,494,016. Si la seed del ADT es distinta, el payload/imagen cambiarán; usar el `sweet-wlan.adt` existente para obtener el hash exacto. La warning `gpu_paint` es esperada.

### 8.3 Reconstruir `shim-boot-0101s0reboot.img`

Igual, con:

- kernel `xnu/out-0101/kernel.development.sweet`
- ADT `shim/out/sweet-gpupool.adt`
- cmdline sin Wi-Fi/files/pmem/usb y con `sweetgpu_reboot=90`:

```
debug=0xc serial=0 cpus=8 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=60 sweetgpu=2 sweetgpu_reboot=90
```

Resultado esperado: payload `b1a21ba8...`, imagen `e0be26fc...`, 17,399,808 B.

### 8.4 Reconstruir `shim-boot-branch-reboot.img`

No hay kernel branch local. Dos opciones:

**A. Principled (requiere el kernel branch):** usar el kernel DC28088, `sweet-wlan.adt`, y el cmdline de branch (`sweetfb_hz=30`, Wi-Fi/files/pmem/usb, `sweetgpu_reboot=120`), con el mismo `mkpayload` + `build.sh`.

**B. Exacta a partir del payload existente:** `payload-branch-reboot.bin` es `payload-wifi-auto.bin` con dos bytes cambiados (`600` → `120`). Se puede verificar:

```bash
cmp -l shim/out/payload-wifi-auto.bin shim/out/payload-branch-reboot.bin
# 416 66 61
# 417 60 62
```

No es recomendable editar el binario a mano para producir una imagen “oficial”; sirve como prueba de que el branch es el kernel Wi-Fi, no una build nueva. Para una imagen reconstruible, conservar el kernel y el ADT y volver a ejecutar la cadena.

Resultado esperado: payload `ff6fef04...`, imagen `833b199c...`, 17,723,392 B.

### 8.5 Verificación de integridad (obligatoria)

```bash
# 1. payload ↔ ramdisk de la imagen
cmp shim/out/check-T/ramdisk shim/out/payload-T.bin

# 2. kernel ↔ Image
cmp shim/out/check-T/kernel shim/out/Image

# 3. DTB ↔ fuente
cmp shim/out/check-T/dtb dtb/boot_unpacked/dtb

# 4. cabecera
python3 -I tools/unpack_bootv2.py shim/out/shim-boot-T.img shim/out/check-T2
cat shim/out/check-T2/header.txt

# 5. payload
python3 - <<'PY'
import struct
b=open("shim/out/payload-T.bin","rb").read()
print(struct.unpack_from("<8sII",b,0))
print([hex(x) for x in struct.unpack_from("<7Q",b,0x10)])
PY

# 6. SHA256
sha256sum shim/out/shim-boot-T.img shim/out/payload-T.bin
```

Los `cmp` de las tres imágenes actuales devuelven 0 para kernel, ramdisk y dtb; eso no garantiza que el kernel sea el correcto, solo que la imagen contiene los archivos esperados.

### 8.6 Checklist de pitfalls

- [ ] ¿El repo del `gh run download` es `limonetexd/ios-sweet-gpu`, no `dipa-studio/ios-sweet`?
- [ ] ¿El run tiene `conclusion: success` y el `Build` step no falló?
- [ ] ¿El artefacto `xnu-kernel` pesa ~61 MB (no 178 KB)?
- [ ] ¿`SHA256SUMS` verifica?
- [ ] ¿El kernel tiene los símbolos esperados (`sweet_bt_init`/`flame_wlan_init`/`RedwoodGPU`/`NativeAdreno` según la variante)?
- [ ] ¿El ADT es el correcto (`wlan` vs `gpupool`) y su seed es la del payload que se quiere reproducir?
- [ ] ¿El `cmp` ramdisk ↔ payload pasa?
- [ ] ¿El `Image` embebido es `94e447f7...`?
- [ ] ¿El cmdline tiene el `sweetgpu_reboot`, `sweetfb_hz` y flags de Wi-Fi esperados?
- [ ] ¿Se registró el SHA256 de la imagen y del payload?
- [ ] ¿Se evitó el `fastboot`/`adb` (este informe es solo build)?

---

## 9. Próximos pasos

Prioridad alta:

1. **Fijar la seed del ADT.** Añadir `--seed HEX` a `tools/mkadt.py` (o guardar el `.adt` exacto y su hash en el manifiesto). Sin esto, ninguna imagen es reproducible byte a byte. Es la causa raíz de que `sweet-local.adt` y `sweet-gpupool.adt` tengan el mismo tamaño y distinto hash.
2. **Corregir el repo en la documentación y en los comandos.** `xnu/README.md` y `NOTES.md:357` deben decir `-R limonetexd/ios-sweet-gpu`; el comando actual da 404 para los runs recientes.
3. **Añadir `build-info.txt` al artefacto `xnu-kernel`.** Debe incluir `head_sha`, run id, `sw_vers`, `xcodebuild -version`, `clang --version`, `ld -v`, KDK (`KDK_13.5_22G74`), lista de patches aplicados/saltados, y `SHA256SUMS`. Sin esto, el artefacto no es autodescriptivo.
4. **Guardar el kernel branch y su commit.** Hoy solo existe el payload; si se pierde `payload-branch-reboot.bin`, no se puede reconstruir la imagen branch. Conservar el `kernel.development.sweet` del branch, su UUID, su `linkarguments` y el run/commit.
5. **Verificar el log de CI de 0105** para `Skipping patch`; si alguno se saltó, documentarlo. No asumir que los 105 se aplicaron.
6. **Comparar el kernel de `macos-latest`** con el de Intel: descargar el artefacto `41502238106`, verificar `SHA256SUMS`, UUID y tamaño; determinar si el cross-compile Intel y el nativo arm64 producen el mismo binario. Si no, fijar un runner.
7. **Añadir un manifiesto de imagen** (`manifest.json` o `.sha256`) que cubra kernel, ADT, DTB, firmware, `Image`, payload e imagen; incluir el cmdline completo y el hash del ADT. Hoy el `sha256sum` solo se imprime a stdout y se pierde.
8. **Hacer que `sweet-gpu-image.sh` acepte el ADT** (`ADT=...`) y no hardcodear `sweet-gpupool.adt`; así super/branch se pueden reconstruir con el script.
9. **Poner `set -o pipefail`** en el wrapper y no silenciar `build.sh` con `grep || true`; si se quiere filtrar la salida, capturar el código de salida antes.
10. **Decidir qué hacer con `0098`/`0100`**: commitearlos si son necesarios o borrarlos si son experimentos. Hoy están untracked y no están en CI; confunden la reproducibilidad.
11. **Registrar la versión de `mkbootimg`** y el `id` de la cabecera; si se cambia de versión, el `id` puede cambiar. No usar el `id` como checksum.
12. **Probar las imágenes** (fuera de este informe): super (Wi-Fi+batería+topaz), 0101s0reboot, branch. No se hizo aquí por la restricción de no tocar el teléfono.

Prioridad media:

- Añadir un job de CI que al menos parsee `mkpayload.py`/`unpack_bootv2.py` con un kernel dummy y valide los asserts; no requiere toolchain aarch64.
- Añadir un test de `mkadt.py` con seed fija y comparar hashes.
- Documentar el `sweetgpu_reboot` real (`N-20` + 12 s) en las notas de boot args.
- Revisar `xnu/README.md`: dice “Built on GitHub's macOS arm64 runners”, pero el run 0105 fue Intel; actualizar.
- Revisar la retención: `xnu-kernel` expira 2027-01-31; `xnu-buildtree` expira 2026-11-09. Copiar el kernel y el buildtree a almacenamiento propio antes de esa fecha.

Riesgos de reproducibilidad, ordenados:

1. **ADT random seed** (bloquea byte-identidad).
2. **Runner/Xcode/KDK no pinneados** (bloquea byte-identidad del kernel; permite reproducibilidad funcional).
3. **Patch skip silencioso** (puede cambiar el kernel sin fallar).
4. **Artefactos sin manifiesto** (no se sabe qué se descargó).
5. **Branch kernel no retenido** (pérdida irreversible de esa variante).
6. **Firmware/DTB/d22ap.adt fuera de git** (pérdida de inputs).
7. **`mkbootimg`/GCC version drift** (cambia `Image`/`id`).
8. **Repo equivocado** (descarga 404 o artefacto de otro proyecto).

---

## 10. Preguntas para otra IA

1. ¿Cuál es el repo canónico para CI: `dipa-studio/ios-sweet` o `limonetexd/ios-sweet-gpu`? ¿Por qué `origin` y `mine` apuntan a distintos? ¿Qué runs pertenecen a cada uno?
2. ¿El kernel 0105 se construyó exactamente con `771481a` + `34e3a8f`, o el árbol de `34e3a8f` incluye cambios posteriores? Confirmar con `git merge-base` y el `linkarguments`.
3. ¿Se aplicaron los 105 patches en 0105? ¿Hay `Skipping patch` en el log? ¿Cuáles?
4. ¿Por qué `0098` y `0100` están untracked? ¿Son necesarios para 0101/0105 o son experimentos locales? ¿Deben commitearse?
5. ¿Qué Xcode/SDK/clang/ld usa `macos-15-intel` en el run 41501352880? ¿Se puede obtener del log o de `xcodebuild -version`?
6. ¿El kernel de `macos-latest` (41502238106) es byte a byte distinto del de Intel? ¿Su UUID/tamaño? ¿Merece la pena usarlo por los 5m vs 19m?
7. ¿Cuál es el commit/artefacto exacto del kernel branch? ¿Se conserva el `kernel.development.sweet` en algún lado? ¿Se puede reconstruir sin el payload?
8. ¿Por qué el `id` de la cabecera no coincide con la recomputación de `mkbootimg` de WSL? ¿Qué versión/orden de inputs usó el build?
9. ¿La seed de `mkadt.py` es intencionalmente aleatoria por seguridad (ASLR del boot) o por descuido? ¿Se puede fijar sin romper la seguridad?
10. ¿El `sweetgpu_reboot=90/120` está pensado como `N-20` + 12 s o debería ser un temporizador exacto? ¿Los valores actuales son los deseados?
11. ¿La imagen super (0105 + wlan ADT) bootea y mantiene Wi-Fi/batería/topaz? ¿Hay log? ¿El `sweetfb_hz=60` es correcto para el panel de 120 Hz?
12. ¿`HANDOFF.md` existe fuera del workspace? Si sí, ¿qué información de build/CI contiene que no esté en `NOTES.md`?
13. ¿Se debe añadir un job de CI para el shim (instalando `gcc-aarch64-linux-gnu` + `mkbootimg`) o se mantiene local por los firmware blobs no redistribuibles?
14. ¿La retención de 90 días de `xnu-kernel` es suficiente? ¿Dónde se archiva el kernel 0105 y el branch antes de que expire?

---

<!-- END -->
