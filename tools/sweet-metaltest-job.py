#!/usr/bin/env python3
"""Add or remove the org.ios-sweet.metaltest launchd job on a mounted root.

  sweet-metaltest-job.py MOUNTED_ROOT [--apply] [--remove]

Edits MOUNTED_ROOT/System/Library/xpc/launchd.plist (binary plist, the same file and
format tools/sweet-root-tweaks.py edits). Dry run unless --apply. Idempotent.

The job runs /redwood/bin/metaltest once at load as root, stdout/stderr left on /dev/null: the kernel copies that to the log for names in boot-arg sweetnull (0048); /dev/console is muted and can stop a job from launching
(so METALTEST: lines reach the kernel log), no KeepAlive. launchd has no start-delay key,
so the program is started with --delay and sleeps 20 s itself, after boot settles.
The process name (metaltest) must be listed in the kernel boot-arg sweetmetal_procs=.
"""
import os, plistlib, sys

KEY = '/System/Library/LaunchDaemons/org.ios-sweet.metaltest.plist'
LABEL = 'org.ios-sweet.metaltest'
JOB = {
    'Label': LABEL,
    'Program': '/redwood/bin/metaltest',
    'ProgramArguments': ['/redwood/bin/metaltest', '--delay'],
    'RunAtLoad': True,
    'UserName': 'root',
}


def main():
    args = sys.argv[1:]
    apply, remove = '--apply' in args, '--remove' in args
    pos = [a for a in args if not a.startswith('--')]
    if len(pos) != 1 or set(args) - {'--apply', '--remove'} - set(pos):
        sys.exit(__doc__)
    path = os.path.join(pos[0], 'System/Library/xpc/launchd.plist')
    if not os.path.isfile(path):
        sys.exit(f'not a mounted root (no {path})')
    st = os.stat(path)
    with open(path, 'rb') as f:
        plist = plistlib.load(f)
    jobs = plist['LaunchDaemons']
    old = [k for k, j in jobs.items() if j.get('Label') == LABEL]
    if remove:
        if not old:
            print('metaltest job not present: nothing to do')
            return
        for k in old:
            del jobs[k]
        print(f'remove {len(old)} job(s): {", ".join(old)}')
    else:
        if old == [KEY] and jobs[KEY] == JOB:
            print('metaltest job already present and current: nothing to do')
            return
        for k in old:
            del jobs[k]
        jobs[KEY] = dict(JOB)
        print(f'{"replace" if old else "add"} LaunchDaemons[{KEY}]:')
        for k, v in JOB.items():
            print(f'    {k} = {v!r}')
    if not apply:
        print('dry run: nothing written (use --apply)')
        return
    with open(path, 'wb') as f:
        plistlib.dump(plist, f, fmt=plistlib.FMT_BINARY)
    os.chown(path, st.st_uid, st.st_gid) if os.geteuid() == 0 else None
    os.chmod(path, st.st_mode & 0o7777)
    print(f'{path}: written')


if __name__ == '__main__':
    main()
