"""tools/session-relaunch/install.sh and uninstall.sh: the forward install and its automated inverse, run for real in
scratch HOMEs whose path holds a space, against a stateful systemctl stand-in on PATH.

Ported from #1116's host-install simulation (run_sim_v6.sh, which ran the applied v6 apply.sh and its manual-inverse block:
v6 PASS 16 FAIL 0, v5 PASS 9 FAIL 7). The fixtures keep their ids and checks: A (a clean apply and inverse), F-B4 (the
handoff directory moved after the apply), F-B3 (the tool directory replaced by a symlink), F-B1a (install-state replaced by
a symlinked directory), F-B1b (a genuine pair reused after a completed cleanup, over someone else's units), F-B1c (a forged
exact manifest with an unbound receipt), F-D (a non-exact directory record, consistently re-bound), E (one failing manager
call stops the inverse before any removal), C (a refused apply over pre-existing units) and R (a completed cleanup retires
the receipt). New for the in-repo scripts: G (a manifest whose source commit is not in the checkout), W (a tool directory
that differs from HEAD refuses the install) and K (a host config passed with --config is installed and recorded).
The stand-in proves control flow, gating, binding and filesystem effects; it does not prove real systemd behaviour.
"""

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = Path("tools") / "session-relaunch"
UNITS = ("ns-session-roster.service", "ns-session-roster.timer", "ns-session-relaunch.service")

# run_sim_v6.sh's stand-in, unchanged: LoadState from the unit file, wants links, ActiveState kept in a file, every call
# logged; SIM_FAIL makes the first matching call return 7.
SYSTEMCTL = r"""#!/usr/bin/env bash
echo "systemctl $*" >> "$SIM_LOG"
if [ -n "${SIM_FAIL:-}" ] && [[ "$*" == *"$SIM_FAIL"* ]] && [ ! -e "$SIM_LOG.failed" ]; then : > "$SIM_LOG.failed"; exit 7; fi
U="$HOME/.config/systemd/user"; A="$HOME/.sim-active"; touch "$A"
unit=""; for a in "$@"; do case "$a" in -*) ;; *.service|*.timer) unit="$a" ;; esac; done
wants() { case "$1" in *.timer) echo "$U/timers.target.wants" ;; *) echo "$U/default.target.wants" ;; esac; }
case "$*" in
  *"LoadState --value"*)
    if [[ "$unit" == stack-alert@* ]]; then echo loaded; exit 0; fi
    if [ -e "$U/$unit" ]; then echo loaded; else echo not-found; fi; exit 0 ;;
  *"ActiveState --value"*) if grep -qx "$unit" "$A"; then echo active; else echo inactive; fi; exit 0 ;;
  "--user daemon-reload") exit 0 ;;
esac
[ -e "$U/$unit" ] || { echo "Unit $unit not found." >&2; exit 1; }
case "$2" in
  enable) mkdir -p "$(wants "$unit")"; ln -sf "$U/$unit" "$(wants "$unit")/$unit"; [ "$3" = --now ] && echo "$unit" >> "$A" ;;
  disable) rm -f "$(wants "$unit")/$unit"; [ "$3" = --now ] && sed -i "/^$unit\$/d" "$A" ;;
  stop) sed -i "/^$unit\$/d" "$A" ;;
esac
exit 0
"""
MUTATING = re.compile(r"systemctl --user (disable|enable|stop|reset-failed|daemon-reload)")


def git(repo, *args, env=None):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout.strip()


class Host:
    """One scratch host: HOME (with a space in its path), the handoff and unit directories, and the systemctl log."""

    def __init__(self, base: Path, name: str, bin_dir: Path):
        self.home = base / name / "space victim" / "home"
        self.log = base / name / "systemctl.log"
        self.r = self.home / ".local/state/native-agent-stack/session-relaunch-install"
        self.t = self.home / ".local/share/native-agent-stack/session-relaunch"
        self.s = self.home / ".local/state/native-agent-stack/session-relaunch"
        self.u = self.home / ".config/systemd/user"
        self.h = self.home / ".local/state/native-agent-stack/coordination/command-center"
        self.i = self.r / "install-state"
        self.m = self.i / "install-manifest.tsv"
        self.receipt = self.r / "apply-receipt.txt"
        self.h.mkdir(parents=True)
        self.u.mkdir(parents=True)
        (self.h / "AUTO-RESTART-20261001T000000Z.md").write_text("old\n")
        self.env = {**os.environ, "HOME": str(self.home), "SIM_LOG": str(self.log),
                    "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
        self.env.pop("SIM_FAIL", None)

    def payloads(self):
        return [self.t / "session_relaunch.py", self.s / "config.json", *(self.u / unit for unit in UNITS)]

    def all_payloads_present(self):
        return all(path.exists() for path in self.payloads())

    def mutations(self):
        return sum(1 for line in self.log.read_text().splitlines() if MUTATING.search(line)) if self.log.exists() else 0

    def clear_log(self):
        self.log.write_text("")

    def foreign_units(self):
        for unit in UNITS:
            (self.u / unit).write_text("# someone else's unit\n")
        subprocess.run(["systemctl", "--user", "enable", "--now", "ns-session-roster.timer"], env=self.env, check=True)
        self.clear_log()


class InstallInverse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="relaunch-install-"))
        cls.bin = cls.base / "bin"
        cls.bin.mkdir()
        (cls.bin / "systemctl").write_text(SYSTEMCTL)
        (cls.bin / "systemctl").chmod(0o755)
        # A scratch checkout holding the tool's bytes in one commit: install.sh reads HEAD and refuses a changed tool
        # directory, and uninstall.sh reads the recorded commit.
        cls.repo = cls.base / "repo"
        shutil.copytree(ROOT / REL, cls.repo / REL, ignore=shutil.ignore_patterns("__pycache__"))
        env = {**os.environ, "GIT_AUTHOR_NAME": "Synthetic Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
               "GIT_COMMITTER_NAME": "Synthetic Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
        git(cls.repo, "init", "-q")
        git(cls.repo, "add", "-A")
        git(cls.repo, "commit", "-q", "-m", "fixture", env=env)
        cls.commit = git(cls.repo, "rev-parse", "HEAD")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)

    def host(self, name):
        return Host(self.base, name, self.bin)

    def run_script(self, host, script, *args, **env):
        return subprocess.run(["bash", str(self.repo / REL / script), *args], env={**host.env, **env},
                              capture_output=True, text=True, cwd=str(host.home.parent))

    def apply(self, host, *args):
        done = self.run_script(host, "install.sh", *args)
        self.out = done.stdout + done.stderr
        return done.returncode

    def inverse(self, host, **env):
        done = self.run_script(host, "uninstall.sh", **env)
        self.out = done.stdout + done.stderr
        return done.returncode

    def assertStops(self, rc, reason):
        """A refusal for the named reason, not an incidental failure."""
        self.assertNotEqual(rc, 0)
        self.assertIn(reason, self.out)

    def test_A_a_clean_apply_and_inverse(self):
        h = self.host("A")
        self.assertEqual(self.apply(h), 0)
        dirs = [line.split("\t")[1:] for line in h.m.read_text().splitlines() if line.startswith("dir\t")]
        self.assertEqual(dirs, [[str(h.home / ".local/share"), "0755", "-"], [str(h.home / ".local/share/native-agent-stack"), "0755", "-"],
                                [str(h.t), "0755", "-"], [str(h.s), "0755", "-"]])
        records = {line.split("\t")[0]: line.split("\t")[1] for line in h.m.read_text().splitlines() if not line.startswith("#")}
        self.assertEqual((records["source_commit"], records["handoff_dir"]), (self.commit, str(h.h)))
        self.assertTrue((h.u / "timers.target.wants" / "ns-session-roster.timer").is_symlink())
        self.assertEqual(self.inverse(h), 0)
        self.assertFalse(any(path.exists() for path in h.payloads()))
        self.assertFalse((h.u / "timers.target.wants" / "ns-session-roster.timer").exists())

    def test_F_B4_a_moved_handoff_directory_stops_with_nothing_changed(self):
        h = self.host("B4")
        self.apply(h)
        h.h.rename(h.h.with_name("command-center.moved"))
        h.clear_log()
        self.assertStops(self.inverse(h), f"STOP: handoff directory {h.h} is missing, moved or a symlink")
        self.assertTrue(h.all_payloads_present())
        self.assertEqual(h.mutations(), 0)

    def test_F_B3_a_tool_directory_replaced_by_a_symlink_stops_and_keeps_the_unlisted_copy(self):
        h = self.host("B3")
        self.apply(h)
        elsewhere = self.base / "B3" / "elsewhere" / "real"
        elsewhere.parent.mkdir(parents=True)
        h.t.rename(elsewhere)
        h.t.symlink_to(elsewhere)
        h.clear_log()
        self.assertStops(self.inverse(h), f"STOP: {h.t} is a symlink or not its real path")
        self.assertTrue((elsewhere / "session_relaunch.py").is_file())
        self.assertEqual(h.mutations(), 0)

    def test_F_B1a_a_symlinked_install_state_stops_with_nothing_changed(self):
        h = self.host("B1a")
        self.apply(h)
        moved = self.base / "B1a" / "x" / "is"
        moved.parent.mkdir(parents=True)
        h.i.rename(moved)
        h.i.symlink_to(moved)
        h.clear_log()
        self.assertStops(self.inverse(h), f"STOP: {h.i} is missing, a symlink or not at its real path")
        self.assertEqual(h.mutations(), 0)
        self.assertTrue(h.all_payloads_present())

    def test_F_B1b_a_reused_genuine_pair_after_a_cleanup_is_refused_over_foreign_units(self):
        h = self.host("B1b")
        self.apply(h)
        manifest, receipt = h.m.read_bytes(), h.receipt.read_bytes()
        self.assertEqual(self.inverse(h), 0)
        h.foreign_units()
        h.i.mkdir()
        h.m.write_bytes(manifest)
        h.receipt.write_bytes(receipt)
        h.clear_log()
        self.assertStops(self.inverse(h), "was already cleaned up (its receipt is consumed)")
        self.assertEqual(h.mutations(), 0)
        self.assertTrue((h.u / "timers.target.wants" / "ns-session-roster.timer").is_symlink())

    def test_F_B1c_a_forged_manifest_with_an_unbound_receipt_is_refused_over_foreign_units(self):
        h = self.host("B1c")
        h.foreign_units()
        h.i.mkdir(parents=True)
        sha = lambda rel: hashlib.sha256(git(self.repo, "show", f"{self.commit}:{REL / rel}").encode() + b"\n").hexdigest()
        lines = ["# forged", f"source_commit\t{self.commit}\t-\t-", f"handoff_dir\t{h.h}\t-\t-",
                 f"file\t{h.t / 'session_relaunch.py'}\t0644\t{sha('session_relaunch.py')}",
                 f"file\t{h.s / 'config.json'}\t0600\t{sha('config.example.json')}",
                 *(f"file\t{h.u / unit}\t0644\t{sha(Path('units') / unit)}" for unit in UNITS)]
        h.m.write_text("\n".join(lines) + "\n")
        h.receipt.write_text(hashlib.sha256(h.m.read_bytes()).hexdigest() + "\n")
        h.clear_log()
        self.assertStops(self.inverse(h), "STOP: receipt and manifest are not bound")
        self.assertEqual(h.mutations(), 0)
        self.assertTrue((h.u / "timers.target.wants" / "ns-session-roster.timer").is_symlink())

    def rebind(self, h, edit):
        """Edit the manifest and re-bind the receipt to it consistently, as someone with write access could."""
        h.m.chmod(0o600)
        h.receipt.chmod(0o600)
        h.m.write_text(edit(h.m.read_text()))
        digest = hashlib.sha256(h.m.read_bytes()).hexdigest()
        h.receipt.write_text(re.sub(r"(?m)^manifest_sha256\t.*$", f"manifest_sha256\t{digest}", h.receipt.read_text()))
        h.clear_log()

    def test_F_D_a_non_exact_directory_record_stops_with_nothing_changed(self):
        h = self.host("D")
        self.apply(h)
        self.rebind(h, lambda text: re.sub(r"(?m)^(dir\t[^\t]*\t)0755(\t-)$", r"\g<1>0700\2", text))
        self.assertStops(self.inverse(h), "STOP: a manifest directory record is not one of the seven computed ancestors")
        self.assertEqual(h.mutations(), 0)
        self.assertTrue(h.all_payloads_present())

    def test_G_a_source_commit_not_in_the_checkout_stops_with_nothing_changed(self):
        h = self.host("G")
        self.apply(h)
        self.rebind(h, lambda text: text.replace(self.commit, "0" * 40))
        self.assertStops(self.inverse(h), f"STOP: source commit {'0' * 40} is not in this checkout")
        self.assertEqual(h.mutations(), 0)
        self.assertTrue(h.all_payloads_present())

    def test_E_one_failing_manager_call_stops_the_inverse_before_any_removal(self):
        for fail in ("disable --now ns-session-roster.timer", "stop ns-session-roster.service", "reset-failed",
                     "-p ActiveState --value ns-session-roster.timer"):
            with self.subTest(fail=fail):
                h = self.host("E-" + re.sub(r"[^a-zA-Z]", "", fail))
                self.apply(h)
                self.assertNotEqual(self.inverse(h, SIM_FAIL=fail), 0)
                self.assertTrue(h.all_payloads_present())

    def test_C_a_refused_apply_over_existing_units_leaves_the_inverse_nothing_to_do(self):
        h = self.host("C")
        h.foreign_units()
        self.assertEqual(self.apply(h), 1)
        self.assertIn(f"STOP: {h.u / UNITS[0]} exists; nothing written", self.out)
        self.assertFalse(h.m.exists() or h.receipt.exists())
        h.clear_log()
        self.assertStops(self.inverse(h), f"STOP: {h.r} is missing, a symlink or not at its real path")
        self.assertEqual(h.mutations(), 0)

    def test_R_a_completed_cleanup_retires_the_receipt(self):
        h = self.host("R6")
        self.apply(h)
        install_id = next(line.split("\t")[1] for line in h.receipt.read_text().splitlines() if line.startswith("install_id\t"))
        self.assertEqual(self.inverse(h), 0)
        consumed = h.r / f"apply-receipt.txt.consumed-{install_id}"
        self.assertFalse(h.receipt.exists())
        self.assertEqual(oct(consumed.stat().st_mode & 0o777), "0o400")
        self.assertFalse(h.i.exists())
        self.assertEqual(self.apply(h), 0, "a later install can run once the receipt is consumed")

    def test_W_a_tool_directory_that_differs_from_head_refuses_the_install(self):
        h = self.host("W")
        script = self.repo / REL / "README.md"
        original = script.read_bytes()
        try:
            script.write_bytes(original + b"\nchanged\n")
            self.assertEqual(self.apply(h), 1)
            self.assertIn(f"STOP: {REL} differs from HEAD {self.commit}", self.out)
        finally:
            script.write_bytes(original)
        self.assertFalse(h.r.exists() and any(h.r.iterdir()))
        self.assertFalse(h.t.exists() or h.s.exists())
        self.assertEqual(h.mutations(), 0)

    def test_K_a_host_config_is_installed_and_its_digest_recorded(self):
        h = self.host("K")
        config = self.base / "K" / "host-config.json"
        text = (self.repo / REL / "config.example.json").read_text().replace('"max_relaunches": 3', '"max_relaunches": 2')
        config.write_text(text)
        self.assertEqual(self.apply(h, "--config", str(config)), 0)
        self.assertEqual((h.s / "config.json").read_text(), text)
        self.assertIn(f"file\t{h.s / 'config.json'}\t0600\t{hashlib.sha256(text.encode()).hexdigest()}\n", h.m.read_text())
        self.assertEqual(self.inverse(h), 0)
        self.assertFalse((h.s / "config.json").exists())
        other = self.base / "K" / "other-state.json"
        other.write_text(text.replace('"~/.local/state/native-agent-stack/session-relaunch"', '"~/elsewhere"'))
        h2 = self.host("K2")
        self.assertEqual(self.apply(h2, "--config", str(other)), 1, "a config naming another state_dir is refused")
        self.assertIn("or names another state_dir; nothing written", self.out)
        self.assertFalse(h2.t.exists())


if __name__ == "__main__":
    unittest.main()
