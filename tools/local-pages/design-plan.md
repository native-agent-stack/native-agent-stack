# Local engineering pages: visual plan

The brief is an engineering reading desk: identify the readiness gate, inspect its evidence, find the open gap, and see the next sequenced milestone. The retained approved plan controls palette, source-only content, local navigation, and 320px layouts. This implementation owns presentation and local browser state; the source composer supplies every operational fact.

## Tokens

| Role | Light | Dark |
| --- | --- | --- |
| Canvas | `#f6f8fb` | `#101c2a` |
| Surface | `#ffffff` | `#17283b` |
| Ink | `#183047` | `#e8eef5` |
| Secondary text | `#51677b` | `#b6c6d7` |
| Link and focus | `#205c9b` | `#93c7ff` |
| Measured / pending | `#246d55` / `#996421` | `#86d4b4` / `#f4cc8f` |

Use Ubuntu Sans, Segoe UI, and system sans-serif fallbacks. The same family carries headings and reading text; bold weights distinguish document structure. Tabular numerals align actual dates and counts. Body lines stay near 70 characters. Source code identifiers use the system monospace stack only when the source content needs it.

## Structure

Shared chrome is a narrow blue edge, a plain title, local navigation, and a visibly labelled theme choice. Readiness spends the visual emphasis on a vertical gate rail; evidence uses a wider reading pane. Gaps are a register of ruled rows, with a search box and two labelled filters above the register. Roadmap milestones follow a single visible sequence with a date gutter, title, stated status, and evidence text. Everything is left aligned.

```text
Readiness                 Gap board                    Roadmap
local nav / theme         local nav / theme            local nav / theme
title + source timestamp  title + source timestamp     title + source timestamp
gate rail | evidence      search / group / severity    date | milestone + evidence
gate rail | source table  count                        date | milestone + evidence
gate rail | next boundary  row / source / measurement   date | milestone + evidence
```

At narrow widths the gate rail returns to source order, filters and milestone gutters stack, navigation wraps, and tables retain a labelled horizontal scrolling container. Text and status labels carry meaning independently of color. Controls have visible focus and at least 44px height. No decorative animation, gradients, external assets, font requests, or invented business content are needed.

## Review before implementation

The first plan would normally turn every metric and gap into a card. That would give heterogeneous evidence the same visual importance and waste the small mobile viewport. Use one compact count strip, ruled gap rows, and the gate rail instead. The roadmap has a connected sequence because dates and ordering are real content, rather than decorative numbered markers. Keep outlines only for interactive focus, group boundaries, and source tables. Rounded controls and restrained panel corners express their different functions.

## Sources and limits

- Installed frontend-design guidance: [Anthropic SKILL.md at `683bc88e56f3e09ba94f7055977f3d3aa499f202`](https://github.com/anthropics/skills/blob/683bc88e56f3e09ba94f7055977f3d3aa499f202/skills/frontend-design/SKILL.md), read in full for the two-pass plan, source-specific structure, and critique. Its verified tree `d79e2a5bb4df4a386c2adcdd9ab8709bba28c3f6` matches the installed manifest pin `33375500bcea98d610eb30ce10ac4e59b89c390d`.
- Approved brief: native state root's `research/fullspeed-20261008/g5-stars-gap/local-pages/local-pages-plan.md` (SHA-256 `dd7df012eb9b56c720a5a2c3db3d05adf708b093cc23619b0fa0163b7512dd32`) and retained resume checkpoints.
- Native markup inspected directly: native state root's `coordination/command-center/pages/north-star-readiness.html` (`.wrap`, `.gates/.gate`, `.tl/.row`, `.road/.col`, `.tablewrap`, and status pills). The source API is [`tools/north-star/build_readiness.py` at `af7a4fe65f724e480bf0c79f0795de40a181b37d`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/af7a4fe65f724e480bf0c79f0795de40a181b37d/tools/north-star/build_readiness.py); source builders remain authoritative for status.
- Browser behavior uses native DOM controls, `matchMedia`, `localStorage`, and `hidden`, with storage failure handled locally. Browser screenshots, keyboard/filter checks, and measured contrast are review gates owned by the parent lane; this plan does not claim them complete.
- Native reference behavior checked in current MDN sources on 2026-10-08: [`Window.localStorage`](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage) documents `SecurityError` for blocked persistence or invalid origins; [`Window.matchMedia`](https://developer.mozilla.org/en-US/docs/Web/API/Window/matchMedia) documents `matches` and `change` events; the [`hidden` attribute](https://developer.mozilla.org/en-US/docs/Web/HTML/Global_attributes/hidden) documents the CSS display override, so the stylesheet preserves `[hidden]` explicitly.

## Implementation critique

The current operator view uses the read-only `cc-now/1` source at native state
root's `coordination/command-center/pages/cc-now.json`. Its compact headline,
gate count, authored estimate and START-first gate strip precede three desktop
columns for next events, owner actions and workstation readings. Dates put
America/New_York before UTC. Each figure identifies a live sample or dated CC
fallback; the manifest below retains its own gate values and marks superseded
cards. The full input scope moves to a separate sources page. The home page
repeats the same gate strip and links the pages. One short evidence footnote
appears per page.

An actual first desktop measurement placed the summary's bottom at
1004.64px in a 1440×1000 viewport. Smaller checklist row padding and consistent
date sizing retained all actions and placed it at960.55px in both themes.
The browser also checked320px and390px document widths. These are measured
local layout results, separate from CC content approval. An optional pool
disclosure was simplified to plain text after the Vercel review, so the summary
adds no new disclosure state. The original source timestamps and authored
estimate remain visible even when the input merits a custodian correction.

The second pass found that the approved pending foreground `#996421` on the first pale amber fill computed to 4.47:1. Retain that foreground and lighten only the badge fill to `#fff6e8`, which computes to 4.67:1. All other reviewed normal text pairs compute above 4.5:1; the light control border computes to 3.39:1 against its white surface. These are calculations from the stylesheet tokens, not rendered browser measurements.

Long gap titles, milestone titles, source paths, and code identifiers can break at narrow widths instead of forcing page overflow. The system dark fallback is limited to screen media so a script-free preview still prints with the light palette. Gap filtering preserves control focus and uses a polite result-count announcement; an optional reset returns focus to search. No motion or card hover effects were added because they do not explain the evidence.

The CSS expects a native first readiness gate section inside `.readiness-content .wrap`, gap rows inside `#gap-register`, and milestone dates, titles, and states with the retained class names. Source order remains the mobile reading order. Actual desktop/mobile screenshots, keyboard navigation, filter combinations, and persistence/blocked-storage behavior remain parent-lane verification gates.

## Foundation and North-star pages

The Architecture generator also writes two catalog pages, `architecture-foundation.html`
and `architecture-north-star.html`. Their job is narrower than the stack overview: for
each layer, show whether it is finalized under the layer resolution protocol, which of
the four conditions is missing, and the repository files to proceed from. The audience
is the next session that revisits a layer.

**Tokens.** The palette above is unchanged. Met conditions use the measured token,
missing ones the pending token, each with a shape (filled square, dashed ring) and a
text label so no state is color alone. Computed states reuse the diagram glyphs: Final
is the filled square, Not terminal the dashed ring, Scheduled the filled circle and
Retired the dotted square. Each diagram keeps its single violet focus. Headings use the
Architecture page's display serif, reading text the shared sans, and monospace only
pins and paths.

**Layout.** Left aligned, in source order: title and lede, one ruled count strip, the
system diagram, the four-condition rail, the layer register, the drift flags, then the
manifest and sources. The North-star page adds the data-layer decisions and the pending
study after its diagram.

```text
title + lede (finalized n of N, commit)
count strip: states as figures | four condition meters
system diagram (topology or data flow) + text view
conditions by layer: layer | verdict | run pin | E2E | invoke | state   <- the bold element
register: per layer, winners x four conditions, missing, open gaps, overturn rule, files
drift flags (final_stack.py --check) | manifest link + sources with SHA-256
```

**Review before implementation.** The first draft gave every layer a card and led with
a large headline number. Cards would give 32 heterogeneous layers equal weight and hide
the one thing that differs between them, the condition pattern. The rail replaces both:
it is the gate rail this plan already uses for readiness, turned sideways, and it is the
only place the page spends emphasis. The register uses ruled rows like the gap board.
No uppercase eyebrows or middle-dot meta strings are added outside the diagrams, whose
lane and zone labels follow diagram-design's eyebrow role.

**Skills and checks.** frontend-design (the installed skill read for this plan, SKILL.md
SHA-256 `d91970639e9f5c37682ac7ab60094d35f1c7c1f38d731bd56396563aee10c1d3`) shaped the
plan and its review. diagram-design 2.6.73 (SKILL.md SHA-256
`9cb173e6d30a9aa4af646f4eba4431ddb03dbbed23c041eaefdc13b1bf445826`; references
type-deployment.md and type-data-flow.md) set the two figures: a zoned deployment at
faithful detail with run-pin chips, and a four-lane, five-step data flow with one focal
step, node and labelled handoff. Connectors are drawn only when an orthogonal segment
clears every other node (§6 rules 1 and 5); the text view lists every connection. The
dataviz skill bundled with Claude Code 2.1.300 set the count strip as stat figures and
meters, not a chart. Its palette validator (`scripts/validate_palette.py`) passes the
met and missing pair in light mode on the normal-vision floor (ΔE 15.8) and warns on
protan separation (7.1); in dark mode the pair falls to ΔE 13.8 normal and 5.4 protan.
The same run FAILs the validator's chroma floor in light mode: the approved light tokens
are muted (OKLCH chroma 0.082 for `--ok` #246d55 and 0.105 for `--warn` #996421), so the
met fill reads as a dark grey-green beside the other marks. The tokens stay unchanged.
Every mark therefore carries its shape and label. Changing the approved status tokens is
left to the critique pass.

### Critique pass

A second frontend-design pass reviewed both rendered pages against the brief and this
plan. It fixed the following:

- **Topology roles.** Nodes outside a foundation layer were labelled "no catalog layer",
  although final-stack.json's index records OmniRoute as a trading-catalog alternate.
  Running chips gave no sign that Grafana, Hindsight, DeerFlow and the OpenHands SDK are
  alternates. Each chip now carries its index role: solid for a winner of a layer in the
  page's catalog, dashed otherwise. The text view names the role and layer.
- **Unrecorded flow nodes.** L0 raw log and K1 ranking have no repository record, yet
  they looked like evidenced nodes. They are now dashed, with a legend entry. (The account
  C node cites the agent-lane calculator policy spec from fix round 1 on.)
- **Captions** mention only the marks a figure draws.
- **Node sublabels** that were unverified ("ranked symbols", "data catalog", "shared by
  lanes") now follow their cited sources.
- **Header.** Three statements of the same count and a 40-character commit in body text
  became one sentence, the four states in one row, and a 12-character commit.
- **Strip headings.** The strip no longer adds two headings to the page outline.
- **Condition definitions** were hover-only. They now sit as a visible key beside the
  rail, numbered as the protocol numbers them. The rail sizes to its content.
- **Register.** Layer-wide facts were repeated in every winner row (the invoke reason 21
  times on one page), and two columns were both named "Run pin". The invoke reason is now
  stated once per layer, and the winner table groups its columns under "Winner and pins"
  and "FINAL conditions", with fixed widths that keep all four conditions in view.
- **Commit.** A branch build cited its own head, which disappears after a squash merge. It
  now cites the merge base with main when every record it read is byte-identical there.

It left the following, with reasons:

- **Dark-mode met and missing pair.** It stays below the dataviz normal-vision floor
  because this plan's status tokens are shared by every local page; shape and label carry
  the state.
- **Diagram labels** keep diagram-design's uppercase eyebrow role for lanes and zones.
- **Drift flags** stay verbatim final_stack.py output.
- **Register length** follows from the brief's per-layer content.

## Overview page

`overview.html` answers one question per section, in a fixed order: where the layers
stand, which data feeds converged, which strategies, which workers run with what
receipt, which repositories win each layer and what closes it, what the page read,
Claude Code, and GitHub. The audience opens the desk and wants the state in one pass,
then follows a link to the Foundation or North-star page for detail.

**Tokens.** The palette above is unchanged; the overview adds no color. Pending blocks
use the pending token as a left rule, the dashed-ring glyph and the word "Pending",
so no state is color alone. Headings use the Architecture pages' display serif,
reading text the shared sans, monospace only pins, paths and record names.

**Layout.** Left aligned, source order, one section per screen height where the
content allows:

```text
title + lede
count strip: FINAL sentence | states as figures | sources present
section links (8)
1 layer stack: trading band above foundation band, one cell per layer   <- the bold element
2 feeds: statement | $0 signal table | baseline, lagging, gated | gaps | addendum results | pending block
3 strategies: statement | family claim | caveats, ablations, selector and sizing   | pending block
4 workers: worker | state | newest receipt
5 repositories: per catalog, shared state once | layer | winners at run pin | survivors | next action
6 evidence: repository records | private records by name | layer pages
7 Claude Code: pin, CHANGELOG delta, screen table     | pending block
8 GitHub: main CI, in review, landing queue
```

**Review before implementation.** The first plan gave each section a card and led
with a large FINAL number. Cards would make eight unlike answers look alike, and a
hero zero is a claim the protocol does not support. The plan instead uses ruled
sections like the layer pages, a sentence for the FINAL count, and spends emphasis
only on the layer stack. Section markers are not numbered on the page: the order
is fixed but the sections are not a sequence. Repository rows put the layer key in
the link title and shorten commit pins to 12 characters, which halved the table's
height in the first browser pass.

**Critique pass.** Sections 2 and 3 are sanitized projections of the convergence
records: selected passages only, and any sentence, cell or lead that cites a path,
digest or line, or names a declared drop term, is withheld. The plain statement
("No measured winner yet.", "No live result; replication next.") stands until the
named result record exists. The review against the brief then changed five things.
The feeds lede no longer repeats a status the generator owns, so it cannot go stale.
Captions that repeat the heading above their table are kept for screen readers only.
A state shared by every catalog layer of a group is said once above its table
instead of on 20 rows, which shortened the repositories section from 1958 to 1672
px at 1440 wide. The strategy caveats, ablations and sizing sit in one row under the
family claim. The pending main-CI block no longer names the record the section line
already names. Left as they are: the figure's capitalised monospace labels, which
the layer pages share, and the repositories and GitHub sections, which still exceed
one screen at 34 layers and nine reviews.

**Skills.** frontend-design (SKILL.md SHA-256
`d91970639e9f5c37682ac7ab60094d35f1c7c1f38d731bd56396563aee10c1d3`) shaped the plan
and the review above. diagram-design 2.6.73 (SKILL.md SHA-256
`9cb173e6d30a9aa4af646f4eba4431ddb03dbbed23c041eaefdc13b1bf445826`, reference
type-layers.md) set the figure: a layer stack of two full-width bands with index tags,
a direction label, one focal band (the trading layers) and a bottom legend; one cell
per layer, with equal cell widths across bands so the bands compare by length. The
caption names only the states the figure draws. The dataviz skill bundled with
Claude Code 2.1.300 set the strip as stat figures, not a chart; its validator again
reports the shared status pair at light ΔE 15.8 normal and 7.1 protan, dark 13.8 and
5.4, so each state carries its glyph and label as on the layer pages.
