# Claude parent skill routing

The profile installs `.claude/skills/native-skill-routing/SKILL.md` as the personal skill `native-skill-routing`
through `tools/adoption/install_claude_profile.py --only skills`. It gives the
parent a direct security-audit invocation description and directs it to load
the installed target before Bash or repository search.
Vendor files and worker tool grants remain unchanged. A worker's `skills`
preload supplies guidance; it does not produce a native `Skill` invocation.

The single authored source is already at the native project discovery path
`.claude/skills/native-skill-routing`. A worktree of the published head
therefore reproduces AFTER routing without changing the host. Personal
installation through the profile is a separate CC-owned post-land step.
`trigger-cases-v4.json` is cc-native-practice's expanded 24-case BEFORE/AFTER
input: the seven original positives and seven near-miss negatives, three more
security-audit phrasings, one real repository-path request and six indirect
requests, with unique IDs. Comparison base remains 60004bb1.

The seven skills appear in the supplied native doctor baseline with zero
lifetime uses: zero observed calls, which is a reason to check wiring and does
not establish absence of demand. CC-owned native BEFORE runs then measured six
targets at 3/3 and security-audit initially at 1/3, later settled at 16/23 with
6/23 in turn one. The six are wired; their routes remain unchanged. Only the
security-audit invocation cue changes. `trigger-baseline.json` records the
names/counts of that BEFORE snapshot.

## Retained AFTER measurement

The AFTER measurement is complete. It is the same-checkout hermetic ablation of
[the decision record](../../../docs/decisions/2026-10-10-daily-skill-invoke-rate.md#primary-effect-size-same-checkout-hermetic-ablation):
128 sessions, 64 per arm, one checkout and one HEAD, with only the inline
`skillOverrides.native-skill-routing` setting changing, on Claude Code 2.1.296.
With the cue hidden against listed, security-audit in turn one was 13/20
against 20/20 (Fisher two-sided p=0.008) and invoked within three turns 17/20
against 20/20; the indirect security-best-practices request in turn one was
8/12 against 12/12; near-miss negatives fired 0/28 in both arms.

Its limits are the record's: synthetic explicit-task prompts, five phrasings,
one model and one client version; observed counts, not an invocation rate.
The earlier three-arm study had other HEAD subjects and is supporting evidence
only. The router stays; the result can be rejected or refined by later
observations.

## Optional re-run with the vendor harness

The ablation above is the retained measurement; the staged suite below is an
optional re-run of the same kind of prompts through the vendor's own harness.
The `evals/` cases use the upstream Claude Code plugin-eval format: a synthetic
`prompt.md`, `allowed_tools: [Skill]`, and a deterministic `tool_used` grader
matching the target name with an optional staging-plugin namespace. They test
target selection whether it is direct or routed. There is no model judge,
service access, workflow execution or file-edit grant in these cases.

Stage the router and the seven installed, manifest-hash-matching skill trees
without installing a plugin:

```sh
python3 tools/skill-usage/stage_routing_eval.py --out /tmp/native-routing-eval
```

The CC can then run the vendor harness with its selected full model ID:

```sh
claude plugin eval /tmp/native-routing-eval \
  --model <full-model-id> --runs 3 --ablation none --threshold 1 \
  --trust-plugin --no-scaffold --no-publish \
  --json /tmp/native-routing-eval-results.json
```

This is 21 model runs. The lane prepares the suite and never launches it.
Report the target Skill-call pass counts for each case. A staged result is a
native trigger smoke measurement for those prompts, not installed-profile
acceptance or a general invocation rate. The personal profile's post-install
native listing and subsequent daily counts remain separate receipts.

Sources: [Claude skills discovery and descriptions](https://code.claude.com/docs/en/skills#where-skills-live),
[visibility settings](https://code.claude.com/docs/en/skills#override-skill-visibility-from-settings)
and [native plugin evals](https://code.claude.com/docs/en/plugin-evals), read
2026-10-10. Installed Claude Code 2.1.296 supports the four visibility states
and native eval graders; [its immutable release history](https://github.com/anthropics/claude-code/blob/2301018b1f61073c501a8e7a4813ef48c239163b/CHANGELOG.md)
records `skillOverrides` at 2.1.129 and `plugin eval` at 2.1.269.
