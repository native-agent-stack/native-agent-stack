"""Synthetic runtime-name and native Betterleaks privacy regressions."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import host_name_scan


class HostNameSourceTests(unittest.TestCase):
    def setUp(self):
        environment = {key: value for key, value in os.environ.items()
                       if key not in (host_name_scan.OVERRIDE, "WSL_DISTRO_NAME")}
        patch = mock.patch.dict(os.environ, environment, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(host_name_scan.shutil, "which", return_value=None)
        patch.start()
        self.addCleanup(patch.stop)

    def test_override_replaces_all_runtime_sources(self):
        with mock.patch.dict(os.environ, {host_name_scan.OVERRIDE: '["fixtureagent"]'}), \
                mock.patch.object(host_name_scan, "_command", side_effect=AssertionError("source used")), \
                mock.patch.object(host_name_scan, "PROFILE_ROOT") as profiles:
            self.assertEqual(host_name_scan.host_names(Path.cwd()), ("fixtureagent",))
            profiles.exists.assert_not_called()

    def test_runtime_identity_hostname_profiles_and_private_email_are_combined(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profiles = root / "profiles"
            profiles.mkdir()
            (profiles / "fixtureprofile").mkdir()
            (profiles / "not-a-profile").write_text("fixture")
            results = [subprocess.CompletedProcess([], 0, "fixtureagent\n", ""),
                       subprocess.CompletedProcess([], 0, "fixturehostname\n", ""),
                       subprocess.CompletedProcess([], 0, "fixturemail@example.invalid\n", "")]
            environment = {key: value for key, value in os.environ.items() if key != host_name_scan.OVERRIDE}
            with mock.patch.dict(os.environ, environment, clear=True), \
                    mock.patch.object(host_name_scan, "PROFILE_ROOT", profiles), \
                    mock.patch.object(host_name_scan, "_command", side_effect=results) as command:
                self.assertEqual(host_name_scan.host_names(root),
                                 ("fixtureagent", "fixturehostname", "fixtureprofile", "fixturemail"))
                self.assertEqual([call.args[0] for call in command.call_args_list],
                                 [["id", "-un"], ["uname", "-n"],
                                  ["git", "config", "--get", "user.email"]])

    def test_invalid_overrides_fail_without_echoing_values(self):
        for value in ('not-json-fixtureagent', '["fixtureagent\\n"]', '[]', '"fixtureagent"', '[1]'):
            with self.subTest(value=value), mock.patch.dict(os.environ, {host_name_scan.OVERRIDE: value}):
                with self.assertRaises(host_name_scan.HostNameScanError) as caught:
                    host_name_scan.host_names(Path.cwd())
                self.assertNotIn("fixtureagent", str(caught.exception))

    def test_source_failures_are_closed_and_value_free(self):
        environment = {key: value for key, value in os.environ.items()
                       if key != host_name_scan.OVERRIDE}
        cases = ([subprocess.CompletedProcess([], 1, "fixtureagent", "fixtureagent")],
                 [subprocess.CompletedProcess([], 0, "fixtureagent\n", ""),
                  subprocess.CompletedProcess([], 2, "fixtureagent", "fixtureagent")])
        for results in cases:
            with self.subTest(count=len(results)), \
                    mock.patch.dict(os.environ, environment, clear=True), \
                    mock.patch.object(host_name_scan, "PROFILE_ROOT") as profiles, \
                    mock.patch.object(host_name_scan, "_command", side_effect=results):
                profiles.iterdir.return_value = []
                with self.assertRaises(host_name_scan.HostNameScanError) as caught:
                    host_name_scan.host_names(Path.cwd())
                self.assertNotIn("fixtureagent", str(caught.exception))

    def test_inaccessible_profile_source_fails_closed(self):
        environment = {key: value for key, value in os.environ.items()
                       if key != host_name_scan.OVERRIDE}
        with mock.patch.dict(os.environ, environment, clear=True), \
                mock.patch.object(host_name_scan, "PROFILE_ROOT") as profiles, \
                mock.patch.object(host_name_scan, "_command", return_value=
                                  subprocess.CompletedProcess([], 0, "fixtureagent\n", "")):
            profiles.iterdir.side_effect = PermissionError("fixtureagent")
            with self.assertRaises(host_name_scan.HostNameScanError) as caught:
                host_name_scan.host_names(Path.cwd())
            self.assertNotIn("fixtureagent", str(caught.exception))

    def test_a_profile_entry_stat_failure_is_not_treated_as_an_absent_source(self):
        environment = {key: value for key, value in os.environ.items()
                       if key != host_name_scan.OVERRIDE}
        with mock.patch.dict(os.environ, environment, clear=True), \
                mock.patch.object(host_name_scan, "PROFILE_ROOT") as profiles, \
                mock.patch.object(host_name_scan, "_command", return_value=
                                  subprocess.CompletedProcess([], 0, "fixtureagent\n", "")):
            entry = mock.Mock()
            entry.stat.side_effect = FileNotFoundError("fixtureagent")
            profiles.iterdir.return_value = [entry]
            with self.assertRaises(host_name_scan.HostNameScanError):
                host_name_scan.host_names(Path.cwd())

    def test_windows_shared_template_and_junction_folders_are_not_personal_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            profiles = Path(temporary)
            for name in ("All Users", "Default", "Default User", "Public", "fixtureprofile"):
                (profiles / name).mkdir()
            results = [subprocess.CompletedProcess([], 0, "Public\n", ""),
                       subprocess.CompletedProcess([], 0, "fixturehostname\n", ""),
                       subprocess.CompletedProcess([], 0, "Default@example.invalid\n", "")]
            with mock.patch.dict(os.environ, {}, clear=True), \
                    mock.patch.object(host_name_scan, "PROFILE_ROOT", profiles), \
                    mock.patch.object(host_name_scan, "_command", side_effect=results):
                # Id and email remain designated sources even if their actual
                # values happen to coincide with a Windows system-folder name.
                self.assertEqual(host_name_scan.host_names(profiles),
                                 ("Public", "fixturehostname", "fixtureprofile", "Default"))

    def test_github_noreply_local_part_is_public_but_coincident_id_stays(self):
        for email in ("123+fixturepublic@users.noreply.github.com",
                      "fixturepublic@USERS.NOREPLY.GITHUB.COM"):
            results = [subprocess.CompletedProcess([], 0, "fixturepublic\n", ""),
                       subprocess.CompletedProcess([], 0, "fixturehostname\n", ""),
                       subprocess.CompletedProcess([], 0, email + "\n", "")]
            with self.subTest(email=email), \
                    mock.patch.object(host_name_scan, "PROFILE_ROOT") as profiles, \
                    mock.patch.object(host_name_scan, "_command", side_effect=results):
                profiles.iterdir.return_value = []
                self.assertEqual(host_name_scan.host_names(Path.cwd()),
                                 ("fixturepublic", "fixturehostname"))

    def test_noreply_email_exclusion_discriminates_private_email_collection(self):
        for role, email in (("public", "123+fixturemail@users.noreply.github.com"),
                            ("public_case", "fixturemail@USERS.NOREPLY.GITHUB.COM"),
                            ("private", "fixturemail@example.invalid"),
                            ("without_separator", "fixturemail")):
            values = {("id", "-un"): "fixtureagent\n", ("uname", "-n"): "fixturehostname\n",
                      ("git", "config", "--get", "user.email"): email + "\n"}
            def command(argv, **kwargs):
                return subprocess.CompletedProcess(argv, 0, values[tuple(argv)], "")
            with self.subTest(role=role), \
                    mock.patch.object(host_name_scan, "PROFILE_ROOT") as profiles, \
                    mock.patch.object(host_name_scan, "_command", side_effect=command):
                profiles.iterdir.return_value = []
                expected = ("fixtureagent", "fixturehostname")
                if role in ("private", "without_separator"):
                    expected += ("fixturemail",)
                self.assertEqual(host_name_scan.host_names(Path.cwd()), expected)

    def test_hostname_equal_to_public_distro_is_excluded_only_from_hostname_source(self):
        for hostname in ("fixture-distro", "FIXTURE-DISTRO", "fixture-private-host"):
            results = [subprocess.CompletedProcess([], 0, "fixtureagent\n", ""),
                       subprocess.CompletedProcess([], 0, hostname + "\n", ""),
                       subprocess.CompletedProcess([], 0, json.dumps({
                           "computer": "fixturecomputer", "profiles": []}), ""),
                       subprocess.CompletedProcess([], 1, "", "")]
            with self.subTest(role="public" if hostname.casefold() == "fixture-distro" else "private"), \
                    mock.patch.dict(os.environ, {"WSL_DISTRO_NAME": "fixture-distro"}), \
                    mock.patch.object(host_name_scan.shutil, "which", return_value="powershell.exe"), \
                    mock.patch.object(host_name_scan, "PROFILE_ROOT") as profiles, \
                    mock.patch.object(host_name_scan, "_command", side_effect=results):
                profiles.iterdir.return_value = []
                expected = ("fixtureagent", "fixturecomputer") if hostname.casefold() == "fixture-distro" \
                    else ("fixtureagent", hostname, "fixturecomputer")
                self.assertEqual(host_name_scan.host_names(Path.cwd()), expected)

    def test_public_distro_does_not_filter_coincident_private_identity_sources(self):
        results = [subprocess.CompletedProcess([], 0, "fixture-distro\n", ""),
                   subprocess.CompletedProcess([], 0, "fixture-distro\n", ""),
                   subprocess.CompletedProcess([], 0, json.dumps({
                       "computer": "fixturecomputer", "profiles": []}), ""),
                   subprocess.CompletedProcess([], 0, "fixture-distro@example.invalid\n", "")]
        with mock.patch.dict(os.environ, {"WSL_DISTRO_NAME": "fixture-distro"}), \
                mock.patch.object(host_name_scan.shutil, "which", return_value="powershell.exe"), \
                mock.patch.object(host_name_scan, "PROFILE_ROOT") as profiles, \
                mock.patch.object(host_name_scan, "_command", side_effect=results):
            profiles.iterdir.return_value = []
            self.assertEqual(host_name_scan.host_names(Path.cwd()),
                             ("fixture-distro", "fixturecomputer"))

    def test_windows_native_sources_work_without_mnt_c_profile_mount(self):
        results = [subprocess.CompletedProcess([], 0, "fixtureagent\n", ""),
                   subprocess.CompletedProcess([], 0, "fixturehostname\n", ""),
                   subprocess.CompletedProcess([], 0, json.dumps({
                       "computer": "fixturecomputer", "profiles": ["fixtureprofilé", "Public"]},
                       ensure_ascii=False), ""),
                   subprocess.CompletedProcess([], 0, "fixturemail@example.invalid\n", "")]
        with mock.patch.object(host_name_scan, "PROFILE_ROOT") as profiles, \
                mock.patch.object(host_name_scan.shutil, "which", return_value="powershell.exe"), \
                mock.patch.object(host_name_scan, "_command", side_effect=results) as command:
            profiles.iterdir.side_effect = FileNotFoundError()
            self.assertEqual(host_name_scan.host_names(Path.cwd()),
                             ("fixtureagent", "fixturehostname", "fixturecomputer", "fixtureprofilé", "fixturemail"))
            self.assertIn("[Console]::OutputEncoding", command.call_args_list[2].args[0][-1])
            self.assertEqual(command.call_args_list[2].kwargs["timeout"], 30)

    def test_wsl_without_windows_source_refuses_without_values(self):
        with mock.patch.dict(os.environ, {"WSL_DISTRO_NAME": "fixture"}), \
                mock.patch.object(host_name_scan, "_command", return_value=
                                  subprocess.CompletedProcess([], 0, "fixtureagent\n", "")):
            with self.assertRaises(host_name_scan.HostNameScanError) as caught:
                host_name_scan.host_names(Path.cwd())
            self.assertNotIn("fixtureagent", str(caught.exception))


@unittest.skipUnless(shutil.which("betterleaks"), "native Betterleaks unavailable")
class NativeHostNameScanTests(unittest.TestCase):
    def test_publication_entries_must_be_json_below_native_lookahead(self):
        for content in ('{"value":"' + "x" * 25000 + '"}', '%PDF-1.7\nfixtureagent', '{\\rtf1\nfixtureagent'):
            with self.subTest(prefix=content[:8]):
                self.target.write_text(content, encoding="utf-8")
                with self.assertRaises(host_name_scan.HostNameScanError):
                    host_name_scan.scan_paths([self.target], root=self.root, names=self.names, reject_email=True)

    def test_native_publication_entries_keep_encoded_tokens_at_every_old_cut(self):
        name = "fixture-private-account"
        email = "a" * 64 + "@" + "b" * 63 + ".example.invalid"
        import base64
        plants = ["".join("%" + format(byte, "02X") for byte in email.encode()),
                  "".join(r"\u" + format(ord(char), "04x") for char in email),
                  base64.b64encode(email.encode()).decode()]
        encoded = name
        for _ in range(5):
            encoded = "".join("%" + format(byte, "02X") for byte in encoded.encode())
            plants.append(encoded)
        lines = [" " * offset + plant for plant in plants
                 for offset in (0, 3900, 3980, 4090, 4110, 8000)]
        paths = [self.root / f"entry-{index:02}.txt" for index in range(len(lines))]
        for path, text in zip(paths, lines):
            path.write_text(json.dumps({"value": text}), encoding="utf-8")
        self.assertEqual(host_name_scan.scan_paths(paths, root=self.root, names=(name,), reject_email=True),
                         [(path, 1) for path in paths])

    def test_complete_publication_lines_keep_decoded_alphanumeric_neighbors(self):
        name = "fixture-private-account"
        plants = []
        for neighbor in ("A", "7"):
            for text in (neighbor + name, name + neighbor):
                for _ in range(5):
                    text = "".join("%" + format(byte, "02X") for byte in text.encode())
                    plants.append(text)
        lines = [" " * offset + plant for plant in plants for offset in (0, 3900, 8000)]
        paths = [self.root / f"neighbor-{index:02}.json" for index in range(len(lines))]
        for path, value in zip(paths, lines):
            path.write_text(json.dumps({"value": value}), encoding="utf-8")
        self.assertEqual(host_name_scan.scan_paths(paths, root=self.root, names=(name,), reject_email=True), [])

    def test_native_publication_guard_counts_serialized_utf8_bytes(self):
        prefix, suffix = '{"value":"', '"}'
        for size in (24999, 25000, 25001):
            content = prefix + "x" * (size - len(prefix) - len(suffix)) + suffix
            self.target.write_text(content, encoding="utf-8")
            with self.subTest(bytes=size):
                if size < 25000:
                    self.assertEqual(host_name_scan.scan_paths([self.target], root=self.root, reject_email=True), [])
                else:
                    with self.assertRaises(host_name_scan.HostNameScanError):
                        host_name_scan.scan_paths([self.target], root=self.root, reject_email=True)

    def test_native_publication_scans_each_entry_without_changing_its_text(self):
        other = self.root / "other.txt"
        contents = [json.dumps({"value": "safe\x1e text\n" + "x" * 24001}),
                    json.dumps({"value": "other\x1f text\nclean"})]
        self.target.write_text(contents[0], encoding="utf-8")
        other.write_text(contents[1], encoding="utf-8")
        original = host_name_scan.subprocess.run
        with mock.patch.object(host_name_scan.subprocess, "run", wraps=original) as run:
            self.assertEqual(host_name_scan.scan_paths([self.target, other], root=self.root,
                                                      names=self.names, reject_email=True), [])
        scans = [call for call in run.call_args_list if call.args[0][1] == "stdin"]
        self.assertEqual([call.kwargs["input"] for call in scans], contents)
        self.assertTrue(all(call.kwargs["env"]["BETTERLEAKS_CONFIG_TOML"] ==
                            host_name_scan._config(self.names, framed=False, reject_email=True)
                            for call in scans))

    def test_email_policy_uses_native_decoding_without_an_account_match(self):
        import base64
        email = "unlisted-contact@example.invalid"
        encoded = [email.replace("@", "%40"),
                   "".join("%" + format(byte, "02X") for byte in email.encode()),
                   "".join(r"\u" + format(ord(char), "04x") for char in email),
                   base64.b64encode(email.encode()).decode()]
        for value in encoded:
            with self.subTest(encoded_bytes=len(value)):
                self.target.write_text(json.dumps({"value": value}), encoding="utf-8")
                self.assertEqual(host_name_scan.scan_paths([self.target], root=self.root, reject_email=True),
                                 [(self.target, 1)])
                self.assertEqual(host_name_scan.scan_paths([self.target], root=self.root), [])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.target = self.root / "synthetic.txt"
        self.names = ("fixtureagent", "fixture--agent", "fixtureagent-", "fixtureéagent")
        self.environment = mock.patch.dict(os.environ, {host_name_scan.OVERRIDE: json.dumps(self.names)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def scan(self, content):
        self.target.write_text(content, encoding="utf-8")
        return host_name_scan.scan_paths([self.target], root=self.root)

    def test_every_ascii_punctuation_boundary_and_hyphen_shape(self):
        from string import punctuation
        lines = [left + name + right for name in self.names for left in punctuation for right in punctuation]
        findings = self.scan("\n".join(lines))
        self.assertEqual(findings, [(self.target, line) for line in range(1, len(lines) + 1)])

    def test_unicode_alphanumeric_neighbors_are_not_bare_names(self):
        # A shorter deny-name can legitimately match before a longer name's
        # punctuation suffix; isolate rules when testing the neighbor invariant.
        for name in self.names:
            with self.subTest(name=name), mock.patch.dict(
                    os.environ, {host_name_scan.OVERRIDE: json.dumps([name])}):
                lines = [left + name + right for left, right in
                         (("A", ""), ("", "7"), ("é", ""), ("", "中"), ("Ⅸ", ""))]
                self.assertEqual(self.scan("\n".join(lines)), [])

    def test_case_insensitive_literal_and_escaped_delimiter_boundaries(self):
        lines = [prefix + "FIXTUREAGENT" for prefix in
                 ("", "/", "%2F", "%5C", "%20", r"\n", r"\t", r"\r", r"\u000a", "%0A")]
        self.assertEqual(self.scan("\n".join(lines)),
                         [(self.target, line) for line in range(1, len(lines) + 1)])

    def test_native_decoders_and_original_line_mapping(self):
        import base64
        name = "fixtureagentextendedmarker"
        encoded = [base64.b64encode(name.encode()).decode(), name.encode().hex(),
                   "".join("%" + format(byte, "02X") for byte in name.encode()),
                   "".join(r"\u" + format(ord(char), "04x") for char in name)]
        with mock.patch.dict(os.environ, {host_name_scan.OVERRIDE: json.dumps([name])}):
            self.assertEqual(self.scan("\n".join("clean\n" + value for value in encoded)),
                             [(self.target, line) for line in (2, 4, 6, 8)])
            neighbors = [value.encode().hex() for value in ("A" + name, name + "A")]
            self.assertEqual(self.scan("\n".join(neighbors)), [])

    def test_decoded_names_at_artificial_cuts_retain_neighbor_guards(self):
        name = "fixtureagentextendedmarker"
        encoded = "".join("%" + format(byte, "02X") for byte in name.encode())
        with mock.patch.dict(os.environ, {host_name_scan.OVERRIDE: json.dumps([name])}):
            lines = ["_" * offset + encoded + "_" * 8000 for offset in (3980, 3990, 4050, 4060, 4090, 4110)]
            self.assertEqual(self.scan("\n".join(lines)),
                             [(self.target, line) for line in range(1, len(lines) + 1)])

    def test_adjacent_names_multifile_lines_and_binary_magic_are_retained(self):
        self.target.write_bytes(b"%PDF-1.4\nfixtureagent_fixtureagent\n")
        other = self.root / "other.txt"
        other.write_text("clean\nfixture--agent\n", encoding="utf-8")
        self.assertEqual(host_name_scan.scan_paths([self.target, other], root=self.root),
                         [(other, 2), (self.target, 2)])

    def test_raw_record_separators_before_names_preserve_probe_lines(self):
        self.target.write_bytes(b"prefix\x1efixtureagent\n"
                                b"prefix\x1ffixtureagent\n")
        self.assertEqual(host_name_scan.scan_paths([self.target], root=self.root),
                         [(self.target, 1), (self.target, 2)])

    def test_larger_multiline_input_retains_end_findings(self):
        lines = ["safe text"] * 18000 + ["fixtureagent"]
        self.assertEqual(self.scan("\n".join(lines)), [(self.target, 18001)])

    def test_long_records_retain_findings_and_unicode_neighbor_context(self):
        lines = ["safe " * 4000 + "fixtureagent",
                 "safe " * 20000 + "|fixtureéagent|" + "safe " * 20000,
                 "中" * 100000 + "fixtureagent" + "中" * 100000,
                 "safe " * 40000 + "fixtureagent"]
        self.assertEqual(self.scan("\n".join(lines)),
                         [(self.target, 1), (self.target, 2), (self.target, 4)])

    def test_long_record_framing_never_introduces_a_candidate(self):
        with mock.patch.dict(os.environ, {host_name_scan.OVERRIDE:
                                          '["x", "xfixture", "fixturex"]'}):
            lines = ["~" * offset + "fixture!" + "~" * 8000
                     for offset in range(3990, 4120)]
            self.assertEqual(self.scan("\n".join(lines)), [])

    def test_mixed_binary_bytes_retain_utf8_names(self):
        self.target.write_bytes(b"\xff%PDF-1.4\x00\n" + "fixtureéagent".encode("utf-8"))
        self.assertEqual(host_name_scan.scan_paths([self.target], root=self.root),
                         [(self.target, 2)])

    def test_each_malformed_utf8_byte_has_the_native_replacement_rune(self):
        with mock.patch.dict(os.environ, {host_name_scan.OVERRIDE: json.dumps(["��"])}):
            self.target.write_bytes(b"\xe2\x82")
            self.assertEqual(host_name_scan.scan_paths([self.target], root=self.root),
                             [(self.target, 1)])

    def test_long_records_keep_names_spanning_artificial_edges(self):
        lines = ["_" * offset + name + "_" * 8000
                 for name in self.names for offset in range(3990, 4120)]
        self.assertEqual(self.scan("\n".join(lines)),
                         [(self.target, line) for line in range(1, len(lines) + 1)])

    def test_invalid_native_metadata_is_refused_without_native_text(self):
        self.target.write_text("fixtureagent", encoding="utf-8")
        invalid = ([{"RuleID": "host-name-0", "StartLine": True}],
                   [{"RuleID": "fixtureagent", "StartLine": 3}],
                   [{"RuleID": "host-name-0", "StartLine": 1}], {"fixtureagent": 1})
        for report in invalid:
            with self.subTest(report=report), mock.patch.object(
                    host_name_scan.subprocess, "run", side_effect=[
                        subprocess.CompletedProcess([], 0, "1.9.0\n", ""),
                        subprocess.CompletedProcess([], 1, json.dumps(report), "fixtureagent")]):
                with self.assertRaises(host_name_scan.HostNameScanError) as caught:
                    host_name_scan.scan_paths([self.target], root=self.root)
                self.assertNotIn("fixtureagent", str(caught.exception))

    def test_literal_config_escaping_and_framing_markers_are_not_matches(self):
        names = ('#', 'fixture"agent', r'fixture\agent', 'fixture[agent]', 'fixture💠agent')
        with mock.patch.dict(os.environ, {host_name_scan.OVERRIDE: json.dumps(names)}):
            self.assertEqual(self.scan("\n".join(names)),
                             [(self.target, line) for line in range(1, len(names) + 1)])
            self.assertEqual(self.scan("safe"), [])

    def test_private_authentication_file_is_refused_before_reading(self):
        for name in (".env", ".credentials.json", "auth.json", "AUTH.JSON"):
            with self.subTest(name=name), mock.patch.object(
                    Path, "read_bytes", side_effect=AssertionError("private file read")):
                with self.assertRaises(host_name_scan.HostNameScanError):
                    host_name_scan.scan_paths([self.root / name], root=self.root)

    def test_symbolic_link_is_refused_without_reading_its_target(self):
        link = self.root / "linked.txt"
        link.symlink_to(self.root / "auth.json")
        with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("target read")):
            with self.assertRaises(host_name_scan.HostNameScanError):
                host_name_scan.scan_paths([link], root=self.root)

    def test_native_errors_do_not_echo_config_or_diagnostics(self):
        self.target.write_text("fixtureagent", encoding="utf-8")
        version = subprocess.CompletedProcess([], 0, "1.9.0\n", "")
        error = subprocess.CompletedProcess([], 2, "fixtureagent config", "fixtureagent failure")
        with mock.patch.object(host_name_scan.subprocess, "run", side_effect=[version, error]):
            with self.assertRaises(host_name_scan.HostNameScanError) as caught:
                host_name_scan.scan_paths([self.target], root=self.root)
        self.assertNotIn("fixtureagent", str(caught.exception))

    def test_locator_sanitizes_parent_and_candidate_filename(self):
        with mock.patch.dict(os.environ, {host_name_scan.OVERRIDE: '["fixtureagent"]'}):
            label = host_name_scan.safe_locator(self.root / "fixtureagent.txt", 4, root=self.root)
        self.assertEqual(label, "<host-name>.txt:4")


if __name__ == "__main__":
    unittest.main()
