# CI and release tracking (`ci-supply-chain`)

Client 2.1.295, checked 2026-10-09. Index: [slots.md](slots.md).

## release-tracking

**Status:** default. **Default:** Scheduled trackers: catalog-freshness.yml (daily read-only report plus a Monday proposal PR), practice-references-freshness.yml (weekly, report-only), the host's upstream surface watch (six sources: npm dist-tags, the Agent SDK settings types, the settings reference, env vars and mods, the Codex release, the CHANGELOG delta), plus Dependabot for action versions

- **Route:** 147 of 148 adopted repositories have a declared tracker (pandas has none); the weekly practice pass reads these reports
- **Alternatives, ranked:** 1. renovatebot/renovate, adopted only if the 2026-10-02 overturn test passes on current Renovate; 2. `autoUpdatesChannel: stable` for the client
- **Rejected:** updatecli/updatecli (failed the 2026-10-02 trial); lilydjwg/nvchecker; Dependabot for catalog and runtime pins; Hosted trackers
- **Evidence:** 2026-10-02 local trial (Renovate 44.132.2, updatecli v0.122.0, nvchecker 2.22) kept the stdlib trackers; L3 R7 tracker map
- **Notes:** Adjudicated: the incumbent stands; the refuter upheld it. Native client floor if the channel ever moves to stable: `minimumVersion` (any settings file); `requiredMinimumVersion` and `requiredMaximumVersion` are the managed startup gates. Dependabot was claude-code-action's only release tracker until its workflows were retired (2026-10-10). Integrity: the opt-in Monday propose job is model-free but holds contents and pull-requests write; schedules on a public repository pause after 60 days without activity. Trigger, installed on the workstation 2026-10-15 (command center, W1): stack-currency.timer runs upstream-surface-watch.service, then currency_due.py --network, daily; the SessionStart currency notice prints the due counts. practice_client_behind (the watched Claude Code release is newer than this skill's client_version) starts this skill's step 2: screen the CHANGELOG delta against the slot rows, adopt by PR with citations, bump client_version, and move each headless role to the release through a retained, sha256-checked copy after a function check of its exact invocation (owner direction 2026-10-14). Host note: gh is a mise shim here, so the installed units carry a PATH drop-in with ~/.local/share/mise/shims; the template's PATH changes only on a second host's evidence.
- **Overturn when:** Current Renovate passes the 2026-10-02 overturn test: seven daily runs on the same runtime rows plus deliberately outdated canaries, with fewer missed pins and no lost archived or renamed flags.
