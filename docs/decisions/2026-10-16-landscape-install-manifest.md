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
837 INCOMPLETE and 51 FAIL. The 131 PASS rows record install paths as prose. Classifying them (2026-10-16) shows:

- mostly versioned release-binary downloads;
- 14 npm global installs, 8 Python packages and 4 vendor install scripts;
- 2 Homebrew lines and 1 `uv add`;
- 11 rows that document no inverse.

**Counting the PASS candidates.** The tables carry a candidate's identity in one of two shapes: `id` with
`repository_url`, or `repository` with `ids`. The 131 PASS rows give:

| Key | Distinct |
| --- | ---: |
| normalized repository URL | 52 |
| `id`, else the repository | 53 |
| (candidate, layer) pair | 60 |
| whole candidate record | 61 |

- The campaign plan's survey counted 62 distinct, and none of these keys reproduces that.
- An earlier draft of this record keyed on `id` alone and undercounted 26.
- A row is one installable artifact, so the manifest's row count follows the converted rows, not these counts.

## The row

[`adoption/landscape-install-row.schema.json`](../../adoption/landscape-install-row.schema.json) (JSON Schema 2020-12)
defines one row per candidate. A candidate installs once, however many layers and families screened it.

| Field | Content | Rule |
| --- | --- | --- |
| `id` | stable row id | the `component_id` of the row's host receipts |
| `candidate` | repository, name, package ids | an https URL with no user information |
| `pin` | an exact `version` (three numeric components, then optional pre-release or build parts), plus `commit` (40 hex) or `artifact` (url, sha256) | no wildcard segment, comparator, range or channel name; commit routes need `commit`, artifact routes `artifact` |
| `screens` | each PASS screen: layer, family, table name, candidate | at least one; verdict `PASS` only |
| `route` | the vendor-path family (below) | fixes the stage the row follows and what its install must bind |
| `install`, `inverse` | lists of argv | no element is a shell, so no command is a shell string |
| `check` | argv, `expect_exit`, `stdout_contains`, and how cleanup proves absence: `absent_by` is `exit` (with `absent_exit`) or `text` | at least one; `text` needs `stdout_contains`; no bare-negation fallback |
| `sources` | where install, check and inverse are documented: a commit, or a client version with the time its help was read | the candidate's docs, or the route tool's where the candidate documents none |
| `dials` | the install plan's service slots the candidate dials (for example `gpt-gateway`) | none of its runs starts before stage S proves that slot's listener |
| `models` | the record of each selection: the inventory slug, the selected model id it maps to, and where it is selected (argv flag, config key or SDK option) | required, empty when none; a record, never a gate |
| `invoke` | kind (`skill`, `plugin`, `mcp-server`, `cli`, `sdk`, `service`) and names | names are tokens; zero calls is a wiring finding |
| `roles` | rows of the role-assignment matrix | never a fenced session |
| `startup_context_cost` | tokens or null, basis, method, receipt name | FINAL needs `measured`, integer tokens and a receipt |
| `label` | TRIAL or FINAL | FINAL only when every layer in `screens` is FINAL with a winner from this repository at this pin |

The row has no port or service fields. A service's port and isolation stay under the install plan's Decision 3.

## Routes

Help texts were captured on NativeStack2604 at 2026-10-16T02:39Z (private, by name: `route-help-20261016-v2.txt`).
Each route binds what it fetches. A version route names the exact version; a commit route names the commit; an
artifact route runs or links the verified download.

| Route | Install, check, inverse | Binds | Stage | Source |
| --- | --- | --- | --- | --- |
| `mise` | `mise use --global <backend:tool@version>`; `mise where <tool@version>`; `mise unuse --global ...` | version | C | mise 2026.10.3 help. A two-part version is a fuzzy prefix in mise, so the pin has three parts. `mise where` exits 1 for an unknown tool name (measured). The registry maps grype, syft, trivy, gitleaks, shellcheck, difftastic, actionlint, ast-grep and worktrunk to `aqua:` backends; prometheus and poutine have no entry and take `github:`. `mise lock` records versions, checksums and URLs. The Homebrew lines fold in here. |
| `uv-tool` | `uv tool install <pkg>==<version>`; `uv tool list`; `uv tool uninstall <pkg>` | version | C | uv 0.12.22 (`70fe1196`), `crates/uv-cli/src/lib.rs:5513`, `:5538` |
| `uv-add` | `uv add --project <env> <pkg>==<version>`; `uv tree --project <env> --package <pkg> --depth 0`; `uv remove --project <env> <pkg>` | version | C | the same, `:1142`, `:1165`, `:1250`; `docs/concepts/projects/dependencies.md:22`, `:92` |
| `npm-global` | `npm install --global <pkg>@<version>`; `npm ls --global <pkg>`; `npm uninstall --global <pkg>` | version | C | npm 11.19.0 help; `npm ls --global` exits 1 for a missing package (measured) |
| `claude-mcp` | `claude mcp add --scope local <name> -- npx -y <pkg>@<version>`; `claude mcp list`; `claude mcp remove --scope local <name>` | version | D | Claude Code 2.1.301 help: `mcp list` and `mcp get` health-check approved servers, so this check runs the server |
| `codex-mcp` | `codex mcp add <name> -- npx -y <pkg>@<version>`; `codex mcp list`; `codex mcp remove <name>` | version | D | codex-cli 0.162.1 help |
| `claude-plugin` | `git clone --no-checkout <marketplace repository> <dir>`; `git -C <dir> checkout --detach <commit>`; `claude plugin marketplace add --scope local <dir>`; `claude plugin install --scope local <plugin>@<marketplace>`; check `claude plugin list`; inverse `claude plugin uninstall --scope local ...` and `claude plugin marketplace remove <marketplace>` | commit | D | Claude Code 2.1.301 help: `marketplace add` takes "a URL, path, or GitHub repo" and documents no ref, so the pin is a local checkout at the commit. Per role project (Decision 9, `:789`) |
| `codex-plugin` | `codex plugin marketplace add <owner/repo> --ref <commit>`; `codex plugin add <plugin>@<marketplace>`; check `codex plugin list`; inverse `codex plugin remove ...` and `codex plugin marketplace remove <marketplace>` | commit | D | codex-cli 0.162.1 help: `--ref <REF>`, "Git ref to fetch for Git marketplace sources". `marketplace upgrade` refreshes snapshots, so a pinned source is never upgraded. Inside each lane's `CODEX_HOME` (Decision 9, `:789`) |
| `skills-cli` | `npx --yes skills@1.7.0 add <tree URL at the commit> -a <agent> -y`; `list`; `remove <skill> -y` | commit | D | the adopted Skills CLI (`adoption/skills/lifecycle.md:13-14`), vercel-labs/skills `7407f389` `README.md:87-92`, `:132` (project scope by default) |
| `systemd-user` | `systemctl --user link {artifact}` (the verified unit file, keeping its unit name), then `enable --now <unit>`; `systemctl --user show --property=ActiveState <unit>` for `ActiveState=active`; `disable --now <unit>` | artifact | S | systemd 259, `systemctl(1)`: `link` takes an absolute unit-file path, "the effect of this may be undone with disable", and `disable` "undoes any changes made by enable or link". The man page calls the LSB exit codes an imperfect map and points to unit states; `show` exits 0 with `ActiveState=inactive` for a missing unit (measured). After Decision 3's port and isolation proofs |
| `vendor-installer` | the verified download of `pin.artifact`, made executable and run directly, with the exact version (or `v` and the version) as an argument | version and artifact | C | the candidate's own installer at its sha256 |

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
  - a remote MCP server reached by URL has no version to pin, so it is not a row.

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
  - There is no bare-negation fallback: under `! <check>` a crash would read as a removal. A check with neither a
    documented absent exit nor a text cannot be a row's check. api-actions' review allowed a labelled fallback; the
    CC's read at `0d78f600` found it weak, and dropping it fails closed.
  - `compose` in [`tests/test_landscape_install_row_schema.py`](../../tests/test_landscape_install_row_schema.py) states
    this composition. Its tests run it under `/bin/sh`, with controls for the plain pipeline, a bare negation and an
    unbraced `cd`.
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

The owner's addendum-19 (2026-10-16, cited by name; it replaces addendum-18's routing) makes model currency
maintenance, not a gate.

- New installs select the inventory's current generation at install time.
- `models` records each selection:
  - the inventory slug (`id`, for example `gpt-6-1-sol`);
  - the selected model id that slug maps to (`model_id`, `gpt-6.1-sol`; `catalogs/foundation/model-currency.json:148`,
    `:151`);
  - where it is selected: an argv flag, a config key or an SDK option.
  - It is a record, never a gate.
- The active-selector check of the [2026-10-09 decision](2026-10-09-active-model-currency.md) reads selector keys and
  model-flag argv (`scripts/active_model_currency.py:33`, `:228-232`, `:489-503` at `5bab63233`), not `models`.
- A stale selection shows in the session-start currency notice (`adoption/hooks/claude/currency-due-notice.py`, which
  exits 0, wired at `adoption/new-wsl/client-config-map.json:170-177`). The notice prints the due file that the daily
  stack-currency timer writes.
- `model_record_problems` in the test checks only the record's join: the slug exists and maps to the recorded model
  id. Age and status stay with the notice.
- Installing that timer on the new WSL is a separate pull request after #1180.

## Generation and checks, in horizon

From the rows, horizon generates:

- the install script and the accept script;
- the role-assignment matrix (Decision 9, `:764-795`);
- the client-configuration map rows for the client-level routes.

Horizon pins this repository by commit (`pins.json`, per horizon's README), so it takes the schema and the rule tests
at one commit. Its checker refuses a row that:

- fails the schema;
- binds nothing its route fetches: a version route without an exact `pin.version`, a commit route without
  `pin.commit`, or an artifact route without the verified `{artifact}`. `unbound_pin` in
  [`tests/test_landscape_install_row_schema.py`](../../tests/test_landscape_install_row_schema.py) states this rule;
  a comparator, range or channel never binds.
- installs a repository that an installed stage C slot already installs. `stage_c_slots` in the same test states this
  rule, and it finds the plan's `claude-agent-sdk` slot.
- carries FINAL without its layers being FINAL with this winner at this pin (`final_label_problems`, below);
- records a model whose slug is not in the inventory or maps to another model id (`model_record_problems`; a record
  check, never a currency gate);
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

- **Label.** A row is TRIAL unless every layer it screens in is FINAL in `catalogs/landscape/final-stack.json`, with a
  winner from this repository whose run pin is this pin. `final_label_problems` states the rule.
  - Plan 6b makes FINAL rows defaults, so the rule fails closed.
  - Today it refuses every FINAL label: no layer is FINAL, and `enforce_final` refuses FINAL while admission is
    redesigned (`scripts/final_stack.py:835`, `:843` at `5bab63233`).
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
| none | `inverse`, `screens`, `sources`, `dials`, `models`, `invoke`, `roles`, `startup_context_cost`, `label` |

## Boundaries

- **Measured** on NativeStack2604, 2026-10-16:
  - the route help texts;
  - the `uv-add` check behaviour;
  - the shell facts behind the composition (dash 0.5.12), and the absent exits of `npm ls`, `mise where` (for an
    unknown tool name), `systemctl show` and a missing command;
  - the classification and candidate counts of the 131 PASS rows;
  - the schema tests (`python3 -m unittest tests.test_landscape_install_row_schema`, jsonschema 4.26.0 as in
    `.github/requirements-ci.txt:17`).
- **Not run:** no route ran on NativeHorizonNY for this record, and no row exists yet.
- **Pins drift.** The campaign plan's survey found superpowers at v7.0.0 against v6.4.1, and claude-code, codex,
  trailofbits and git unpinned in places. Every row here binds its exact version, commit or artifact; a new pin is a
  new row version through review.
- **Not covered:** a source build (for example `make build` in a source workspace) has no route. The OpenHands SDK's
  screen points to its modular packages once their exact versions are bound; those take `uv-add`.
- **Overturn.** No PASS screen row is an installer that covers these routes. The screens were classified by install
  path, not by candidate kind. So this record reuses each route's own tool and the repository's host receipts, and the
  protocol compares installers under `recovery-portability`. A screened installer that covers these routes, with
  receipts and inverses, supersedes this generation through a recorded supersession.
