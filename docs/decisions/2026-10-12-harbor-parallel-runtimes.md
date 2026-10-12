# Decision: Harbor as the container harness for parallel runtime work (2026-10-12)

**Status:** Proposed, recorded 2026-10-12T19:03:15Z on base `2f59d744`, in a draft pull request.
The CC's 2026-10-12 rulings on the environment shim, telemetry and route b are recorded
under "Decision". Not yet reviewed and not FINAL. The measured receipt is
[harbor-smoke-20261012.json](../../evidence/receipts/harbor-smoke-20261012.json); it is
registered in `manifests/evidence.json` and covers the new `harbor` component in
`manifests/stack.json` (see "Registration").

## Context

[2026-10-09-harbor-0240-profile.md](2026-10-09-harbor-0240-profile.md) selected Harbor
0.24.0 as an optional, unprovisioned source recommendation and expressly did not install
it or qualify its runtime. The 2026-09-20 architecture-wave record
(`catalogs/convergence-practice/architecture-wave/harbor-framework__harbor.json`) carries
disposition `defer-install`. This record is the next step: Harbor's own install path and
Harbor's own example task, run on this host, with no wrapper or adapter of ours.

Layer resolution ([protocol](2026-10-11-layer-resolution-protocol.md)): no research
dispatch or comparison was started and no survivor set was re-adjudicated. This record is
input to the owning layer's run pin and E2E condition; it claims no layer is FINAL. The
upstream's own test command (`uv sync --all-packages --all-extras --locked && uv run pytest
...`, profile acceptance) was **not** run: it was outside the assigned scope and stays UNRUN as in
the 2026-10-09 profile (the v0.24.0 source is obtainable from the tag or the sdist; the
mirror is a shallow clone at a later commit).

## Pin correction

The CC's delta check of 2026-10-12 names `v0.24.0` at `dc933be7`. They are different commits.

| Fact | Value | Source |
|---|---|---|
| Mirror head (read for source) | `dc933be707feafbb9efcdf092cb8a0e391332617`, 2026-10-10T21:40:12-07:00, shallow, no tags | `git rev-parse`, `rev-parse --is-shallow-repository` in the mirror |
| Release `v0.24.0` | annotated tag object `bf8996ef6d97d014924dc1a5e4acc7e9b19b27a1`, peeled commit `b53b8134e1241686dca7759af188f987ecc48e8b`, published 2026-10-05T05:04:52Z, latest release | `gh api repos/harbor-framework/harbor/{releases/latest,git/ref/tags/v0.24.0,commits/v0.24.0}` |
| Mirror head vs release | `status=ahead ahead_by=31 behind_by=0`, merge base `b53b8134` | `gh api .../compare/v0.24.0...dc933be7` |
| Version string at mirror head | `0.24.0` (`pyproject.toml:3`), so `harbor --version` cannot tell the two apart | mirror |
| PyPI | latest stable `0.24.0`; daily nightly builds `0.24.1.dev...` (newest `0.24.1.dev202610120805`) | `https://pypi.org/pypi/harbor/json`; nightly install form in `docs-mintlify/getting-started/installation.mdx` |
| Licence | Apache-2.0 | `pyproject.toml:6`, `LICENSE` |
| Python | `>=3.12` | `pyproject.toml` |

Installed artifact: the `v0.24.0` wheel. Source cited below: the installed wheel's files
(path under `harbor/`), which equal the mirror head for every cited file except the five
below. Where a cited line number differs, both are given.

| File | Wheel (v0.24.0) vs mirror head |
|---|---|
| `agents/installed/base.py` | +48 lines at head (`_env_sources` 676-681 in wheel, 724-729 at head) |
| `agents/installed/codex.py` | +53/-16 at head (route anchors move; both numbers given) |
| `agents/installed/mini_swe_agent.py` | line 51 only, `or ""`; no route effect |
| `environments/docker/docker.py` | +5 at head (adds `DOCKER_CONFIG` handling, 646-647); `start` 1005 vs 1010 |
| `cli/jobs.py` | +4 lines at head, after the cited line 2260; no cited line moves |

## Install receipt

Command, exactly as run (the profile's `uv tool install harbor==0.24.0` plus uv scope
flags; the documented route is `uv tool install harbor`, `README.md:22`,
`docs-mintlify/getting-started/installation.mdx`):

```text
uv tool install --no-build --python <mise python 3.13.16> harbor==0.24.0
  with UV_TOOL_DIR=/var/tmp/cc-harbor-tmp/uv-tools  UV_TOOL_BIN_DIR=/var/tmp/cc-harbor-tmp/bin
       UV_CACHE_DIR=/var/tmp/cc-harbor-tmp/uv-cache UV_PYTHON_INSTALL_DIR=/var/tmp/cc-harbor-tmp/uv-python
       UV_PYTHON_DOWNLOADS=never UV_NO_CONFIG=1 HOME=/var/tmp/cc-harbor-tmp/home TMPDIR=/var/tmp/cc-harbor-tmp/tmp
```

- Exit code 0, 2026-10-12T17:06:35Z to 17:06:37Z, uv 0.12.22, Python 3.13.16, 91
  distributions resolved, executables `harbor`, `hb`, `hr`.
- `harbor --version` prints `0.24.0`, exit 0.
- The v0.24.0 wheel re-downloaded from the immutable PyPI URL has SHA256
  `23b7ba616a3aae4eff561ced5e2c51c7186f2981e53a770dea9c689d3969877c`, 2,331,740 bytes:
  both equal PyPI's published values and the 2026-10-09 receipt. Installed `RECORD`: 488
  files ok, 0 bad, 0 missing. Installed `harbor/` tree equals the extracted wheel (479
  files identical).
- Resolved set: freeze SHA256 `51a14f564eb8991e7d7f3331a7b19d2dc320290796e4cfc1997685a8d47a6a5d`;
  litellm 1.105.0, pydantic 2.14.1, typer 0.27.3, supabase 2.32.0, fastapi 0.143.0,
  httpx 0.28.1, requests 2.34.2, PyJWT 2.15.1. Harbor's own requirements are lower bounds
  (`pyproject.toml`), so a later install can resolve a different set; the freeze is the
  record.
- A user-scope Harbor 0.24.0 install already exists on this host (`uv tool`, `no-build`,
  tool receipt dated 2026-10-08T02:22:45Z, entry points in `<HOME>/.local/bin`). It was
  neither used nor modified (snapshots unchanged).

Harbor 0.24.0 hard-codes `~/.cache/harbor` (`constants.py:4`, `skills.py:39`) and takes
the user config directory from platformdirs (`telemetry.py:535-536`); Harbor has no setting
for either, and `XDG_*` moves only the platformdirs paths, not the hard-coded ones. Every
Harbor invocation here therefore ran with `HOME` redirected to the scratch tree,
`DOCKER_HOST` naming the rootless daemon socket (the redirected `HOME` hides the rootless
docker context), `TMPDIR` in scratch, `HARBOR_TELEMETRY=off` and an absolute `--jobs-dir`:

```text
env HOME=/var/tmp/cc-harbor-tmp/home TMPDIR=/var/tmp/cc-harbor-tmp/tmp HARBOR_TELEMETRY=off \
    DOCKER_HOST=unix:///run/user/1000/docker.sock \
  /var/tmp/cc-harbor-tmp/bin/harbor run -p <task dir> -a <agent> -m <model> -e docker \
    -o /var/tmp/cc-harbor-tmp/jobs --job-name <name> -n 1 -y
```

The run used a short environment shim with these exports (scratch, not committed; it sets
environment, changes to the scratch working directory and execs `harbor`; it contains no
Harbor logic). The CC accepted it on 2026-10-12 as a disclosed, scratch-only isolation
measure, and made `HARBOR_TELEMETRY=off` standing for every Harbor run; the disclosure is
kept in the receipt (`data.harbor_run_environment`).

## Route table (source read, no inference)

The eight named adapters are in `harbor/agents/installed/` (the extra `terminus-2` row is
under `harbor/agents/terminus_2/`); lines are v0.24.0 (installed wheel).
Model intake is `-m` into `AgentConfig.model_name`, in `provider/model` form for the
adapters below. Key and URL names only. "Measured" means the live smoke or the route-b probe
below; everything else is read from source and is an untested boundary. The route b column
says what each adapter's source accepts; it does not say the gateway is reachable from a
container, and the probe below measured that it is not.

| Adapter | Route a: Anthropic API, key from environment | Route b: OpenAI-compatible base URL (gateway `http://127.0.0.1:21128/v1`; source accepts it, container reachability measured as not open) |
|---|---|---|
| claude-code | **Yes, measured.** Spec `claude_code.py:124-128`: provider anthropic, keys `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN`, URL `ANTHROPIC_BASE_URL`; host env is a key source (`base.py:676-681`); forwarded at `claude_code.py:1809-1810`; model `1745-1758` | **No**, unless the gateway serves the Anthropic Messages wire: only `ANTHROPIC_BASE_URL` is accepted (`claude_code.py:127`, `1810`) |
| codex | **No.** `default_provider="openai"` (`codex.py:132`); model is `split("/")[-1]` into `codex exec --model` (`1668`); key written as `OPENAI_API_KEY` into the container auth file (`1718`) | **Yes (source).** `OPENAI_BASE_URL` / `OPENAI_API_BASE` become `openai_base_url` in the container `config.toml` (`1576-1581`, `1726-1728`; head: `1604-1609`, `1761-1763`). Opt-in upload of the host Codex auth file via `CODEX_FORCE_AUTH_JSON` / `CODEX_AUTH_JSON_PATH` (`1628-1656`; head `1656-1684`). Wire format is the CLI's |
| opencode | **Yes (source).** `passthrough=True` (`opencode.py:79`) forwards the provider's own key name (`model_connection.py:22-26`, `229-238`); needs `anthropic/<model>` (`622`) | **Yes (source)** for `openai/<model>`: URL goes to `provider.options.baseURL` (`548-552`) |
| pi | **Yes (source).** `passthrough=True` (`pi.py:98`); `--provider anthropic --model <id>` (`424`) | **Yes, only with `--ak model_api=...`**: custom provider `harbor-endpoint` with `baseUrl` (`212-250`; raises without `model_api`, `225`) |
| goose | **Yes (source).** Providers anthropic, databricks, google, openai, tetrate (`goose.py:746-753`); `ANTHROPIC_BASE_URL` remapped to `ANTHROPIC_HOST` (`38-41`, `93-104`) | **Yes, honoring unverified.** `OPENAI_BASE_URL` is forwarded unchanged (`89`, `model_connection.py:243-244`); only anthropic and google hosts are remapped (`38-41`) |
| mini-swe-agent | **Yes (source).** Spec `mini_swe_agent.py:508-512`: `MSWEA_API_KEY` first, then the provider's key by passthrough; error if none (`760`) | **Yes (source).** `OPENAI_BASE_URL`, `OPENAI_API_BASE` (`510`, `516-529`) |
| openhands-sdk | **Yes, under a renamed variable.** `LLM_API_KEY` is required (`openhands_sdk.py:221-222`), `LLM_MODEL = model_name` (`230`); a credential-runner entry must export `LLM_API_KEY` | **Yes (source).** `LLM_BASE_URL` (`224-226`; runner `openhands_sdk_runner.py:192`, `213`) |
| deerflow | **Yes (source).** `anthropic` maps to `langchain_anthropic:ChatAnthropic` with `ANTHROPIC_API_KEY` (`deerflow.py:130-133`, `260-262`); keys are forwarded from the host env by a fixed list (`38-57`, `642-644`) | **Only via the OpenRouter slug:** `-m openrouter/<model> --ak openrouter_base_url=<url>` with `OPENROUTER_API_KEY` (`76-79`, `253-259`). `OPENAI_BASE_URL` is not forwarded |
| terminus-2 (extra) | Host-side client: LiteLLM in the Harbor process (`terminus_2/terminus_2.py:397-401`) | **Yes (source), and the only registered route that avoids the container-to-host problem below:** `--ak api_base=<url>` (`terminus_2.py:93`, `268`, `401`; `llms/lite_llm.py:118`, `653`) |

**Route policy (CC ruling, 2026-10-12).** Gateway routes in the comparison use `terminus-2`
with `--ak api_base=`; container adapters use route a only until a measured route exists.
The Docker daemon and its rootlesskit flags are host configuration and are not changed for
this.

**Container image.** No adapter ships an image. Harbor builds the task's Dockerfile
(`environments/docker/docker-compose-build.yaml`: `build.context ${CONTEXT_DIR}`;
hello-world is `FROM ubuntu:24.04`, `environment/Dockerfile:1`), runs it as `main`, and
each adapter's `install()` installs its CLI inside at setup. Teardown is
`docker compose down --rmi local --volumes --remove-orphans` (`docker.py:1208`).

| Adapter | `install()` inside the container | Version default |
|---|---|---|
| claude-code | apt `curl bash nodejs npm procps`; downloads.claude.ai `bootstrap.sh` piped to bash (`claude_code.py:466-491`); skip if already installed (`451-472`) | latest (`477`) |
| codex | apt deps with ripgrep; nvm; `npm install -g @openai/codex` (`codex.py:417-457`) | latest (`426`) |
| opencode | apt deps; nvm; `npm i -g opencode-ai` (`opencode.py:130-151`) | latest (`137`) |
| pi | apt `curl`; nvm; `npm install -g --ignore-scripts <package>` (`pi.py:141-196`) | latest (`179`) |
| goose | apt `curl bzip2 libxcb libgomp`; GitHub release `download_cli.sh` piped to bash (`goose.py:129-176`) | `stable` (`133`) |
| mini-swe-agent | apt incl. build tools and git; astral uv installer; `uv python install`; `uv tool install mini-swe-agent --with litellm --with orjson --with fastapi` (`mini_swe_agent.py:637-672`) | latest (`642`) |
| openhands-sdk | apt `curl coreutils`; astral uv installer; `uv python install 3.12`; venv; `uv pip install openhands-sdk openhands-tools fastapi` (`openhands_sdk.py:131-178`) | latest (`153`) |
| deerflow | apt `git curl`; astral uv installer; `git clone --depth 1` of bytedance/deer-flow at a pinned commit; `uv pip install` of its harness (`deerflow.py:534-590`) | pinned `7a6c4a99...` (`33`) |

The reproducibility limit follows: seven of eight adapters install the latest CLI unless
`--ak version=<x>` is given (`harbor agent schema claude-code`: "Agent CLI version to
install. Omit for latest."). The smoke below ran Claude Code 2.1.296 because that was
latest.

### All registered adapters

`agents/factory.py:40-90` registers 45 adapters; `models/agent/name.py:4-51` has 47 names
(`terminus` and `terminus-1` are not registered). 18 declare a `MODEL_CONNECTION` spec
(provider, key names, URL names, passthrough); 27 have none and parse `-m` and read their
own environment (`agents/base.py:281-290`: no spec means an empty connection). Names only,
generated mechanically over the wheel (matrix retained privately, hash in the receipt).

| Adapter | File under `harbor/agents/` | Model connection spec (`MODEL_CONNECTION`) | Other credential/endpoint names read (+ count of other names) |
|---|---|---|---|
| oracle | oracle.py | none: custom env contract | - |
| nop | nop.py | none: custom env contract | - |
| acp | installed/acp.py | none: custom env contract | - |
| terminus-2 | terminus_2/ (6 files) | none: custom env contract | - |
| claude-code | installed/claude_code.py | provider anthropic; key ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN; base URL ANTHROPIC_BASE_URL; property overridden | ANTHROPIC_SMALL_FAST_MODEL_AWS_REGION, AWS_BEARER_TOKEN_BEDROCK, AWS_REGION, CLAUDE_CODE_MAX_OUTPUT_TOKENS, CLAUDE_CODE_OAUTH_TOKEN, CLAUDE_FORCE_OAUTH, MAX_THINKING_TOKENS (+5) |
| copilot-cli | installed/copilot_cli.py | none: custom env contract | COPILOT_GITHUB_TOKEN, GH_TOKEN, GITHUB_TOKEN |
| code-puppy | installed/code_puppy.py | key <expr>; passthrough | - |
| aider | installed/aider.py | passthrough; property overridden | - |
| cline-cli | installed/cline/ (3 files) | none: custom env contract | - |
| codex | installed/codex.py | provider openai | CODEX_AUTH_JSON_PATH, CODEX_FORCE_AUTH_JSON |
| cortex-code | installed/cortex_code.py | none: custom env contract | - |
| cursor-cli | installed/cursor_cli.py | none: custom env contract | CURSOR_API_KEY |
| gemini-cli | installed/gemini_cli.py | provider google; key GEMINI_API_KEY; base URL GOOGLE_GEMINI_BASE_URL; passthrough; property overridden | GEMINI_FORCE_OAUTH, GEMINI_OAUTH_CREDS_PATH |
| antigravity-cli | installed/antigravity_cli.py | none: custom env contract | AGY_ADC_AUTH, GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_GEMINI_BASE_URL |
| antigravity-sdk | installed/antigravity_sdk.py | none: custom env contract | GEMINI_API_KEY, GOOGLE_GEMINI_BASE_URL (+1) |
| rovodev-cli | installed/rovodev_cli.py | none: custom env contract | ROVODEV_USER_API_TOKEN (+2) |
| goose | installed/goose.py | passthrough; property overridden | GOOSE_MAX_TOKENS (+3) |
| grok-build | installed/grok_build.py | none: custom env contract | - (+1) |
| hermes | installed/hermes.py | none: custom env contract | OPENAI_BASE_URL, OPENROUTER_API_KEY |
| junie | installed/junie.py | none: custom env contract | JUNIE_API_KEY |
| kimi-code | installed/kimi_code.py | none: custom env contract | - |
| kimi-cli | installed/kimi_cli.py | none: custom env contract | - (+1) |
| langgraph | installed/langgraph.py | none: custom env contract | - (+1) |
| deerflow | installed/deerflow.py | none: custom env contract | fixed forward list at deerflow.py:38-57 |
| mini-swe-agent | installed/mini_swe_agent.py | key MSWEA_API_KEY; base URL OPENAI_BASE_URL, OPENAI_API_BASE; passthrough; property overridden | - |
| nemo-agent | installed/nemo_agent.py | none: custom env contract | - (+1) |
| swe-agent | installed/swe_agent.py | passthrough | OPENAI_API_KEY, OPENAI_BASE_URL (+1) |
| opencode | installed/opencode.py | passthrough; property overridden | - |
| mimo | installed/mimo.py | passthrough; property overridden | - |
| mcode | installed/mcode.py | passthrough | - |
| openclaw | installed/openclaw.py | none: custom env contract | - |
| openhands | installed/openhands.py | key LLM_API_KEY; base URL LLM_BASE_URL, HOSTED_VLLM_API_BASE, VLLM_API_BASE, OPENAI_API_BASE, AZURE_API_BASE; property overridden | LLM_BASE_URL (+14) |
| openhands-sdk | installed/openhands_sdk.py | none: custom env contract | LLM_API_KEY, LLM_BASE_URL (+1) |
| pi | installed/pi.py | passthrough | ANTHROPIC_OAUTH_TOKEN |
| qwen-coder | installed/qwen_code.py | provider openai; passthrough | OPENAI_API_KEY, OPENAI_BASE_URL (+1) |
| devin | installed/devin.py | none: custom env contract | DEVIN_API_KEY, DEVIN_API_SERVER_URL |
| trae-agent | installed/trae_agent.py | passthrough; property overridden | - |
| computer-1 | computer_1/ (10 files) | none: custom env contract | - |
| eve | installed/eve.py | none: custom env contract | - |
| fx | installed/fx.py | provider vercel_ai_gateway; key AI_GATEWAY_API_KEY, VERCEL_AI_GATEWAY_API_KEY | VERCEL_OIDC_TOKEN (+1) |
| fx-dev | installed/fx_dev.py | none: custom env contract | - (+2) |
| dspy-rlm | dspy_rlm.py | none: custom env contract | - |
| vibe | installed/vibe.py | none: custom env contract | OPENAI_BASE_URL, VIBE_API_BASE, VIBE_API_KEY_ENV (+3) |
| muse-code | installed/muse_code.py | provider meta; key META_API_KEY; base URL MUSE_CODE_BASE_URL; property overridden | - (+1) |
| strands | installed/strands.py | passthrough; property overridden | - |

"none" means no `MODEL_CONNECTION` spec; it does not mean the adapter makes no model call.
The name scan sees string-literal `_get_env` / `os.environ` / `Env` calls only; it misses
names read through a loop or a mapping (deerflow's forward list, the `PROVIDERS` map in
`model_connection.py:15-140`).

## Oracle dry run (zero spend)

Harbor's own `oracle` agent runs the task's reference solution through the same Docker
environment and verifier as the smoke, with no model call and no key.
`harbor run -p hello-world -a oracle ...`: exit 0, 2026-10-12T17:08:24Z to 17:09:01Z (37 s),
1 trial, 0 exceptions, reward 1.0; phases: environment setup 4.29 s, agent execution 0.36 s,
verifier 19.28 s (the verifier runs apt, the astral uv installer and pytest inside the
container, `tests/test.sh`).

## Smoke receipt

Harbor's smallest example (`examples/tasks/hello-world`: `FROM ubuntu:24.04`, "Create a
file called hello.txt with "Hello, world!" as the content.") with the `claude-code`
adapter, `-m anthropic/claude-haiku-5-5`, key injected per command:
`python3 -I tools/credentials/credential_run.py anthropic-api-4 -- <harbor command>` from
the primary checkout. Slot `anthropic-api-4` worked; no fallback slot was tried. The local
`--path` form was used so no task is fetched from the Harbor hub.

| Measure | Value |
|---|---|
| Exit code, wall | 0; 2026-10-12T17:09:58Z to 17:13:24Z, 206 s (Harbor "Total runtime 3m 24s") |
| Result | 1 trial, 0 exceptions, reward 1.0 (`hello-world__8NxiCZF`) |
| Trial phases | environment setup 3.55 s, **agent setup 171.34 s**, agent execution 3.91 s, verifier 5.71 s, trial 204.17 s |
| Agent in container | Claude Code 2.1.296, model `claude-haiku-5-5`, key source reported `ANTHROPIC_API_KEY` |
| Harbor tokens | input 32,704, cache 26,847, output 106 |
| Harbor cost | $0.001053495 (equals Claude's own `total_cost_usd`) |
| Claude result event | 2 turns, 2,931 ms (API 2,726 ms), `end_turn`, one `Write` call |

Token derivation, so 32,704 is not misread: Harbor `n_input_tokens` = `input_tokens` +
`cache_creation_input_tokens` + `cache_read_input_tokens` = 4 + 5,853 + 26,847; Harbor
`n_cache_tokens` is the cache-read part only. The job-level `result.json` `started_at` and
`finished_at` are naive local time (13:09:59 to 13:13:23); the trial-level fields and the
`date -u` run metadata are UTC.

## Route b probe (measured)

The CC ruled for one probe from a throwaway `ubuntu:24.04` container (already local, run
with `--pull=never`) and no change to the Docker daemon or its rootlesskit flags. The
container used the rootless daemon's default bridge network (container default gateway
`172.17.0.1`), which leaves through the same `tap0` as Harbor's compose networks.

Address used: the gvisor-tap-vsock gateway `10.0.2.1`. Why that is the host address the
network exposes, from the source at the installed version: rootlesskit v3.1.0 (tag object
`4fab82caf726318cef33bf82912546b8a529eaab`, commit `62d2101fbbe4f79bc845a337c4e868d27ff602c9`),
`pkg/network/gvisortapvsock/gvisortapvsock.go:106-124` computes the gateway as the network
base plus 1, and `142-148` configures the NAT from `10.0.2.1` to the host's `127.0.0.1`
only when `--disable-host-loopback` is absent. The installed rootlesskit is 3.1.0 and runs
with that flag (process list); the gateway service listens on `127.0.0.1:21128` only.

| TCP connect from the container (no data sent) | Result |
|---|---|
| `10.0.2.1:21128` (the gateway port) | **Not open: timed out after 5 s** (exit 124, 5,004 ms); silently dropped, no refusal received |
| `10.0.2.1:53` (control: the virtual gateway's own DNS) | Open in 7 ms |

The control shows the address and the probe method work, so the timeout is the missing NAT
and not a broken probe. "Refused" is not what was observed; the attempt was dropped.
Consequence: no measured route exists from a container to the gateway, and under the CC's
route policy container adapters use route a only. Not tested: other host addresses, compose
network variants, or any changed daemon configuration (host configuration, not ours to
change).

## Isolation check

Method: snapshots of modification times and sizes (never contents), a marker file with
`find -newer`, and the redirected HOME's own listing.

| Item | Before | After | Reading |
|---|---|---|---|
| `<HOME>/.claude/settings.json` | 2026-10-11T05:08:40Z, 20,489 B | same | unchanged |
| `<HOME>/.claude.json` | 17:09:49Z, 116,761 B | 17:13:18Z, 116,761 B | rewritten by this live session and its sibling agents; size identical |
| newest file under `<HOME>/.claude/projects` | 17:09:51Z (12,088 files) | 17:13:43Z (12,089 files) | session transcripts of this and sibling agents |
| real-HOME `.cache/harbor`, `.config/harbor`, `.docker`, `.local/share/uv/tools`, `.local/bin`, `.cache/uv` | | | all unchanged |
| primary checkout `git status` | `?? .agents/`, `?? blobs/` | same | unchanged |
| docker images | 24 | 24, same names | unchanged; no leftover Harbor image (`--rmi local`) |
| docker containers | 67 | 66 | none was named for Harbor, hello-world or `hb__` before or after; an external change |

The two moving `<HOME>/.claude*` values do not discriminate by themselves, so the
attribution rests on construction and on the redirected HOME: after the run it holds only
`.cache/harbor/notifications.json` (Harbor's first-run hint, `cli/notifications.py:21-45`,
`cli/jobs.py:2260`, written during the oracle run) and `.docker/buildx/**` (docker CLI
build state); it has no `.claude*`, `.codex*` or `.config` entry. In the container,
`CLAUDE_CONFIG_DIR` is pinned to the trial logs directory (`claude_code.py:1895`); the only
host-side `~/.claude` access in the adapter is `ClaudeCode.handoff` (`claude_code.py:202-226`),
which `harbor run` does not call. Writes under scratch since the smoke marker: the job
directory (20 files), the tool venv's bytecode caches, the redirected HOME entries above;
`tmp/` empty afterwards, no Harbor-named entry in `/tmp`, no leftover process. gitleaks over
the job directory: 0 findings. gitleaks over the receipt logs: 1 finding, a false positive
on the `job=` field of the run-metadata line (no key material).

## Open questions and blockers

1. **Route b is not open from inside an agent container as configured (measured).** The
   probe above timed out at `10.0.2.1:21128` while the control opened; the cause is the
   rootless daemon's `--disable-host-loopback` (rootlesskit v3.1.0 source, cited above).
   Harbor 0.24.0 ships no host-gateway handling (`host.docker.internal` appears only in a
   comment, `antigravity_base_url.py:24`); it offers `extra_docker_compose` for user compose
   overrides (`models/trial/config.py:219`) and `extra_allowed_hosts`, which is a network
   allowlist (`trial/network_policy.py:76`, `113`). Options, none applied: `terminus-2`
   with `--ak api_base=` (the model client runs in the Harbor process on the host; source
   read, no live check yet), or exposing the gateway on an address the container network
   reaches, which changes host configuration and is the CC's call.
2. Route b's live check also waits for Codex pool capacity, and the wire format (Responses
   versus chat completions) is a property of each CLI, not of Harbor.
3. Agent CLI versions are unpinned (table above). A run pin needs `--ak version=` for each
   adapter, and the wheel SHA256 plus the mirror head in the record.
4. Agent setup was 171 s of a 204 s trial on a bare image. For N parallel trials every trial
   reinstalls; Harbor can skip installation when the CLI is already in the image
   (`claude_code.py:451-472`) and tasks can name a prebuilt image (`task.toml`
   `docker_image`, `docker.py` prebuilt path). Neither was measured.
5. `openhands-sdk` reads `LLM_API_KEY`, not a provider-named variable; the credential runner
   can only inject an entry's declared variables, so it needs a new inventory entry.
6. Telemetry is on by default (`telemetry.py:40-45`, `479-480`; `docs-mintlify/telemetry/telemetry.mdx`;
   opt-out `HARBOR_TELEMETRY=off`). The user-scope install's config directory holds a 33-byte
   file created 2026-10-03T03:13:17Z, consistent with the install id that is written when the
   first event is captured (`telemetry.py:411-431`, `500-536`); its contents were not read.
   Every run in this lane set the opt-out, and the CC made it standing for every Harbor run.
7. Two Harbor 0.24.0 installs now exist (user scope, untouched; private scope here). The CC
   decides which is canonical and whether the user-scope one gets `HARBOR_TELEMETRY=off`.
8. Security surface to keep in mind under the key threat model: the container receives the
   API key in its environment and runs the agent with bypassed permissions and outbound
   network (`claude_code.py:98-102`, `1889-1890`); codex can upload the host auth file on
   opt-in (`codex.py:1628-1656`); deerflow forwards a fixed list of host keys
   (`deerflow.py:38-57`). Job directories stay private (0 gitleaks findings here).
9. The upstream acceptance command was not run (see Context).

## Registration

Registered through the repository's own helpers and generators, following the hot-file
protocol in [docs/lanes.md](../lanes.md); nothing in `manifests/evidence.json` was edited by
hand.

- **Receipt.** `evidence/receipts/harbor-smoke-20261012.json`: `receipts[]` through
  `freshness_propose.register_receipt` and `files[]` through `host_receipts.register_file`.
  Before registration `scripts/validate.py` failed with `evidence file is not hash-listed`
  (`scripts/validate.py:528`).
- **Component.** `manifests/stack.json`: new `harbor` component in profile `optional`
  (membership added; commands `harbor --version` and `harbor run --help`; evidence id the
  receipt), because the receipt's `component_ids` is `["harbor"]` and a receipt record
  needs a known component.
- **What a new component pulls in** (each failed a CI check until added): the recipe map
  (`adoption/manifest.json`, `harbor` mapped to `recipes/README.md`) and a `harbor` row in
  `recipes/README.md` (`build_ecosystem.py --check`: "recipe map must cover exactly the
  selected stack"); a freshness row in `catalogs/landscape/upstream-snapshot.json` built with
  the snapshot's own method (four `gh api` calls with output hashes, a `scoped_refreshes`
  entry, summary counts 71 components and 66 latest-release successes and +4 API commands),
  because `landscape.py` requires one row per selected component; a `harbor` row and the two
  counters (71 selected, 830 non-selected identities) in the lifecycle audit
  `blueprints/token-native-focus/saturation-audit.json`
  (`tests.test_stack_lifecycle`: every stack component needs an audit row); the regenerated
  `catalogs/us-equities/decision-index.json` (`scripts/catalog_decisions.py --write`) and
  `catalogs/landscape/final-stack.json` (`scripts/final_stack.py --write`). Inserting the
  component moved every `manifests/stack.json` line after it, so the architecture edition's
  one live line citation (the Nemotron revision, `pin_source` in
  `catalogs/foundation/new-wsl-architecture-20261001.json`) moves from line 2118 to 2141 (the
  cited revision is unchanged; `tests.test_architecture_pin_source` and
  `tests.test_ecosystem_manifest` fail without it), and the handbook is regenerated through
  its own builder (`scripts/build_new_wsl_handbook.py --write`) with the entries its rolling
  receipt `evidence/artifacts/new-wsl-handbook-20261001/receipt.json` keeps for each
  regeneration, as #854 did. `component_matrix.py`, `new_host_grand_list.py` and
  `build_ecosystem.py` wrote no tracked change (the explorer `docs/ecosystem/index.html` is
  gitignored). Older prose citations of `stack.json` lines in earlier decision records and
  evidence artifacts name older snapshots of that file and are left as recorded.
- **Landscape candidate: a deviation, for the CC to rule on.** `landscape.py:1326` requires
  every selected stack component to appear as a candidate in some layer, else "selected
  component lacks a current role explanation". Hindsight (#854) was already a candidate
  before it joined the stack; Harbor was not. This change adds one hand-written candidate,
  `Harbor` (disposition `conditional`, evidence kind `native_execution`, the receipt as its
  reference), to the `quality-evaluation` layer in `catalogs/landscape/foundation.json`,
  following the slot this repository already recorded for Harbor
  (`foundation/quality-evaluation/trajectory-analysis`,
  `evidence/artifacts/harbor-0240-currency-20261009/receipt.json`). It changes no verdict
  field: the local run of the verdict review gate
  (`python3 scripts/verdict_review_gate.py --root . --base 2f59d744`) reports 0 changed rows
  and 0 violations, and `tools/sota-convergence/build_verdicts.py --check` passes. The usual
  route (a sweep adds the candidate, then the stack follows) was not run; this record does
  not claim the layer was reopened.

`python3 scripts/validate.py` exits 0 on this change (71 components, 240 receipts, 11,801
hashed files; the base `2f59d744` has 70, 239 and 11,800). The sixteen steps of the
pull-request validation sequence in `.github/workflows/validate.yml` (shard 0), plus the
verdict review gate, pass locally.

## Decision (proposed)

1. Adopt Harbor 0.24.0 (`uv tool install --no-build harbor==0.24.0`, wheel SHA256 above) as
   the container harness for parallel runtime work, in one owned tool scope (open question 7).
2. Operating rules, each measured above: redirect `HOME`, `TMPDIR`, `DOCKER_HOST` and set
   `HARBOR_TELEMETRY=off` on every invocation; absolute `--jobs-dir`; local `--path` tasks;
   `-y` for unattended runs; key per command through the credential runner; an oracle dry
   run (no spend) before any live trial on a new task or image; `--ak version=` on every run
   that must be reproducible; record both the wheel SHA256 and the mirror head.
3. Route policy: gateway routes in the comparison use `terminus-2` with `--ak api_base=`;
   container adapters use route a only until a measured route exists. The Docker daemon and
   its rootlesskit flags stay unchanged.
4. Claim scope: install plus one claude-code trial of one trivial task on the Anthropic
   route, and one route-b probe. Route b for container adapters is measured not open;
   seven of the eight named adapters stay source-read until their live checks run.

CC rulings of 2026-10-12 folded in above: the environment shim is accepted as a disclosed,
scratch-only isolation measure (HOME, DOCKER_HOST and TMPDIR; no Harbor logic; never
committed; disclosure kept in the receipt); `HARBOR_TELEMETRY=off` is standing for every
Harbor run; route b follows the policy in item 3 and was measured with the single probe.

## Supersession

On this host, for the install step and one end-to-end run, this measured record supersedes
the 2026-09-20 `defer-install` disposition and the 2026-10-09 profile statement that the
entry is unprovisioned and unrun. It confirms the profile's pin (0.24.0 wheel, same SHA256)
and does not supersede the profile's remaining gaps (upstream acceptance command, destination
acceptance, provider benchmarks).

## Inverse

Revert this change's single commit: it removes this record, the receipt, the `files[]` and
`receipts[]` entries in `manifests/evidence.json`, the `harbor` component and its profile
membership in `manifests/stack.json`, and the regenerated derived files. Outside the
repository, the only effects are the private install and scratch tree: remove the install
with `UV_TOOL_DIR=/var/tmp/cc-harbor-tmp/uv-tools UV_TOOL_BIN_DIR=/var/tmp/cc-harbor-tmp/bin
uv tool uninstall harbor`, then delete `/var/tmp/cc-harbor-tmp` by literal path. The
user-scope Harbor install was never touched. The Docker daemon, rootlesskit and the gateway
were not changed; the probe left no container (`--rm`).

## Sources

- Mirror `harbor-framework/harbor` at `dc933be707feafbb9efcdf092cb8a0e391332617`
  (`README.md:22`, `pyproject.toml:3,6`, `docs-mintlify/getting-started/installation.mdx`,
  `docs-mintlify/telemetry/telemetry.mdx`, `docs-mintlify/agents/pre-integrated-agents.mdx`,
  `examples/tasks/hello-world/`).
- Installed wheel `harbor-0.24.0-py3-none-any.whl`, SHA256 `23b7ba61...`, from
  `https://pypi.org/pypi/harbor/0.24.0/json`; release `v0.24.0` at
  `https://github.com/harbor-framework/harbor/releases/tag/v0.24.0`.
- This repository: `docs/decisions/2026-10-09-harbor-0240-profile.md`,
  `evidence/artifacts/harbor-0240-currency-20261009/receipt.json`,
  `tools/credentials/credential_run.py`.
- `rootless-containers/rootlesskit` v3.1.0 (tag object `4fab82caf726318cef33bf82912546b8a529eaab`,
  commit `62d2101fbbe4f79bc845a337c4e868d27ff602c9`),
  `pkg/network/gvisortapvsock/gvisortapvsock.go:106-124,142-148`, read through the GitHub
  contents API at that tag.
- Receipt: `evidence/receipts/harbor-smoke-20261012.json`.
