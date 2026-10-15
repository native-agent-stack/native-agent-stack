#!/usr/bin/env bash
# Forward install of the session-relaunch tool for one host (README.md, Install). Ported from #1116's applied host install
# v6 (apply.sh, applied on NativeStack2604 on 2026-10-15) with three changes: the sources are this checkout's committed
# bytes at HEAD, the host's config can be passed in, and the install state lives in its own root. Every gate stops the run
# before any write; after the gates and before the first write it seals an install manifest of what it creates, which
# uninstall.sh reverses. Usage: install.sh [--config <host config.json>]   (default: config.example.json at HEAD)
set -euo pipefail
REL=tools/session-relaunch
TOOL=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
REPO=$(git -C "$TOOL" rev-parse --show-toplevel)
COMMIT=$(git -C "$REPO" rev-parse --verify HEAD)
R="$HOME/.local/state/native-agent-stack/session-relaunch-install"
T="$HOME/.local/share/native-agent-stack/session-relaunch"
S="$HOME/.local/state/native-agent-stack/session-relaunch"
U="$HOME/.config/systemd/user"
I="$R/install-state"
M="$I/install-manifest.tsv"
RECEIPT="$R/apply-receipt.txt"    # outside install-state; uninstall.sh gates on it
UNITS=(ns-session-roster.service ns-session-roster.timer ns-session-relaunch.service)
# The only directories this install may create, parents first.
ANCESTORS=("$HOME/.local" "$HOME/.local/share" "$HOME/.local/share/native-agent-stack" "$T"
           "$HOME/.local/state" "$HOME/.local/state/native-agent-stack" "$S")
CONFIG=""
case "${1:-}" in
  "") ;;
  --config) CONFIG=${2:?--config needs a file}; [ "$#" -eq 2 ] || { echo "usage: install.sh [--config <file>]"; exit 2; } ;;
  *) echo "usage: install.sh [--config <file>]"; exit 2 ;;
esac

# Gate 1: the tool's directory has no change against HEAD, so the installed bytes are the committed ones; they are read
# from HEAD into a private staging directory, never from the working tree.
if ! git -C "$REPO" diff --quiet HEAD -- "$REL" || [ -n "$(git -C "$REPO" status --porcelain -- "$REL")" ]; then
  echo "STOP: $REL differs from HEAD $COMMIT; commit or discard first; nothing written"; exit 1
fi
STAGE=$(umask 077; mktemp -d)
trap 'rm -rf -- "$STAGE"' EXIT
for f in session_relaunch.py config.example.json "${UNITS[@]/#/units/}"; do
  git -C "$REPO" show "$COMMIT:$REL/$f" > "$STAGE/${f#units/}"
done
[ -n "$CONFIG" ] || CONFIG="$STAGE/config.example.json"
if [ -L "$CONFIG" ] || [ ! -f "$CONFIG" ]; then echo "STOP: config $CONFIG is not a regular file; nothing written"; exit 1; fi
H=$(python3 -I -c 'import json, os, sys
c = json.load(open(sys.argv[1]))
assert isinstance(c.get("profiles"), list) and c.get("handoff_dir") and c.get("state_dir")
assert os.path.expanduser(c["state_dir"]).rstrip("/") == sys.argv[2], "state_dir is not " + sys.argv[2]
print(os.path.expanduser(c["handoff_dir"]).rstrip("/"))' "$CONFIG" "$S") \
  || { echo "STOP: config $CONFIG does not parse, lacks profiles, handoff_dir or state_dir, or names another state_dir; nothing written"; exit 1; }
FILES=("$STAGE/session_relaunch.py|$T/session_relaunch.py|0644" "$CONFIG|$S/config.json|0600"
       "$STAGE/${UNITS[0]}|$U/${UNITS[0]}|0644" "$STAGE/${UNITS[1]}|$U/${UNITS[1]}|0644" "$STAGE/${UNITS[2]}|$U/${UNITS[2]}|0644")

# Gate 2: no target and no earlier manifest exists, a dangling symlink included; nothing is overwritten or adopted.
for p in "$T" "$S" "$I" "$RECEIPT" "$U/${UNITS[0]}" "$U/${UNITS[1]}" "$U/${UNITS[2]}"; do
  if [ -e "$p" ] || [ -L "$p" ]; then echo "STOP: $p exists; nothing written"; exit 1; fi
done

# Gate 2b: every directory this install writes under, and every one it may create under, is a real path: no symlink
# anywhere in it (realpath of the deepest existing ancestor equals itself), so the manifest's paths are real paths.
for p in "$R" "$U" "$H" "${ANCESTORS[@]}"; do
  q="$p"; while [ ! -e "$q" ] && [ "$q" != / ]; do q=$(dirname -- "$q"); done
  if [ -L "$q" ] || [ "$(realpath -e -- "$q")" != "$q" ]; then echo "STOP: $q is not a real path (symlink in it); nothing written"; exit 1; fi
done

# Gate 3: the OnFailure handler loads. A failed read, or any value but loaded, stops (loadability only, not delivery).
if ! state=$(systemctl --user show stack-alert@ns-session-relaunch.service.service --property=LoadState --value); then
  echo "STOP: reading the alert handler's LoadState failed; nothing written"; exit 1
fi
[ "$state" = loaded ] || { echo "STOP: stack-alert@ns-session-relaunch.service.service LoadState=${state:-<empty>}"; exit 1; }

# Gate 4: the handoff directory and the unit directory exist.
[ -d "$H" ] || { echo "STOP: handoff directory $H missing"; exit 1; }
[ -d "$U" ] || { echo "STOP: unit directory $U missing"; exit 1; }

# The install's own state root. It stays after an uninstall (it keeps the consumed receipt and the evidence), so the
# directories made for it are not this install's to remove and are created before the manifest counts what is missing.
umask 077
mkdir -p -- "$R"

# The install manifest, sealed before the first target write. Tab-separated: kind, path or value, mode, sha256.
#   install_id      a random id, also in the receipt; source_commit and handoff_dir: what uninstall.sh checks against
#   dir             each listed ancestor missing now, in creation order (install -D creates them, mode 0755)
#   file            each installed file with its mode and the sha256 of its source
#   handoff         each AUTO-RESTART file and write_atomic temporary file (.AUTO-RESTART-*.md.*) present now
INSTALL_ID=$(cat /proc/sys/kernel/random/uuid)
mkdir "$I"
{
  printf '# install manifest, session-relaunch install, written %s before the first write\n' "$(date -u +%FT%TZ)"
  printf 'install_id\t%s\t-\t-\n' "$INSTALL_ID"
  printf 'source_commit\t%s\t-\t-\n' "$COMMIT"
  printf 'handoff_dir\t%s\t-\t-\n' "$H"
  for d in "${ANCESTORS[@]}"; do
    if [ ! -e "$d" ] && [ ! -L "$d" ]; then printf 'dir\t%s\t0755\t-\n' "$d"; fi
  done
  for f in "${FILES[@]}"; do
    IFS='|' read -r src dst mode <<< "$f"
    printf 'file\t%s\t%s\t%s\n' "$dst" "$mode" "$(sha256sum < "$src" | cut -d' ' -f1)"
  done
  (cd "$H" && find . -maxdepth 1 \( -name 'AUTO-RESTART-*.md' -o -name '.AUTO-RESTART-*.md.*' \) -printf 'handoff\t%f\t-\t-\n' | LC_ALL=C sort)
} > "$M"
chmod 0400 "$M"
# The retained apply receipt: the manifest's full sha256, sealed beside install-state. uninstall.sh stops unless the
# manifest is a regular file whose digest equals this one.
printf 'install_id\t%s\nmanifest\t%s\nmanifest_sha256\t%s\n' "$INSTALL_ID" "$M" "$(sha256sum < "$M" | cut -d' ' -f1)" > "$RECEIPT"
chmod 0400 "$RECEIPT"
umask 022

install -D -m 0644 "$STAGE/session_relaunch.py" "$T/session_relaunch.py"
install -D -m 0600 "$CONFIG" "$S/config.json"
install -m 0644 "$STAGE/${UNITS[0]}" "$STAGE/${UNITS[1]}" "$STAGE/${UNITS[2]}" "$U/"

# Each manifest file is now there with its sha256 and mode, or the install stops before enabling anything.
while IFS=$'\t' read -r kind path mode sha; do
  if [ "$kind" = dir ]; then [ -d "$path" ] || { echo "STOP: $path was not created; nothing enabled"; exit 1; }; continue; fi
  [ "$kind" = file ] || continue
  [ "$(sha256sum < "$path" | cut -d' ' -f1)" = "$sha" ] && [ "$(stat -c %a "$path")" = "${mode#0}" ] \
    || { echo "STOP: $path differs from the manifest; nothing enabled"; exit 1; }
done < "$M"

systemctl --user daemon-reload    # the one explicit reload; enable reloads implicitly as well
systemctl --user enable --now ns-session-roster.timer
systemctl --user enable ns-session-relaunch.service    # runs at the next boot; not started now
echo "applied at $(date -u +%FT%TZ); install_id $INSTALL_ID; source $COMMIT; manifest $M; manifest sha256 $(sha256sum < "$M" | cut -d' ' -f1); receipt $RECEIPT"
