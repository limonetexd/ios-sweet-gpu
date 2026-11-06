#!/usr/bin/env python3
"""Root-side fixes for the HakiOS (sweet) iOS 16.7.16 root, as separate named steps.

  sudo tools/sweet-root-fixes.py MOUNTED_ROOT [--dry-run] [--only a,b] [--skip a,b] [--no-STEP ...]

Run it on the mounted HFS+ root AFTER tools/sweet-root-tweaks.py (same workflow:
`fsck.hfsplus -fy`, `mount -t hfsplus -o loop,force`), as root, with configd /
launchd not running (offline image). Idempotent: a second run reports "ok" for
every step and changes nothing. --dry-run prints every change and writes nothing.
No Apple file is embedded; the script only edits files already in the root.

Steps (default on unless noted). Reference recipes were read on 2026-11-06:

  xpc-flag          ExtensionKit feature flag enforce_xpc_cache_code_signing=off
                    Source: joranv1/ios-sailfish @6f27e41, tools/sweet-root-tweaks.py
                    feature_flags(). (ios-topaz @e477291 has no root-side equivalent: it
                    solves the same problem in the kernel, patches 0147/0150/0151.)
  migrate-sentinel  empty /private/var/datamigrator/migrate so DataMigration runs once and
                    registers the app extensions.
                    Source: ios-sailfish @6f27e41 tools/sweet-root-tweaks.py main().
                    Evidence: ios-sweet NOTES.md (boot 0056n) quotes datamigrator strings
                    "Migration sentinel present. Migration necessary."
  staged-apps       move /private/var/staged_system_apps/*.app -> /Applications and drop the
                    LaunchServices caches so lsd rebuilds them.
                    Source: ios-sailfish @6f27e41 README.md "How to do it yourself" step 2.
                    The cache cleanup is our own addition (sailfish does not document one).
  wallpaper         HEIC layers of /Library/Wallpaper/Collections -> PNG twins, main.caml
                    points at the PNG. Equivalent of ios-sailfish @6f27e41
                    tools/wallpaper-heic2png.sh (commit c8959cb) for Linux: uses
                    heif-convert, magick/convert or vips if installed, else warns and skips.
  netprefs          explicit en0 / AirPort / DHCP service + set in
                    /private/var/preferences/SystemConfiguration/preferences.plist.
                    Source: Yofuness/ios-flame @a1b6eb8 tools/sunfish-netprefs.py (MIT),
                    adapted to edit the offline file instead of using the phone.
  wland-boot        remove stale /private/var/local/wland.boot (wland exits "already
                    started in this boot" when kern.boottime matches; the calendar restarts
                    at the epoch on every boot without an RTC).
                    Source: DC28088/ios-sweet codex/native-adreno-metal NOTES.md ~l.1360-1500,
                    as summarised in reports/research-2026-11-06-wifi.md section 1.1.
  migration-prefs   OFF by default (--only migration-prefs or --migration-prefs): remove
                    LastSystemVersion / DMUserDataDisposition from com.apple.migration
                    (written by sweet-root-tweaks.py) because the sentinel step is the
                    approach that actually registers extensions (ios-sailfish and our
                    NOTES.md boot 0056n: LastSystemVersion alone left 1 of 524 appex).
"""
import argparse, glob, os, plistlib, re, shutil, subprocess, sys

STEPS = ['xpc-flag', 'migrate-sentinel', 'staged-apps', 'wallpaper', 'netprefs', 'wland-boot',
         'migration-prefs']
DEFAULT_OFF = {'migration-prefs'}
MOBILE = 501

DRY = False
STATS = {'changed': 0, 'ok': 0, 'warn': 0}


def say(msg):
    print(('[dry-run] ' if DRY else '') + msg)


def changed(msg):
    STATS['changed'] += 1
    say(msg)


def unchanged(msg):
    STATS['ok'] += 1
    print('ok: ' + msg)


def warn(msg):
    STATS['warn'] += 1
    print('warning: ' + msg, file=sys.stderr)


def load(path):
    with open(path, 'rb') as f:
        return plistlib.load(f)


def chown_mode(path, uid, gid, mode):
    if DRY:
        return
    try:
        os.chown(path, uid, gid)
    except (PermissionError, AttributeError):  # AttributeError: no os.chown on Windows
        warn(f'cannot chown {path} to {uid}:{gid} (not root?)')
    os.chmod(path, mode)


def write_plist(path, data, uid, gid, mode, fmt):
    """Write a plist atomically-ish and set owner/mode."""
    if DRY:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        plistlib.dump(data, f, fmt=fmt)
    chown_mode(path, uid, gid, mode)


def rel(root, path):
    return '/' + os.path.relpath(path, root).replace(os.sep, '/')


# ---------------------------------------------------------------- steps

def step_xpc_flag(root):
    path = os.path.join(root, 'private/var/preferences/FeatureFlags/Domain/ExtensionKit.plist')
    want = {'enforce_xpc_cache_code_signing': {'Enabled': False}}
    data = load(path) if os.path.exists(path) else {}
    if data.get('enforce_xpc_cache_code_signing') == want['enforce_xpc_cache_code_signing']:
        return unchanged(rel(root, path) + ' already has enforce_xpc_cache_code_signing off')
    data.update(want)
    changed(f'write {rel(root, path)}: enforce_xpc_cache_code_signing -> Enabled=False')
    write_plist(path, data, 0, 0, 0o644, plistlib.FMT_XML)


def step_migrate_sentinel(root):
    path = os.path.join(root, 'private/var/datamigrator/migrate')
    if os.path.exists(path):
        return unchanged(rel(root, path) + ' exists')
    changed(f'create empty {rel(root, path)} (owner mobile, as sailfish)')
    if not DRY:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'a').close()
        chown_mode(path, MOBILE, MOBILE, 0o644)


LS_CACHE_GLOBS = [
    'private/var/mobile/Library/Caches/com.apple.LaunchServices-*.csstore',
    'private/var/mobile/Library/Caches/com.apple.LaunchServices-*.csstore.*',
    'private/var/containers/Data/System/*/Library/Caches/com.apple.LaunchServices-*.csstore',
    'private/var/containers/Data/System/*/Library/Caches/com.apple.LaunchServices-*.csstore.*',
    'private/var/db/lsd/com.apple.lsdschemes.plist',
]


def step_staged_apps(root):
    staged = os.path.join(root, 'private/var/staged_system_apps')
    apps_dir = os.path.join(root, 'Applications')
    if not os.path.isdir(staged):
        return unchanged('no /private/var/staged_system_apps (already moved or absent)')
    entries = sorted(e for e in os.listdir(staged) if e.endswith('.app'))
    moved = 0
    for e in entries:
        src, dst = os.path.join(staged, e), os.path.join(apps_dir, e)
        if os.path.lexists(dst):
            warn(f'/Applications/{e} already exists; left {rel(root, src)} in place')
            continue
        changed(f'move {rel(root, src)} -> /Applications/{e}')
        moved += 1
        if not DRY:
            os.makedirs(apps_dir, exist_ok=True)
            try:
                os.rename(src, dst)
            except OSError:
                shutil.move(src, dst)
    others = sorted(set(os.listdir(staged)) - set(entries))
    if others:
        warn('non-.app entries left in staged_system_apps: ' + ', '.join(others[:10]))
    if not entries:
        unchanged('staged_system_apps has no .app bundles')
    if moved:
        # lsd must rebuild its database to see the new locations.
        for pat in LS_CACHE_GLOBS:
            for f in sorted(glob.glob(os.path.join(root, pat))):
                changed(f'delete LaunchServices cache {rel(root, f)}')
                if not DRY:
                    os.remove(f)


def find_converter():
    for name, argv in (('heif-convert', ['heif-convert', '{src}', '{dst}']),
                       ('magick', ['magick', '{src}', '{dst}']),
                       ('convert', ['convert', '{src}', '{dst}']),
                       ('vips', ['vips', 'copy', '{src}', '{dst}'])):
        if shutil.which(name):
            return name, argv
    return None, None


CAML_RE = re.compile(rb'\.(?:HEIC|heic)"')


def step_wallpaper(root):
    base = os.path.join(root, 'Library/Wallpaper/Collections')
    if not os.path.isdir(base):
        return unchanged('no /Library/Wallpaper/Collections in this root')
    heics = []
    for d, _, files in os.walk(base):
        heics += [os.path.join(d, f) for f in files if f.lower().endswith('.heic')]
    camls = []
    for d, _, files in os.walk(base):
        camls += [os.path.join(d, f) for f in files if f == 'main.caml']
    todo = [h for h in heics if not os.path.exists(os.path.splitext(h)[0] + '.png')]
    name, argv = find_converter()
    if todo and name is None and not DRY:
        return warn(f'{len(todo)} wallpaper HEIC layers need conversion but no heif-convert / '
                    'magick / convert / vips was found (apt install libheif-examples); step skipped. '
                    'Alternative: run sailfish tools/wallpaper-heic2png.sh on macOS.')
    if todo and name is None:
        warn('dry-run: no HEIC converter found; the real run would skip this step')
    for h in todo:
        png = os.path.splitext(h)[0] + '.png'
        changed(f'convert {rel(root, h)} -> .png' + (f' with {name}' if name else ''))
        if DRY:
            continue
        cmd = [shutil.which(argv[0])] + [a.format(src=h, dst=png) for a in argv[1:]]
        try:
            r = subprocess.run(cmd, capture_output=True)
        except OSError as ex:
            warn(f'cannot run {cmd[0]}: {ex}')
            continue
        if r.returncode != 0 or not os.path.exists(png) or os.path.getsize(png) == 0:
            warn(f'conversion failed for {rel(root, h)}: {r.stderr.decode(errors="replace")[:200]}')
            if os.path.exists(png):
                os.remove(png)
        else:
            chown_mode(png, os.stat(h).st_uid, os.stat(h).st_gid, 0o644)
    edited = 0
    for caml in sorted(camls):
        with open(caml, 'rb') as f:
            data = f.read()
        if not CAML_RE.search(data):
            continue
        # Do not repoint a layer whose PNG twins are not all present.
        ca_dir = os.path.dirname(caml) + os.sep
        missing = [h for h in heics if h.startswith(ca_dir)
                   and not os.path.exists(os.path.splitext(h)[0] + '.png')]
        if missing and not DRY:
            warn(f'{rel(root, caml)} not edited: {len(missing)} PNG twin(s) missing')
            continue
        changed(f'edit {rel(root, caml)}: .HEIC" -> .png"')
        edited += 1
        if not DRY:
            st = os.stat(caml)
            with open(caml, 'wb') as f:
                f.write(CAML_RE.sub(b'.png"', data))
            os.chmod(caml, st.st_mode & 0o7777)
    if not todo and not edited:
        unchanged(f'wallpaper layers: {len(heics)} HEIC, all have PNG twins, no caml references HEIC')


NET_SVC = '5EE7C0DE-5EE7-4000-8000-00000000E000'
NET_SET = '5EE7C0DE-5EE7-4000-8000-00000000A000'


def netprefs_wanted():
    svc = {
        'DNS': {}, 'IPv4': {'ConfigMethod': 'DHCP'}, 'IPv6': {'ConfigMethod': 'Automatic'},
        'Proxies': {'ExceptionsList': ['*.local', '169.254/16'], 'FTPPassive': 1},
        'Interface': {'DeviceName': 'en0', 'Hardware': 'AirPort', 'Type': 'Ethernet',
                      'UserDefinedName': 'Wi-Fi'},
        'UserDefinedName': 'Wi-Fi'}
    st = {
        'Network': {'Global': {'IPv4': {'ServiceOrder': [NET_SVC]}},
                    'Interface': {'en0': {'AirPort': {'JoinModeFallback': ['DoNothing'],
                                                      'PowerEnabled': True}}},
                    'Service': {NET_SVC: {'__LINK__': '/NetworkServices/' + NET_SVC}}},
        'UserDefinedName': 'Automatic'}
    return svc, st


def step_netprefs(root):
    path = os.path.join(root, 'private/var/preferences/SystemConfiguration/preferences.plist')
    p = load(path) if os.path.exists(path) else {}
    svc, st = netprefs_wanted()
    if (p.get('NetworkServices', {}).get(NET_SVC) == svc and p.get('Sets', {}).get(NET_SET) == st
            and p.get('CurrentSet') == '/Sets/' + NET_SET):
        return unchanged(rel(root, path) + ' already has the en0 / AirPort / DHCP service')
    p.setdefault('NetworkServices', {})[NET_SVC] = svc
    p.setdefault('Sets', {})[NET_SET] = st
    p['CurrentSet'] = '/Sets/' + NET_SET
    changed(f'{"update" if os.path.exists(path) else "create"} {rel(root, path)}: service {NET_SVC} '
            f'(en0, AirPort, DHCP), set {NET_SET}, CurrentSet')
    write_plist(path, p, 0, 0, 0o644, plistlib.FMT_BINARY)


def step_wland_boot(root):
    path = os.path.join(root, 'private/var/local/wland.boot')
    if not os.path.lexists(path):
        return unchanged(rel(root, path) + ' absent')
    changed(f'delete {rel(root, path)}')
    if not DRY:
        os.remove(path)


def step_migration_prefs(root):
    path = os.path.join(root, 'private/var/mobile/Library/Preferences/com.apple.migration.plist')
    if not os.path.exists(path):
        return unchanged(rel(root, path) + ' absent')
    p = load(path)
    keys = [k for k in ('LastSystemVersion', 'DMUserDataDisposition') if k in p]
    if not keys:
        return unchanged('com.apple.migration.plist has no LastSystemVersion / DMUserDataDisposition')
    for k in keys:
        del p[k]
    changed(f'remove {keys} from {rel(root, path)}')
    st = os.stat(path)
    write_plist(path, p, st.st_uid, st.st_gid, st.st_mode & 0o7777, plistlib.FMT_BINARY)


FUNCS = {
    'xpc-flag': step_xpc_flag, 'migrate-sentinel': step_migrate_sentinel,
    'staged-apps': step_staged_apps, 'wallpaper': step_wallpaper, 'netprefs': step_netprefs,
    'wland-boot': step_wland_boot, 'migration-prefs': step_migration_prefs,
}


def main():
    global DRY
    ap = argparse.ArgumentParser(description='HakiOS root fixes (see module docstring)',
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog='steps: ' + ', '.join(STEPS) + ' (migration-prefs is off by default)')
    ap.add_argument('root', help='mounted iOS root directory')
    ap.add_argument('--dry-run', action='store_true', help='print every change, write nothing')
    ap.add_argument('--only', help='comma-separated steps to run (overrides defaults)')
    ap.add_argument('--skip', help='comma-separated steps to skip')
    for s in STEPS:
        ap.add_argument('--no-' + s, action='append_const', dest='no', const=s,
                        help=argparse.SUPPRESS if s in DEFAULT_OFF else f'skip step {s}')
    ap.add_argument('--migration-prefs', action='store_true', help='also run migration-prefs')
    a = ap.parse_args()
    DRY = a.dry_run
    root = a.root
    if not os.path.isdir(os.path.join(root, 'System/Library')) or not os.path.isdir(os.path.join(root, 'private/var')):
        sys.exit(f'{root} does not look like a mounted iOS root (needs System/Library and private/var)')

    def names(v):
        out = [x.strip() for x in v.split(',') if x.strip()]
        bad = [x for x in out if x not in STEPS]
        if bad:
            sys.exit('unknown step(s): ' + ', '.join(bad) + '; valid: ' + ', '.join(STEPS))
        return out
    if a.only:
        run = names(a.only)
    else:
        run = [s for s in STEPS if s not in DEFAULT_OFF]
        if a.migration_prefs:
            run.append('migration-prefs')
    skip = set(names(a.skip) if a.skip else []) | set(a.no or [])
    for s in STEPS:
        if s in run and s not in skip:
            print(f'== {s}')
            FUNCS[s](root)
    print(f'done: {STATS["changed"]} change(s){" (not written, dry run)" if DRY else ""}, '
          f'{STATS["ok"]} already ok, {STATS["warn"]} warning(s)')


if __name__ == '__main__':
    main()
