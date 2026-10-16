# Decision: the landscape install manifest for stage H (2026-10-16)

**Status:** PROPOSAL, routed to the [layer-resolution protocol](2026-10-11-layer-resolution-protocol.md) under
`foundation/recovery-portability` and `foundation/scheduling-supervision`. Nothing installs from it. The installs wait
until the co-op's INCOMPLETE screens are finished; that is step 3 of the campaign.

## Trigger

- **The owner, 2026-10-15 ET (paraphrased):** run full-landscape convergence over the starred repositories, the awesome
  lists and the research runtimes' output, and install the converged candidates into NativeHorizonNY (private
  horizon). Every SOTA repository is covered.
- **The command center (CC), 2026-10-16:** draft this design with api-actions, who owns horizon. Installs start only
  after the incomplete screens finish, and every row is pinned.
- **The install plan's Decision 9** ([2026-10-15-new-wsl-clean-install-plan.md](2026-10-15-new-wsl-clean-install-plan.md)
  `:717-795` at `5bab63233`) already sets stage H:
  - An unscreened candidate never installs (`:733-734`).
  - Each candidate that passes its screen at a pin installs through its vendor's own path, with one check, a recorded
    inverse, invoke wiring and a FINAL or TRIAL label (`:739-743`).
  - Order: stage H follows stage C; client-level installs follow stage D; a candidate that dials the gateway runs only
    after stage S (`:744-761`).
  - Every screened candidate is installed but enabled by role, through a generated role-assignment matrix
    (`:764-795`). The generator is a named gap (`:778`).

This record proposes the row format and the generation that carry those rules.

## Why a new manifest

The 10-02 install plan cannot hold stage H as it stands:

- Each `install-plan.json` row must match a slot of the definitive manifest. `check_plan.py` refuses a duplicated slot
  (`evidence/artifacts/new-wsl-install-plan-20261002/check_plan.py:343-345`) and a row with no counterpart in the
  manifest's foundation rows (`:395-398`), at `5bab63233`.
- Its commands are shell strings, and it has no inverse field and no label.

The co-op's screen tables (private, cited by name: `ns2604-coop/screens-20261015/tables`) hold 1,019 rows: 131 PASS,
837 INCOMPLETE and 51 FAIL. The 131 PASS rows cover 26 distinct candidates, and they record install paths as prose.
Classifying them (2026-10-16) shows:

- mostly versioned release-binary downloads;
- 14 npm global installs, 8 Python packages and 4 vendor install scripts;
- 2 Homebrew lines and 1 `uv add`;
- 11 rows that document no inverse.

## The row

[`adoption/landscape-install-row.schema.json`](../../adoption/landscape-install-row.schema.json) (JSON Schema 2020-12)
defines one row per candidate. A candidate installs once, however many layers and families screened it.

| Field | Content | Rule |
| --- | --- | --- |
| `id` | stable row id | the `component_id` of the row's host receipts |
| `candidate` | repository, name, package ids | an https URL with no user information |
| `pin` | exact `version`, plus `commit` (40 hex) or `artifact` (url, sha256) | no `latest`, `stable`, `main`, `HEAD`, range or wildcard; a `vendor-installer` row needs `artifact` |
| `screens` | each PASS screen: layer, family, table name, candidate | at least one; verdict `PASS` only |
| `route` | the vendor-path family (below) | fixes the stage the row follows |
| `install`, `inverse` | lists of argv | no element is a shell, so no command is a shell string |
| `check` | argv, `expect_exit`, `stdout_contains`, and how cleanup proves absence: `absent_by` (`exit` with `absent_exit`, `text`, or the labelled fallback `negation`) | at least one; `text` needs `stdout_contains` |
| `sources` | where install, check and inverse are documented, at a pin | the candidate's docs, or the route tool's where the candidate documents none |
| `dials` | the install plan's service slots the candidate dials (for example `gpt-gateway`) | none of its runs starts before stage S proves that slot's listener |
| `models` | each model the row selects, by its `catalogs/foundation/model-currency.json` id, and where it is selected | required, empty when none; the active-selector check refuses one that is not current |
| `invoke` | kind (`skill`, `plugin`, `mcp-server`, `cli`, `sdk`, `service`) and names | what invoke tracking counts, so zero calls is a wiring finding |
| `roles` | rows of the role-assignment matrix | never a fenced session |
| `startup_context_cost` | tokens or null, basis, method, receipt name | FINAL needs `measured`, integer tokens and a receipt |
| `label` | TRIAL or FINAL | FINAL only when every layer in `screens` is FINAL with this candidate as winner at this pin |

The row has no port or service fields. A service's port and isolation stay under the install plan's Decision 3.

## Routes

Help texts were captured on NativeStack2604 at 2026-10-16T02:39Z (private, by name: `route-help-20261016-v2.txt`).

| Route | Install, check, inverse | Stage | Source |
| --- | --- | --- | --- |
| `mise` | `mise use --global <backend:tool@version>`; `mise where <tool@version>`; `mise unuse --global ...` | C | mise 2026.10.3 help; `mise where` exits 1 for a tool that is not installed (measured). Its registry maps grype, syft, trivy, gitleaks, shellcheck, difftastic, actionlint, ast-grep and worktrunk to `aqua:` backends; prometheus and poutine have no registry entry and take the `github:` backend. `mise lock` records versions, checksums and download URLs. The Homebrew lines fold in here. |
| `uv-tool` | `uv tool install <pkg>==<version>`; `uv tool list`; `uv tool uninstall <pkg>` | C | uv 0.12.22 (`70fe1196`), `crates/uv-cli/src/lib.rs:5513`, `:5538` |
| `uv-add` | `uv add --project <env> <pkg>==<version>`; `uv tree --project <env> --package <pkg> --depth 0`; `uv remove --project <env> <pkg>` | C | the same, `:1142`, `:1165`, `:1250`; `docs/concepts/projects/dependencies.md:22`, `:92` |
| `npm-global` | `npm install --global <pkg>@<version>`; `npm ls --global <pkg>`; `npm uninstall --global <pkg>` | C | npm 11.19.0 help; `npm ls --global` exits 1 for a missing package (measured) |
| `claude-plugin` | `claude plugin install --scope local <plugin>@<marketplace>`; `claude plugin list`; `claude plugin uninstall --scope local ...` | D | Claude Code 2.1.301 help; per role project (Decision 9, `:789`) |
| `claude-mcp` | `claude mcp add --scope local <name> -- <command>`; `claude mcp list`; `claude mcp remove --scope local <name>` | D | Claude Code 2.1.301 help: `mcp list` and `mcp get` health-check approved servers, so this check runs the server |
| `codex-plugin` | `codex plugin add <plugin>@<marketplace>`; `codex plugin list`; `codex plugin remove ...` | D | codex-cli 0.162.1 help; inside each lane's `CODEX_HOME` (Decision 9, `:789`) |
| `codex-mcp` | `codex mcp add <name> -- <command>`; `codex mcp list`; `codex mcp remove <name>` | D | codex-cli 0.162.1 help |
| `skills-cli` | `npx --yes skills@1.7.0 add <immutable tree URL> -a <agent> -y`; `list`; `remove <skill> -y` | D | the adopted Skills CLI (`adoption/skills/lifecycle.md:13-14`), vercel-labs/skills `7407f389` `README.md:87-92`, `:132` (project scope by default) |
| `systemd-user` | `systemctl --user enable --now <unit>`; `systemctl --user show --property=ActiveState <unit>` for `ActiveState=active`; `disable --now` | S | systemd 259. Its man page calls the LSB exit codes an imperfect map and points to unit states instead; `show` exits 0 with `ActiveState=inactive` for a missing unit (measured). After Decision 3's port and isolation proofs |
| `vendor-installer` | the verified download of `pin.artifact`, made executable and run directly with the exact version as an argument | C | the candidate's own installer at its sha256 |

Notes on the routes:

- **Python libraries take `uv-add`.** A library has no console script, so `uv tool install` does not fit it. The
  measured behaviour, in a scratch project with idna 3.10 on uv 0.12.22: `uv tree` prints `idna v3.10`, and after
  `uv remove` it still exits 0 but prints no such line. So the check's `stdout_contains` decides, not the exit code.
- **The 10-02 plan's library rows use a per-tool venv** (`uv pip install --python <venv>`, as in the `claude-agent-sdk`
  slot). A project with a lockfile adds hashes and a documented inverse (`uv remove`). The difference is recorded here,
  and it changes no stage C row.
- **Client-level routes follow stage D.** The client-configuration tool renders `enabledPlugins` from a closed-world
  map (`tools/adoption/new_wsl_client_config.py:533` at `5bab63233`). So each enablement is a delta to that apply, and
  the map gains its rows before any re-apply (Decision 9, `:745-749`).
- **Not rows:**
  - a bundled capability of an installed client, such as `claude -p` composition or the bundled `/batch` skill (both
    PASS in `orchestration-frameworks`), installs nothing; enabling it is role configuration;
  - a candidate already installed as a stage C slot stays with stage C. For example the plan's `claude-agent-sdk`
    slot is at 0.2.163 and its screen is at 0.2.167; its re-pin goes through the plan.

## Receipts: host receipts, no new format

Each row's runs are recorded with `scripts/host_receipts.py record` (`adoption/host-receipt.schema.json`), with the
row id as `component_id`. The install-stage receipt carries the install argv and the checks. The cleanup-stage receipt
carries the inverse argv and the checks, which must no longer pass.

- **Commands.** `record` runs each `--cmd` with `shell=True` (`scripts/host_receipts.py:733-738` at `5bab63233`).
  That is `/bin/sh -c` (CPython v3.13.16 `cbc944f4`, `Lib/subprocess.py:1851-1853`), dash 0.5.12 on NativeStack2604.
  `record` marks a receipt `pass` only when every exit is 0 (`:1033`). A pipeline's status follows the pipefail option
  ([POSIX.1-2024, 2.9.2 Pipelines](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/V3_chap02.html#tag_19_09_02)).
  dash accepts `set -o pipefail`, but by default `false | true` exits 0 (measured), so the composition relies on
  neither. It is built from quoted parts, as api-actions reviewed it at `2bb57790`:
  - an argv is passed as `shlex.join(argv)`, which the shell runs as exactly that argv (`Lib/shlex.py:316-318`);
  - an install-stage check is `<check>; test $? -eq N`, with N its `expect_exit`. With `stdout_contains`, it is
    `out=$(<check>); test $? -eq N && printf '%s\n' "$out" | grep -F -e <quoted text>`. An assignment-only command
    takes its command substitution's status (2.9.1 Simple Commands; `out=$(exit 3)` returns 3, measured), so a check
    that prints its text but fails fails the receipt.
  - a cleanup-stage check proves absence by its `absent_by`:
    - `exit`: `<check>; test $? -eq <absent_exit>`. Examples: 127 for a command that is gone (2.8.2 Exit Status for
      Commands; measured); 1 for `npm ls --global` and for `mise where` (measured).
    - `text`: `out=$(<check>); test $? -eq N && ! printf '%s\n' "$out" | grep -q -F -e <quoted text>`. The check ran
      normally and its text is gone.
    - `negation`: `! <check>`, the labelled fallback for a check with no documented absence. Any failing exit, a crash
      included, reads as absent there.
  - `compose` in [`tests/test_landscape_install_row_schema.py`](../../tests/test_landscape_install_row_schema.py) states
    this composition. Its tests run it under `/bin/sh`, with controls for the plain pipeline and for an unbraced `cd`.
- **Role locations.** `record` runs every command in the repository root (`run_command(cmd, cwd=root, ...)`, `:1023`).
  A client-level row runs in each role's location (Decision 9, `:789`): the role's project for Claude Code
  (`--scope local`), or the lane's own `CODEX_HOME` for Codex.
  - For Claude Code, the generator wraps the composed command as `cd <quoted project> && { <command>; }`. Without the
    braces, a failed `cd`'s own status can satisfy an absent exit.
  - For Codex, it puts the lane home on the argv itself.
- **No credential in a check.** `sanitize` (`:273-285`) replaces home and user names and the 11 private-content
  patterns of `scripts/validate.py:38`, which include some token shapes. It is not a general secret filter. So checks
  use version, list and help forms, and no check prints a credential.
- **One receipt per stage.** `record` refuses a second receipt for the same host, component, stage and day unless
  `--supersedes` names the latest one (`:1008-1010`, `:1964-1970`). So a row records one install-stage receipt, whose
  commands cover every role location, not one receipt per role.
- **Digests.** `output_sha256` is the sha256 of the sanitized excerpt (`:1012-1029`; `sanitize` at `:273`), so a
  receipt binds only published bytes.
- **CI lines.** The generated accept script takes horizon's head (`git rev-parse HEAD`). After its
  `sh tests/hooks_test.sh` line, it writes one `CI: exit <rc> at <40-hex head>: <shlex.join(argv)>` line per check into
  the receipts file that horizon's lander reads.
- **Where things live.** Receipts and third-party bytes stay in private horizon. This repository carries URL, pin and
  sha256, and cites horizon receipts by name.
- **PROPOSAL.** `validate_receipt_cross_references` (`:1250`) accepts a `component_id` only from
  `manifests/stack.json` or the landscape winners (`:1290-1291`). A row id is neither, so validating these receipts
  needs that check to accept install-manifest row ids, or horizon validates them against its own list.

## Model selection

The owner's addendum-18 to the CC's direction (2026-10-16, cited by name) makes the latest models and practice hard
rules on NativeHorizonNY and every later distribution.

- Each row names the models it selects (`models`), by their `catalogs/foundation/model-currency.json` ids. The
  active-selector check of the [2026-10-09 decision](2026-10-09-active-model-currency.md)
  (`scripts/active_model_currency.py`) can then refuse a row whose model is not current.
- PROPOSAL: build the row check from `model_currency_problems` (`scripts/validate.py:68-162` at `5bab63233`). That code
  holds the 42-day release-age and 7-day landscape-age limits and the `in_use`, `held` and `package_bound` statuses.
  The check runs as one of horizon's required checks, which api-actions owns.
- Running the same check from the installer and the session-start hook, with its inverse, is a separate pull request
  after #1180.

## Generation and checks, in horizon

From the rows, horizon generates:

- the install script and the accept script;
- the role-assignment matrix (Decision 9, `:764-795`);
- the client-configuration map rows for the client-level routes.

Horizon pins this repository by commit (`pins.json`, per horizon's README), so it takes the schema and the rule tests
at one commit. Its checker refuses a row that:

- fails the schema;
- on a versioned route, has no install argv naming `pin.version`. `unbound_version` in
  [`tests/test_landscape_install_row_schema.py`](../../tests/test_landscape_install_row_schema.py) states this rule.
- installs a repository that an installed stage C slot already installs. `stage_c_slots` in the same test states this
  rule, and it finds the plan's `claude-agent-sdk` slot.
- is a `systemd-user` row whose unit has no port and isolation entry under Decision 3;
- starts a run before stage S has proved, for each slot in `dials`, the listener-ownership check (Decision 9,
  `:750-761`).

## Roles

The roles are the rows of the role-assignment matrix (Decision 9, `:787-795`): `builder`, `reviewer`, `auditor`,
`researcher`, `command-center`, `co-op`, and the runtime workers `worker-pi`, `worker-opencode` and `worker-muse`.

- Fenced sessions and Jev take no framework (`:794-795`), so they are never a row's role.
- The screens carry roles as prose. Mapping them to matrix rows is the conversion step. The role owner,
  cc-native-practice, rules that mapping (step 6 of the owner-approved landscape campaign plan of 2026-10-15,
  private).
- A worker built on an SDK has no matrix row yet. It gains one when the matrix generator names its profile
  (PROPOSAL).

## Labels and start-up cost

- **Label.** A row is TRIAL unless every layer it screens in is FINAL with this candidate as the winner at this pin
  (`scripts/final_stack.py`, `enforce_final`).
- **Start-up cost.** The matrix measures each role's start-up cost at session start, against its plain control profile
  (Decision 9, `:779-780`). Most screens give only an ESTIMATE, often with no total; the schema keeps such a cost
  TRIAL.

## Mapping from the 10-02 install plan

| `install-plan.json` `owners[]` | Row |
| --- | --- |
| `slot` | `id` |
| `repository` | `candidate.repository` |
| `release`, `source_pin`, `version_pinned`, `package_integrity` | `pin` |
| `route` | `route` |
| `commands` (shell strings) | `install` (argv) |
| `acceptance` | `check` |
| `service` | none: Decision 3 |
| `needs` (host prerequisites) | none: stage C provides them |
| none | `inverse`, `screens`, `sources`, `dials`, `invoke`, `roles`, `startup_context_cost`, `label` |

## Boundaries

- **Measured** on NativeStack2604, 2026-10-16:
  - the route help texts;
  - the `uv-add` check behaviour;
  - the shell facts behind the composition (dash 0.5.12), and the absent exits of `npm ls`, `mise where`,
    `systemctl show` and a missing command;
  - the classification of the 131 PASS rows;
  - the schema tests (`python3 -m unittest tests.test_landscape_install_row_schema`, jsonschema 4.26.0 as in
    `.github/requirements-ci.txt:17`).
- **Not run:** no route ran on NativeHorizonNY for this record, and no row exists yet.
- **Pins drift.** The campaign plan's survey found superpowers at v7.0.0 against v6.4.1, and claude-code, codex,
  trailofbits and git unpinned in places. Every row here is pinned; a new pin is a new row version through review.
- **Not covered:** a source build (for example `make build` in a source workspace) has no route. The OpenHands SDK's
  screen points to its modular packages once their exact versions are bound; those take `uv-add`.
- **Overturn.** No PASS screen row is an installer that covers these routes. The screens were classified by install
  path, not by candidate kind. So this record reuses each route's own tool and the repository's host receipts, and the
  protocol compares installers under `recovery-portability`. A screened installer that covers these routes, with
  receipts and inverses, supersedes this generation through a recorded supersession.
