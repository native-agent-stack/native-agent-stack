# One strict paper-URL normalizer for credential gates

Lane A's preflight exited before making a broker request because a valid
paper inventory URL ending in /v2 failed the credential-source string check.
The fixed refusal was alpaca_paper_only:not_paper_host. Capacity's merged
#1069 had already adopted strict version-path compatibility; adaptive-paper
credential gates still used the earlier bare-host comparison.

This correction supersedes the bare-host-only comparison in the 2026-09-25
credential-source addendum to 2026-09-22-broker-credential-handling.md. The
credential storage, source selection, masking and actual request-host pins
continue to apply. No owner-managed credential store is changed.

## Source mechanism

Primary source: alpacahq/alpaca-py v0.44.0,
cc4cb3b7ba50ae250e621983c2779047fb16bb28. common/enums.py:9 declares
BaseURL.TRADING_PAPER = https://paper-api.alpaca.markets. common/rest.py:36,64
stores API version v2 separately; :107-109 appends version and request path
to the base URL. The inventory's version suffix is a compatibility spelling,
not an alternate request destination. The existing SDK owns request routing.

#1069's capacity implementation at 3acbb95adc08b14d4ae16ec47d2afb1d28fd69ba
is the retained reference for strict components and raw-input guards. This
change moves that mechanism to credential_source.normalize_paper_base_url
and reuses it from capacity.env_base_url instead of keeping two parsers.

## Accepted inputs and refusals

The shared normalizer returns only the canonical paper host or None. It
requires HTTPS and the exact canonical authority paper-api.alpaca.markets,
with no explicit port. Paths are empty, /, /v2 or /v2/; /v2// is refused.
Userinfo, other authorities, every port (including 443), other paths,
query/fragment delimiters (including empty components), whitespace and raw
ASCII controls are refused. The CC's 2026-10-13 review ruling retains the
prior credential gate's no-port policy and makes capacity stricter than #1069,
whose port rule accepted 443. A versioned env value never becomes the request URL.

[RFC 3986 section 3.2.2](https://www.rfc-editor.org/rfc/rfc3986#section-3.2.2)
defines hosts as case-insensitive and recommends lowercase registered names.
This gate deliberately requires the exact lowercase canonical spelling rather
than accepting and case-folding equivalent names. Mixed-case, trailing-dot,
IDN/punycode and fullwidth host spellings are refused, as are uppercase /V2,
foreign-host userinfo and Unicode whitespace including U+00A0.

The credential-source reason gate retains absent-URL compatibility and its
fixed live-host/other-host refusal codes. Both env-file loaders (runner and
market_research), keychain-env and process-env selection use that same gate.
Mover reuses runner's file loader without paper_only=True and has no URL
gate at its paper/recover credential reads; adding that gate is a separate
follow-up, not coverage supplied by this PR. The
capacity external env reader uses the shared normalizer; internal
CapacityConfig.validate still requires the canonical PAPER_URL.
Capacity's new receipts include credential_source.py in source_provenance,
binding the newly shared parsing dependency. Historical receipts are retained.

## Remove the temporary unit override

The immediate old-pin operating record normalized the public base URL inside
the credential-runner child. With this PR's parser, that child override is
removed from all three replacement unit bindings. The credential runner
injects the inventory's unchanged /v2 value directly into keychain-env.

Replacement ExecStart forms (the operator binds every placeholder literally
in a NEW sealed record at a merged pin, preserving all existing stage ids,
config bytes, state-root, output, budgets and timeout properties):

```ini
ExecStart=<engine-python> -B <merged-code-root>/tools/credentials/credential_run.py <paper-inventory-id> -- <engine-python> -B <merged-code-root>/blueprints/us-equities/adaptive-paper/runner.py preflight --credentials keychain-env --config <config-path> --output <preflight-output> --trial <trial-id> --state-root <state-root>
ExecStart=<engine-python> -B <merged-code-root>/tools/credentials/credential_run.py <paper-inventory-id> -- <engine-python> -B <merged-code-root>/blueprints/us-equities/adaptive-paper/runner.py paper --credentials keychain-env --config <config-path> --output <paper-output> --trial <trial-id> --state-root <state-root>
ExecStart=<engine-python> -B <merged-code-root>/tools/credentials/credential_run.py <paper-inventory-id> -- <engine-python> -B <merged-code-root>/blueprints/us-equities/adaptive-paper/runner.py recover --credentials keychain-env --config <config-path> --output <recover-output> --trial <trial-id> --state-root <state-root>
```

These replacements contain no child env utility or base-URL override. Live
unit installation stays with the co-op after the new pin and exact operating
record are ready. Existing sealed records and running units are not edited
by this source PR; no paper command is run from its unmerged branch.

## Verification boundary

Fail-before tests on the base reproduce rejection of /v2 in the shared reason
gate, keychain-env and env-file source selection. Fake-file tests exercise
both real guarded loaders. Capacity's four accepted authority/path forms
and rejection controls continue to run through its actual config validation.
All fake files live in scratch outside Git; no real keys or broker calls.

Normalization idempotence covers all four allowed lower-case spellings;
the raw-input matrix checks all ASCII controls at multiple positions plus
malformed components. These are deterministic unittest matrices and finite
metamorphic checks, not a claim of exhaustive testing of arbitrary Unicode.
Review regressions for :443 fail at 3b6279f3 through the normalizer, reason
gate, both guarded file loaders and capacity. The additional case, userinfo
and Unicode refusal cases already pass there; their new tests pin existing
behavior rather than claim a reproduced acceptance defect.

Follow-ups: add the missing paper_only base-URL gate to mover paper and
recover credential reads (mover_runner.py:705,936 at 3b6279f3) in its own PR.
The separately recorded mover config-snapshot race remains a different PR.
Actual account readiness and the new unit/pin activation are
observed operator events, not predictions from these synthetic checks.
