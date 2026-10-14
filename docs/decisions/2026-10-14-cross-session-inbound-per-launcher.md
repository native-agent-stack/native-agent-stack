# Cross-session inbound: accept per launcher, not in user settings — 2026-10-14

## Decision

1. **No template sets `crossSessionInbound`.** The new WSL distribution's additions
   (`adoption/new-wsl/templates/claude.settings.additions.json`) no longer carry `"accept"`, and the client-configuration
   map loses its entry. The agent-messaging slot loses its `claude_inbound_piece` key, which no code read.
   `tools/adoption/new_wsl_client_config.py` keeps the key in `AUTHORIZATION_PIECES`, so a template that brings it back is
   classed authorization, never practice.
2. **A `-p` worker that must take messages unattended gets `accept` on its own command line:**
   `--settings '{"crossSessionInbound":"accept"}'`. `recipes/claude-native-profile.md` says so for headless runs, and
   `recipes/claude-native-ultracode.md` already said it for its workers. Review, evaluation and other fenced runs stay
   without it.
3. **Interactive sessions use the client's default.** In this ecosystem they all run in bypass mode, so they receive each
   other's messages.
4. **The hcom adapter stops requiring the template value.**
   `evidence/artifacts/new-wsl-install-plan-20261002/config/hcom-client-config.py` checked that the template carried
   `"accept"` and refused otherwise. hcom's own transport runs through its hooks and does not use the setting. The adapter
   now only checks that an entry, if one comes back, is classed authorization.

## Why

A user-scope `accept` lets every session take messages from any of the user's other sessions, whatever their
permission modes. That includes `-p` workers that should not be steered from outside. The client's documentation names
the narrower route, and the measurements below show that it gives the coordinators the same delivery.

## Sources

- **Settings reference**, `https://code.claude.com/docs/en/settings-reference.md`, fetched 2026-10-14T05:40:19Z, sha256
  `2db996847f31ad322a4eff57aa8a1e5ca4618701fd1caf2191327a3922be095c`, lines 5093-5112:
  - `accept`, `hold` or `refuse`;
  - "A project or local value applies only when it's stricter than the value managed settings, the `--settings` flag,
    or user settings give."
- **Cross-session messaging**, `https://code.claude.com/docs/en/cross-session-messaging.md`, same fetch, sha256
  `7b359027749ff27d84019a388145bf78edce1dc424aaa9a50896c6c88e4b1edd`:
  - line 203: the default decides per message from the two sessions' permission-mode classes;
  - line 231: "To let a `-p` worker take messages unattended, start it with `crossSessionInbound` set to `accept` in its
    `--settings` value. An `accept` in your user settings also works but applies to every session you run."
- **The installed client**, 2.1.299 (binary sha256 `2d894a4b1bfaaa9aab72aeff7803e3c73bc2510f279a171f6b8f59f72d17d077`):
  - the first value found among managed settings, `--settings` and user settings wins; project and local values can only
    tighten it;
  - without a value, a session is in the bypass class in `bypassPermissions` mode (or in plan mode with bypass
    available) and in the prompting class otherwise, `dontAsk` included.

## Evidence on this host

`evidence/artifacts/cross-session-inbound-20261014/` holds the probes and their receipts. Every arm runs real 2.1.299
client processes in a scratch HOME and a scratch `XDG_RUNTIME_DIR`, so no real session sees them. Each client talks to
a loopback stand-in for the Messages API: no model, no spend. The sender's stand-in makes it call SendMessage.
"Delivered" means the receiver's model was sent a request carrying the probe's marker.

| Arm | Sender | Receiver | Receiver's value | Result |
| --- | --- | --- | --- | --- |
| A1 | dontAsk `-p` | bypass | none | held |
| A2 | bypass | bypass | none | delivered |
| A3 | bypass | dontAsk `-p` | `accept` from `--settings` | delivered |
| A3c | bypass | dontAsk `-p` | none | held |
| A4 | dontAsk `-p` | bypass | `accept` in user settings | delivered |
| A5 | dontAsk `-p` | bypass | `accept` in project settings only | held |
| A6 | bypass | a trader-shaped worker (`-p`, prompt on stdin, `--tools Bash,Read`, dontAsk, mid-run) | `accept` from `--settings` | delivered |
| A6c | bypass | the same worker | none | held, then dropped when the run ended |

The live-reload arms (L1-L3) rewrite the scratch user settings while a trader-shaped worker runs:
- **L1:** removing `accept` before a send makes the worker hold the message.
- **L2:** adding `accept` before a send delivers it.
- **L3:** adding `accept` after a send releases the held message.

So a running session follows a change to its user settings: the user-scope value comes off a host only after every
running worker that needs messages carries its own `--settings` value.

## Supersessions

This decision replaces the user-scope `accept` that these records chose or relied on:
- `2026-09-27-mac-single-writer-staged.md` line 57: "The receiving side sets `crossSessionInbound: "accept"`". Its
  receiving side now carries the value on its own command line.
- `2026-09-28-terminal-experience.md` line 249: the terminal tabs' messages between bypass-mode sessions. The default
  already delivers those (A2).
- `2026-10-04-new-wsl-changelog-parity.md`, decision 2: `crossSessionInbound = "accept"` as an authorization piece of the
  new WSL distribution.
- `2026-10-04-round2-plan-g1-messaging.md` line 25: "Claude <-> Claude remains native SendMessage/ListAgents with
  `crossSessionInbound=accept`". Claude to Claude stays native SendMessage and ListAgents, under the client's default and
  per-worker `accept`.

The map entry this removes cited an owner directive of 2026-10-04 ("we need all the sota features … fully enalbed
seamlessly within our naitve workflow"). The documentation's own route (line 231) keeps the feature fully working for
every session that needs it: interactive coordinators receive by default, and each worker receives by its launcher.

## Risk

- **A message between two prompting sessions still delivers by default.** A prompting sender to a bypass receiver is
  held. This host runs no prompting-mode sender today: the traders run `--tools Bash,Read`, and the fenced runs restrict
  their tools.
- **A worker launched without the flag holds its coordinator's messages.** In `-p` nobody approves them, and they are
  dropped when the run ends (A6c). The recipe names the flag.
- **A host that keeps the user-scope value keeps today's behaviour.** The new WSL tool never removes a value a file
  already has.

## Inverse

Put `"crossSessionInbound": "accept"` back into the additions template and its map entry (the parent commit's bytes),
and restore the adapter's check and the tests' expectations.

## Tests

- `tests/test_cross_session_inbound.py` (8 tests): no settings template sets the value; the map has no entry for it
  while the tool still classes it authorization; both headless recipes name the per-launcher value; the receipts show
  the arms above and hold no message id, path or key. On main's files 3 of the 8 fail
  (`receipts/fail-before.txt`).
- `tests/test_new_wsl_client_config.py`: 231 tests pass. The declared changes are in the dated addendum of
  `2026-10-02-new-wsl-client-configuration.md` (402 pieces, `authorization: 15`).
- The hcom adapter test (`test_hcom_apply_never_grants_inbound_authorization_or_requires_codex`) passes unchanged for an
  absent, `accept` and `hold` value in the user's file.

## Overturn when

- A client release changes the default's mode classes or the order of the setting's sources.
- Or the owner chooses a user-scope value for this host again.
