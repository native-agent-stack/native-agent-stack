# Runtime follow-ups after #1033

Base: `703d588c5660d698a87b622efe0e3bd8c22f7e29`. These changes close the
deferred environment, preparation, executable, startup and gateway findings.
They do not qualify alias-read containment, replace an isolation-layer winner,
or establish provider/MCP readiness for the frozen W6 profiles.

## Gateway installation contract first

The landscape stager and Codex profile select 21128. The general service now
requires an explicit `@OMNIROUTE_PORT@` substitution: 21128 for the current
deployment, 20128 to reproduce historical units. The SDK example and current
installation instructions use the same selected port. Historical receipts and
historical build/traffic observations remain dated and unchanged.

Primary source: `diegosouzapw/OmniRoute@7f3cbb046b3706bf0bbc047b7eaa0cbada8d9e50:
bin/cli/commands/serve.mjs:86,180-182` documents `--port` and derives API/dashboard
ports from that selection. The vendor default remains 20128. This is a
prospective installation contract, not an executed host migration. It must
land before another host is installed from the general template.

The regression stages the real lane and compares its default endpoint with a
21128-rendered service; an explicit 21128 override is also checked. At the base
the regression fails (exit 1); the changed template passes (exit 0). The existing
50 gateway-unit checks pass with historical 20128 explicitly rendered.

## Validation boundary

Gateway staging/unit checks are local integration without inference. Native
provider acceptance and a live service restart are outside this PR. No private
W6 configuration, authentication state, session output or failed-log digest is
published here.
