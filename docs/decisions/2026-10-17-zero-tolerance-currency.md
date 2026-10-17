# Decision: zero tolerance for stale models, runtimes and repositories (2026-10-17)

**Status:** proposed for the command center's (CC) review, on the owner's directions, each dated by the day it was
given (paraphrased, not quoted). It changes no CI check, unit template, catalog row, model setting or host file.
The [CC's 2026-10-17 review rulings](https://github.com/native-agent-stack/native-agent-stack/pull/1237#issuecomment-6228929765) are cited below as "CC ruling N".
**Base:** `origin/main` at `90471d63f20918efa3a63ef949caffd8c012656c`; every `path:line` below is at that commit.
**Supersession:** only the parts listed under "Superseded". The earlier records stay unchanged as dated history; this
file amends them.

## The rule

1. **2026-10-17.** No stale model, runtime, repository or reference stays in use. A stale verdict starts replacement
   work at once; a notice does not answer it. The work is the newest best-evidenced successor through the layer's
   screen, a smoke test, a measured trial against the current pick, the switch, then removal of the old artifacts
   with the inverse recorded. A stale reference mirror or catalog record is refreshed. Replacements are never rationed
   on usage.
2. **2026-10-16.** No pick is stale, whether a default, a live pick or a trial arm. Each pick comes from a current
   cross-vendor landscape screen, and each release date in it from a tool read, never from memory.
3. **2026-10-15.** Enforcement does not break the workflow mechanically. No required CI check fails pull requests
   because the date rolled over; "The existing age failure" below applies this. Currency work runs in parallel lanes
   and never displaces a gate read.
4. **2026-10-16.** A release is never set aside for being new. It is screened, and quantization or on-demand loading
   is tried before anyone concludes that it cannot fit. An upstream's own cooldown window still applies (Kept).

## Superseded

- **A proposal or notice as the end state.** The first clause of [`docs/model-currency.md`](../model-currency.md)
  `:15` ("This automation proposes reviews") and `:119-120` (the CC "reviews and routes the private proposal through
  the normal owner and PR process"), and the due-file line of the
  [2026-09-30 notice record](2026-09-30-session-currency-notice.md) (`:151-152`, "exactly one read-only SessionStart
  line from that file") taken as the whole response. Now each proposal of a newer release or revision, each
  `refresh_landscape` and each `source_review` proposal (`scripts/freshness_propose.py:1172-1184,1195-1206`), each
  `pins_behind` or `stale_models` count (`scripts/currency_due.py:110,120-122`) and each unreviewed surface key
  (`:116,119`) is a dispatch trigger.
- **A successor's evidence.** The [2026-10-15 record](2026-10-15-model-currency-landscape-check.md) `:44` records
  Haiku 5.5 "for normal migration/quality-cost review and authorized application", and `:54-55` says a better
  compatible candidate "with accepted common-harness evidence reopens its role". Now the trial that produces that
  evidence is dispatched at once. The paired Haiku check of `:96-102` is that trial, and the unchanged 4.5 pin is
  migration staging (`:110-111`) while it runs.
- **A same-publisher search as a pick's landscape.** The bounded publisher searches of the 2026-10-15 record
  (`:21-25`) stay dated observations. A pick needs the cross-vendor screen.
- **Waiting on a release, for a selection in use.** The [2026-10-13 engine record](2026-10-13-engine-currency.md)
  compares three releases (`:37-43`). Only NautilusTrader is a selection in use (2.0.0rc5, "selected destination").
  Its wait ends: it moves to v2.0.0rc7, the newest release (Sources), through the trading lane's screen and the
  foundation re-pin (the CC's queue item Q-NT1). Lumibot 4.6.11 stays a reviewed candidate, and the alpaca-mcp-server
  re-pin trigger stays: "a named MCP role must first pass the execution layer's requirement screen" (`:150-151`).
  CC ruling 5.
- **Release age beyond the upstream's own window.** Release age no longer keeps an older pick once the upstream's own
  cooldown has passed, and no age buffer of ours extends that window, except the Dependabot control named under Kept.
  That ends the 7-day cooldown of the [2026-09-25 workstation refresh](2026-09-25-workstation-sota-refresh.md)
  `:237-238`, named again in the [2026-09-27 record](2026-09-27-model-currency.md) `:494-496`, wherever it is longer
  than the upstream's. The "cooldown" at `docs/model-currency.md:106` now means the upstream's own window. CC ruling 1
  sets this scope; the windows themselves stay (Kept).

## The existing age failure

The model-currency age check compares release and landscape-check dates with the current UTC date
(`scripts/validate.py:73-75,246-248`) inside the required check: shard 0 of the validate matrix
(`.github/workflows/validate.yml:20-21,173-178`), aggregated as `validate` (`:451-454`;
`docs/github-automation.md:34-36`). For a release more than 42 days old, a `landscape_check` that turns eight days
old therefore fails that check for any pull request until it is refreshed. On 2026-10-15 the "nine October 7
landscape exceptions became eight days old at UTC rollover", and the current-date `model_currency_problems(document)`
check "reproduces nine errors on the base inventory" (2026-10-15 record `:4,48-49`). The 2026-10-15 direction rules
out such a required check, so this record endorses
[PR #1201](https://github.com/native-agent-stack/native-agent-stack/pull/1201), which turns the age failure into a
notice (Sources). Until #1201 lands, the check stays as it is and the daily runs keep each `landscape_check` fresh.
Enforcement stays with the daily runs, the CC's review and immediate replacement work. CC ruling 6.

## Kept

- **The windows.** The 42-day release and seven-day landscape limits stay (`scripts/validate.py:69-70,163-166`;
  `catalogs/foundation/model-currency.json:4-8`), and #1201 keeps them. This record adds no new date-triggered
  required check.
- **Upstream cooldowns and supply-chain gates.** Each upstream's own documented cooldown stays, such as a tool's
  minimum release age (mise's `minimum_release_age`, Sources). So do the lanes' release, security and integrity gates
  (`docs/model-currency.md:105-106`). Inside such a window the pick is the newest release past it; a security fix that
  exists only in the newer release overrides the window.
- **Our Dependabot cooldown.** The 7-day Dependabot cooldown (`.github/dependabot.yml:40-43`, `default-days: 7`;
  `docs/github-automation.md:145-146`) is our own deliberate supply-chain control, longer than Dependabot's 3-day
  default (Sources). This record does not touch it. CC ruling 1.
- **Read-only detectors.** The collectors never apply a pin, download weights, change a model or publish a PR
  (`scripts/freshness_propose.py:22-26`; `adoption/templates/systemd/stack-currency.service:37`). Replacement is lane
  work, not a timer that switches. The [2026-10-07 record](2026-10-07-model-currency-enforcement.md)'s "An automatic
  model switch would cross the selection and host-application boundary without model qualification" (`:56-57`)
  stands, and the CC's refresh still "owns switches and host apply" (`:10`).
- **Date bases.** A date keeps its basis (`docs/model-currency.md:32-35`). Hub repository creation and last
  modification do not date a product release (`:100-101`).
- **No startup audit.** Dispatch happens in a lane, never at session start. The September 30 no-startup-audit
  contract stays authoritative ([2026-10-09 record](2026-10-09-active-model-currency.md) `:65-66`).
- **Each replacement's gates.** The layer's screen and multi-angle convergence
  ([2026-10-12 record](2026-10-12-converged-candidates-only.md)); the 2026-10-13 re-pin triggers (`:88-98`,
  `:128-135`, `:150-160`); and trading runtime selections, which stay with the trading lane
  (`blueprints/us-equities/AGENTS.md:9`). This record makes their qualification due at once and relaxes no
  trading-strategy or order-path gate. A candidate that fails its screen or cannot fit keeps its recorded reason and
  re-check trigger, as the 2026-09-27 holds do (`:67-84`).
- **The layer-resolution protocol** governs each dispatch ([2026-10-11 record](2026-10-11-layer-resolution-protocol.md)
  `:29-60`): read the verdict and the latest sweep, then dispatch only the delta. A newer release that a daily run
  finds triggers its layer's sweep at once, as a targeted sweep run, and a FINAL layer still reopens only through
  that sweep (`:62-63`, unchanged). CC ruling 3.

## Enforcement

1. **Daily runs.** `stack-currency.timer` (`adoption/templates/systemd/stack-currency.timer:14-17`) starts
   `stack-currency.service`, which pulls in and runs after `upstream-surface-watch.service`
   (`stack-currency.service:51-52,63-64`; `upstream-surface-watch.service:49-50`). Both run from the live clone
   (`stack-currency.service:7-9`; `upstream-surface-watch.service:16`).
2. **Fast-forward before each run.** The templates carry no fetch or fast-forward step. On the workstation each service
   has a user drop-in, `~/.config/systemd/user/<unit>.d/10-live-clone-ff.conf`, that runs `git fetch origin main` and
   then `git merge --ff-only origin/main`, each with systemd's `-` prefix. This is a host observation, read with
   `systemctl --user show` at 2026-10-17T02:19:57Z; no repository receipt holds it. `--ff-only` refuses a diverged
   clone and exits non-zero (git v2.53.0, below).
3. **The CC's review** fails a change that introduces, re-records, or touches and leaves stale a model, runtime or
   repository pin. A change that touches no pin is not held for it (CC ruling 4). A dated record that names an older
   pick as history is not a pick (`docs/active-model-currency.md:144-147`).
4. **Immediate dispatch.** The CC acts at once on each stale verdict, from a daily run, a landscape check or a review,
   in a parallel currency lane. A newer release that a daily run finds schedules its layer's targeted sweep at once:
   the cross-vendor screen that the daily runs cannot do, since they check only each row's own release line and its
   landscape check's age (`docs/model-currency.md:101-102,108-111`). A FINAL layer reopens only through that sweep
   (protocol `:62-63`), and the lane then dispatches only the delta. A comparison whose inputs exist and has not run
   is a defect (protocol `:92-94`); work starts when its inputs exist, never on a date (`AGENTS.md:8`).
5. **Dates from tool reads.** Each date names the field it came from, read at pick time: the Hub's `createdAt`
   (repository creation) or the selected revision's commit date, labelled as such; the Anthropic models API
   `created_at` (release time, an epoch value when unknown); PyPI's per-file `upload_time_iso_8601`; a GitHub
   release's `published_at` (its `created_at` is the commit date); npm's `time` entry for the version.

## Limits and follow-ups

- The templates do not carry the fast-forward, so a host that installs the units from them with the commands at
  `adoption/lifecycle.md:246-251` runs without it. Carrying the drop-in's two steps in both templates is a follow-up
  for the units' owner.
- Step order. In `stack-currency.service` the drop-in's steps run after the unit's own
  `freshness_propose.py --model-currency` pre-step, in the order `systemctl --user show` reported. Normally the watch
  has just fast-forwarded the same clone. When the paper-window check skips the watch, its later commands are skipped
  too (`upstream-surface-watch.service:26-32`), so that day's model proposals read the clone before the fast-forward.
  A failed fetch also leaves a run on the last fast-forwarded bytes, as the drop-in's own comment says.
- `docs/model-currency.md` keeps the superseded wording; a pointer to this record is a follow-up, left out here because
  open PRs #1201 and #840 edit that guide.
- This is governance text (`source_review`). No unit, catalog, setting or model changed, and no run measured the rule.

## Alternatives

- **A date-compared required check, new or kept.** Rule 3 rules it out ("The existing age failure").
- **Notices and proposals alone,** the superseded reading. A known stale pick stays in use until someone acts.
- **A timer that switches.** Rejected for the reason the 2026-10-07 record gives (`:56-57`, quoted under Kept).

## Overturn

- The owner rewords the direction.
- A recorded incident shows a stale pick that the daily runs, the CC's review and dispatch all missed. The enforcement
  then moves into a hook, workflow or check that no date rollover can fail.

## Sources

- **Superseded records at the base**, sha256 of their bytes (each equal to its `manifests/evidence.json` entry, except
  the 2026-09-30 record, which has none):
  `docs/model-currency.md` `76e7aa43d641b89ffeea1fbfbaceb803d800e5ea384e613863e5bd767c023f01`;
  `2026-09-25-workstation-sota-refresh.md` `40819d49b9fa55a49f86a37d3046ec4c140ae454eebbec471f119b48ec72fb6f`;
  `2026-09-27-model-currency.md` `4d34666cb1a18a5e8a86729b03d4caf46ea3d6164f908e92df65dd84babaa4f5`;
  `2026-09-30-session-currency-notice.md` `f3c94023025a177c81af73d3b13d4a8ed2b6a368eeba5218b143c44e24b2a775`;
  `2026-10-13-engine-currency.md` `b4d36592a4029145c54a6c18bf87f85b7e2f8b0387db737b04e3b5078e7c9293`;
  `2026-10-15-model-currency-landscape-check.md` `2351ea7da59e6fc93556b4048efeec2be0288fa01bdbe36139c870d9b5a2e6ec`.
- **Hub dates:** `huggingface/huggingface_hub` at `bd4a76030582d118e28dc9ad6c7a5911ea76176b`, the 2026-10-07
  record's pin:
  [`src/huggingface_hub/hf_api.py:799-801`](https://github.com/huggingface/huggingface_hub/blob/bd4a76030582d118e28dc9ad6c7a5911ea76176b/src/huggingface_hub/hf_api.py#L799-L801)
  (`created_at` is the repository's creation on the Hub),
  [`cli/models.py:223-237`](https://github.com/huggingface/huggingface_hub/blob/bd4a76030582d118e28dc9ad6c7a5911ea76176b/src/huggingface_hub/cli/models.py#L223-L237)
  (`hf models info`) and
  [`constants.py:60`](https://github.com/huggingface/huggingface_hub/blob/bd4a76030582d118e28dc9ad6c7a5911ea76176b/src/huggingface_hub/constants.py#L60)
  (default revision `main`). Re-read 2026-10-17.
- **Registry and vendor dates**, re-read 2026-10-17: the [Anthropic models list API](https://platform.claude.com/docs/en/api/models/list)
  (`created_at`), cited by the 2026-10-09 record; the [PyPI JSON API](https://docs.pypi.org/api/json/) and the
  [GitHub latest-release API](https://docs.github.com/en/rest/releases/releases#get-the-latest-release), cited by the
  2026-10-07 record; the [npm registry document](https://registry.npmjs.org/@anthropic-ai/claude-code) (`time`), cited
  by the 2026-09-27 record.
- **Minimum release age:** `jdx/mise` at `v2026.10.12` (commit `de922674adb7aa8927e0c6a425e252053dbeb03c`),
  the installed client:
  [`settings.toml:2090-2096`](https://github.com/jdx/mise/blob/de922674adb7aa8927e0c6a425e252053dbeb03c/settings.toml#L2090-L2096)
  (`minimum_release_age` holds back newly published versions to limit supply-chain risk). Re-read 2026-10-17.
- **Dependabot cooldown:** GitHub's
  [Dependabot options reference, `cooldown`](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference#cooldown-):
  Dependabot applies a 3-day default cooldown to version updates even when `cooldown` is not configured, and
  `default-days` sets another. Read 2026-10-17.
- **NautilusTrader:** the GitHub releases API for `nautechsystems/nautilus_trader`, read 2026-10-17. v2.0.0rc7 is the
  newest release, published 2026-10-15T21:07:45Z. Its annotated tag peels to commit
  `55c0e82053142bce3a5cba4de4221d3929c2d3bc`.
- **PR #1201** at head `459bf4fd4dd0f90f76eb5af2bbce7e3d82a72a50`:
  `scripts/validate.py:867-869` reads the age findings as notices
  (`enforce_age=False`, then `model_currency_due`), and `:1088` reports "Age findings are maintenance notices;
  publication validation passed." `:73-74,167-170` keep the 42-day and seven-day policy.
- **Fast-forward:** git v2.53.0, the installed client,
  [`Documentation/merge-options.adoc:79-81`](https://github.com/git/git/blob/v2.53.0/Documentation/merge-options.adoc#L79-L81).
- **systemd:** `systemd/systemd@v259.5`,
  [`man/systemd.service.xml:1443-1444`](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.service.xml#L1443-L1444)
  (the `-` prefix), cited by the 2026-10-07 record.
- Michael Nygard, [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions),
  2011-11-15: supersession rather than erasure, cited by the protocol record.
