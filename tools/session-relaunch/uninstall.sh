#!/usr/bin/env bash
# The automated inverse of install.sh (README.md, Uninstall). Ported from #1116's host install v6 MANUAL-INVERSE.md, the
# block the command center ran by hand, with its gates unchanged: it deletes only what the install manifest lists, and
# every check below runs before the first unit command, copy or removal. One change: the expected file records are not
# hardcoded digests but the bytes of the recorded source commit in this checkout (the manifest's source_commit, bound by
# the receipt), and the config's digest is the manifest's own record. Run it from a checkout that holds that commit.
set -euo pipefail
REL=tools/session-relaunch
TOOL=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
REPO=$(git -C "$TOOL" rev-parse --show-toplevel)
# 0. Names, the receipt-manifest binding and the exact records.
R="$HOME/.local/state/native-agent-stack/session-relaunch-install"
T="$HOME/.local/share/native-agent-stack/session-relaunch"; S="$HOME/.local/state/native-agent-stack/session-relaunch"
U="$HOME/.config/systemd/user"
I="$R/install-state"; M="$I/install-manifest.tsv"; RECEIPT="$R/apply-receipt.txt"
UNITS=(ns-session-roster.service ns-session-roster.timer ns-session-relaunch.service)
real() { [ -e "$1" ] && [ ! -L "$1" ] && [ "$(realpath -e -- "$1")" = "$1" ]; }
for p in "$R" "$I" "$M" "$RECEIPT"; do if ! real "$p"; then echo "STOP: $p is missing, a symlink or not at its real path; nothing changed"; exit 1; fi; done
if [ ! -d "$I" ] || [ ! -f "$M" ] || [ ! -f "$RECEIPT" ]; then echo "STOP: install-state, manifest or receipt is not the expected type; nothing changed"; exit 1; fi
rid=$(awk -F'\t' '$1=="install_id"{print $2}' "$RECEIPT"); rman=$(awk -F'\t' '$1=="manifest"{print $2}' "$RECEIPT"); rsha=$(awk -F'\t' '$1=="manifest_sha256"{print $2}' "$RECEIPT")
mid=$(awk -F'\t' '$1=="install_id"{print $2}' "$M"); msha=$(sha256sum < "$M" | cut -d' ' -f1)
if [ -z "$rid" ] || [ "$rid" != "$mid" ] || [ "$rman" != "$M" ] || [ "$rsha" != "$msha" ]; then echo "STOP: receipt and manifest are not bound (install_id, path or sha256 differ); nothing changed"; exit 1; fi
if [ -e "$R/apply-receipt.txt.consumed-$rid" ]; then echo "STOP: install $rid was already cleaned up (its receipt is consumed); nothing changed"; exit 1; fi
commit=$(awk -F'\t' '$1=="source_commit"{print $2}' "$M"); H=$(awk -F'\t' '$1=="handoff_dir"{print $2}' "$M")
if [ "$(awk -F'\t' '$1=="source_commit"' "$M" | wc -l)" != 1 ] || [ "$(awk -F'\t' '$1=="handoff_dir"' "$M" | wc -l)" != 1 ] || [ -z "$H" ]; then echo "STOP: the manifest does not name exactly one source commit and one handoff directory; nothing changed"; exit 1; fi
if ! [[ "$commit" =~ ^[0-9a-f]{40}$ ]] || ! git -C "$REPO" cat-file -e "$commit^{commit}" 2>/dev/null; then echo "STOP: source commit ${commit:-<none>} is not in this checkout ($REPO); nothing changed"; exit 1; fi
gitsha() { git -C "$REPO" show "$commit:$REL/$1" | sha256sum | cut -d' ' -f1; }
csha=$(awk -F'\t' -v p="$S/config.json" '$1=="file"&&$2==p&&$3=="0600"{print $4}' "$M")
if ! [[ "$csha" =~ ^[0-9a-f]{64}$ ]]; then echo "STOP: the manifest has no 0600 config record with a sha256; nothing changed"; exit 1; fi
expected=$(printf '%s\t%s\t%s\n' "$T/session_relaunch.py" 0644 "$(gitsha session_relaunch.py)" "$S/config.json" 0600 "$csha" \
  "$U/${UNITS[0]}" 0644 "$(gitsha "units/${UNITS[0]}")" "$U/${UNITS[1]}" 0644 "$(gitsha "units/${UNITS[1]}")" \
  "$U/${UNITS[2]}" 0644 "$(gitsha "units/${UNITS[2]}")")
recorded=$(awk -F'\t' '$1=="file"{print $2"\t"$3"\t"$4}' "$M")
if [ "$recorded" != "$expected" ]; then echo "STOP: the manifest's file records are not the five expected ones; nothing changed"; exit 1; fi
allowed=$(printf '%s\n' "$HOME/.local" "$HOME/.local/share" "$HOME/.local/share/native-agent-stack" "$T" "$HOME/.local/state" "$HOME/.local/state/native-agent-stack" "$S")
dirs_ok=$(awk -F'\t' -v allowed="$allowed" 'BEGIN{n=split(allowed,a,"\n"); for(i=1;i<=n;i++) ok[a[i]]=1; good=1} $1=="dir"{ if(!($2 in ok) || $3!="0755" || $4!="-") good=0 } END{print good}' "$M")
if [ "$dirs_ok" != 1 ]; then echo "STOP: a manifest directory record is not one of the seven computed ancestors with mode 0755; nothing changed"; exit 1; fi
# 1. Real paths of everything the inverse may touch, and the provenance of every unit file that exists.
if ! real "$H" || [ ! -d "$H" ]; then echo "STOP: handoff directory $H is missing, moved or a symlink; nothing changed"; exit 1; fi
while IFS=$'\t' read -r f mode h; do d=$(dirname -- "$f"); while [ "$d" != "$HOME" ] && [ "$d" != / ]; do if [ -e "$d" ] && ! real "$d"; then echo "STOP: $d is a symlink or not its real path; nothing changed"; exit 1; fi; d=$(dirname -- "$d"); done; if [ -e "$f" ] || [ -L "$f" ]; then if ! real "$f" || [ ! -f "$f" ]; then echo "STOP: $f is a symlink, not a regular file or not its real path; nothing changed"; exit 1; fi; fi; done <<< "$expected"
for u in ns-session-roster.timer ns-session-relaunch.service ns-session-roster.service; do if [ -e "$U/$u" ]; then h=$(awk -F'\t' -v p="$U/$u" '$1=="file"&&$2==p{print $4}' "$M"); if [ "$(sha256sum < "$U/$u" | cut -d' ' -f1)" != "$h" ]; then echo "STOP: $U/$u is not the unit this install wrote; nothing changed"; exit 1; fi; fi; done
# 2. Evidence and the handoff inventory, computed into files with checked commands.
RB=$(umask 077; mktemp -d "$R/rollback-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX"); echo "evidence: $RB"
cp -p -- "$M" "$RECEIPT" "$RB/"
if [ -d "$S" ]; then cp -rp -- "$S" "$RB/state-copy"; fi
awk -F'\t' '$1=="handoff"{print $2}' "$M" | LC_ALL=C sort > "$RB/handoffs-before.txt"
find "$H" -mindepth 1 -maxdepth 1 \( -name 'AUTO-RESTART-*.md' -o -name '.AUTO-RESTART-*.md.*' \) -printf '%f\n' > "$RB/handoffs-now.unsorted"
LC_ALL=C sort "$RB/handoffs-now.unsorted" > "$RB/handoffs-now.txt"
LC_ALL=C comm -13 "$RB/handoffs-before.txt" "$RB/handoffs-now.txt" > "$RB/new-handoffs.txt"
cat "$RB/new-handoffs.txt"
# 3. Units: each state read must succeed and be loaded or not-found; only loaded units are touched.
loaded=()
for u in ns-session-roster.timer ns-session-relaunch.service ns-session-roster.service; do st=$(systemctl --user show -p LoadState --value "$u"); case "$st" in loaded) loaded+=("$u") ;; not-found) echo "$u: not-found, nothing to stop" ;; *) echo "STOP: $u LoadState=${st:-<empty>}"; exit 1 ;; esac; done
for u in "${loaded[@]}"; do case "$u" in ns-session-roster.timer|ns-session-relaunch.service) systemctl --user disable --now "$u" ;; ns-session-roster.service) systemctl --user stop "$u" ;; esac; done
if [ "${#loaded[@]}" -gt 0 ]; then systemctl --user reset-failed "${loaded[@]}"; fi
for u in "${loaded[@]}"; do as=$(systemctl --user show -p ActiveState --value "$u"); if [ "$as" != inactive ]; then echo "STOP: $u ActiveState=${as:-<empty>}; no file removed"; exit 1; fi; done
# 4. Files: each removed only if it is a regular file at its real path that still has its manifest sha256.
: > "$RB/kept.txt"
while IFS=$'\t' read -r f mode h; do if real "$f" && [ -f "$f" ] && [ "$(sha256sum < "$f" | cut -d' ' -f1)" = "$h" ]; then rm -f -- "$f"; echo "removed $f"; else echo "kept $f (absent or changed)" | tee -a "$RB/kept.txt"; fi; done <<< "$expected"
if [ "${#loaded[@]}" -gt 0 ]; then systemctl --user daemon-reload; fi
# 5. Directories the manifest lists, deepest first, only when empty and at their real path.
for d in "$S" "$HOME/.local/state/native-agent-stack" "$HOME/.local/state" "$T" "$HOME/.local/share/native-agent-stack" "$HOME/.local/share" "$HOME/.local"; do if awk -F'\t' -v p="$d" '$1=="dir"&&$2==p{x=1}END{exit !x}' "$M"; then if real "$d" && [ -d "$d" ] && rmdir -- "$d" 2>/dev/null; then echo "removed $d"; else echo "kept $d (not empty, not a directory or not its real path)" | tee -a "$RB/kept.txt"; fi; fi; done
# 6. What remains; then either "reconciliation pending" or a completed cleanup that retires the receipt and the manifest.
for p in "$S" "$T"; do if [ -e "$p" ]; then ls -la -- "$p"; fi; done > "$RB/remaining.txt"
if [ -s "$RB/new-handoffs.txt" ] || [ -s "$RB/kept.txt" ] || [ -s "$RB/remaining.txt" ]; then echo "cleanup completed, reconciliation pending: see $RB"; else mv -- "$RECEIPT" "$R/apply-receipt.txt.consumed-$rid"; chmod 0400 "$R/apply-receipt.txt.consumed-$rid"; mv -- "$I" "$RB/install-state"; echo "cleanup completed: nothing remains; receipt consumed for install $rid"; fi
