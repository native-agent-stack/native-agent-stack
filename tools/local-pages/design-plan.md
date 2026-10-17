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
5 repositories: finalize-all waves | F1 and F2 status | per catalog, shared state once | layer | winners | survivors | next action
6 evidence: studies (arms by worker and model family, judges, result as stated) | repository records | private records | layer pages
7 Claude Code: run pin and prepared pin | CHANGELOG counts per version | best-practice slots   | pending blocks
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

## Atlas page

`atlas.html` is the harness atlas. Citation keys in this section: **FD** is the
installed frontend-design `SKILL.md` at the manifest pin
`33375500bcea98d610eb30ce10ac4e59b89c390d` (tree
`d79e2a5bb4df4a386c2adcdd9ab8709bba28c3f6`, SHA-256
`d91970639e9f5c37682ac7ab60094d35f1c7c1f38d731bd56396563aee10c1d3`, row
`adoption/skills/manifest.json:525`); **DP** is this file above this section.
The approved brief controls palette and layout (DP:3), and FD itself says a
brief's pinned direction wins (FD:45).

**Brief** (FD:11-13). Subject: the native agent harness, three model families
each in its vendor's client across the seven harness layers, with the catalog
verdict and the measured use. Audience: the owner opening the local desk, and
the next agent session. Primary job: in one pass, what each family runs at each
layer, what is settled and what is not, and what measurement shows the lanes
used. Every fact names its record.

**Tokens.** The palette above is unchanged and the atlas adds no color: Canvas
`#f6f8fb`/`#101c2a`, Surface `#ffffff`/`#17283b`, Ink `#183047`/`#e8eef5`,
Secondary `#51677b`/`#b6c6d7`, Link and focus `#205c9b`/`#93c7ff`, and the
reserved status pair Measured `#246d55`/`#86d4b4` and Pending
`#996421`/`#f4cc8f` (FD:48; DP:7-14). `assets/atlas.css` uses `var(--…)`
only. Type: the shared sans for reading text and section headings, the
overview's display serif for the title and the matrix row headers only, and
monospace (`<code>`) for the identifiers and commands the page quotes: pins,
paths and record names, catalog layer ids, slot keys, model ids and declared
effort values, route text, MCP server names, agent roles, monitoring commands,
the ccusage command and change kinds (FD:19; DP:16, DP:175-176).
Unlike the overview, whose section headings take the serif (DP:175-176), the
atlas keeps them in the sans, so the row headers stay the body's one serif
element (rule 11). Defining the serif token would otherwise reach every section
heading through the shared `.mf-view > h2` rule
(`assets/architecture-manifest.css:31`), so `atlas.css` sets them back.

**Layout.** Left aligned, source order; the order is fixed but is not a
sequence, so no section is numbered (FD:30):

```text
title "Harness atlas" + lede (one sentence)
count strip: FINAL sentence | states (glyph + label + figure) | measured days | last measured day | changes since previous row
section links (9)
atlas-terms      four definitions as a visible key; the stack terms generated from catalog requirements and slots
atlas-layers     layer | Claude (Claude Code) | GPT (Codex) | Muse (Muse Code)      <- the one bold element
                 each cell: a cited mechanism, the Claude practice slots, or "No recorded mechanism";
                 a ruled foot row per layer: catalog state glyph + label (status), winners at 12-character pins
atlas-stacks     per stack: layer | requirement | state | winners | survivors; slots; MCP servers the lanes called, with their role
atlas-measured   closed days per lane | today so far | daily rows (14, older in <details>) | coverage and unknowns
atlas-routing    role | family and client | declared model | declared effort; then observed models per lane
atlas-monitoring surface | what it shows | how to open it | record (+ one-line port note)
atlas-rules      rule | recorded in | mechanism | state (Recorded, or Pending with its trigger)
atlas-changes    the ledger: rows newest first | what changed; chain check
atlas-evidence   repository records | private records by name | skills at their pins
```

**Review before implementation.** The default first draft would be a card per
family and per layer (FD:42), led by a large "0 / 32 FINAL" hero (FD:17). It
would give 21 unlike cells equal weight and put a number the protocol frames as
a gap in the hero. The revision: one ruled matrix as the only bold element, the
FINAL count as a sentence (DP:196-198), the stacks and measured use as ruled
tables, and no section numbers (DP:199-200). The measured-use draft would be
charts; with no pinned dataviz skill, and since tables carry the exact values
the next session needs, the measured section is tables.

**Rules, each cited.**

| # | Rule | Applied as | Citation |
| --- | --- | --- | --- |
| 1 | Plan in two passes: a compact token plan, a review against the brief, then build | This section's Tokens, Layout and Review come before the code; the Critique pass after it | FD:47-53 |
| 2 | Ground the design in the subject's real content | Every word comes from the records; the hero is the layer-by-family question | FD:11-13 |
| 3 | No default hero | The FINAL count is the strip's sentence | FD:17; DP:196-198 |
| 4 | A 4-6 value palette, and the brief's tokens win | The shared tokens only; no color literal in `atlas.css` | FD:48, FD:45; DP:7-14 |
| 5 | One or two clearly distinct families | Shared sans and the display serif, scoped to `body[data-page="atlas"]` | FD:19; DP:16 |
| 6 | A clear type scale; lines under 80 characters | Body text at 72ch; notes and citations at 80ch | FD:21-23; DP:16 |
| 7 | Tabular numerals for counts and dates | Every numeric table column | DP:16; `assets/site.css:128` |
| 8 | No one-word accent, all-caps labels or unnecessary labels | Sentence-case headings, no eyebrow, no `text-transform` | FD:25-28; FD:43 |
| 9 | Structure is information; number only real sequences | Ruled sections and rows; no 01/02 markers | FD:30; DP:199-200 |
| 10 | Avoid the SaaS-card kit | No cards; ruled rows and one matrix table | FD:42; DP:35, DP:102-106 |
| 11 | Spend boldness in one place | The matrix's heavier top rule in the ink token and serif row headers | FD:59; DP:185 |
| 12 | Motion | None; `prefers-reduced-motion` is already honored | FD:32; DP:31 |
| 13 | Quality floor | 320px layouts, a visible 3px focus, 44px controls (each disclosure summary too, sized as `assets/site.css:322` sizes `.pool-note summary`), light print | FD:59; DP:31, DP:68 |
| 14 | State never by color alone | Glyph plus label; pending blocks add the left rule and the word | DP:80-84, DP:173-175 |
| 15 | Watch selector specificity | Rules sit under `body[data-page="atlas"]` or `.atlas-*`; a shared rule is restyled only inside that scope and at a higher specificity, never by stylesheet order (for example, `.atlas-matrix.ov-table table` outranks `.ov-table table`). `CascadeTests` in `tests/test_local_pages_atlas_view.py` compares the winning atlas declaration of each property with the same-named property of each shared declaration on the same element, at the same importance; the helper expands only margin, padding, border and gap to longhands, so a pair such as `background` and `background-color` is not compared | FD:55 |
| 16 | Copy: plain verbs, active voice; failures say what is missing and how to fix it | Pending blocks name their trigger; the ledger refusal says the file is kept for inspection | FD:61-71 |
| 17 | Long identifiers wrap; tables scroll in a labelled region | `.table-wrap` with `role="region"`, `tabindex="0"` and `aria-label` | DP:31; `assets/site.css:268` |
| 18 | Captions that repeat a visible heading are for screen readers | `_table(..., hide_caption=True)` | DP:210-211 |
| 19 | Layer-wide facts once, not per row | A family's statement once per cell, catalog state once per layer, an unmeasured lane's reason once per row | DP:149-152, DP:211-213 |
| 20 | Both themes and the shared theme picker | The shared `document()` shell and `site.js`; no page script | DP:42-43; `build_pages.py:170-171` |

No figure or chart is drawn, so the design-plan rules that rest on
diagram-design or dataviz (DP:112-126, DP:221-229) are not cited. The state
glyphs are the shared ones (`overview_view.glyph`, which draws
`architecture_diagrams.STATE_GLYPH`, drawn under diagram-design); whether to
keep them or use text-only state labels is the CC's call.

**Critique pass.** A browser pass with the installed chrome-devtools MCP read
the built page at 320, 390 and 1440 px in light and dark. No width scrolls the
page horizontally; every table scrolls inside its labelled region. Tab order
runs skip link, brand, the eleven pages, the theme picker, the nine section
links, then each table region in order, each with the 3px focus ring. The pass
changed these things:

- **Matrix foot rows.** The shared rule that sets `small` to a block in table
  cells split each winner without a run pin over three lines; the foot rows now
  read as one sentence, with the status in parentheses after the state.
- **Family headers.** The route paths read as "through" and "inside" their
  record.
- **Measured tables.** A lane with no collector reads its reason once across the
  row instead of in twelve cells; zero counts drop their "per 100" note; the
  window states its inclusive last day; the closed-day table fits 1440px.
- **Section verdicts** sit in the overview's `ov-statement` wrapper, which keeps
  them in the ink color, and the list labels are `h4` headings.
- **Monitoring commands** wrap at spaces only, never inside a flag.
- **Narrow widths** drop the strip's separator rule, which started a wrapped
  line, and narrow the matrix's layer column.
- **Print.** The page's minimum table widths outranked the shared print rule
  (`assets/site.css:465-472`), so they are released for print, and the two
  13-column measured tables print with tight cells. The MCP exposes no print
  emulation, so print was checked by applying the print rules at an A4 width
  (794px): every table then fits.

Remove one accessory (FD:59): the routing table's separate Client column became
"Family and client"; the sixteen agent definitions in the evidence list fold
into one disclosure; the repeated "Not measured" cells became one spanning cell.
No new color pair is introduced, so the stylesheet contrast calculations above
(DP:66) stand. The shared navigation now wraps to a second line at 1440px with
eleven pages; that is shared chrome and is left to a later change.

**Review fold.** A review of this build found three claims false at its head;
each now has a cascade test over the built page (`CascadeTests` in
`tests/test_local_pages_atlas_view.py`, through `tests/local_pages_css_cascade.py`,
which parses and matches with tinycss2 and cssselect2; see "CSS cascade helper").
The disclosure summaries were under the 44px floor of rule 13. Atlas rules
overrode four shared rules by stylesheet order alone, against rule 15: the
matrix's heavier top rule over `.table-wrap`, the table type sizes over
`.ov-table table`, the print cells over `.ov-table td, .ov-table th`, and the
term margins over `.lp-defs dd`. Defining the serif token set all nine section
headings in the serif, against the Type line and rule 11. The installed chrome-devtools MCP measured the same synthetic page
built before and after the fold, at 1440px: the matrix summaries went from 30.47
to 44px and the full-width summaries from 35.19 to 44.78px; the section headings
moved to the sans while the title and the seven row headers kept the serif. On
the real page the same heights held at 1440 and 320px in light and at 1440px in
dark, with no horizontal page scroll; the overrides render as before and now win
by specificity.

**Skills.** frontend-design (FD) shaped the brief, the plan, its review and the
critique. tdd (`mattpocock/skills` at `d81f3a183412e71a5b1e84ca21bc1a35eea03a60`,
SKILL.md SHA-256 `93ea419b76e9caaf26153b828e984f7c3fb136f4caa67b14af95f32ea965a1cc`)
set red before green, one seam at a time. codebase-design (same pin, SKILL.md
SHA-256 `2c20617f87ec8af6a434859f381b2f061a69b530444e74eb39e78bb016a6d1e2`) set
the shared source-map loader and reader behind small interfaces now that a
second page uses them. claude-native-practice supplied data only: the Claude
practice slots.

**CSS cascade helper.** The first helper parsed the stylesheets and matched
selectors itself, and screened only soupsieve 3.0.3 and cssselect 1.6.0. A
review found that cssselect2 0.10.1 with tinycss2 1.5.1, current on PyPI at
2026-10-17, was not screened. That pair is adopted for parsing, selector
matching and specificity, and the stdlib selector engine is removed.

- **Screen at the pins.** Both are pure-Python BSD-3-Clause wheels requiring
  Python 3.10 or later, with webencodings 0.6.1 as the one shared dependency; no
  release is yanked (PyPI JSON read 2026-10-17, wheel hashes in
  `.github/requirements-ci.txt`). tinycss2's `parse_stylesheet`,
  `parse_rule_list` and `parse_blocks_contents` return rules, at-rules and
  declarations with their `important` flag; cssselect2's `compile_selector_list`
  compiles a selector with its specificity, and `Matcher.match` returns
  sorted `(specificity, order, pseudo, payload)` tuples for the matching
  selectors, so by specificity, then by order of addition (cssselect2
  `__init__.py` at the pin; the API reference at
  https://doc.courtbouillon.org/cssselect2/stable/api_reference.html).
- **Measured on the built atlas page,** from a scratch environment installed
  from the hash-pinned entries: all 756 selectors of the four sheets compile;
  the matching rule sets agree on all 9,905 element-by-setting pairs, and so
  does each selector's specificity. The rewritten helper and the stdlib helper
  it replaces then returned identical `Cascade.declarations()` lists, compared
  as (property, value, importance, sheet, selector, specificity, order), for
  all 76,717 declarations at the five settings of `CascadeTests`.
- **Still ours, because neither package ships it:** the ElementTree that
  cssselect2 matches against (built with `html.parser`, with each node's text
  and tail set because cssselect2 compiles `:empty` as a test of the node's
  children and text, and guarded against the shapes a browser would build
  differently); `@media` and `@container`
  evaluation, since neither package evaluates a media query; the shorthand
  expansion; and the importance, specificity and order rank across sheets.
- **Cost.** Three hash-pinned entries in `.github/requirements-ci.txt`, which
  every workflow that installs the CI analyzer already reads. The packages are
  imported when a `Cascade` is built, so a missing package fails the four
  `CascadeTests` and no other test.
