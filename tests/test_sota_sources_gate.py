"""The reusable sota-sources gate and the check it shares with pr-metadata.yml.

.github/workflows/sota-sources-gate.yml is pr-metadata.yml's required sota-sources job made callable (`on:
workflow_call`), so a repository scaffolded by tools/adoption/scaffold_repo.py enforces the same pull-request rule by
calling it at a pinned commit. These tests keep the two copies one check:

- from the job's `if:` line to its end the gate's job is pr-metadata.yml's byte for byte (only the leading comment may
  differ), and a one-character drift is caught;
- the gate is only a reusable workflow, with a read-only token, and pr-metadata.yml keeps the job the main ruleset
  requires;
- run the way actions/github-script runs a script (an AsyncFunction over the named arguments,
  src/async-function.ts at the pinned v9.0.0 commit 3a2844b7), both copies pass and fail the same descriptions, and
  both pull-request templates fail until their SOTA sources section is filled in;
- zizmor finds nothing in the gate or in the scaffold's rendered caller, while the caller's unrendered `<sha>`
  placeholder is an unpinned-uses finding. zizmor 1.30.1 collects nested .github/workflows directories, so the
  scaffold keeps that file under a `.template` name that validate.yml's repository-wide zizmor gate does not collect.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
VALIDATE = WORKFLOWS / "pr-metadata.yml"
GATE = WORKFLOWS / "sota-sources-gate.yml"
RULESET = ROOT / ".github/main-ruleset.json"
SCAFFOLD = ROOT / "adoption/scaffold"
CALLER_TEMPLATE = SCAFFOLD / ".github/workflows/sota-sources.yml.template"
PR_TEMPLATES = {"scaffold": SCAFFOLD / ".github/pull_request_template.md",
                "repository": ROOT / ".github/pull_request_template.md"}
JOB_ID = "sota-sources"
GATE_REFERENCE = "seathatflowsinourveins/native-agent-stack/.github/workflows/sota-sources-gate.yml"
NODE = shutil.which("node")
ZIZMOR = shutil.which("zizmor")
A_COMMIT = "0123456789abcdef0123456789abcdef01234567"

sys.path.insert(0, str(ROOT / "tools" / "adoption"))


def jobs(text: str) -> dict:
    """{job_id: job_text} of the top-level jobs mapping, split as tests/test_workflow_hardening.py splits it."""
    body = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"(?m)^  ([A-Za-z0-9_-]+):[ \t]*(?:#.*)?$", body)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def check_body(job_text: str) -> str:
    """The job from its `if:` line to its end, trailing blank lines dropped: everything the runner evaluates. Only
    comment lines may come before it."""
    lines = job_text.rstrip("\n").split("\n")
    start = next((index for index, line in enumerate(lines) if line.startswith("    if: ")), None)
    if start is None:
        raise ValueError("the job has no `if:` line")
    if any(line.strip() and not line.lstrip().startswith("#") for line in lines[:start]):
        raise ValueError("something other than a comment comes before the job's `if:` line")
    return "\n".join(lines[start:]) + "\n"


def inline_script(job_text: str) -> str:
    """The job's github-script `script: |` block, dedented."""
    match = re.search(r"(?m)^( +)script: \|\n((?:\1  [^\n]*\n?|[ \t]*\n)+)", job_text)
    if match is None:
        raise ValueError("the job has no `script: |` block")
    return textwrap.dedent(match.group(2))


def sota_job(path: Path) -> str:
    return jobs(path.read_text(encoding="utf-8"))[JOB_ID]


# actions/github-script v9.0.0 (3a2844b7e9c422d3c10d287c895573f7108da1b3) src/async-function.ts: the script is the
# body of `new AsyncFunction(...Object.keys(args), source)`, called with the argument values. The fixture supplies
# `context`, `core` and the REST client, and main.ts's handleError turns a rejected script into core.setFailed.
HARNESS = r"""
const fs = require('fs');
const AsyncFunction = Object.getPrototypeOf(async () => null).constructor;
const {script, payloads} = JSON.parse(fs.readFileSync(0, 'utf8'));
(async () => {
  const results = [];
  for (const payload of payloads) {
    const outcome = {failed: null, info: null, requests: []};
    const core = {setFailed: (message) => { outcome.failed = String(message); },
                  info: (message) => { outcome.info = String(message); }};
    const context = {payload, repo: {owner: 'fixture-owner', repo: 'fixture-repo'},
                     issue: {number: payload.pull_request?.number || 17}};
    const github = {rest: {pulls: {get: async (parameters) => {
      outcome.requests.push(parameters);
      if (payload.retrieval_error) throw new Error(payload.retrieval_error);
      return {data: payload.current_pull_request ?? payload.pull_request ?? {}};
    }}}};
    try {
      await new AsyncFunction('context', 'core', 'github', script)(context, core, github);
    } catch (error) {
      core.setFailed(`Unhandled error: ${error}`);
    }
    results.push(outcome);
  }
  process.stdout.write(JSON.stringify(results));
})().catch((error) => { process.stderr.write(String((error && error.stack) || error)); process.exit(1); });
"""


def run_check(script: str, payloads: list) -> list:
    result = subprocess.run([NODE, "-e", HARNESS], input=json.dumps({"script": script, "payloads": payloads}),
                            capture_output=True, text=True, timeout=60, check=False)
    if result.returncode != 0:
        raise AssertionError(f"node exited {result.returncode}: {result.stderr[:2000]}")
    return json.loads(result.stdout)


def body(text) -> dict:
    return {"pull_request": {"body": text}}


# (case, pull_request payload, whether the check passes)
CASES = [
    ("a ## section naming a source", body("## Summary\n\nx\n\n## SOTA sources\n\n- https://github.com/o/r at v1.2.3, "
                                          "src/x.py\n\n## Evidence\n\ny\n"), True),
    ("a ### section last in the body", body("### SOTA sources\n- https://example.org/paper\n"), True),
    ("CRLF line endings", body("## Summary\r\n\r\nx\r\n\r\n## SOTA sources\r\n\r\n- https://example.org/r\r\n"), True),
    ("only a comment in the section", body("## SOTA sources\n\n<!-- fill in -->\n\n## Evidence\n\ny\n"), False),
    ("no section", body("## Summary\n\nx\n"), False),
    ("a lower-case heading", body("## sota sources\n- https://example.org/r\n"), False),
    ("a level-4 heading", body("#### SOTA sources\n- https://example.org/r\n"), False),
    ("the next heading right after it", body("## SOTA sources\n## Evidence\ny\n"), False),
    ("an empty body", body(""), False),
    ("a null body", body(None), False),
    ("no pull_request in the payload", {}, False),
]


class GateIdentityTests(unittest.TestCase):
    def test_the_gate_is_only_a_reusable_workflow_with_a_read_only_token(self):
        text = GATE.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^on:\n  workflow_call:\n\n")
        self.assertEqual(re.findall(r"(?m)^on:.*$", text), ["on:"])
        self.assertEqual(re.findall(r"(?m)^  [a-z_]+:", text.split("\non:\n", 1)[1].split("\n\n", 1)[0]),
                         ["  workflow_call:"])
        # No default token scope or cache access; the job grants only the current-PR retrieval scope.
        self.assertIn("\npermissions: {}\ncache-mode: none\n\n", text)
        self.assertRegex(text, r"(?m)^    permissions:\n      pull-requests: read\n    steps:")
        self.assertNotRegex(text, r"(?m)^[ \t]*[\w-]+:[ \t]*write(?:-all)?[ \t]*(?:#.*)?$")
        self.assertEqual(list(jobs(text)), [JOB_ID])

    def test_the_gate_runs_pr_metadata_ymls_check_byte_for_byte(self):
        self.assertEqual(check_body(sota_job(GATE)), check_body(sota_job(VALIDATE)))
        self.assertEqual(inline_script(sota_job(GATE)), inline_script(sota_job(VALIDATE)))
        self.assertIn("core.setFailed(", inline_script(sota_job(GATE)))

    def test_a_one_character_drift_in_either_copy_is_caught(self):
        original = sota_job(GATE)
        for old, new in (("#{2,3}[ \\t]+SOTA sources", "#{2,4}[ \\t]+SOTA sources"), ("timeout-minutes: 2", "timeout-minutes: 3"),
                         ("egress-policy: audit", "egress-policy: block")):
            with self.subTest(drift=new):
                self.assertEqual(original.count(old), 1, old)
                self.assertNotEqual(check_body(original.replace(old, new)), check_body(sota_job(VALIDATE)))
        with self.assertRaises(ValueError):
            check_body(original.replace("    if: ", "    name: x\n    if: ", 1))

    def test_pr_metadata_yml_keeps_the_job_the_main_ruleset_requires(self):
        contexts = [check["context"] for rule in json.loads(RULESET.read_text(encoding="utf-8"))["rules"]
                    if rule.get("type") == "required_status_checks"
                    for check in rule["parameters"]["required_status_checks"]]
        self.assertIn(JOB_ID, contexts)
        self.assertIn(JOB_ID, jobs(VALIDATE.read_text(encoding="utf-8")))


@unittest.skipUnless(NODE, "node unavailable; CI's runner images carry it")
class GateBehaviourTests(unittest.TestCase):
    def test_both_copies_pass_and_fail_the_same_descriptions(self):
        payloads = [payload for _, payload, _ in CASES]
        outcomes = {name: run_check(inline_script(sota_job(path)), payloads)
                    for name, path in (("pr-metadata.yml", VALIDATE), ("sota-sources-gate.yml", GATE))}
        self.assertEqual(outcomes["pr-metadata.yml"], outcomes["sota-sources-gate.yml"])
        for (case, _, passes), outcome in zip(CASES, outcomes["sota-sources-gate.yml"]):
            with self.subTest(case=case):
                self.assertIs(outcome["failed"] is None, passes, outcome)
                if passes:
                    self.assertRegex(outcome["info"], r"^SOTA sources section present \(\d+ characters\)\.$")
                else:
                    self.assertIn('non-empty "SOTA sources" section', outcome["failed"])

    def test_both_copies_judge_the_current_body_instead_of_the_event_body(self):
        valid = "### SOTA sources\n- https://github.com/o/r at v1.2.3, src/x.py\n"
        for path in (VALIDATE, GATE):
            with self.subTest(workflow=path.name):
                script = inline_script(sota_job(path))
                removed, restored = run_check(script, [
                    {**body(valid), "current_pull_request": {"body": "## Summary\nNo sources\n"}},
                    {**body(""), "current_pull_request": {"body": valid}},
                ])
                self.assertIsNotNone(removed["failed"])
                self.assertIsNone(restored["failed"], restored)
                for outcome in (removed, restored):
                    self.assertEqual(outcome["requests"], [{"owner": "fixture-owner", "repo": "fixture-repo",
                                                          "pull_number": 17}])

    def test_a_rejected_pulls_get_fails_both_copies_even_with_a_valid_event_body(self):
        payload = {**body("### SOTA sources\n- https://example.org/paper\n"), "retrieval_error": "request denied"}
        for path in (VALIDATE, GATE):
            with self.subTest(workflow=path.name):
                (outcome,) = run_check(inline_script(sota_job(path)), [payload])
                self.assertIn("Unhandled error:", outcome["failed"])
                self.assertIn("request denied", outcome["failed"])
                self.assertIsNone(outcome["info"])
                self.assertEqual(len(outcome["requests"]), 1)

    def test_both_pull_request_templates_fail_until_the_section_is_filled_in(self):
        script = inline_script(sota_job(GATE))
        for name, path in PR_TEMPLATES.items():
            with self.subTest(template=name):
                text = path.read_text(encoding="utf-8")
                headings = re.findall(r"(?m)^#{2,3} SOTA sources$", text)
                self.assertEqual(len(headings), 1, "exactly one SOTA sources heading the check can find")
                filled = text.replace(headings[0] + "\n", headings[0] + "\n\n- https://github.com/o/r at v1.2.3, "
                                      "src/x.py\n", 1)
                empty, done = run_check(script, [body(text), body(filled)])
                self.assertIsNotNone(empty["failed"])
                self.assertIsNone(done["failed"], done)


# Correction #145: home paths reached public PR bodies. The fixtures assemble each private-looking value at run time,
# so this file itself carries none of them for scripts/validate.py's own scan.
SOURCES = "\n\n### SOTA sources\n- https://github.com/o/r at v1.2.3, src/x.py\n"
HOME = "/" + "home/"
PRIVACY_CASES = [
    # (case, body, the rule ids the gate must name; [] means the body passes)
    ("a Linux home path", "Logs are in " + HOME + "alice/state/x.log." + SOURCES, ["personal-home-path"]),
    ("a macOS home path", "See /" + "Users/alice/notes.md." + SOURCES, ["personal-home-path"]),
    ("a Windows profile through WSL", "From /mnt/c/" + "Users/Alice/AppData." + SOURCES,
     ["personal-home-path", "windows-user-path"]),  # its /Users/<name>/ part is a home path as well, as in Python
    ("an encoded scratch directory", "In /tmp/claude-1000/" + "-home-" + "alice-code-x/scratchpad." + SOURCES,
     ["encoded-home-path"]),
    ("an Anthropic-shaped key", "key " + "sk-" + "ant-" + "A" * 30 + SOURCES, ["api-secret"]),
    ("a GitHub token", "token " + "gh" + "p_" + "a" * 36 + SOURCES, ["github-token"]),
    ("a tilde path passes", "Logs are in ~/" + ".local/state/x.log." + SOURCES, []),
    ("a masked home passes", "Logs are in " + HOME + "<user>/state/x.log." + SOURCES, []),
    ("the documented example home passes", "e.g. " + HOME + "example/x." + SOURCES, []),
    # The co-op's GPT read of 07595323 (P2-1): escaped and rendered forms are judged as they read.
    ("a percent-encoded home path", "%2F" + "home%2Falice%2Fx" + SOURCES, ["personal-home-path"]),
    ("a JSON-escaped slash", HOME.replace("/", "\\/") + "alice\\/x" + SOURCES, ["personal-home-path"]),
    ("a JSON unicode escape", "\\u002f" + "home\\u002falice\\u002fx" + SOURCES, ["personal-home-path"]),
    ("HTML character references", "&#47;" + "home&#x2F;alice&sol;x" + SOURCES, ["personal-home-path"]),
    ("a name split by a Markdown link", HOME + "[al](https://example.org)ice/x" + SOURCES, ["personal-home-path"]),
    ("a name split by emphasis", HOME + "**alice**/x" + SOURCES, ["personal-home-path"]),
    ("a home path as a link destination", "[logs](file://" + HOME + "alice/x)" + SOURCES, ["personal-home-path"]),
    ("a mixed-case macOS home", "See /" + "uSeRs/alice/x" + SOURCES, ["macos-user-path"]),
    ("a lower-case macOS home", "See /" + "users/alice/x" + SOURCES, ["macos-user-path"]),
    ("an API route passes", "GET https://api.github.com/" + "users/alice" + SOURCES, []),
    ("an encoded masked home passes", "%2F" + "home%2F%3Cuser%3E%2Fx" + SOURCES, []),
    ("an escaped example home passes", "&#47;" + "home&#47;example&#47;x" + SOURCES, []),
    ("a rendered masked home passes", HOME + "**<user>**/x" + SOURCES, []),
    ("a glob home passes", "Under /mnt/c/" + "Users/*/AppData and C:\\" + "Users\\*\\x" + SOURCES, []),
    ("a glob under a home passes", HOME + "*/" + ".config" + SOURCES, []),
    ("an underscored name", HOME + "_alice_/x" + SOURCES, ["personal-home-path"]),
    ("a placeholder in angle brackets passes", "C:\\" + "Users\\<name>\\AppData and /mnt/c/" + "Users/<name>/x" + SOURCES, []),
    ("a path split by an inline tag", "/" + "home<b></b>/alice/x" + SOURCES, ["personal-home-path"]),
    # (P2-2) Python's Unicode \w, not JavaScript's: an accented name is a word, and so is an accent before a token.
    ("an accented encoded name", "home-" + chr(0xE9) + "-code-x" + SOURCES, ["encoded-home-path"]),
    ("an accent glued to a token passes", chr(0xE9) + "hf_" + "a" * 20 + SOURCES, []),
]

# Cases the gate judges beyond validate.py's patterns: decoded or rendered forms, and the gate-only macOS rule.
GATE_ONLY_CASES = {"a percent-encoded home path", "a JSON-escaped slash", "a JSON unicode escape",
                   "HTML character references", "a name split by a Markdown link", "a name split by emphasis", "a path split by an inline tag",
                   "a mixed-case macOS home", "a lower-case macOS home"}


@unittest.skipUnless(NODE, "node unavailable; CI's runner images carry it")
class GatePrivacyTests(unittest.TestCase):
    def test_both_copies_fail_a_private_body_naming_only_the_rule(self):
        payloads = [body(text) for _, text, _ in PRIVACY_CASES]
        outcomes = {path.name: run_check(inline_script(sota_job(path)), payloads) for path in (VALIDATE, GATE)}
        self.assertEqual(outcomes["pr-metadata.yml"], outcomes["sota-sources-gate.yml"])
        for (case, text, rules), outcome in zip(PRIVACY_CASES, outcomes["sota-sources-gate.yml"]):
            with self.subTest(case=case):
                if not rules:
                    self.assertIsNone(outcome["failed"], outcome)
                    continue
                self.assertIsNotNone(outcome["failed"])
                self.assertIn(f"(rules: {', '.join(rules)})", outcome["failed"])
                for token in re.findall(r"\S+", text):  # no piece of the body is echoed back
                    if "/" in token or token.startswith(("sk-", "ghp_")) or "home-" in token:
                        self.assertNotIn(token.strip(".,"), outcome["failed"])

    def test_both_problems_are_reported_together(self):
        (outcome,) = run_check(inline_script(sota_job(GATE)), [body("See " + HOME + "alice/x.")])
        self.assertIn('non-empty "SOTA sources" section', outcome["failed"])
        self.assertIn("(rules: personal-home-path)", outcome["failed"])

    def test_the_body_is_refused_before_it_is_read(self):
        # (P2-3) A non-text, oversized, malformed or control-character body fails with a fixed id, in both copies;
        # 65,536 characters is the API's own limit ("Body is too long (maximum is 65536 characters)").
        at_limit = "x" * (65536 - len(SOURCES)) + SOURCES
        cases = [
            ("at the limit", body(at_limit), None),
            ("one over the limit", body(at_limit + "x"), "body-size"),
            ("far over the limit", body("a" * 1_000_000 + SOURCES), "body-size"),
            ("a NUL", body("abc\x00def" + SOURCES), "body-control"),
            ("an escape character", body("\x1b[31m" + SOURCES), "body-control"),
            ("a C1 control", body("\x85" + SOURCES), "body-control"),
            ("a lone surrogate", body("\ud800" + SOURCES), "body-encoding"),
            ("an object", body({}), "body-type"),
            ("a list", body([]), "body-type"),
            ("a number", body(12), "body-type"),
            ("a boolean", body(True), "body-type"),
            ("tabs and CRLF pass", body("a\tb\r\n" + SOURCES), None),
        ]
        payloads = [payload for _, payload, _ in cases]
        outcomes = {path.name: run_check(inline_script(sota_job(path)), payloads) for path in (VALIDATE, GATE)}
        self.assertEqual(outcomes["pr-metadata.yml"], outcomes["sota-sources-gate.yml"])
        for (case, _, refused), outcome in zip(cases, outcomes["sota-sources-gate.yml"]):
            with self.subTest(case=case):
                if refused is None:
                    self.assertIsNone(outcome["failed"], outcome)
                else:
                    self.assertEqual(outcome["failed"], f"The PR description cannot be checked (rule: {refused}): it "
                                     "must be text of at most 65536 characters, with no control characters other "
                                     "than tabs and line breaks.")

    def test_credential_lengths_agree_with_scripts_validate_at_each_minimum(self):
        # (P2-2) one below, at and one above each rule's minimum length, alone and glued to Unicode word characters.
        sys.path.insert(0, str(ROOT / "scripts"))
        import validate
        patterns = dict(validate.PRIVATE_CONTENT)
        grid = [("hugging-face-token", "Hugging Face token", ["hf_"], 20),
                ("github-token", "GitHub token", ["gh" + c + "_" for c in "pousr"] + ["github_pat_"], 30),
                ("tavily-token", "Tavily token", ["tvly-", "tvly-prod-", "tvly-dev-"], 24),
                ("api-secret", "API secret", ["sk-", "sk-proj-", "sk-ant-"], 24),
                ("bearer-credential", "bearer credential", ["Bearer ", "bearer\u3000"], 30)]
        cases = []
        for rule, name, prefixes, minimum in grid:
            for prefix in prefixes:
                for length in (minimum - 1, minimum, minimum + 1):
                    for before, after in (("", ""), (chr(0xE9), ""), ("", chr(0xE9)), ("x", ""), ("\u0663", "")):
                        cases.append((rule, name, before + prefix + "a" * length + after))
        outcomes = run_check(inline_script(sota_job(GATE)), [body(text + SOURCES) for _, _, text in cases])
        for (rule, name, text), outcome in zip(cases, outcomes):
            with self.subTest(rule=rule, case=repr(text[:16]), length=len(text)):
                self.assertEqual(rule in (outcome["failed"] or ""), bool(patterns[name].search(text + SOURCES)))

    def test_each_rule_agrees_with_scripts_validate(self):
        # The gate's rules are validate.py's PRIVATE_CONTENT patterns written in JavaScript; on every case each rule
        # gives the same verdict as its Python original.
        sys.path.insert(0, str(ROOT / "scripts"))
        import validate
        python = {"personal-home-path": "personal home path", "windows-user-path": "Windows user path",
                  "encoded-home-path": "encoded home path", "hugging-face-token": "Hugging Face token",
                  "github-token": "GitHub token", "tavily-token": "Tavily token", "api-secret": "API secret",
                  "private-key": "private key", "bearer-credential": "bearer credential"}
        patterns = dict(validate.PRIVATE_CONTENT)
        corpus = [text for case, text, _ in PRIVACY_CASES if case not in GATE_ONLY_CASES] + [
            "hf_" + "b" * 24, "tvly-" + "dev-" + "c" * 26, "-----BEGIN " + "RSA PRIVATE KEY-----",
            "Bearer " + "d" * 40, "C:\\" + "Users\\Bob\\x", "-" + "Users-" + "bob-x", "home-" + "bob-code-x",
            "plain text with no secret", HOME + "example/a", "x-home-" + "example-y"]
        outcomes = run_check(inline_script(sota_job(GATE)), [body(text + SOURCES) for text in corpus])
        for text, outcome in zip(corpus, outcomes):
            for rule, name in python.items():
                with self.subTest(rule=rule, case=text[:24]):
                    self.assertEqual(rule in (outcome["failed"] or ""), bool(patterns[name].search(text + SOURCES)))


# (P2-2) Each rule against its Python original over every code point Python assigns (bar surrogates and the
# supplementary private-use planes), placed where Unicode classes and boundaries decide the verdict.
PYTHON_NAMES = {"personal-home-path": "personal home path", "windows-user-path": "Windows user path",
                "encoded-home-path": "encoded home path", "hugging-face-token": "Hugging Face token",
                "github-token": "GitHub token", "tavily-token": "Tavily token", "api-secret": "API secret",
                "private-key": "private key", "bearer-credential": "bearer credential"}
X = "\x01"  # where each code point goes
TEMPLATES = {
    "personal-home-path": ["/home/" + X, X + "/home" + "/al", "/home" + "/al" + X, "/home/example" + X, "/Users/" + X + "/a",
                           "/" + X + "ome/al/"],
    "windows-user-path": ["C:\\User" + X + "\\bo", X + ":\\Users\\bo", "C:\\Users\\" + X,
                          "C:\\Users\\example" + X, "/mnt/" + X + "/Users" + "/bo", "c:\\" + X + "sers\\bo"],
    "encoded-home-path": [X + "-home-" + "bo-x", "-home-" + X, "-home-" + "bo" + X, "-home-example" + X, "home-" + X + "-code-x",
                          X + "home-bo" + "-code-", "-User" + X + "-bo-", X + "--Users-" + "bo-", "-mnt-" + X + "-Users-" + "bo-",
                          "-home-" + "bo" + X + "x", "home-bo" + X + "-code-"],
    "hugging-face-token": [X + "hf_" + "a" * 20, "hf_" + "a" * 20 + X, "hf_" + "a" * 19 + X],
    "github-token": [X + "ghp_" + "a" * 30, "ghp_" + "a" * 30 + X, "github_pat_" + "a" * 29 + X],
    "tavily-token": [X + "tvly-" + "a" * 24, "tvly-" + "a" * 24 + X, "tvly-dev-" + "a" * 23 + X],
    "api-secret": [X + "sk-" + "a" * 24, "sk-" + "a" * 24 + X, "sk-ant-" + "a" * 23 + X],
    "private-key": ["-----BEGIN " + X + "PRIVATE KEY-----"],
    "bearer-credential": [X + "Bearer " + "a" * 30, "Bearer" + X + "a" * 30, "Bearer " + "a" * 29 + X,
                          "Bearer " + X + "a" * 29],
}
# Every letter the Python rules match case-insensitively, replaced in turn (re.IGNORECASE folds some non-ASCII
# letters onto ASCII ones).
for word, prefix, suffix, rule in (("Users", "C:\\", "\\bo", "windows-user-path"),
                                   ("mnt", "/", "/c/Users" + "/bo", "windows-user-path"),
                                   ("example", "C:\\Users\\", "", "windows-user-path"),
                                   ("Users", "-", "-bo-", "encoded-home-path"),
                                   ("mnt", "-", "-c-Users-bo-", "encoded-home-path"),
                                   ("Bearer", "", " " + "a" * 30, "bearer-credential")):
    for index in range(len(word)):
        TEMPLATES[rule].append(prefix + word[:index] + X + word[index + 1:] + suffix)
ORACLE = r"""
const fs = require('fs');
const {rules, templates, ranges} = JSON.parse(fs.readFileSync(0, 'utf8'));
const privacy = new Function(rules + '\nreturn privacy;')();
const points = [];
for (const [first, last] of ranges) for (let cp = first; cp <= last; cp++) points.push(cp);
const out = {flags: Object.fromEntries(privacy.map(([id, pattern]) => [id, pattern.flags])), verdicts: {}};
for (const [id, pattern] of privacy) {
  if (!(id in templates)) continue;
  out.verdicts[id] = templates[id].map((template) => {
    const [head, tail] = template.split('\x01');
    return points.map((cp) => (pattern.test(head + String.fromCodePoint(cp) + tail) ? '1' : '0')).join('');
  });
}
process.stdout.write(JSON.stringify(out));
"""


def assigned_ranges():
    import unicodedata
    ranges, start, previous = [], None, None
    for cp in range(0x110000):
        category = unicodedata.category(chr(cp))
        keep = category not in ("Cn", "Cs") and not (category == "Co" and cp > 0xFFFF) and cp != 1
        if keep and start is None:
            start = cp
        if not keep and start is not None:
            ranges.append((start, previous))
            start = None
        previous = cp
    if start is not None:
        ranges.append((start, previous))
    return ranges


def privacy_rules(script: str) -> str:
    return script.split("// privacy-rules-begin\n", 1)[1].split("// privacy-rules-end\n", 1)[0]


@unittest.skipUnless(NODE, "node unavailable; CI's runner images carry it")
class GateUnicodeParityTests(unittest.TestCase):
    def test_every_rule_is_unicode_aware(self):
        result = subprocess.run([NODE, "-e", ORACLE], input=json.dumps(
            {"rules": privacy_rules(inline_script(sota_job(GATE))), "templates": {}, "ranges": []}),
            capture_output=True, text=True, timeout=60, check=True)
        for rule, flags in json.loads(result.stdout)["flags"].items():
            with self.subTest(rule=rule):
                self.assertIn("u", flags)

    def test_each_rule_agrees_with_python_on_every_code_point(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import validate
        patterns = dict(validate.PRIVATE_CONTENT)
        ranges = assigned_ranges()
        points = [cp for first, last in ranges for cp in range(first, last + 1)]
        result = subprocess.run([NODE, "-e", ORACLE], input=json.dumps(
            {"rules": privacy_rules(inline_script(sota_job(GATE))), "templates": TEMPLATES, "ranges": ranges}),
            capture_output=True, text=True, timeout=900, check=False)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        verdicts = json.loads(result.stdout)["verdicts"]
        self.assertEqual(set(verdicts), set(TEMPLATES))
        for rule, templates in TEMPLATES.items():
            pattern = patterns[PYTHON_NAMES[rule]]
            for template, javascript in zip(templates, verdicts[rule]):
                head, tail = template.split(X)
                python = "".join("1" if pattern.search(head + chr(cp) + tail) else "0" for cp in points)
                differing = [hex(cp) for cp, left, right in zip(points, python, javascript) if left != right]
                with self.subTest(rule=rule, template=template.replace(X, "<X>")):
                    self.assertEqual(differing, [], f"{len(differing)} code points differ")


def zizmor(path: Path, directory: Path) -> tuple:
    """zizmor offline, as tests/test_workflow_security_coverage.py runs it: (exit status, finding idents)."""
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"GH_TOKEN", "GITHUB_TOKEN", "ZIZMOR_GITHUB_TOKEN"}}
    result = subprocess.run(
        [ZIZMOR, "--offline", "--no-config", "--no-ignores", "--no-progress", "--persona", "regular",
         "--strict-collection", "--format", "json", "--cache-dir", str(directory / "cache"), str(path)],
        cwd=directory, env=environment, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
        check=False)
    try:
        findings = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise AssertionError(f"zizmor did not return JSON (exit {result.returncode}): {result.stderr[:2000]}")
    return result.returncode, {finding["ident"] for finding in findings}


@unittest.skipUnless(ZIZMOR, "native zizmor unavailable; CI installs the pinned analyzer")
class GateZizmorTests(unittest.TestCase):
    def test_both_metadata_workflows_have_no_offline_findings(self):
        for path in (GATE, VALIDATE):
            with self.subTest(workflow=path.name), tempfile.TemporaryDirectory() as temporary:
                status, idents = zizmor(path, Path(temporary))
                self.assertEqual((status, idents), (0, set()))


class ScaffoldCallerTests(unittest.TestCase):
    def test_the_caller_calls_the_gate_at_a_placeholder_commit(self):
        text = CALLER_TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"(?m)^    uses: (\S+)$", text), [f"{GATE_REFERENCE}@<sha>"])
        self.assertIn("\npermissions:\n  contents: read\n", text)
        self.assertIn("\n  pull-requests: read\n", text)
        self.assertRegex(text, r"(?m)^  pull_request:\n    # [^\n]*\n    types: \[opened, synchronize, reopened, edited\]$")

    def test_no_scaffold_file_is_collected_as_a_workflow(self):
        # validate.yml's zizmor gate audits the repository root with --strict-collection, and zizmor 1.30.1 collects
        # a nested .github/workflows/*.yml, so a scaffold workflow holding its placeholder must not carry that name.
        collected = [path.relative_to(ROOT).as_posix() for path in SCAFFOLD.rglob("*")
                     if path.suffix in {".yml", ".yaml"}]
        self.assertEqual(collected, [])

    def test_the_rendered_caller_pins_a_commit_and_the_placeholder_does_not(self):
        import scaffold_repo
        rendered = scaffold_repo.render_caller(CALLER_TEMPLATE.read_text(encoding="utf-8"), A_COMMIT)
        self.assertIn(f"    uses: {GATE_REFERENCE}@{A_COMMIT}\n", rendered)
        self.assertNotIn("<sha>", rendered)
        for bad in ("", "main", "0123456", A_COMMIT.upper(), A_COMMIT + "0"):
            with self.subTest(sha=bad), self.assertRaises(ValueError):
                scaffold_repo.render_caller(CALLER_TEMPLATE.read_text(encoding="utf-8"), bad)

    @unittest.skipUnless(ZIZMOR, "native zizmor unavailable; CI installs the pinned analyzer")
    def test_zizmor_finds_nothing_in_the_rendered_caller_and_flags_the_raw_placeholder(self):
        import scaffold_repo
        text = CALLER_TEMPLATE.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            workflow = directory / "sota-sources.yml"
            workflow.write_text(scaffold_repo.render_caller(text, A_COMMIT), encoding="utf-8")
            self.assertEqual(zizmor(workflow, directory), (0, set()))
            workflow.write_text(text, encoding="utf-8")
            status, idents = zizmor(workflow, directory)
        self.assertNotEqual(status, 0)
        self.assertIn("unpinned-uses", idents)


if __name__ == "__main__":
    unittest.main()
