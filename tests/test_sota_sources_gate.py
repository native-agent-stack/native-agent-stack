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

import hashlib
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
BS = "\\"
GRAPH_ID = "home-" + "alice-code-project"  # a graph project id, in the form without a leading dash
MAX_BODY = 262144  # the gate's own bound, in code points
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
    # Codex's review of de4eed8f: decoders compose, PKCS #8 and OpenPGP key labels, a repository named like a graph
    # project, and redundant leading slashes.
    ("character references around emphasis", "&#47;" + "home&#47;**alice**&#47;x" + SOURCES, ["personal-home-path"]),
    ("percent escapes around a link-split name", "%2F" + "home%2F[al](https://example.org)ice%2Fx" + SOURCES,
     ["personal-home-path"]),
    ("an escaped masked home around emphasis passes", "&#47;" + "home&#47;**<user>**&#47;x" + SOURCES, []),
    ("an encrypted PKCS #8 key", "-----BEGIN " + "ENCRYPTED PRIVATE KEY-----" + SOURCES, ["private-key"]),
    ("an OpenPGP private key block", "-----BEGIN " + "PGP PRIVATE KEY BLOCK-----" + SOURCES, ["private-key"]),
    ("a public key passes", "-----BEGIN " + "PUBLIC KEY-----" + SOURCES, []),
    ("a repository named like a graph project is refused", "https://github.com/acme/" + "home-" + "assistant-code-review"
     + SOURCES, ["encoded-home-path"]),
    ("a graph project id in a cache path", "~/.cache/codebase-memory-mcp/" + "home-" + "alice-code-x.db" + SOURCES,
     ["encoded-home-path"]),
    ("an encoded home in a local URL", "http://127.0.0.1:8788/p/" + "-home-" + "alice-code-x/" + SOURCES,
     ["encoded-home-path"]),
    ("a lower-case macOS home in a file URL", "file:///" + "users/alice/x" + SOURCES,
     ["windows-user-path", "macos-user-path"]),  # file: ends in a drive-letter shape, as in Python
    ("redundant leading slashes", "///" + "users/alice/x" + SOURCES, ["macos-user-path"]),
    ("a doubled slash inside a URL path passes", "https://example.org/a//" + "users/alice" + SOURCES, []),
    # The co-op's GPT read of fc60da90: the URL exemption is for a public code host's URL path only. A graph id behind a
    # loopback, localhost, private or unlisted host, in userinfo or a query, or under an upper-case host is still read.
    ("a graph id in a loopback URL", "http://127.0.0.1:8788/p/" + GRAPH_ID + SOURCES, ["encoded-home-path"]),
    ("a graph id in a localhost URL", "https://localhost/p/" + GRAPH_ID + SOURCES, ["encoded-home-path"]),
    ("a graph id in an IPv6 loopback URL", "http://[::1]/p/" + GRAPH_ID + SOURCES, ["encoded-home-path"]),
    ("a graph id under a .localhost name", "http://pages.localhost/p/" + GRAPH_ID + SOURCES, ["encoded-home-path"]),
    ("a graph id in a private-address URL", "http://192.168.1.5:8788/" + GRAPH_ID + SOURCES, ["encoded-home-path"]),
    ("a graph id on an unlisted public host", "https://example.org/p/" + GRAPH_ID + SOURCES, ["encoded-home-path"]),
    ("a graph id behind a code host in userinfo", "https://github.com@127.0.0.1/" + GRAPH_ID + SOURCES,
     ["encoded-home-path"]),
    ("a graph id in a code host URL's query", "https://github.com/a?u=" + GRAPH_ID + SOURCES, ["encoded-home-path"]),
    ("a graph id under an upper-case code host", "https://GITHUB.COM/acme/" + GRAPH_ID + SOURCES, ["encoded-home-path"]),
    ("a repository on a code host's subdomain is refused", "https://gist.github.com/acme/" + GRAPH_ID + SOURCES,
     ["encoded-home-path"]),
    # The command center's Claude read of 4e5ef13d (B3): the exemption is for the repository segment of a code-host URL
    # that starts its own token, so an inner scheme, a query, a link destination, a delimiter or a deeper path is read.
    ("a graph id behind a code host inside a local URL", "http://127.0.0.1:8788/p/https://github.com/" + GRAPH_ID + SOURCES,
     ["encoded-home-path"]),
    ("a graph id behind a code host in a local URL's query", "http://localhost/?q=https://github.com/p/" + GRAPH_ID + SOURCES,
     ["encoded-home-path"]),
    ("a graph id as a code-host link's destination", "[https://github.com/o/r](" + GRAPH_ID + ")" + SOURCES,
     ["encoded-home-path"]),
    ("a graph id after a comma behind a code-host URL", "https://github.com/o/r," + GRAPH_ID + SOURCES, ["encoded-home-path"]),
    ("a graph id deeper in a code-host URL's path", "https://github.com/o/r/blob/main/" + GRAPH_ID + ".db" + SOURCES,
     ["encoded-home-path"]),
    ("a graph id after a pipe behind a code-host URL", "| https://github.com/o|" + GRAPH_ID + " |" + SOURCES,
     ["encoded-home-path"]),
    ("a graph id after a table cell's code-host URL", "|https://github.com/acme|/" + GRAPH_ID + "|" + SOURCES,
     ["encoded-home-path"]),
    ("a graph id after a code-host URL and a semicolon", "https://github.com/acme;/" + GRAPH_ID + SOURCES,
     ["encoded-home-path"]),
    ("a graph id after a code-host URL and a comma", "https://github.com/acme,/" + GRAPH_ID + SOURCES,
     ["encoded-home-path"]),
    ("a linked repository named like a graph project is refused", "[r](https://github.com/acme/" + GRAPH_ID + ")" + SOURCES,
     ["encoded-home-path"]),
    ("an autolinked repository named like a graph project is refused", "<https://gitlab.com/acme/" + GRAPH_ID + ">"
     + SOURCES, ["encoded-home-path"]),
    # The command center's Claude micro at 752d9618 (M2): a code-host URL glued inside another URL after a token-start
    # character still exempted a graph id. With the exemption gone, each is refused.
    *[("a graph id behind a code host glued after " + glue, "http://localhost/?q=" + glue + "https://github.com/o/" + GRAPH_ID
       + SOURCES, ["encoded-home-path"]) for glue in ("(", "'", '"', "[", "<", ">")],
    ("a graph id behind a code host in a nested link destination", "[t](http://localhost/(https://github.com/o/" + GRAPH_ID
     + "))" + SOURCES, ["encoded-home-path"]),
    # Codex's review of d81969dd (T8): GitHub hides an HTML comment, so a value split by one reads whole.
    ("a home path split by an HTML comment", "/ho<!--x-->me/alice/x" + SOURCES, ["personal-home-path"]),
    ("a home path split by an empty HTML comment", "/ho<!-->me/alice/x" + SOURCES, ["personal-home-path"]),
    ("a token split by an HTML comment", "gh<!-- -->p_" + "a" * 36 + SOURCES, ["github-token"]),
    ("a home path split by a reference to a zero-width space", "/ho&#x200b;me/alice/x" + SOURCES, ["personal-home-path"]),
    # The micro at 752d9618: two link shapes 4e5ef13d decoded and 752d9618 did not.
    ("a name split by a link whose title is on the next line", HOME + "[al](https://example.org\n\"t\")ice/x" + SOURCES,
     ["personal-home-path"]),
    ("a name split by a link whose title holds a parenthesis", HOME + "[al](https://example.org \"t(x\")ice/x" + SOURCES,
     ["personal-home-path"]),
    # The same read (B4): a WSL distribution's home through its Windows UNC path, as File Explorer and the WSL
    # documentation write it, and JSON-escaped.
    ("a WSL home through wsl.localhost", BS * 2 + "wsl.localhost" + BS + "Ubuntu" + BS + "home" + BS + "alice" + BS + "x"
     + SOURCES, ["personal-home-path"]),
    ("a WSL home through wsl$", BS * 2 + "wsl$" + BS + "Ubuntu-24.04" + BS + "home" + BS + "alice" + SOURCES,
     ["personal-home-path"]),
    ("a WSL home through the wsl prefix", BS * 2 + "WSL" + BS + "Ubuntu" + BS + "home" + BS + "alice" + SOURCES,
     ["personal-home-path"]),
    ("a JSON-escaped WSL home", BS * 4 + "wsl.localhost" + BS * 2 + "Ubuntu" + BS * 2 + "home" + BS * 2 + "alice" + BS * 2
     + "x" + SOURCES, ["personal-home-path"]),
    ("a masked WSL home passes", BS * 2 + "wsl$" + BS + "Ubuntu" + BS + "home" + BS + "<WSL_USER>" + BS + "x" + SOURCES, []),
    ("the example WSL home passes", BS * 2 + "wsl.localhost" + BS + "Ubuntu" + BS + "home" + BS + "example" + BS + "x"
     + SOURCES, []),
    # The micro at 752d9618: the rarer UNC forms (.NET's file path formats: device UNC paths, either slash).
    ("a WSL home through a device UNC path", BS * 2 + "?" + BS + "UNC" + BS + "wsl.localhost" + BS + "D" + BS + "home" + BS
     + "alice" + SOURCES, ["personal-home-path"]),
    ("a WSL home through a dot device UNC path", BS * 2 + "." + BS + "unc" + BS + "wsl$" + BS + "D" + BS + "home" + BS
     + "alice" + BS + "x" + SOURCES, ["personal-home-path"]),
    ("a WSL home with mixed slashes", "//wsl$/D" + BS + "home" + BS + "alice" + BS + "x" + SOURCES, ["personal-home-path"]),
    ("a WSL home under a distribution name with a space", BS * 2 + "wsl$" + BS + "Ubuntu 24.04" + BS + "home" + BS + "alice"
     + SOURCES, ["personal-home-path"]),
    ("a WSL home under a long distribution name", BS * 2 + "wsl$" + BS + "d" * 100 + BS + "home" + BS + "alice" + SOURCES,
     ["personal-home-path"]),
    ("a Windows profile through a WSL home's mount", BS * 2 + "wsl.localhost" + BS + "D" + BS + "mnt" + BS + "c" + BS
     + "Users" + BS + "alice" + BS + "x" + SOURCES, ["personal-home-path"]),
]

# Cases the gate judges beyond validate.py's patterns: decoded, rendered or projected forms, and the gate-only macOS rule.
GATE_ONLY_CASES = {"a percent-encoded home path", "a JSON-escaped slash", "a JSON unicode escape",
                   "HTML character references", "a name split by a Markdown link", "a name split by emphasis", "a path split by an inline tag",
                   "a mixed-case macOS home", "a lower-case macOS home", "character references around emphasis",
                   "percent escapes around a link-split name", "a home path split by an HTML comment",
                   "a home path split by an empty HTML comment", "a token split by an HTML comment",
                   "a home path split by a reference to a zero-width space",
                   "a name split by a link whose title is on the next line",
                   "a name split by a link whose title holds a parenthesis",
                   "a lower-case macOS home in a file URL", "redundant leading slashes"}

# The HTML5 named-reference table as github/cmark-gfm pins it (src/entities.inc), the gate's subset's source.
CMARK_PIN = "587a12bb54d95ac37241377e6ddc93ea0e45439b"
ENTITY_FIXTURE = ROOT / "tests/fixtures/cmark-gfm-entities-587a12bb.json"
UPSTREAM_CMARK = Path.home() / "code/upstream/github/cmark-gfm"
NODE_PROJECT = r"""
const fs = require('fs');
const project = (s) => s.replace(/(?![\t\n\r])[\p{Cc}\p{Cf}\p{Zl}\p{Zp}\p{Default_Ignorable_Code_Point}]/gu, '').normalize('NFKC');
process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0, 'utf8')).map(project)));
"""


def node_project(text: str) -> str:
    """The gate's character projection (strip, then NFKC), run in node as the job runs it."""
    result = subprocess.run([NODE, "-e", NODE_PROJECT], input=json.dumps([text]), capture_output=True, text=True,
                            timeout=60, check=True)
    return json.loads(result.stdout)[0]


def gate_entity_subset() -> dict:
    """The gate's named-reference map, evaluated from the job's script between its entities markers."""
    script = inline_script(sota_job(GATE))
    block = script.split("// entities-begin\n", 1)[1].split("// entities-end\n", 1)[0]
    result = subprocess.run([NODE, "-e", block + "\nprocess.stdout.write(JSON.stringify(Object.fromEntries(named)));"],
                            capture_output=True, text=True, timeout=60, check=True)
    return json.loads(result.stdout)


# The repository's own WSL recipe, receipts and their frozen copies write the UNC form with the user masked.
MASKED_WSL_FILES = ["adoption/platforms/linux-wsl2-new-distro.md", "adoption/templates/wsl/stage1-receipt.example.json",
                    "docs/decisions/2026-10-01-new-wsl-distro-recipe.md", "docs/secret-storage.md",
                    "evidence/artifacts/new-wsl-fix-wave-20261004/frozen-inputs/linux-wsl2-new-distro.md.txt",
                    "evidence/artifacts/new-wsl-fix-wave-20261004/frozen-inputs/test_wsl_new_distro_recipe.py.txt",
                    "evidence/artifacts/new-wsl-rehearsal-20261002/runs-on-wsl-3.0.1.json",
                    "evidence/artifacts/new-wsl-rehearsal-20261002/stage1-receipt.json",
                    "evidence/artifacts/user-facing-local-time-20261005/frozen-inputs/2026-10-01-new-wsl-distro-recipe.md.txt",
                    "evidence/artifacts/user-facing-local-time-20261005/frozen-inputs/stage1-receipt.example.json.txt",
                    "tests/test_wsl_new_distro_recipe.py"]


class ScriptsValidateWslHomeTests(unittest.TestCase):
    def test_scripts_validate_reads_a_wsl_unc_home(self):
        # The command center's Claude read of 4e5ef13d (B4), in validate.py's copy of the rule.
        sys.path.insert(0, str(ROOT / "scripts"))
        import validate
        pattern = dict(validate.PRIVATE_CONTENT)["personal home path"]
        cases = [(case, text, rules) for case, text, rules in PRIVACY_CASES if "WSL home" in case]
        self.assertEqual(len(cases), 12)
        for case, text, rules in cases:
            with self.subTest(case=case):
                self.assertEqual(bool(pattern.search(text)), rules == ["personal-home-path"])

    def test_the_tracked_masked_wsl_homes_stay_clean(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import validate
        pattern = dict(validate.PRIVATE_CONTENT)["personal home path"]
        unc_home = re.compile(r"\\\\+[Ww][Ss][Ll](?:\.localhost|\$)\\+[^\\\s]+\\+home\\+")
        lines = [line for path in MASKED_WSL_FILES for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
                 if unc_home.search(line)]
        self.assertGreaterEqual(len(lines), len(MASKED_WSL_FILES))
        self.assertEqual(sum(1 for line in lines if pattern.search(line)), 0)


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
        # (P2-3) A non-text, oversized, malformed or control-character body fails with a fixed id, in both copies.
        # The size bound is the gate's own, in code points: GitHub's REST update keeps at most 262,144 UTF-8 bytes
        # (measured 2026-10-11), and #786's description has 75,726 characters.
        at_limit = "x" * (MAX_BODY - len(SOURCES)) + SOURCES
        astral = chr(0x1F600) * (MAX_BODY - len(SOURCES)) + SOURCES  # twice as many UTF-16 code units
        cases = [
            ("at the limit", body(at_limit), None),
            ("one over the limit", body(at_limit + "x"), "body-size"),
            ("astral characters at the limit", body(astral), None),
            ("one astral character over the limit", body(astral + chr(0x1F600)), "body-size"),
            ("a description as long as #786's", body("x" * (75_726 - len(SOURCES)) + SOURCES), None),
            ("far over the limit", body("a" * 4 * MAX_BODY + SOURCES), "body-size"),
            ("a NUL", body("abc\x00def" + SOURCES), "body-control"),
            ("an escape character", body("\x1b[31m" + SOURCES), "body-control"),
            ("a C1 control", body("\x9b" + SOURCES), "body-control"),
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
                                     f"must be text of at most {MAX_BODY} characters, with no control characters "
                                     "other than tabs and line breaks.")

    def test_the_guard_admits_tabs_and_line_breaks_only(self):
        # The command center's Claude read of 4e5ef13d (B1): #1003's mirror finds section content in U+001C and U+0085,
        # so the guard must not refuse them. A line break is a paragraph separator, Bidi_Class B in the Unicode
        # Character Database Python carries; every other C0 and C1 control is refused, in both copies.
        import unicodedata
        controls = [chr(code) for code in [*range(0x20), *range(0x7F, 0xA0)]]
        payloads = [body("a" + control + "b" + SOURCES) for control in controls]
        outcomes = {path.name: run_check(inline_script(sota_job(path)), payloads) for path in (VALIDATE, GATE)}
        self.assertEqual(outcomes["pr-metadata.yml"], outcomes["sota-sources-gate.yml"])
        for control, outcome in zip(controls, outcomes["sota-sources-gate.yml"]):
            with self.subTest(control=hex(ord(control))):
                admitted = control == "\t" or unicodedata.bidirectional(control) == "B"
                self.assertEqual(outcome["failed"] is None, admitted, outcome)
                if not admitted:
                    self.assertIn("(rule: body-control)", outcome["failed"])

    def test_a_value_split_by_an_admitted_or_format_character_is_still_caught(self):
        # The command center's Claude micro at 752d9618 (M1): the guard admits U+001C to U+001E and U+0085, and the
        # scan never removed them, so a value split by one passed both copies (52 of 68); at 4e5ef13d all 68 were
        # refused. The rules now also read a projection without Cc, Cf, Zl and Zp characters (but tab, LF and CR).
        shapes = ["/home/<s>alice/x", "/ho<s>me/alice/x", "/home<s>/alice/x", "-home-<s>alice-code-x/", "home-al<s>ice-code-x",
                  "ho<s>me-alice-code-x", "C:" + BS + "Users" + BS + "<s>Alice", "C:" + BS + "Us<s>ers" + BS + "Alice",
                  BS * 2 + "wsl$" + BS + "D" + BS + "home" + BS + "<s>alice", BS * 2 + "wsl$" + BS + "D" + BS + "ho<s>me" + BS
                  + "alice", "gh" + "p_<s>" + "a" * 36, "gh" + "p_" + "a" * 18 + "<s>" + "a" * 18, "sk-" + "ant-<s>" + "A" * 30,
                  # the separator only beside the value
                  "<s>" + HOME + "alice/x", HOME + "alice/x<s>", "<s>" + GRAPH_ID, "<s>gh" + "p_" + "a" * 36]
        separators = ["\x1c", "\x1d", "\x1e", "\x85", "\u200b", "\u00ad", "\u2028", "\u2029", "\u202e", "\ufeff", "\u2060"]
        cases = [(shape, separator) for separator in separators for shape in shapes]
        payloads = [body("x " + shape.replace("<s>", separator) + " y" + SOURCES) for shape, separator in cases]
        outcomes = {path.name: run_check(inline_script(sota_job(path)), payloads) for path in (VALIDATE, GATE)}
        self.assertEqual(outcomes["pr-metadata.yml"], outcomes["sota-sources-gate.yml"])
        self.assertEqual(len(cases), 187)
        for (shape, separator), outcome in zip(cases, outcomes["sota-sources-gate.yml"]):
            with self.subTest(shape=shape[:24], separator=hex(ord(separator))):
                self.assertIn("(rules: ", outcome["failed"] or "")

    def test_a_value_split_or_completed_by_markup_references_or_ignorables_is_caught(self):
        # The command center's micro at e15d1259 (N1, N2, N3) and its terminal ruling: the projection reads the sets the
        # specifications define. Raw HTML of every kind in the GFM grammar (github/cmark-gfm@587a12bb test/spec.txt
        # :9360-9431), the HTML5 named references, every Default_Ignorable_Code_Point, and NFKC width forms.
        cases = []
        markup = ["<x>", "</x>", "<x/>", '<x y="z">', "<font>", "</font>", "<nobr>", "<input>", "<template></template>",
                  "<custom-el>", "<![CDATA[x]]>", "<?x?>", "<!-- c -->", "<!DOCTYPE x>", "<a href='q'>", "<x\ny=z>"]
        for piece in markup:
            cases.append(("markup " + piece, "/ho" + piece + "me/alice/x", "personal-home-path"))
        cases += [("markup in a Windows profile", "C:" + BS + "Us<x>ers" + BS + "Alice", "windows-user-path"),
                  ("CDATA in a Windows profile", "C:" + BS + "Users" + BS + "Al<![CDATA[]]>ice", "windows-user-path"),
                  ("markup in a graph id", "home-al<x>ice-code-x", "encoded-home-path"),
                  ("a processing instruction in a graph id", "home-al<?p?>ice-code-x", "encoded-home-path"),
                  ("markup in a GitHub token", "gh<b>p_" + "a" * 36, "github-token"),
                  ("markup in an Anthropic key", "sk-" + "ant-" + "A" * 15 + "<i>" + "A" * 15, "api-secret")]
        for name in ("shy", "zwj", "zwnj", "lrm", "rlm", "ZeroWidthSpace", "NoBreak", "it", "ic", "af", "InvisibleTimes",
                     "NegativeThinSpace"):
            cases.append(("reference &" + name + ";", "/ho&" + name + ";me/alice/x", "personal-home-path"))
        cases += [("&UnderBar; completes a token", "ghp&UnderBar;" + "a" * 36, "github-token"),
                  ("&UnderBar; in a fine-grained token", "github&UnderBar;pat_" + "a" * 30, "github-token"),
                  ("&dollar; completes a UNC home", BS * 2 + "wsl&dollar;" + BS + "D" + BS + "home" + BS + "alice",
                   "personal-home-path"),
                  ("&quest; completes a device path", BS * 2 + "&quest;" + BS + "UNC" + BS + "wsl.localhost" + BS + "D" + BS
                   + "home" + BS + "alice", "personal-home-path"),
                  ("&sol; and math letters", "&sol;&hopf;ome&sol;alice&sol;x", "personal-home-path")]
        # Astra's read at 30f2e005 (P1): the placeholder exception kept a construct between whitespace, so a comment or a
        # tag between "Bearer" and its token hid it from the bearer rule, while GitHub shows the token whole.
        for piece in ("<!--x-->", "<x>", "<font>", "<input>", "<?x?>", "<![CDATA[x]]>", "<!X y>", "</x>"):
            cases.append(("bearer split by " + piece, "Bearer " + piece + " " + "A" * 40, "bearer-credential"))
            cases.append(("a token prefix split by " + piece, "gh" + "p_" + piece + "a" * 36, "github-token"))
            cases.append(("a key prefix split by " + piece, "sk-" + "ant-" + piece + "A" * 30, "api-secret"))
            cases.append(("a fine-grained token prefix split by " + piece, "github" + "_pat_" + piece + "a" * 30,
                          "github-token"))
            cases.append(("a Hugging Face prefix split by " + piece, "hf" + "_" + piece + "a" * 20, "hugging-face-token"))
            cases.append(("a Tavily prefix split by " + piece, "tvly-" + piece + "a" * 24, "tavily-token"))
            cases.append(("a spaced token prefix split by " + piece, "Bearer " + piece + " " + "gh" + "p_" + "a" * 36,
                          "github-token"))
        # Only a tag is kept as a path placeholder: a comment, a processing instruction, a declaration or CDATA between
        # path separators is removed, as GitHub hides it, so the name after it is read.
        for piece in ("<!-- -->", "<?x?>", "<!X y>", "<![CDATA[]]>"):
            cases.append(("a home split by " + piece + " between separators", "C:/" + "Users/" + piece + "/Alice",
                          "windows-user-path"))
        for point in (0x034F, 0xFE00, 0xFE0F, 0xE0100, 0x180B, 0x180F, 0x17B4, 0x3164, 0x115F, 0x2065, 0xFFF0, 0xE0002,
                      0xE0041, 0xE007F):
            cases.append((f"default-ignorable U+{point:04X}", "/ho" + chr(point) + "me/alice/x", "personal-home-path"))
        cases += [("a numeric reference to VS16", "/ho&#xFE0F;me/alice/x", "personal-home-path"),
                  ("a numeric reference to CGJ", "/ho&#x34F;me/alice/x", "personal-home-path"),
                  ("a fullwidth solidus", chr(0xFF0F) + "home" + chr(0xFF0F) + "alice" + chr(0xFF0F) + "x", "personal-home-path"),
                  ("a fullwidth reverse solidus", "C:" + chr(0xFF3C) + "Users" + chr(0xFF3C) + "Alice", "windows-user-path"),
                  ("fullwidth letters", "/" + "".join(chr(0xFF41 + ord(c) - 97) for c in "home") + "/alice/x",
                   "personal-home-path")]
        payloads = [body("x " + text + " y" + SOURCES) for _, text, _ in cases]
        outcomes = {path.name: run_check(inline_script(sota_job(path)), payloads) for path in (VALIDATE, GATE)}
        self.assertEqual(outcomes["pr-metadata.yml"], outcomes["sota-sources-gate.yml"])
        for (case, _, rule), outcome in zip(cases, outcomes["sota-sources-gate.yml"]):
            with self.subTest(case=case):
                self.assertIn(rule, outcome["failed"] or "")

    def test_a_sample_across_the_entity_subset_is_decoded(self):
        # Every 4th name of the gate's subset, each placed where its decoded character completes a value (or, for a
        # name that projects to nothing, inside one).
        table = json.loads(ENTITY_FIXTURE.read_text(encoding="utf-8"))["entities"]
        subset = gate_entity_subset()
        templates = [(HOME + "alice/x", "personal-home-path"), ("gh" + "p_" + "abcdefghijklmnopqrstuvwxyz0123456789",
                                                             "github-token"), ("C:" + BS + "Users" + BS + "Alice", "windows-user-path")]
        cases = []
        for name in sorted(subset)[::4]:
            projected = node_project("".join(map(chr, table[name])))
            if projected == "":
                cases.append((name, "/ho&" + name + ";me/alice/x", "personal-home-path"))
                continue
            for template, rule in templates:
                if len(projected) == 1 and projected in template:
                    cases.append((name, template.replace(projected, "&" + name + ";", 1), rule))
                    break
        self.assertGreater(len(cases), 30)
        payloads = [body("x " + text + " y" + SOURCES) for _, text, _ in cases]
        outcomes = run_check(inline_script(sota_job(GATE)), payloads)
        for (name, _, rule), outcome in zip(cases, outcomes):
            with self.subTest(name=name):
                self.assertIn(rule, outcome["failed"] or "")

    def test_the_entity_subset_is_regenerated_from_the_pinned_table(self):
        # The gate's map holds exactly the names of the pinned HTML5 table (cmark-gfm src/entities.inc at 587a12bb,
        # kept as tests/fixtures/cmark-gfm-entities-587a12bb.json) whose text, after the gate's character projection,
        # is ASCII or nothing, each with its table value.
        fixture = json.loads(ENTITY_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(len(fixture["entities"]), 2125)
        expected = {name: "".join(map(chr, points)) for name, points in fixture["entities"].items()
                    if all(ord(c) < 128 for c in node_project("".join(map(chr, points))))}
        self.assertEqual(gate_entity_subset(), expected)
        self.assertEqual(len(expected), 297)

    @unittest.skipUnless((UPSTREAM_CMARK / "src/entities.inc").exists(), "the github/cmark-gfm mirror is not on this host")
    def test_the_entity_fixture_is_the_pinned_upstream_table(self):
        raw = subprocess.run(["git", "-C", str(UPSTREAM_CMARK), "show", CMARK_PIN + ":src/entities.inc"],
                             capture_output=True, check=True).stdout
        fixture = json.loads(ENTITY_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), fixture["sha256"])
        table = {}
        for name, numbers in re.findall(rb'[{][(]unsigned char[*][)]"([A-Za-z0-9]+)", [{]([0-9, ]+)[}][}]', raw):
            data = bytes(int(number) for number in numbers.decode().split(","))
            table[name.decode()] = [ord(c) for c in data.split(b"\0", 1)[0].decode("utf-8")]
        self.assertEqual(table, fixture["entities"])

    def test_ordinary_markup_and_placeholders_still_pass(self):
        texts = ["<details><summary>Notes</summary>See ~/" + ".config and the logs.</details>", "a <b>bold</b> word<br>",
                 "<!-- a comment --> and <sub>2</sub>", "C:" + BS + "Users" + BS + "<name>" + BS + "AppData",
                 HOME + "<user>/x", BS * 2 + "wsl$" + BS + "D" + BS + "home" + BS + "<WSL_USER>" + BS + "x",
                 "Use `<x>` or <kbd>Ctrl</kbd>&shy;C, a&zwj;b, x&UnderBar;y and &dollar;5.", "fullwidth " + chr(0xFF21) + "BC",
                 "an unclosed <!-- comment", "an unclosed <?pi and <![CDATA[ and <!X", "a < b > c and 1<2",
                 "C:/" + "Users/<name>/AppData and " + HOME + "<!-- c -->/x", "Bearer <user> token",
                 # A backslash-escaped '<' is text: GitHub shows C:\\Users<x>alice, so the tag is not removed.
                 "C:" + BS + "Users" + BS + "<x>alice"]
        outcomes = {path.name: run_check(inline_script(sota_job(path)), [body(text + SOURCES) for text in texts])
                    for path in (VALIDATE, GATE)}
        self.assertEqual(outcomes["pr-metadata.yml"], outcomes["sota-sources-gate.yml"])
        self.assertEqual([outcome["failed"] for outcome in outcomes["sota-sources-gate.yml"]], [None] * len(texts))

    def test_clean_bodies_with_admitted_and_format_characters_pass(self):
        # The projection removes characters; it never refuses a body that carries them around ordinary text.
        texts = ["See the notes" + character + "in the docs, ~/" + ".config and <user>." for character in
                 ("\x1c", "\x1d", "\x1e", "\x85", "\u200b", "\u00ad", "\u2028", "\u2029", "\u202e", "\ufeff", "<!-- a comment -->")]
        outcomes = {path.name: run_check(inline_script(sota_job(path)), [body(text + SOURCES) for text in texts])
                    for path in (VALIDATE, GATE)}
        self.assertEqual(outcomes["pr-metadata.yml"], outcomes["sota-sources-gate.yml"])
        self.assertEqual([outcome["failed"] for outcome in outcomes["sota-sources-gate.yml"]], [None] * len(texts))

    def test_a_body_at_the_bound_is_scanned_in_bounded_time(self):
        # The graph-id rule searched from every home- to the end of its run, quadratic in the run's length: a
        # 262,144-character run of "home-a.b-c_d-" took 21 s in the gate per form and 93 s in validate.py. The name now
        # runs at most 256 characters to -code-.
        sys.path.insert(0, str(ROOT / "scripts"))
        import time
        import validate
        run = ("home-a.b-c_d-" * (MAX_BODY // 13 + 1))[:MAX_BODY - len(SOURCES)]
        start = time.monotonic()
        dict(validate.PRIVATE_CONTENT)["encoded home path"].search(run)
        self.assertLess(time.monotonic() - start, 5)
        mixed = ("home-a.b-c_d-%2F&#47;**a**\\/" * (MAX_BODY // 27 + 1))[:MAX_BODY - len(SOURCES)]
        # The co-op's GPT read of fc60da90: a link label that may hold '[' rescans to the end of the body from every
        # unmatched '[', so 262,144 of them gave no verdict within 125 s.
        brackets = ["[" * (MAX_BODY - len(SOURCES)), ("![" * MAX_BODY)[:MAX_BODY - len(SOURCES)],
                    ("[a][" * MAX_BODY)[:MAX_BODY - len(SOURCES)]]
        # The command center's Claude read of 4e5ef13d (B2): adjacent whitespace quantifiers around an empty link
        # destination retried every split of the run, so "[a](" and 65,536 spaces gave no verdict within 130 s.
        unclosed = ["[a](" + filler * (MAX_BODY - 4 - len(SOURCES)) for filler in (" ", "\n", "\t")] + [
            ("[a](" + "(b) " * MAX_BODY)[:MAX_BODY - len(SOURCES)], ("[a](b " * MAX_BODY)[:MAX_BODY - len(SOURCES)]]
        # Round 2: unclosed comments, and the titled link shape's quote and whitespace runs.
        projected = [("<!--" * MAX_BODY)[:MAX_BODY - len(SOURCES)], ("[a](" + '"' * MAX_BODY)[:MAX_BODY - len(SOURCES)],
                     ("[a](b " + " \n" * MAX_BODY)[:MAX_BODY - len(SOURCES)], ("[a](\"x" * MAX_BODY)[:MAX_BODY - len(SOURCES)]]
        # The terminal round: unclosed markup of each kind, attribute runs, references and width forms.
        projected += [(unit * MAX_BODY)[:MAX_BODY - len(SOURCES)] for unit in
                      ("<?", "<![CDATA[", "<!X", "<a b='", '<a b="', "<a b ", "<a ", "&shy;", "&UnderBar;", chr(0xFF0F))]
        start = time.monotonic()
        outcomes = run_check(inline_script(sota_job(GATE)),
                             [body(text + SOURCES) for text in [run, mixed] + brackets + unclosed + projected])
        self.assertLess(time.monotonic() - start, 45)
        self.assertEqual([outcome["failed"] for outcome in outcomes], [None] * 24)

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
        patterns = dict(validate.PRIVATE_CONTENT)
        corpus = [text for case, text, _ in PRIVACY_CASES if case not in GATE_ONLY_CASES] + [
            "hf_" + "b" * 24, "tvly-" + "dev-" + "c" * 26, "-----BEGIN " + "RSA PRIVATE KEY-----",
            "-----BEGIN " + "EC PRIVATE KEY-----", "-----BEGIN " + "PRIVATE KEY BLOCK-----",
            "Bearer " + "d" * 40, "C:\\" + "Users\\Bob\\x", "-" + "Users-" + "bob-x", "home-" + "bob-code-x",
            "plain text with no secret", HOME + "example/a", "x-home-" + "example-y",
            "home-" + "a" * 256 + "-code-x", "home-" + "a" * 257 + "-code-x", "home-" + "a.b-" * 64 + "-code-x"]
        outcomes = run_check(inline_script(sota_job(GATE)), [body(text + SOURCES) for text in corpus])
        for text, outcome in zip(corpus, outcomes):
            for rule, name in PYTHON_NAMES.items():
                with self.subTest(rule=rule, case=text[:24]):
                    self.assertEqual(rule in (outcome["failed"] or ""), bool(patterns[name].search(text + SOURCES)))


# (P2-2) Each rule against its Python original over every code point Python assigns (bar surrogates and the
# supplementary private-use planes), placed where Unicode classes and boundaries decide the verdict.
PYTHON_NAMES = {"personal-home-path": "personal home path", "windows-user-path": "Windows user path",
                "encoded-home-path": "encoded home path", "hugging-face-token": "Hugging Face token",
                "github-token": "GitHub token", "tavily-token": "Tavily token", "api-secret": "API secret",
                "private-key": "private key", "bearer-credential": "bearer credential"}
# validate.py rules the gate leaves out (a pull request body may cite an identifier on purpose), and gate-only rules.
SESSION_RULES = {"local session identifier", "local companion task handle"}
GATE_ONLY_RULES = {"macos-user-path"}
X = "\x01"  # where each code point goes
TEMPLATES = {
    "personal-home-path": ["/home/" + X, X + "/home" + "/al", "/home" + "/al" + X, "/home/example" + X, "/Users/" + X + "/a",
                           "/" + X + "ome/al/", BS * 2 + "wsl$" + BS + "U" + BS + "home" + BS + X,
                           BS * 2 + "wsl$" + BS + "U" + BS + "home" + BS + "example" + X,
                           BS * 2 + "ws" + X + ".localhost" + BS + "U" + BS + "home" + BS + "al",
                           BS * 2 + "wsl.localhos" + X + BS + "U" + BS + "home" + BS + "al",
                           BS * 2 + "wsl$" + BS + X + BS + "home" + BS + "al", BS + X + "wsl$" + BS + "U" + BS + "home" + BS + "al",
                           BS * 2 + "wsl$" + BS + "U" + BS + "hom" + X + BS + "al",
                           BS * 2 + "wsl" + X + BS + "U" + BS + "home" + BS + "al",
                           BS * 2 + "?" + BS + "UN" + X + BS + "wsl$" + BS + "U" + BS + "home" + BS + "al",
                           BS * 2 + X + BS + "UNC" + BS + "wsl$" + BS + "U" + BS + "home" + BS + "al",
                           "/" + X + "wsl$/U" + BS + "home" + BS + "al",
                           BS * 2 + "wsl$" + BS + "U" + BS + "mnt" + BS + "c" + BS + "User" + X + BS + "al",
                           BS * 2 + "wsl$" + BS + "U" + BS + "mn" + X + BS + "c" + BS + "Users" + BS + "al"],
    "windows-user-path": ["C:\\User" + X + "\\bo", X + ":\\Users\\bo", "C:\\Users\\" + X,
                          "C:\\Users\\example" + X, "/mnt/" + X + "/Users" + "/bo", "c:\\" + X + "sers\\bo"],
    "encoded-home-path": [X + "-home-" + "bo-x", "-home-" + X, "-home-" + "bo" + X, "-home-example" + X, "home-" + X + "-code-x",
                          X + "home-bo" + "-code-", "-User" + X + "-bo-", X + "--Users-" + "bo-", "-mnt-" + X + "-Users-" + "bo-",
                          "-home-" + "bo" + X + "x", "home-bo" + X + "-code-"],
    "hugging-face-token": [X + "hf_" + "a" * 20, "hf_" + "a" * 20 + X, "hf_" + "a" * 19 + X],
    "github-token": [X + "ghp_" + "a" * 30, "ghp_" + "a" * 30 + X, "github_pat_" + "a" * 29 + X],
    "tavily-token": [X + "tvly-" + "a" * 24, "tvly-" + "a" * 24 + X, "tvly-dev-" + "a" * 23 + X],
    "api-secret": [X + "sk-" + "a" * 24, "sk-" + "a" * 24 + X, "sk-ant-" + "a" * 23 + X],
    "private-key": ["-----BEGIN " + X + "PRIVATE KEY-----", "-----BEGIN" + X + "PRIVATE KEY-----",
                    "-----BEGIN ENCRYPTED" + X + "PRIVATE KEY-----", "-----BEGIN PGP PRIVATE KEY" + X + "BLOCK-----",
                    "-----BEGIN PRIVATE KEY" + X + "-----"],
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

    def test_every_scripts_validate_rule_has_its_gate_rule(self):
        # Codex's review of de4eed8f: a rule added to or renamed in validate.py's PRIVATE_CONTENT fails here until
        # the gate carries it, so the two scans cannot drift apart unnoticed.
        sys.path.insert(0, str(ROOT / "scripts"))
        import validate
        self.assertEqual(set(PYTHON_NAMES.values()), {name for name, _ in validate.PRIVATE_CONTENT} - SESSION_RULES)
        result = subprocess.run([NODE, "-e", ORACLE], input=json.dumps(
            {"rules": privacy_rules(inline_script(sota_job(GATE))), "templates": {}, "ranges": []}),
            capture_output=True, text=True, timeout=60, check=True)
        self.assertEqual(set(json.loads(result.stdout)["flags"]), set(PYTHON_NAMES) | GATE_ONLY_RULES)

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
