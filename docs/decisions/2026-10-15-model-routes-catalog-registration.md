# Register the pending model-routes layer for a covering sweep

Status: catalog scope registration awaiting CC read. No winner, comparison,
terminal state, provider/model/account selection or route activation.

The CC's D1/F5 ruling (2026-10-14 23:50Z, reaffirmed 2026-10-15 00:29Z)
requires this exact scope:

> the routing layer that selects provider, model, account pool and effort for each agent request (gateway, fallback, rate-limit and credit handling) across the Codex lanes, Claude Code (subscription and API slots) and the runtime workers

At main base `a339425ca56ec3fb87dff0fa8ad5dffc83354168`, the foundation
catalog, taxonomy and derived final stack have no model-routes row. At #1058 head
`252babe4040e39173cc178317c67699371806df6`, the retained final-stack model-routes
entry is angle-only and unswept: no catalog verdict, winner, sweep or frozen
comparison. Its candidates are INSUFFICIENT or explicitly rejected under that
source record; their route/account and comparative-run gaps remain. This record
does not import their scores as a catalog choice or open a discovery stream.

Authority: PLAN-finalize-all-20261014.md SHA256
`5692d4bfb6f30dbee76d79c45733c3ac2236f995bb690e69edfe40caa851562c`, F5
and F3; ROWS-252babe4.md SHA256
`872e4b9b748b4c0967465ac08c90ead44e9f8f6c8d7455d2825e4c335c902c1a`;
the co-op's retained D1/F5 direction and CC pending-empty schema ruling.

## Registration and evidence boundary

Add the scope to catalogs/foundation/manifest.json and
catalogs/landscape/foundation.json as pending_lanes, with empty candidates,
winners and alternatives, unsealed pending lanes and named evidence gaps.
Research-state and quality coverage carry the same scope and pending action.
The former native-clients sentence denying a separate route layer is superseded
explicitly; historical client observations and selections remain dated evidence.
Derived matrix/final-stack outputs reflect the pending row without selecting it.

The existing landscape validator previously required a selected candidate and
alternative even for a pending row. A narrowly bounded registration path now
permits empty candidates only when the verdict is pending_lanes, winners and
alternatives are empty, both lanes are unsealed/pending and a named gap exists.
An empty recorded row or empty pending row without that gap still fails. Quality
coverage may carry empty challengers only for that same empty pending layer.
No broad non-GitHub candidate exception or source/receipt relaxation is added.

The regression fails before the change with "layer needs candidates", after
loading a complete fixture; it passes after the pending-empty path. The two
negative controls preserve the recorded/gap boundary. Native catalog validation
and generator checks are required before commit. Full validate.py's inherited
date-rollover currency incident is separately owned and remains disclosed; this
PR cannot fabricate new landscape checks for those models.

## Next named input and sources

The CC reads this PR; after it lands the existing landscape-sweep runs with
--slots 2 under the co-op's paced-stream allocation. This is readiness by named
inputs, not a calendar schedule. The sweep must retain its sources, per-role
dispositions and comparison/reopening contract. No model route becomes FINAL
from scope registration, angle-only evidence, installation or a harness smoke.

- Native reference at base: scripts/landscape.py:854-859 documents pending-lane
  empty verdict containers; build_landscape:1264-1318 supplies the catalog and
  candidate integrity path being extended, and :1556-1578 owns coverage joins.
- #1058 at `252babe4040e39173cc178317c67699371806df6`,
  catalogs/landscape/final-stack.json model-routes entry and
  catalogs/landscape/angles/foundation-model-routes.json: retained initial source
  review only. The angle record's absence on main is explicit, not a fabricated
  local source reference.
- docs/decisions/2026-10-11-layer-resolution-protocol.md: absent verdict/sweep
  is an explicit gap; dispatch only that gap and do not treat no_selection or
  still-undecided as terminal without a frozen comparison.
- python/cpython v3.13.16 Lib/unittest/case.py TestCase.assertRaises and
  assertEqual: the existing regression harness, matching installed Python.

Inventing placeholder selected candidates would falsely imply resolution.
Leaving the scope outside the taxonomy would keep the sweep/coverage join
undefined. The chosen registration exposes that gap through the existing schema.
Reopen this registration design only if a retained validator/sweep result shows
that its pending boundary cannot represent the named layer without false claims.
