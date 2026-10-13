#!/usr/bin/env python3
"""Store one operator-supplied credential entry from adoption/credential-inventory.json.

Run it in your own terminal, directly or through open_credential_terminal.sh. Each value
is read with hidden input (getpass; the tool refuses if the terminal cannot hide input).
Values are never printed, logged or passed on a command line. They are written as
`export NAME=value` lines to the entry's file (mode 0600) in the per-host store (mode 0700,
owned by you, outside every Git worktree). Every write is made through a directory handle
opened without following symlinks. The output names variables only.

Live broker keys are deliberately not a stored entry (docs/secret-storage.md).

    python3 tools/credentials/set_credential.py alpaca-paper

`--from-env` is the one form without a terminal. It stores an entry that declares exactly one
variable from this process's environment, where `scripts/kernel_keyring.py exec` puts a key that
lives only in the kernel keyring, so the value never passes through an agent, a prompt or a command
line. It is create-only (it never replaces a file), refuses unless the interpreter was started with
-I -S, and prints only `<id>: stored`:

    python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- python3 -I -S tools/credentials/set_credential.py tavily --from-env

`--from-file` takes custody of a key file the operator downloaded, for an entry whose store is a private file (a
GitHub App's .pem). In your own terminal it asks for the downloaded file's path (visible: a path is not secret) and
copies the file, unread and unprinted, into the store as a new 0600 file. It checks the stored copy with
`openssl pkey -noout` (only its exit status is used), and removes the original only after that check passes:

    python3 tools/credentials/set_credential.py github-review-app --from-file
"""
from __future__ import annotations

import os
import sys

FROM_ENV_START = "python3 -I -S tools/credentials/set_credential.py <id> --from-env"

if __name__ == "__main__":
    if "--from-env" in sys.argv[1:]:
        # The value is already in this interpreter's environment, so whatever ran at start-up ran beside it. Only
        # -I -S starts no such code: -I ignores PYTHONPATH, PYTHON* variables and the user site directory, and -S
        # skips site, whose .pth lines of the interpreter's own site-packages run even under -I. Re-running cannot
        # undo a start that already ran such code, so this mode refuses and never re-executes.
        if not (sys.flags.isolated and sys.flags.no_site):
            sys.stderr.write(f"refused: --from-env needs an interpreter started with -I -S: {FROM_ENV_START}\n")
            raise SystemExit(2)
    elif not sys.flags.isolated:
        # Re-run isolated (-I): ignore PYTHONPATH, PYTHONSTARTUP and user site-packages, so a
        # poisoned environment cannot shadow getpass or any other module this tool imports.
        os.execv(sys.executable, [sys.executable, "-I", os.path.abspath(__file__), *sys.argv[1:]])

import argparse  # noqa: E402
import getpass  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import stat  # noqa: E402
import warnings  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import credential_status as cs  # noqa: E402  (stdlib-only checker; shares template and worktree rules)

OPERATOR_STATUSES = {"required", "optional", "user_only_paid"}
BARE_VALUE = re.compile(r"^[A-Za-z0-9._+/=:@-]+$")          # no ~ (a sourcing shell would expand it)
QUOTED_VALUE = re.compile(r'^[\x20-\x7e]+$')                 # printable ASCII only
QUOTED_FORBIDDEN = set('"$`\\')
KEY_PREFIX_HINT = {"alpaca-paper": "PK", "alpaca-paper-2": "PK", "alpaca-paper-c": "PK"}
# --from-file: the classes whose stored file is a private key that `openssl pkey` reads, the largest file it takes
# (a GitHub App key is a few KiB; a bigger file is the wrong one), and the check's time limit.
KEY_FILE_CLASSES = {"github_app_private_key"}
MAX_KEY_FILE_BYTES = 64 * 1024
OPENSSL_SECONDS = 30
CLEANUP_INCOMPLETE = 3  # the key is stored and checked, but the downloaded file was not removed


class Refused(Exception):
    """A safety rule refused the operation; the message never contains a value."""


def load_entry(entry_id: str, root: Path = ROOT, env=None) -> dict:
    env = os.environ if env is None else env
    inventory = json.loads((root / cs.INVENTORY).read_text(encoding="utf-8"))
    errors = cs.inventory_errors(inventory, root)
    if errors:
        raise Refused("invalid inventory: " + "; ".join(errors))
    entry = next((e for e in inventory["entries"] if e["id"] == entry_id), None)
    if entry is None:
        raise Refused(f"unknown entry id {entry_id!r}; see {cs.INVENTORY}")
    if entry["store"]["kind"] != "private_env_file" or entry["status"] not in OPERATOR_STATUSES:
        raise Refused(f"{entry_id}: not an operator-supplied stored entry (status {entry['status']})")
    store_root = cs.expand_template(cs.STORE_ROOT, env)
    path = cs.expand_template(entry["store"]["path_template"], env)
    if path.parent != store_root:
        raise Refused(f"{entry_id}: file is not directly under the store root")
    return entry


def load_file_entry(entry_id: str, root: Path = ROOT, env=None) -> dict:
    """The inventory entry for --from-file: an operator-supplied private_file of a key-file class, directly under the
    store root. load_entry keeps refusing such an entry, so neither the hidden prompt nor --from-env ever writes an
    `export` line to a key file."""
    env = os.environ if env is None else env
    inventory = json.loads((root / cs.INVENTORY).read_text(encoding="utf-8"))
    errors = cs.inventory_errors(inventory, root)
    if errors:
        raise Refused("invalid inventory: " + "; ".join(errors))
    entry = next((e for e in inventory["entries"] if e["id"] == entry_id), None)
    if entry is None:
        raise Refused(f"unknown entry id {entry_id!r}; see {cs.INVENTORY}")
    if entry["store"]["kind"] != "private_file" or entry["class"] not in KEY_FILE_CLASSES \
            or entry["status"] not in OPERATOR_STATUSES:
        raise Refused(f"{entry_id}: --from-file takes only an operator-supplied private key file "
                      f"(class {entry['class']}, store {entry['store']['kind']})")
    store_root = cs.expand_template(cs.STORE_ROOT, env)
    path = cs.expand_template(entry["store"]["path_template"], env)
    if path.parent != store_root:
        raise Refused(f"{entry_id}: file is not directly under the store root")
    return entry


def open_source(source: str, uid: int) -> tuple[int, os.stat_result]:
    """The downloaded file, opened without following a symlink: a regular, nonempty file of at most
    MAX_KEY_FILE_BYTES, owned by the operator and with exactly one link. Custody removes that link; a second link would
    keep the key, with whatever mode it has, where custody cannot see it (Astra's first read of #1057, finding 1; the link
    count is st_nlink, CPython v3.13.16 cbc944f4 Doc/library/os.rst:3125). Its
    mode is not checked: a Windows drive mounted in WSL reports invented mode bits, and the one link is removed once
    the stored copy passes its check."""
    if not source or "\0" in source:
        raise Refused("no source path given")
    try:
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        raise Refused("source file not found") from None
    except OSError:
        raise Refused("source is not a regular file that can be opened (a symlink or no permission)") from None
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):
        os.close(fd)
        raise Refused("source is not a regular file")
    if info.st_size == 0 or info.st_size > MAX_KEY_FILE_BYTES:
        os.close(fd)
        raise Refused(f"source size is not that of a key file (1 to {MAX_KEY_FILE_BYTES} bytes)")
    if info.st_uid != uid:
        os.close(fd)
        raise Refused("source is not owned by you; nothing moved")
    if info.st_nlink != 1:
        os.close(fd)
        raise Refused("source has another hard link; nothing moved: remove its other links first, so that custody "
                      "leaves no copy behind")
    return fd, info


def key_file_valid(dfd: int, name: str, openssl: str) -> bool:
    """`openssl pkey -noout -passin pass:` on the stored copy, given on its standard input through the checked store
    handle (no path is resolved again): True only when it exits 0. Its output is discarded, and the empty passphrase
    makes a passphrase-protected key fail instead of prompting."""
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dfd)
    except OSError:
        return False
    try:
        done = subprocess.run([openssl, "pkey", "-noout", "-passin", "pass:"], stdin=fd, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=OPENSSL_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    finally:
        os.close(fd)
    return done.returncode == 0


def run_from_file(entry_id: str, *, env=None, uid=None, ask=None, prompt=getpass.getpass, out=None,
                  root: Path = ROOT, openssl: str | None = None) -> int:
    """Take custody of a downloaded key file: copy it into the store as a new 0600 file, check the copy with
    `openssl pkey -noout`, and only then remove the original. Every refusal comes before the stored name changes; a
    copy that fails the check is removed and the original stays. The output names the entry, never contents or a path:
    a failed file operation before the key is stored is a refusal with fixed text (nothing moved), and one after it
    returns CLEANUP_INCOMPLETE with the state of both files (Astra's first read of #1057, finding 2), as does an interrupt
    after it. The stored key given as its own source changes nothing. The steps are CPython v3.13.16 (cbc944f4) os.replace
    (Doc/library/os.rst:2754), os.fsync (:1108) and os.lstat (:2412); a removal leaves the inode while another link names
    it, which the open descriptor's st_nlink (:3125) shows."""
    env = os.environ if env is None else env
    uid = os.getuid() if uid is None else uid
    ask = input if ask is None else ask  # both looked up per call, not bound when the module loads
    out = sys.stdout if out is None else out
    entry = load_file_entry(entry_id, root, env)
    openssl = openssl or shutil.which("openssl")
    if not openssl:
        raise Refused("openssl not found; nothing moved")
    path = cs.expand_template(entry["store"]["path_template"], env)
    print(f"{entry['label']}: give the path of the downloaded file (it is moved into the store and removed "
          "from where it is).", file=out)
    source = ask("  path: ").strip()
    src_fd, src_info = open_source(source, uid)
    stored = False
    try:
        dfd = open_store(path.parent, uid)
        try:
            try:
                held = os.stat(path.name, dir_fd=dfd, follow_symlinks=False)
            except FileNotFoundError:
                held = None
            if held is not None and (held.st_dev, held.st_ino) == (src_info.st_dev, src_info.st_ino):
                print(f"{entry_id}: the path given is the stored key itself; nothing changed", file=out)
                return 1
            if existing(dfd, path.name, uid):
                answer = prompt(f"{entry_id}: a stored key exists. Type 'replace' to rotate it (hidden): ")
                if answer.strip() != "replace":
                    print(f"{entry_id}: unchanged; the downloaded file was left where it is", file=out)
                    return 1
            tmp = f".{path.name}.{os.urandom(8).hex()}.tmp"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dfd)
            try:
                os.fchmod(fd, 0o600)
                copied = 0
                while True:
                    chunk = os.read(src_fd, 65536)
                    if not chunk:
                        break
                    copied += len(chunk)
                    if copied > MAX_KEY_FILE_BYTES:
                        raise Refused("source grew past the size of a key file; nothing moved")
                    os.write(fd, chunk)
                os.fsync(fd)
                os.close(fd)
                fd = -1
                if not key_file_valid(dfd, tmp, openssl):
                    raise Refused("the file is not a private key openssl can read without a passphrase; "
                                  "nothing moved, the downloaded file stays where it is")
                os.replace(tmp, path.name, src_dir_fd=dfd, dst_dir_fd=dfd)
                stored = True
                os.fsync(dfd)
            except BaseException:
                if fd >= 0:
                    os.close(fd)
                try:
                    os.unlink(tmp, dir_fd=dfd)
                except FileNotFoundError:
                    pass
                raise
        finally:
            os.close(dfd)
        # The stored copy is in place and checked: remove the original, but only if the typed path still names the
        # file that was copied (same device and inode) and that file still has one link.
        now = os.lstat(source)
        if (now.st_dev, now.st_ino) != (src_info.st_dev, src_info.st_ino) or now.st_nlink != 1:
            print(f"stored {entry_id} -> {entry['store']['path_template']} (0600); key check passed; source cleanup "
                  "incomplete: the downloaded file changed or gained a link while it was copied, so it was not "
                  "removed: remove every copy of it yourself", file=out)
            return CLEANUP_INCOMPLETE
        os.unlink(source)
        # A link made after that check keeps the inode: the open descriptor's link count says whether the removal was
        # the last one (Astra's delta read of #1057 at 60fbe1c6, finding 2).
        if os.fstat(src_fd).st_nlink != 0:
            print(f"stored {entry_id} -> {entry['store']['path_template']} (0600); key check passed; source cleanup "
                  "incomplete: the downloaded file still has another link: remove every copy of it yourself", file=out)
            return CLEANUP_INCOMPLETE
    except OSError:
        # The exception text is never shown: it would name the source path.
        if stored:
            print(f"stored {entry_id} -> {entry['store']['path_template']} (0600); key check passed; source cleanup "
                  "incomplete: the downloaded file could not be checked or removed: remove it yourself", file=out)
            return CLEANUP_INCOMPLETE
        raise Refused("a file operation failed; nothing moved, the downloaded file stays where it is") from None
    except KeyboardInterrupt:
        if stored:
            print(f"stored {entry_id} -> {entry['store']['path_template']} (0600); key check passed; cancelled before "
                  "the downloaded file was removed: source cleanup incomplete: remove it yourself", file=out)
            return CLEANUP_INCOMPLETE
        raise
    finally:
        os.close(src_fd)
    print(f"stored {entry_id} -> {entry['store']['path_template']} (0600); key check passed; the downloaded file "
          "was removed", file=out)
    return 0


def encode(name: str, value: str) -> str:
    if not value or value != value.strip():
        raise Refused(f"{name}: empty value or leading/trailing whitespace")
    # `export NAME=value` is the documented store format; every repository parser accepts it
    # and pit-availability/measure.py accepts only it (docs/secret-storage.md, Storage rules).
    if BARE_VALUE.match(value):
        return f"export {name}={value}\n"
    if QUOTED_VALUE.match(value) and not QUOTED_FORBIDDEN & set(value):
        return f'export {name}="{value}"\n'
    raise Refused(f"{name}: value has a character this store format does not allow")


def open_store(store: Path, uid: int) -> int:
    """Create the store if needed and return a checked O_DIRECTORY|O_NOFOLLOW handle."""
    store.mkdir(mode=0o700, parents=True, exist_ok=True)
    if cs.git_worktree_of(store) is not None:
        raise Refused("store directory is inside a Git worktree")
    try:
        dfd = os.open(store, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        raise Refused("store is not a real directory (symlink or other file)") from None
    info = os.fstat(dfd)
    if info.st_uid != uid:
        os.close(dfd)
        raise Refused("store directory is not owned by you")
    if stat.S_IMODE(info.st_mode) != 0o700:
        os.fchmod(dfd, 0o700)
    return dfd


def existing(dfd: int, name: str, uid: int) -> bool:
    try:
        info = os.stat(name, dir_fd=dfd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(info.st_mode):
        raise Refused("existing credential path is not a regular file")
    if info.st_uid != uid:
        raise Refused("existing credential file is not owned by you")
    return True


def write_atomically(dfd: int, name: str, text: str) -> None:
    tmp = f".{name}.{os.urandom(8).hex()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dfd)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd)
        os.fsync(dfd)
    except BaseException:
        try:
            os.unlink(tmp, dir_fd=dfd)
        except FileNotFoundError:
            pass
        raise


def create_exclusively(dfd: int, name: str, text: str) -> None:
    """Write text to a new file `name` in the directory dfd; never replace one that exists.

    The complete, fsynced temporary file gets its final name with os.link, which fails with EEXIST when the
    name exists (os.replace would overwrite it), so the existence check and the creation are one step in the
    kernel. The temporary name is then removed, leaving one link."""
    tmp = f".{name}.{os.urandom(8).hex()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dfd)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd, follow_symlinks=False)
        except FileExistsError:
            raise Refused(f"{name} already exists; --from-env never replaces a stored file") from None
    finally:
        try:
            os.unlink(tmp, dir_fd=dfd)
        except FileNotFoundError:
            pass
    os.fsync(dfd)


def run(entry_id: str, *, env=None, uid=None, prompt=getpass.getpass, out=sys.stdout,
        root: Path = ROOT) -> int:
    env = os.environ if env is None else env
    uid = os.getuid() if uid is None else uid
    entry = load_entry(entry_id, root, env)
    path = cs.expand_template(entry["store"]["path_template"], env)
    dfd = open_store(path.parent, uid)
    try:
        if existing(dfd, path.name, uid):
            answer = prompt(f"{entry_id}: a stored value exists. Type 'replace' to rotate it (hidden): ")
            if answer.strip() != "replace":
                print(f"{entry_id}: unchanged", file=out)
                return 1
        print(f"{entry['label']}: values are hidden while you type; paste and press Enter.", file=out)
        lines, stored = [], []
        for name in entry["variables"]:
            lines.append(encode(name, prompt(f"  {name}: ")))
            stored.append(name)
        for name in entry["optional_variables"]:
            value = prompt(f"  {name} (optional, Enter to skip): ")
            if value:
                lines.append(encode(name, value))
                stored.append(name)
        hint = KEY_PREFIX_HINT.get(entry_id)
        key_line = next((line for line in lines if line.startswith("export APCA_API_KEY_ID=")), "")
        if hint and key_line and not key_line.split("=", 1)[1].strip().strip('"').startswith(hint):
            print(f"  warning: APCA_API_KEY_ID does not start with {hint}, the usual prefix for this "
                  "account type. Check you pasted the right key.", file=out)
        write_atomically(dfd, path.name, "".join(lines))
    finally:
        os.close(dfd)
    print(f"stored {entry_id}: {', '.join(stored)} -> {entry['store']['path_template']} (0600)", file=out)
    return 0


def run_from_env(entry_id: str, *, env=None, uid=None, out=sys.stdout, root: Path = ROOT,
                 isolated_start: bool | None = None) -> int:
    """Store the entry's one variable from env (os.environ by default) in a new file; create-only.

    Refused unless the interpreter was started with -I -S (isolated_start defaults to sys.flags.isolated and
    sys.flags.no_site), for an entry that does not declare exactly one variable (a pair's provenance cannot be
    proven from an inherited environment), for an absent, empty or out-of-grammar value, and when the file
    exists. The value is popped from env first, so no child of this process inherits it (Linux still shows the
    start-up environment in /proc/<pid>/environ while this short process runs). The only output is
    `<id>: stored`; no message holds the value or any part of it."""
    env = os.environ if env is None else env
    if isolated_start is None:
        isolated_start = bool(sys.flags.isolated and sys.flags.no_site)
    if not isolated_start:
        raise Refused(f"--from-env needs an interpreter started with -I -S: {FROM_ENV_START}")
    uid = os.getuid() if uid is None else uid
    entry = load_entry(entry_id, root, env)
    declared = entry["variables"] + entry["optional_variables"]
    if len(declared) != 1:
        raise Refused(f"{entry_id}: --from-env stores only an entry with exactly one variable; this one "
                      f"declares {len(declared)}, and a pair's provenance cannot be proven from an inherited "
                      "environment")
    name = declared[0]
    value = env.pop(name, None)
    if value is None:
        raise Refused(f"{name}: not set in this process's environment; nothing written")
    line = encode(name, value)  # refuses an empty, padded or out-of-grammar value without quoting it
    path = cs.expand_template(entry["store"]["path_template"], env)
    exists = Refused(f"{path.name} already exists; --from-env never replaces a stored file "
                     f"(rotate with tools/credentials/open_credential_terminal.sh {entry_id})")
    if os.path.lexists(path):  # every refusal comes before the first write, even open_store's mkdir or chmod
        raise exists
    dfd = open_store(path.parent, uid)
    try:
        try:
            os.stat(path.name, dir_fd=dfd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:  # again through the checked directory handle; create_exclusively's link settles any later race
            raise exists
        create_exclusively(dfd, path.name, line)
    finally:
        os.close(dfd)
    print(f"{entry_id}: stored", file=out)
    return 0


def main(argv=None) -> int:
    # No abbreviations: --from would otherwise select --from-env, which the start-up check above does not see.
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0], allow_abbrev=False)
    parser.add_argument("entry_id", help="an operator-supplied id from adoption/credential-inventory.json")
    parser.add_argument("--from-env", action="store_true",
                        help="store the entry's one variable from this process's environment in a new file "
                             "(create-only, no terminal; needs python3 -I -S)")
    parser.add_argument("--from-file", action="store_true",
                        help="move a downloaded private key file into the entry's private file store, check it "
                             "with openssl pkey -noout, then remove the original (interactive terminal)")
    args = parser.parse_args(argv)
    if args.from_env and args.from_file:
        print("refused: --from-env and --from-file are separate modes", file=sys.stderr)
        return 2
    if args.from_env:
        try:
            return run_from_env(args.entry_id)
        except Refused as error:
            print(f"refused: {error}", file=sys.stderr)
            return 2
        except KeyboardInterrupt:
            print("cancelled; check with python3 scripts/credential_status.py", file=sys.stderr)
            return 130
        except Exception as error:  # no traceback: it could quote whatever was being handled
            print(f"failed: unexpected {type(error).__name__}; no value was printed; "
                  "check with python3 scripts/credential_status.py", file=sys.stderr)
            return 1
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("refused: run this in an interactive terminal (values are typed, never piped)", file=sys.stderr)
        return 2
    warnings.simplefilter("error", getpass.GetPassWarning)  # never fall back to echoed input
    try:
        if args.from_file:
            return run_from_file(args.entry_id)
        return run(args.entry_id)
    except Refused as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    except getpass.GetPassWarning:
        print("refused: this terminal cannot hide input; nothing written", file=sys.stderr)
        return 2
    except (KeyboardInterrupt, EOFError):
        print("\ncancelled; nothing written", file=sys.stderr)
        return 130
    except Exception as error:  # no traceback: it could quote a path or whatever was being handled
        print(f"failed: unexpected {type(error).__name__}; no path or value was printed; "
              "check with python3 scripts/credential_status.py", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
