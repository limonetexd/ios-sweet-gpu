#!/bin/bash
# xnu-mkpatch.sh: turn the edits you made in the tree of tools/xnu-tree.sh into a numbered patch.
#
#   tools/xnu-mkpatch.sh NNNN-sweet-short-name MESSAGE.txt
#
# MESSAGE.txt: line 1 = subject, then a blank line, then the body (what / why / how to see it in
# the log). The patch goes to xnu/patches/NAME.patch (the series CI builds), or to
# xnu/patches-pending/ with PENDING=1 (CI does not apply those), or to $OUT_DIR if you set it.
# It is generated with `git diff` (so hunks, blank context lines and counts are right), checked with
# tools/check-patch.py (a literal newline inside a C string broke CI three times) and re-applied to
# the tree WITHOUT your edits (git apply --check), then committed in the tree with the patch file
# name as subject, so `tools/xnu-tree.sh update` knows it is in.
#
# Number: one more than the highest file in xnu/patches/ (the Wi-Fi drafts in patches-pending/ keep
# their old numbers there and get a new one when they are promoted). Never rewrite a patch CI has
# built: add a new one.
set -e
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="${XNU_TREE:-$HOME/cxnu}"
N="$1"
M="$2"
if [ -z "$N" ] || [ ! -f "$M" ]; then
  sed -n 2,16p "${BASH_SOURCE[0]}"
  exit 2
fi
case "$N" in [0-9][0-9][0-9][0-9]-*) ;; *) echo "name must look like 0139-sweet-what"; exit 2 ;; esac
if [ -n "${OUT_DIR:-}" ]; then
  OUT="$OUT_DIR/$N.patch"
elif [ -n "${PENDING:-}" ]; then
  OUT="$R/xnu/patches-pending/$N.patch"
else
  OUT="$R/xnu/patches/$N.patch"
fi
if [ -e "$OUT" ] && [ -z "${FORCE:-}" ]; then
  echo "$OUT exists: pick a new number (or FORCE=1 for a patch CI has not built yet)"
  exit 1
fi
cd "$T"
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
  echo "no edits in $T"
  exit 1
fi
git add -A
{
  printf 'From: HakiOS\nSubject: [PATCH %s] %s\n' "${N%%-*}" "$(head -1 "$M")"
  tail -n +2 "$M"
  printf -- '---\n'
  git diff --cached
} > "$OUT"
tr -d '\r' < "$OUT" > "$OUT.lf" && mv "$OUT.lf" "$OUT"
python3 -I "$R/tools/check-patch.py" "$OUT" || { echo "check-patch.py found problems (above): fix the tree, run again with FORCE=1"; exit 1; }
git stash -q
if git apply --check "$OUT"; then
  echo "apply check ok on the tree without your edits: $OUT"
else
  echo "APPLY CHECK FAILED: $OUT"
  git stash pop -q
  exit 1
fi
git stash pop -q
git add -A
git commit -qm "$N.patch"
echo "added lines: $(grep -c '^+' "$OUT")"
