# Retire adoption macOS CI (2026-10-10)

**Status:** selected by the owner on 2026-10-10, around 02:28 UTC; the
implementation is subject to the normal PR review and merge checks.

## Decision and scope

Remove `bootstrap-macos`, `bootstrap-macos-brew` and `validate-macos` from
`.github/workflows/adoption-bootstrap.yml`. Remove their macOS path classifier,
`MACOS_PATTERNS` drift guard, mode outputs, and tests whose contract requires
those jobs. The remaining `changes` job selects the Linux bootstrap on pull
requests using the existing input patterns. Missing SHAs and failed diffs keep
its fail-open behavior. Linux still runs on eligible main pushes, the daily
06:47 UTC schedule, and manual dispatch.

The day-to-day environment the owner uses is WSL/Linux. Maintaining an
additional advisory adoption lane distracts from that environment. The macOS
jobs were reported red during 2026-10-07 through 2026-10-09; the retained
[portability repair record](2026-10-09-validate-macos-portability.md) cites a
specific native failure and distinguishes its measured failures from the
broader reported window. This decision does not claim a new survey of all runs.

GitHub documents standard GitHub-hosted runner use as free for public
repositories. These standard macOS jobs therefore offered no runner-minute
bill to eliminate. The benefit is a smaller maintenance obligation and more
attention for the environment in use. Larger runners and storage have separate
billing rules; no savings estimate is claimed for them.

The daily macOS proposal [#914](https://github.com/seathatflowsinourveins/native-agent-stack/pull/914)
is superseded. Its close comment links to the implementation PR for this
decision. Required status contexts stay as already configured; the removed
jobs were advisory and outside that required set.

## Retained portability and evidence

The portable repairs in
[#948](https://github.com/seathatflowsinourveins/native-agent-stack/pull/948)
remain: resolved SDK containment/relative references, the stricter independent
source-policy guard, canonical disposable fixture roots and the other portable
interfaces. Darwin/capability skip guards remain in the tests. The macOS
bootstrap script, platform profile, manual instructions and portable installer
tests remain available.

Past hosted receipts and their recorded run IDs remain historical evidence.
The retained hosted-smoke metadata is marked retired; it does not advertise an
active job or change the profile's drafted acceptance state. Removing CI gives
no new native macOS acceptance result. WSL/Linux runs and simulations continue
to carry their own evidence limits.

This retirement is bounded to the three adoption jobs. The separate
`hardware-profile-smoke.yml` diagnostic has its own owner and scope. Historical
records and artifacts are preserved.

The generated WSL handbook records the normalized adoption manifest digest.
Its maintained builder refreshes that reference and the output receipt when
the historical hosted-smoke row gains retirement metadata. The landed
[resolver prerequisite #959](https://github.com/seathatflowsinourveins/native-agent-stack/pull/959)
at main `0a053e1e5861a5522dcbbeea1c5006c4d8937b95` recognizes Linux
`scripts/validate_shards.py run` as root `test*.py` discovery. The repository
fixture keeps `ci_discovered` protection for a future root test module;
retirement does not turn the test package into an advisory inventory.

The recording guides describe the retired jobs in past tense. Their Python
3.9 floor remains guarded portably over all six recording/verdict scripts by
`ast.parse(..., feature_version=(3, 9))`, with a Python 3.10 `match` rejection
control. This is best-effort syntax validation, not execution on Python 3.9
or a new macOS observation. The doc assertion failed before the stale
current-CI claims were corrected.

`docs/acceptance-evidence-policy.md` is unchanged and remains registered
publication evidence. Only the retired jobs named it as a workflow-derived
`ci_named` protected path; removing that category is the bounded consequence
of retiring their run text. The document's acceptance standards remain in
force, while future document edits receive normal publication/CI review.
The resolver continues to exclude monitoring-only read inventories from
refusal categories and unions trusted/base/head protection for outgoing
changes; no gate permission, allow-list or protected-code rule is relaxed.

## Superseded decisions

This policy replaces the adoption macOS job/scope/coverage requirements in:

- [2026-10-03-macos-ci-scope.md](2026-10-03-macos-ci-scope.md).
- [2026-10-03-macos-full-suite-coverage.md](2026-10-03-macos-full-suite-coverage.md).
- [2026-10-05-macos-ci-advisory.md](2026-10-05-macos-ci-advisory.md).

Those documents receive dated forward pointers. Their earlier measurements,
implementation history and native failure artifacts remain available. The
native-after-run expectation in the 2026-10-09 repair record also ends with
retirement of these jobs; its portable code changes remain in force.

## Revisit

Reconsider maintained macOS CI when the owner requests it, or when a macOS
adopter appears who needs that coverage. Establish the new scope and native
validation evidence in a fresh decision at that time.

## Executable inverse

This is a local restoration rehearsal, bounded to the adoption workflow and
the removed CI contract tests. Its donor is landed main
`a56f85e8397751d36fdbdc03910f15ac877ad00c`, including the #948 portable repairs;
it uses no PR-branch source pin. The workflow at that pin is byte-identical to
pre-retirement main `c4f4990737c4e2ed8f0452d069e25a460f897bb5`.
Git 2.53.0 supplies `worktree` and `restore --source`; CPython 3.13.16's AST
locates the unchanged donor test definitions. No current test module is
replaced wholesale. The restored graph has `changes`, `bootstrap-linux`,
`bootstrap-macos`, `bootstrap-macos-brew` and `validate-macos`; the donor
contracts check the `MACOS_PATTERNS` selector and `bootstrap`, `macos`,
`macos_tests` outputs, including full and changed-tests modes.

Run from a clean checkout of landed retirement main. The scratch worktree
starts at the executing checkout's HEAD, then the following commands restore
the workflow and reinstate the named tests only there. The current Linux-only
job-set assertion is expected to refuse that graph; a future restoration PR
must replace that retirement assertion with the reviewed restored policy.
This rehearsal does not apply a new CI policy or alter required contexts.

```sh
set -eu
restore_pin=a56f85e8397751d36fdbdc03910f15ac877ad00c
git cat-file -e "${restore_pin}^{commit}"
git merge-base --is-ancestor "$restore_pin" HEAD
restore_tmp=$(mktemp -d)
restore_tree="$restore_tmp/tree"
git worktree add --quiet --detach "$restore_tree" HEAD
trap 'git worktree remove --force "$restore_tree"; rmdir "$restore_tmp"' EXIT
(
  cd "$restore_tree"
  git restore --source="$restore_pin" -- .github/workflows/adoption-bootstrap.yml
  RESTORE_PIN="$restore_pin" python3 - <<'PY'
import ast
import os
from pathlib import Path
import subprocess

pin = os.environ["RESTORE_PIN"]
def source(path):
    return subprocess.check_output(["git", "show", pin + ":" + path], text=True)
def segment(text, node):
    start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    return "\n".join(text.splitlines()[start - 1:node.end_lineno]) + "\n"

hardening = source("tests/test_workflow_hardening.py")
keep = {"AdoptionBootstrapMacosAdvisoryTests", "ValidateMacosGateEvaluationTests",
        "MacosPatternsTests", "ValidateMacosModeTests", "ChangesModeComputationTests",
        "ChangedTestsStepRunTests"}
nodes = ast.parse(hardening).body
probe = "\n".join(segment(hardening, node) for node in nodes
                  if not isinstance(node, ast.ClassDef) or node.name in keep)
Path("tests/_macos_restore_source.py").write_text(probe, encoding="utf-8")
portable = source("tests/test_adoption_bootstrap_macos.py")
keep = {"CIEmbedModelCacheOrderTests", "CIRecordingToolingSmokeTests", "CIWorkflowTriggerPathsTests"}
addition = '\nWORKFLOW_PATH = ROOT / ".github/workflows/adoption-bootstrap.yml"\n'
addition += "\n".join(segment(portable, node) for node in ast.parse(portable).body
                       if isinstance(node, ast.ClassDef) and node.name in keep)
path = Path("tests/test_adoption_bootstrap_macos.py")
assert not keep.intersection(n.name for n in ast.parse(path.read_text()).body
                             if isinstance(n, ast.ClassDef)), "CI tests already restored"
path.write_text(path.read_text() + addition, encoding="utf-8")
PY
  nice -n 19 ionice -c 3 python3 -B -m unittest \
    tests._macos_restore_source.AdoptionBootstrapMacosAdvisoryTests \
    tests._macos_restore_source.ValidateMacosGateEvaluationTests \
    tests._macos_restore_source.MacosPatternsTests \
    tests._macos_restore_source.ValidateMacosModeTests \
    tests._macos_restore_source.ChangesModeComputationTests \
    tests._macos_restore_source.ChangedTestsStepRunTests \
    tests.test_adoption_bootstrap_macos.CIEmbedModelCacheOrderTests \
    tests.test_adoption_bootstrap_macos.CIRecordingToolingSmokeTests \
    tests.test_adoption_bootstrap_macos.CIWorkflowTriggerPathsTests
  python3 -B - <<'PY'
import unittest
name = "tests.test_workflow_hardening.AdoptionBootstrapLinuxPolicyTests." \
       "test_bootstrap_linux_stays_path_gated_on_pull_request_and_still_runs_off_it"
result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromName(name))
assert result.testsRun == 1 and len(result.failures) == 1 and not result.errors
assert "retirement permits only" in result.failures[0][1]
PY
  nice -n 19 ionice -c 3 python3 -B -m unittest \
    tests.test_runtime_worker_openhands_push_gate \
    tests.test_runtime_worker_openhands_resolver \
    tests.test_adoption_bootstrap_macos.ScriptStructureTests \
    tests.test_adoption_bootstrap_macos.ScriptBehaviorTests \
    tests.test_adoption_bootstrap_macos.EmbedAcceptanceScriptTests \
    tests.test_adoption_bootstrap_macos.PlatformPageTests.test_retired_recording_smoke_keeps_a_portable_python_39_syntax_guard
  rm tests/_macos_restore_source.py
  python3 scripts/build_new_wsl_handbook.py --write
  python3 scripts/build_new_wsl_handbook.py --check
  python3 - <<'PY'
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, "scripts")
import host_receipts
paths = subprocess.check_output(["git", "diff", "--name-only", "origin/main"], text=True).splitlines()
reports = {"manifests/evidence.json", "catalogs/landscape/component-evidence-matrix.json",
           "docs/component-evidence-matrix.md", "catalogs/landscape/new-host-grand-list.json",
           "docs/new-host-grand-list.md"}
for path in paths:
    if path not in reports:
        host_receipts.register_file(Path("."), path)
PY
  python3 scripts/component_matrix.py --write
  python3 scripts/new_host_grand_list.py --write
  python3 scripts/evidence_manifest.py --write
  nice -n 19 ionice -c 3 python3 scripts/validate.py
)
```

The scratch worktree is removed on exit. Keep the retained hosted receipts
historical: neither this inverse nor local fixtures constitute native macOS
execution. A real restoration still needs a fresh reviewed decision and a
GitHub-hosted macOS or physical Mac run, with the Python 3.9 execution floor,
embedding backend and provisioning evidence recorded on that platform.

Scratch verification on 2026-10-10: **58 donor CI contract tests passed**;
the current retirement job-set assertion rejected the restored graph with the
expected single failure. **299 current protection/portability tests passed,
with one capability skip**. Native handbook write/check, generated reports,
manifest normalization and **FULL validate exited 0** (70 components, four
profiles and 239 receipts). The donor bodies and decorators were unchanged.
The initial whole-old-module import failed on an unrelated removed
verdict-review job; bounded extraction avoids that rollback. The first
scratch validate exposed stale registrations inherited from the landing
rebase's main-only manifest. Re-registering the own changes against origin/main
as above resolved them. These retained attempts and the final pass establish
local reversibility and integrity; they provide no native macOS acceptance.

## Validation and sources

The implementation uses the repository's existing workflow structure and
keeps the Linux event/path contracts. Local validation uses the CI-pinned
`kjanat/actionlint` 1.17.0 and `zizmor` 1.30.1, the workflow-policy and hardening
modules, affected portable/adoption tests, and FULL evidence validation. Exact
commands and measured outcomes belong to the implementation PR; a syntax or
fixture check does not establish a native macOS run.

## SOTA sources

- GitHub, [GitHub Actions billing — Free use of GitHub Actions](https://docs.github.com/en/billing/concepts/product-billing/github-actions#free-use-of-github-actions),
  read **2026-10-10**: standard GitHub-hosted runners are free for public
  repositories; larger runners are charged separately.
- GitHub, [GitHub-hosted runners](https://docs.github.com/en/actions/concepts/runners/github-hosted-runners),
  read **2026-10-10**: the supported hosted-runner model and its public-repository
  use. This decision retires the existing job graph rather than replacing the
  runner platform.
- Maintained repository source at
  [`a56f85e8397751d36fdbdc03910f15ac877ad00c`](https://github.com/seathatflowsinourveins/native-agent-stack/tree/a56f85e8397751d36fdbdc03910f15ac877ad00c):
  `.github/workflows/adoption-bootstrap.yml`, the workflow contract tests and
  the landed #948 portable repairs.
- The same maintained source pin's
  scripts/build_new_wsl_handbook.py, --write/--check, and
  blueprints/runtime-workers/openhands/resolver/push_gate.py,
  derive_ci_protected: supported handbook regeneration and the distinction
  between workflow-named protection and advisory read-derived inventory.
- CI tool pins: `.github/workflows/validate.yml` selects
  [`kjanat/actionlint` v1.17.0](https://github.com/kjanat/actionlint/releases/tag/v1.17.0)
  with its SHA256-verified release archive; `.github/requirements-ci.txt`
  checksum-locks [`zizmor` 1.30.1](https://github.com/zizmorcore/zizmor/releases/tag/v1.30.1).
  The installed clients report those same versions.
- CPython [v3.13.16 ast.parse](https://github.com/python/cpython/blob/v3.13.16/Lib/ast.py)
  and [AST documentation](https://github.com/python/cpython/blob/v3.13.16/Doc/library/ast.rst):
  `feature_version=(3, 9)` is a best-effort grammar check, not target-version
  execution or a parsing-equivalence guarantee.
- The resolver discovery prerequisite at main
  [`0a053e1e5861a5522dcbbeea1c5006c4d8937b95`](https://github.com/seathatflowsinourveins/native-agent-stack/tree/0a053e1e5861a5522dcbbeea1c5006c4d8937b95):
  `scripts/validate_shards.py` root discovery and the own-repository
  protected-module regression retain the Linux test enforcement after retirement.
- Git [v2.53.0 git-restore](https://github.com/git/git/blob/v2.53.0/Documentation/git-restore.adoc)
  and [git-worktree](https://github.com/git/git/blob/v2.53.0/Documentation/git-worktree.adoc):
  native `restore --source` and disposable detached worktrees bound the inverse;
  the installed Git 2.53.0 client exposes these options.
