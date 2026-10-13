# Plugin pins

`pins.json` is the record of the reviewed commit of every plugin that a profile template enables (CPA-V-11, stage 1). The decision record is
[`docs/decisions/2026-10-13-plugin-pins-stage-1.md`](../../docs/decisions/2026-10-13-plugin-pins-stage-1.md); the captures it rests on are in
[`evidence/artifacts/plugin-pins-20261013/`](../../evidence/artifacts/plugin-pins-20261013/).

| Field | Meaning |
| --- | --- |
| `id`, `marketplace` | the plugin as `name@marketplace` and the marketplace name that a template registers |
| `marketplace_source` | the source exactly as the template's `extraKnownMarketplaces` writes it (a marketplace source takes a `ref`, never a `sha`) |
| `pin` | `tag`: the template's `ref` resolves to `sha`; `exception`: the template cannot name the reviewed commit, and `exception` says why and what is checked instead; `builtin`: a built-in mod of the client |
| `sha` | the reviewed commit, a full 40-character lowercase SHA |

`tests/test_plugin_pins.py` holds the record to the templates and to the revision check of `adoption/bootstrap.md` step 4a. A template that enables a plugin with no entry here fails it.
