# search-first follows the selected ECC pin

The skill installer previously selected search-first at affaan-m/ECC c70874fae9eb0e5ad0365beb7e2955899fd1d30f while the stack selected dd6ee538aee0f548d4a6b520118f875431fd749e. The skill trees differ. This change aligns the skill manifest with the stack, refreshes the runtime-worker reuse_ref metadata, and recomputes the description/byte catalog budgets. Historical decisions and audit entries remain historical; no new vendor security-audit result is inferred.

| Upstream identity | search-first tree | SKILL.md SHA256 | Bytes | Description characters |
| --- | --- | --- | ---: | ---: |
| dd6ee538aee0f548d4a6b520118f875431fd749e | 89e0ce14188958a85fbfc7ae0bdc30a0dc9681e1 | d66d744228b9cf860acf35f8a90cbbe8195e61367860da9d3632f9fc65706733 | 8021 | 141 |
| c70874fae9eb0e5ad0365beb7e2955899fd1d30f | 3ac0daf42ee5c7d0cbe28c399f02ff057283b889 | 76835db48dd910061d2e4271b1151793d2fddbabeb2d2866eed068b3580c55d5 | 8210 | 328 |

Primary source: https://github.com/affaan-m/ECC at both commits, skills/search-first/SKILL.md:1-6 (description), :12-20 (trigger), and :77-133 (preflight/agent workflow). The body is otherwise unchanged between these two skill trees. Public copies are retained under sources/. Git tree identities, exact bytes and frontmatter metadata were derived from a fresh upstream bare clone using git rev-parse and git show, rather than trusting the manifest or another lane's summary.

iterative-retrieval is unchanged: its tree is 1f1e8d67cf41d72acf2315dc7e6edeac0fc231a6 and SKILL.md SHA256 b453b16d3e36174b8487c05ab807d0321a66c2d058812b2ae129d82824183725 (6786 bytes) at dd6ee538, 2b6e839771e53096d8451a213d40dc64ec8acac0, c70874fa and upstream head b92f181b3b748d1abbc2afd94af6aa7d8c8fca29. Its manifest entry and installed copy are not changed.

regression.json retains the one-failure-before/one-pass-after reference test and 66 passing bounded manifest/runtime-reuse/installer tests. The documented installer dry run reports search-first planned, rc0, without a host install.

trigger-check.json records two fresh native Claude Code 2.1.300 project-scope measurements at the exact selected source tree, resolved model claude-sonnet-5-5 and requested effort medium. The positive close-paraphrase retry task discovered and invoked Skill(search-first) once. The arithmetic control discovered it but invoked no tools. Both calls exited0. The positive tool-result base directory was verified as the independent project skill; its loaded body exactly matches the selected upstream body. No external searches, file edits or delegated agents were permitted. This N=1-per-case trigger measurement establishes loading in this fixture, not general reliability, quality parity or production use. It is not directly comparable with the historical different-model trigger measurement.

Host install is deferred until the PR lands. Then run the repository's supported command from the landed revision: python3 tools/adoption/install_skills.py --only search-first --json, followed by the --check-only variant. Preserve the actual install UTC timestamp and send the receipt. Do not infer the production transition from this probe or PR creation time. Do not overwrite local modifications with --force; preserve and report a native refusal.

Claude-side F2 accounting belongs to cc-native-practice in PR #1137; the Codex evidence PR is #1135 and is not moved by this change. After the re-pin lands and the host install completes, the Claude-side owner records the failed-pin window and re-includes only activations from the actual transition. Production activation window_start remains null in this pre-install receipt.

Validation and privacy boundaries: only public upstream copies and sanitized summaries are published. Private model transcripts, native session IDs and raw-output digests remain excluded. Native evidence registration and scripts/validate.py run before commit; normal commit/push gates and the body scan remain enabled.
