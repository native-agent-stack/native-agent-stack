"""The install plan's memory-owner row installs the receipted ai-memory 3.1.0 run pin through the vendor's route.

The command center moved ai-memory from 2.6.6 to 3.1.0 on 2026-10-16 (its GO at 16:51Z), and condition 4 of PR (b)
retargets the plan row so the landed plan matches the host. The receipt is
evidence/artifacts/memory-owner-v3.1.0-run-pin-20261017/run-pin.json: the version, its commit, the release archive with
the sha256 verified against the publisher's sidecar, the binary inside it, and the vendor install.sh with its own
sidecar-verified sha256. It supersedes the F1 run pin (2.6.6) as the plan's pin source only.

The route follows the CC's rulings D1, D2 and D5 for condition 4 (RULINGS-gino-9109.md, outside the repository):
- install.sh at tag v3.1.0, fetched and verified, installs the release (akitaonrails/ai-memory@11ca7c5b install.sh:148-216);
- `ai-memory setup --yes --agent claude-code --agent codex` writes the systemd user unit, both clients' MCP entries,
  hooks and skills (setup.rs:1-31, 755-860), so the row writes no unit of its own: the stack's additions go in a
  repo-owned drop-in, ai-memory.service.d/override.conf, written before setup starts the service;
- `ai-memory install-hooks --agent claude-code --no-capture-prompts --apply` follows in the same step, because setup
  passes no capture flag (setup.rs:982-997) and a first install captures prompts (install_hooks.rs:1247-1261); it runs
  even when setup fails, and a later bare re-apply keeps the opt-out (install_hooks.rs:1263-1274, cli.rs:3262-3267).
These tests fail while the row, its install and acceptance functions, its --list line or owners.json name another
version, digest, source commit or route.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "evidence/artifacts/new-wsl-install-plan-20261002"
RUN_PIN = ROOT / "evidence/artifacts/memory-owner-v3.1.0-run-pin-20261017/run-pin.json"
ASSETS = RUN_PIN.parent / "outputs/github-api-release-assets.json"
# setup puts the unit under $XDG_CONFIG_HOME when that is absolute, otherwise ~/.config (akitaonrails/ai-memory@11ca7c5b
# crates/ai-memory-cli/src/commands/user_service.rs:236-249), so the drop-in goes to that directory.
DROP_DIR = '"${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/ai-memory.service.d"'
OPT_OUT = "install-hooks --agent claude-code --no-capture-prompts --apply"
# The local release tree install.sh reads through AI_MEMORY_RELEASE_BASE_URL: its url_dir is <base>/download/v<version>
# (akitaonrails/ai-memory@11ca7c5b install.sh:162-166).
TREE = "$HOME/.local/opt/ai-memory-{version}"


def function(text: str, name: str) -> str:
    return re.search(rf"(?ms)^{re.escape(name)}\(\) \{{\n.*?^\}}\n", text).group(0)


def load_checker():
    import importlib.util
    spec = importlib.util.spec_from_file_location("memory_owner_plan_check", PLAN / "check_plan.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MemoryOwnerRunPinTests(unittest.TestCase):
    def setUp(self):
        pin = json.loads(RUN_PIN.read_text(encoding="utf-8"))["proposed_run_pin"]
        self.version, self.commit = pin["version"], pin["commit"]
        self.binary_sha = pin["release_archive"]["binary_sha256"]
        self.archive_url, self.archive_sha = pin["release_archive"]["url"], pin["release_archive"]["sha256"]
        self.script_url, self.script_sha = pin["install_script"]["url"], pin["install_script"]["sha256"]
        assets = {a["name"]: a for a in json.loads(ASSETS.read_text(encoding="utf-8"))["assets"]}
        sidecar = assets[self.archive_url.rsplit("/", 1)[1] + ".sha256"]
        self.sidecar_url, self.sidecar_sha = sidecar["browser_download_url"], sidecar["digest"].removeprefix("sha256:")
        rows = json.loads((PLAN / "install-plan.json").read_text(encoding="utf-8"))["owners"]
        self.row, = [r for r in rows if r["slot"] == "memory-owner"]
        self.install = (PLAN / "install.sh").read_text(encoding="utf-8")
        self.accept = (PLAN / "accept.sh").read_text(encoding="utf-8")

    def step(self, needle):
        found = [c for c in self.row["commands"] if needle in c]
        self.assertEqual(len(found), 1, (needle, self.row["commands"]))
        return found[0]

    def test_the_row_installs_the_receipted_release_with_the_vendor_installer(self):
        self.assertEqual((self.row["owner"], self.row["release"], self.row["route"]),
                         (f"ai-memory {self.version}", f"v{self.version}", "native-installer"))
        fetch = self.row["commands"][0]
        self.assertTrue(fetch.startswith(f"fetch_verified {self.script_url} {self.script_sha} "), fetch)
        install = self.row["commands"][1]
        self.assertIn(f"AI_MEMORY_VERSION={self.version} ", install)
        self.assertIn("install.sh", install)
        # The archive's own binary, digest from the run pin: the installer's sidecar check is the publisher's.
        self.assertIn(f"printf '%s  %s\\n' {self.binary_sha} \"$HOME/.local/lib/ai-memory/ai-memory\" "
                      "| sha256sum --check --status", install)
        for stale in ("2.5.2", "2.6.6", ".local/opt/ai-memory-" + self.version + "/ai-memory-linux"):
            self.assertNotIn(stale, json.dumps(self.row["commands"]))

    def test_install_sh_reads_only_a_release_the_row_verified_first(self):
        # On its own install.sh checks the archive only against a sidecar from the same origin, and runs the unpacked
        # binary before any check of the row's (akitaonrails/ai-memory@11ca7c5b install.sh:20-23 and 186-197). So the
        # row's first step also fetches the archive, against the run pin's digest, and its sidecar, against the asset
        # digest the release reports, into a local release tree, and install.sh reads that tree through a file://
        # AI_MEMORY_RELEASE_BASE_URL (url_dir is <base>/download/v<version>, install.sh:162-166).
        tree = TREE.format(version=self.version)
        download = f"{tree}/download/v{self.version}/{self.archive_url.rsplit('/', 1)[1]}"
        fetch, install = self.row["commands"][0], self.row["commands"][1]
        parts = fetch.split(" && ")
        self.assertEqual(parts, [f'fetch_verified {self.script_url} {self.script_sha} "{tree}/install.sh"',
                                 f'fetch_verified {self.archive_url} {self.archive_sha} "{download}"',
                                 f'fetch_verified {self.sidecar_url} {self.sidecar_sha} "{download}.sha256"'])
        self.assertIn(fetch, function(self.install, "memory-owner"))
        self.assertIn(f'AI_MEMORY_RELEASE_BASE_URL="file://{tree}" ', install)
        self.assertIn(f'sh "{tree}/install.sh"', install)
        self.assertNotIn("https://", install)
        # The sidecar install.sh's verify() reads is "<hex>  <asset>" (install.sh:114-126): the run pin's archive digest.
        self.assertEqual(hashlib.sha256(f"{self.archive_sha}  {download.rsplit('/', 1)[1]}\n".encode()).hexdigest(),
                         self.sidecar_sha)
        if not shutil.which("bash"):
            self.skipTest("bash is needed to run the step")
        helper = function(self.install, "fetch_verified")
        with tempfile.TemporaryDirectory() as tmp:
            stub = Path(tmp) / "bin/curl"
            stub.parent.mkdir()
            # A curl that serves $BODY for any URL: fetch_verified must keep only bytes with the pinned digest.
            stub.write_text('#!/bin/bash\nout=""\nwhile [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift 2 ;; '
                            '--proto) shift 2 ;; *) shift ;; esac; done\nprintf "%s" "$BODY" > "$out"\n')
            stub.chmod(0o755)
            for name, part, body, want_rc in (
                    ("a replaced archive", parts[1], "not the release archive\n", 1),
                    ("the sidecar", parts[2], f"{self.archive_sha}  {download.rsplit('/', 1)[1]}\n", 0)):
                with self.subTest(name):
                    env = {"PATH": f"{stub.parent}:/usr/bin:/bin", "HOME": tmp, "BODY": body}
                    result = subprocess.run(["bash", "-euo", "pipefail", "-c", helper + part], env=env,
                                            capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode != 0, bool(want_rc), result.stderr)
                    target = Path(tmp) / part.rsplit('"$HOME/', 1)[1].rstrip('"')
                    self.assertEqual(target.is_file(), not want_rc)

    def test_install_sh_list_and_owners_json_follow_the_row(self):
        body = function(self.install, "memory-owner")
        self.assertIn(f"fetch_verified {self.script_url} {self.script_sha} ", body)
        self.assertNotIn("2.5.2", body)
        self.assertIn(f"'memory-owner | ai-memory {self.version} | native-installer | planned'", self.install)
        owners = json.loads((PLAN / "owners.json").read_text(encoding="utf-8"))["owners"]
        self.assertEqual([o["owner"] for o in owners if o["slot"] == "memory-owner"], [f"ai-memory {self.version}"])

    def test_setup_owns_the_unit_and_the_row_adds_only_its_drop_in(self):
        joined = "\n".join(self.row["commands"])
        self.assertNotIn('> "$HOME/.config/systemd/user/ai-memory.service"', joined)
        self.assertNotIn("packaging/systemd/ai-memory-user.service", joined)
        # setup wires Codex's hooks; the row's own Codex install-hooks runs only where setup is deferred (--no-start).
        self.assertEqual([c for c in self.row["commands"] if "install-hooks --agent codex" in c],
                         [c for c in self.row["commands"] if "setup --yes" in c])
        drop = self.step(DROP_DIR)
        setup = self.step("setup --yes --agent claude-code --agent codex")
        self.assertLess(self.row["commands"].index(drop), self.row["commands"].index(setup))
        self.assertIn("systemctl --user daemon-reload", drop)
        self.assertIn('install -m 0644 "$plan_dir/config/ai-memory-override.conf" "$drop"', drop)
        self.assertIn("copy_config 'ai-memory-override.conf'", function(self.install, "memory-owner"))
        conf = (PLAN / "config/ai-memory-override.conf").read_text(encoding="utf-8")
        active = [line for line in conf.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(active[0], "[Service]")
        keys = {line.split("=", 1)[0] for line in active[1:]}
        self.assertEqual(keys, {"Environment", "CPUWeight", "MemoryMax"})
        self.assertIn("CPUWeight=idle", active)
        self.assertTrue(any(line.startswith("Environment=PATH=%h/.local/bin:") for line in active), active)
        self.assertFalse(any(line.startswith("ExecStart") for line in active))
        # MemoryMax is a labelled provisional bound until a measured peak sets it (the CC's ruling G5).
        self.assertIn("MemoryMax=4G", active)
        self.assertRegex(conf, r"(?m)^# PROVISIONAL: MemoryMax=4G ")

    def test_the_drop_in_goes_to_setups_unit_directory_and_only_the_plans_bytes_stay(self):
        # setup writes the unit under $XDG_CONFIG_HOME when that is absolute (user_service.rs:236-249 at 11ca7c5b), so a
        # drop-in under ~/.config would not attach there. The step installs the plan's own bytes and, as the Dagu step
        # does, refuses any other ai-memory.service.d/*.conf and an override.conf that differs.
        drop = self.step(DROP_DIR)
        if not shutil.which("bash"):
            self.skipTest("bash is needed to run the step")
        plan_bytes = (PLAN / "config/ai-memory-override.conf").read_bytes()
        for xdg in (False, True):
            for name, seed, want_rc in (("fresh", {}, 0), ("the plan's copy", {"override.conf": plan_bytes}, 0),
                                        ("an edited copy", {"override.conf": plan_bytes + b"MemoryMax=1T\n"}, 1),
                                        ("another drop-in", {"override.conf": plan_bytes, "10-x.conf": b"[Service]\n"}, 1)):
                with self.subTest(xdg=xdg, case=name), tempfile.TemporaryDirectory() as tmp:
                    home = Path(tmp) / "home"
                    config = Path(tmp) / "xdg" if xdg else home / ".config"
                    (Path(tmp) / "bin").mkdir()
                    (Path(tmp) / "bin/systemctl").write_text("#!/bin/sh\nexit 0\n")
                    (Path(tmp) / "bin/systemctl").chmod(0o755)
                    unit_dir = config / "systemd/user/ai-memory.service.d"
                    unit_dir.mkdir(parents=True)
                    for file, data in seed.items():
                        (unit_dir / file).write_bytes(data)
                    env = {"PATH": f"{Path(tmp) / 'bin'}:/usr/bin:/bin", "HOME": str(home), "plan_dir": str(PLAN),
                           **({"XDG_CONFIG_HOME": str(config)} if xdg else {})}
                    result = subprocess.run(["bash", "-euo", "pipefail", "-c", drop], env=env, capture_output=True,
                                            text=True, timeout=60)
                    self.assertEqual(result.returncode != 0, bool(want_rc), result.stderr)
                    if not want_rc:
                        self.assertEqual((unit_dir / "override.conf").read_bytes(), plan_bytes)
                        self.assertEqual(sorted(p.name for p in unit_dir.iterdir()), ["override.conf"])
                        if xdg:
                            self.assertFalse((home / ".config/systemd").exists())
                    else:
                        self.assertIn("needs_owner", result.stderr)
                        self.assertEqual({p.name: p.read_bytes() for p in unit_dir.iterdir()}, seed)

    def test_the_config_is_setups_and_its_bind_is_set_before_setup_wires_the_clients(self):
        joined = "\n".join(self.row["commands"])
        self.assertNotIn(".config/ai-memory/config.toml", joined)
        bind = self.step("embedding_provider")
        self.assertIn('"$HOME/.local/share/ai-memory/config.toml"', bind)
        init = self.step(" init")
        setup = self.step("setup --yes")
        order = [self.row["commands"].index(c) for c in (init, bind, setup)]
        self.assertEqual(order, sorted(order))

    def test_setup_and_the_prompt_capture_opt_out_are_one_step_that_survives_a_failed_setup(self):
        setup = self.step("setup --yes --agent claude-code --agent codex")
        self.assertIn(OPT_OUT, setup)
        self.assertLess(setup.index("setup --yes"), setup.index(OPT_OUT))
        if not shutil.which("bash"):
            self.skipTest("bash is needed to run the step")
        with tempfile.TemporaryDirectory() as tmp:
            stub = Path(tmp) / "bin/ai-memory"
            stub.parent.mkdir()
            log = Path(tmp) / "calls"
            stub.write_text('#!/bin/bash\nprintf "%s token=%s\\n" "$*" "${AI_MEMORY_AUTH_TOKEN-unset}" >> "$LOG"\n'
                            'case " $* " in *" setup "*) exit "${SETUP_RC:-0}" ;; esac\n')
            stub.chmod(0o755)
            # With --no-start setup (which starts the service) is deferred and install-hooks writes Codex's hooks, so
            # ai-memory's Codex groups precede rtk's as in a normal install; the Claude opt-out runs in every case.
            for no_start, setup_rc, want_rc, first in (("0", "0", 0, "setup --yes --agent claude-code --agent codex"),
                                                       ("0", "3", 3, "setup --yes --agent claude-code --agent codex"),
                                                       ("1", "0", 0, "install-hooks --agent codex --apply")):
                with self.subTest(no_start=no_start, setup_rc=setup_rc):
                    log.write_text("")
                    env = {"PATH": f"{stub.parent}:/usr/bin:/bin", "HOME": tmp, "LOG": str(log),
                           "SETUP_RC": setup_rc, "NS2604_NO_START": no_start,
                           "AI_MEMORY_AUTH_TOKEN": "synthetic-not-a-credential"}
                    result = subprocess.run(["bash", "-euo", "pipefail", "-c", setup], env=env,
                                            capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode, want_rc, result.stderr)
                    calls = log.read_text().splitlines()
                    self.assertEqual(len(calls), 2, calls)
                    self.assertIn(first, calls[0])
                    self.assertIn(OPT_OUT, calls[1])
                    self.assertEqual(no_start == "1", not any(" setup " in f" {call} " for call in calls), calls)
                    # setup and install-mcp copy an exported token into client configs; the step unsets it.
                    self.assertTrue(all(call.endswith("token=unset") for call in calls), calls)

    def test_the_checker_holds_the_one_writer_route(self):
        checker = load_checker()
        funcs = checker.functions(self.install)
        errors = []
        checker.memory_owner_contract(funcs, lambda tag, message: errors.append((tag, message)))
        self.assertEqual(errors, [])
        body = funcs["memory-owner"]
        mutations = {
            "unit": body + "\n  run_command 'sed s/a/b/ x > \"$HOME/.config/systemd/user/ai-memory.service\"' || return \"$?\"\n",
            "opt-out": body.replace(" env -u AI_MEMORY_AUTH_TOKEN ai-memory --data-dir \"$HOME/.local/share/ai-memory\" " + OPT_OUT + ";", ""),
            "no-start": body.replace('if [[ "${NS2604_NO_START:-0}" != 1 ]]; then ', "if true; then "),
            "codex-hooks": body.replace("install-hooks --agent codex --apply || rc=$?", "true"),
            # The drop-in under ~/.config while setup's unit is under $XDG_CONFIG_HOME, and with no refusal of other drop-ins.
            "drop-in-dir": body.replace('"${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/ai-memory.service.d"',
                                        '"$HOME/.config/systemd/user/ai-memory.service.d"'),
            "unknown-drop-ins": body.replace('for f in "$dir"/*.conf;', 'for f in "$dir"/override.conf;'),
            "staged-copy": body.replace('install -m 0644 "$plan_dir/config/ai-memory-override.conf"',
                                        'install -m 0644 "$config_root/ai-memory-override.conf"'),
            # install.sh fetching the archive and its sidecar itself, from GitHub.
            "release-origin": body.replace(f'AI_MEMORY_RELEASE_BASE_URL="file://{TREE.format(version=self.version)}"',
                                           "AI_MEMORY_RELEASE_BASE_URL=https://github.com/akitaonrails/ai-memory/releases"),
            "unfetched-archive": re.sub(r' && fetch_verified \S+/ai-memory-linux-x86_64\.tar\.gz [0-9a-f]{64} "[^"]+"', "",
                                        body),
        }
        for name, changed in mutations.items():
            with self.subTest(mutation=name):
                self.assertNotEqual(changed, body)
                errors = []
                checker.memory_owner_contract({**funcs, "memory-owner": changed},
                                              lambda tag, message: errors.append((tag, message)))
                self.assertTrue(errors and all(tag == "memory-owner" for tag, _ in errors), errors)

    def test_acceptance_reads_the_prompt_capture_opt_out_and_the_drop_in(self):
        checker = load_checker()
        checks = checker.checks_of(checker.functions(self.accept)["memory-owner"])
        program = next(command for stage, _, kind, command in checks if stage == "post_install")
        self.assertEqual(program, self.row["acceptance"]["post_install"]["command"])
        if not (shutil.which("bash") and shutil.which("jq")):
            self.skipTest("bash and jq are needed to run the check")
        events = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PreCompact", "Stop", "SessionEnd")

        def hook(event, agent):
            return [{"matcher": "", "hooks": [{"type": "command", "command":
                    f"/x/ai-memory --data-dir /x hook --event {event.lower()} --agent {agent} --server-url http://h"}]}]

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "bin").mkdir()
            (home / "bin/ai-memory").write_text("#!/bin/sh\necho 'ai-memory 3.1.0'\n")
            (home / "bin/ai-memory").chmod(0o755)
            (home / ".codex").mkdir()
            (home / ".codex/hooks.json").write_text(json.dumps({"hooks": {e: hook(e, "codex") for e in events}}))
            (home / ".claude").mkdir()
            # The acceptance compares the installed drop-in with the plan's bytes, in setup's unit directory
            # ($XDG_CONFIG_HOME here), and fails on any other drop-in there.
            unit_dir = home / "xdg/systemd/user/ai-memory.service.d"
            unit_dir.mkdir(parents=True)
            plan_bytes = (PLAN / "config/ai-memory-override.conf").read_bytes()
            env = {"PATH": f"{home / 'bin'}:/usr/bin:/bin", "HOME": tmp, "XDG_CONFIG_HOME": str(home / "xdg"),
                   "plan_dir": str(PLAN)}
            claude = ("SessionStart", "PreToolUse", "PostToolUse", "PreCompact", "Stop", "SessionEnd",
                      "SubagentStart", "SubagentStop")
            opted_out = {e: hook(e, "claude-code") for e in claude}
            for name, settings, drop_ins, want in (
                    ("opted out", opted_out, {"override.conf": plan_bytes}, 0),
                    ("captures prompts", {e: hook(e, "claude-code") for e in (*claude, "UserPromptSubmit")},
                     {"override.conf": plan_bytes}, 1),
                    ("no ai-memory hooks", {}, {"override.conf": plan_bytes}, 1),
                    ("an edited drop-in", opted_out, {"override.conf": b"[Service]\n"}, 1),
                    ("another drop-in", opted_out, {"override.conf": plan_bytes, "10-x.conf": b"[Service]\n"}, 1),
                    ("no drop-in", opted_out, {}, 1)):
                with self.subTest(settings=name):
                    (home / ".claude/settings.json").write_text(json.dumps({"hooks": settings}))
                    for old in unit_dir.iterdir():
                        old.unlink()
                    for file, data in drop_ins.items():
                        (unit_dir / file).write_bytes(data)
                    result = subprocess.run(["bash", "-euo", "pipefail", "-c", program], env=env,
                                            capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode != 0, bool(want), result.stderr)

    def test_the_row_reads_its_port_from_the_host_allocation(self):
        # The CC's ruling D3: the row reads its port from ~/.config/new-wsl-native-stack/.service-ports.json, the way
        # config/observability_config.py and NO_START_PORTS.md do, so no literal 29374 is stated where the row controls
        # the port: run_command and check render @PORT_MEMORY@ from the staged allocation (install.sh run_command,
        # accept.sh check, observability_config.py render_command).
        texts = {"commands": "\n".join(self.row["commands"]),
                 "acceptance": json.dumps(self.row["acceptance"]),
                 "install.sh": "\n".join(line for line in function(self.install, "memory-owner").splitlines()
                                         if not line.lstrip().startswith("#")),
                 "accept.sh": "\n".join(line for line in function(self.accept, "memory-owner").splitlines()
                                        if not line.lstrip().startswith("#"))}
        for where, text in texts.items():
            with self.subTest(where=where):
                self.assertNotRegex(text, r"(?<![0-9])29374(?![0-9])")
        bind = self.step("embedding_provider")
        self.assertIn('bind = "127.0.0.1:@PORT_MEMORY@"', bind)
        health = self.row["acceptance"]["service_health"]["command"]
        self.assertIn("http://127.0.0.1:@PORT_MEMORY@/healthz", health)
        manifest = json.loads((ROOT / "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json")
                              .read_text(encoding="utf-8"))
        interim = next(row["interim"] for row in manifest["slots"] if row["slot_id"] == "memory-owner")
        gates = "\n".join(interim["open_acceptance_gates"])
        self.assertNotRegex(gates, r"(?<![0-9])29374(?![0-9])")
        self.assertIn(".service-ports.json", gates)
        # A moved allocation reaches the config the row writes.
        import importlib.util
        spec = importlib.util.spec_from_file_location("memory_owner_ports", PLAN / "config/observability_config.py")
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        ports = renderer.service_ports({"NS_PORT_MEMORY": "23374"})
        self.assertIn("http://127.0.0.1:23374/healthz", renderer.render_command(health, ports))
        if not shutil.which("bash"):
            self.skipTest("bash is needed to run the step")
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / ".local/share/ai-memory/config.toml"
            config.parent.mkdir(parents=True)
            config.write_text('bind = "127.0.0.1:49374"\nlog_level = "info"\n[auth]\nsecure_cookie = false\n')
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", renderer.render_command(bind, ports)],
                                    env={"PATH": "/usr/bin:/bin", "HOME": tmp}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('bind = "127.0.0.1:23374"\nembedding_provider = "local"\n', config.read_text())

    def test_the_interim_states_the_route_the_row_runs_and_is_dated_after_its_evidence(self):
        # The wave-6 amendment corrects the interim fields the 3.1.0 route makes false (INTERIM_AMENDABLE gains
        # configuration and sources): the listen port is the host allocation's (D3), setup renders and owns the unit, and
        # setup writes Codex's tool approval unconditionally (install_mcp.rs:1923 at 11ca7c5b; the CC's ruling G1).
        manifest = json.loads((ROOT / "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json")
                              .read_text(encoding="utf-8"))
        row = next(row for row in manifest["slots"] if row["slot_id"] == "memory-owner")
        config = row["interim"]["configuration"]
        self.assertNotRegex(config["listen"], r"127\.0\.0\.1:29374")
        self.assertIn(".service-ports.json", config["listen"])
        self.assertIn("setup renders", config["service"])
        self.assertIn("unconditionally", config["codex_tool_approval"])
        self.assertIn("install_mcp.rs:1923", config["codex_tool_approval"])
        sources = "\n".join(row["interim"]["sources"])
        for stale in ("7580b74d", "v2.5.2"):
            self.assertNotIn(stale, sources)
        self.assertIn(f"/blob/{self.commit}/", sources)
        self.assertIn(f"/releases/tag/v{self.version}", sources)
        self.assertIn(str(RUN_PIN.relative_to(ROOT)), sources)
        amendment = row["amendments"][-1]
        self.assertEqual(set(amendment["interim_replaced"]["configuration"]), {"listen", "service", "codex_tool_approval"})
        # The batch is dated when its evidence exists: not before the run pin's capture (E-F4).
        consensus = json.loads((ROOT / "evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json")
                               .read_text(encoding="utf-8"))
        captured = json.loads(RUN_PIN.read_text(encoding="utf-8"))["proposed_run_pin"]["tag_resolution"]["read_at"][:10]
        self.assertGreaterEqual(consensus["wave6"]["date_utc"], captured)
        self.assertEqual(amendment["date_utc"], consensus["wave6"]["date_utc"])

    def test_every_cited_ai_memory_source_is_at_the_run_pin_commit(self):
        for where, text in (("install-plan.json", json.dumps(self.row)),
                            ("install.sh", function(self.install, "memory-owner")),
                            ("accept.sh", function(self.accept, "memory-owner"))):
            commits = set(re.findall(r"akitaonrails/ai-memory/([0-9a-f]{40})/", text))
            self.assertTrue(commits, where)
            self.assertEqual(commits, {self.commit}, where)


if __name__ == "__main__":
    unittest.main()
