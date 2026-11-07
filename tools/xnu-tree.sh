#!/bin/bash
# xnu-tree.sh: a local copy of the kernel source exactly as CI sees it, to write and check patches.
#
# ~/cxnu (override: XNU_TREE=dir) = clean xnu-8796.141.3 + the HFS staging script + every
# xnu/patches/*.patch applied the way darwin-xnu-build does it (git apply --check, then git apply;
# a patch that does not apply is SKIPPED, as in CI), one git commit per patch, the commit subject
# is the patch file name. Nothing here can compile XNU (that is CI's job, Apple SDK): it checks
# that patches APPLY and gives you the files to edit.
#
#   tools/xnu-tree.sh            rebuild from the clean base (the clone is kept, ~1 minute)
#   tools/xnu-tree.sh update     apply only the patches not committed in the tree yet
#   tools/xnu-tree.sh check P    git apply --check one patch file on top of the tree (no commit)
#   tools/xnu-tree.sh status     how many patches are in, which were skipped
#
# Two agents must never edit the same tree at once: copy it (cp -a ~/cxnu ~/cxnu-NAME) and run
# with XNU_TREE=$HOME/cxnu-NAME. Run from WSL; the repo path is found from this script's location.
set -e
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="${XNU_TREE:-$HOME/cxnu}"
if [ ! -d "$T/.git" ]; then
  git clone -q --depth 1 --branch xnu-8796.141.3 https://github.com/apple-oss-distributions/xnu "$T"
  git -C "$T" config user.email t@t
  git -C "$T" config user.name t
  git -C "$T" tag base
fi
cd "$T"
case "$1" in
check)
  tr -d '\r' < "$2" > /tmp/xnu-tree-check.patch
  git apply --check -v /tmp/xnu-tree-check.patch 2>&1 | tail -8
  exit "${PIPESTATUS[0]}"
  ;;
status)
  echo "tree: $T"
  echo "commits: $(git log --oneline | wc -l) (patches in: $(git log --format=%s | grep -c '\.patch$'))"
  for p in "$R"/xnu/patches/*.patch; do
    b=$(basename "$p")
    git log --format=%s | grep -qxF "$b" || echo "NOT IN THE TREE: $b"
  done
  exit 0
  ;;
esac
if [ "$1" != "update" ]; then
  git reset -q --hard base
  git clean -qfdx
  MACHINE_CONFIG=SWEET MACOS_VERSION=13.5 bash "$R/xnu/patches/0026-stage-hfs.sh" && echo "staged hfs"
  git add -A > /dev/null
  git commit -qm "0026-stage-hfs.sh"
fi
for p in "$R"/xnu/patches/*.patch; do
  b=$(basename "$p")
  if git log --format=%s | grep -qxF "$b"; then continue; fi
  tr -d '\r' < "$p" > /tmp/xnu-tree-p.patch
  if git apply --check /tmp/xnu-tree-p.patch 2> /tmp/xnu-tree-apply.err; then
    git apply /tmp/xnu-tree-p.patch
    git add -A > /dev/null
    git commit -qm "$b"
    echo "ok   $b"
  else
    echo "SKIP $b: $(head -2 /tmp/xnu-tree-apply.err | tr '\n' ' ')"
  fi
done
echo "commits: $(git log --oneline | wc -l)"
