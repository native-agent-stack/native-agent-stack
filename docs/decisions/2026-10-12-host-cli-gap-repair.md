# Repair selected host CLI installs through the Linux bootstrap

The default `python3 tools/adoption/install_skills.py --check-only` failed
with `skills not found` even though a pinned CLI existed in another isolated
prefix. `tvly` and `orx` were also absent from the host PATH. The existing
bootstrap could install their pinned artifacts, but only through a whole
profile, with a core node/uv/gh refresh; no profile selected these two research
CLIs. Installing packages or editing PATH separately would bypass that route.

Add repeatable `--only <pinned-id>` to the Linux bootstrap. It uses the same
vendor installers, checksums, publication links, lock and bounded version
report. It selects no implicit core tools and cannot combine with profile
configuration. `skills` uses the existing skills CLI manifest, including its
version/archive/hash; all other ids use the existing Linux pins. This is
selection glue around supported installers, with no replacement package manager.

The [host receipt](../../evidence/artifacts/host-cli-gaps-20261012/receipt.json)
records the default check failing before and reporting `28/28 ok` afterward.
Native versions are skills 1.7.0, tavily-cli 0.1.8 and orx 0.2.15. The ecosystem
bin directory was already on PATH; no shell-profile change was needed. Vendor
inverse commands and removal of owned publication links were exercised in a
disposable prefix, preserving the live install. No skill folders were changed.

## Sources at the executed pins

- `vercel-labs/skills@7407f3893ad4dceab546ac002c3ef806e4000c73`
  (1.7.0), `README.md:20`: native CLI skill installation. Its verified npm
  archive and isolated install are already pinned in `adoption/skills/manifest.json`.
- npm 11.19.0, `npm/cli@bfacd33ccbcd908480610703b60455d2da5b57a9`,
  [`folders.md:22-29`](https://github.com/npm/cli/blob/bfacd33ccbcd908480610703b60455d2da5b57a9/docs/lib/content/configuring-npm/folders.md#L22-L29)
  and [`:45-48`](https://github.com/npm/cli/blob/bfacd33ccbcd908480610703b60455d2da5b57a9/docs/lib/content/configuring-npm/folders.md#L45-L48):
  global prefix and executable publication;
  [`npm-uninstall.md:13-25`](https://github.com/npm/cli/blob/bfacd33ccbcd908480610703b60455d2da5b57a9/docs/lib/content/commands/npm-uninstall.md#L13-L25):
  inverse. This exact version's source was fetched; the npm repository is unmirrored locally.
- uv 0.12.22, `astral-sh/uv@70fe1196a546e49148a73b1c592b2f74c33af80e`,
  [`tools.md:195-207`](https://github.com/astral-sh/uv/blob/70fe1196a546e49148a73b1c592b2f74c33af80e/docs/guides/tools.md#L195-L207)
  and [`storage.md:150-168`](https://github.com/astral-sh/uv/blob/70fe1196a546e49148a73b1c592b2f74c33af80e/docs/reference/storage.md#L150-L168):
  exact-version tool install and isolated tool/bin directories. The installed
  `uv tool uninstall --help` supplies the executed inverse. The local mirror is
  newer; these source blobs were read at the executed version's exact commit.
- tavily-cli 0.1.8: the official PyPI sdist already pinned in
  `adoption/pins-linux-x86_64.json` was independently downloaded and matched to
  its published checksum; its `README.md:35-39` documents the Python package
  route. The bootstrap's existing uv install owns the isolated environment.
  The local repository mirror is 0.1.9; it was not treated as 0.1.8 evidence.
- `alphaXiv/OpenResearch@ee36ef0333ca3c533eace915f1bec322a1efde1c`
  (v0.2.15), `README.md:36`, plus the Linux-musl release archive/hash in
  `adoption/pins-linux-x86_64.json` and the existing qualification receipt.
  The current local mirror is 0.2.7; the exact v0.2.15 README was fetched.
- Existing reference composition at base
  `d8f7e2051b61bde6361a85b64f41413798015353`,
  `adoption/bootstrap-linux.sh`: `install_npm`, `install_uv_tool`,
  `install_single_binary_tarball`, `install_pin` and `write_version_report`.
  The repair reuses these mechanisms.

## Platform and qualification boundaries

Poppler's current [recipe](../../blueprints/convergence-practice/document-ingestion/README.md#build-and-qualify-another-explicit-mac-prefix)
qualifies 26.09.0 only in an explicit Mac prefix. It neither installs a global
default nor qualifies Linux. There is no Linux bootstrap pin, so `pdftotext`
remains absent here and explicitly unqualified. A distro package would need
its own pinned Linux recipe and acceptance, rather than an implicit install.
Agent-browser remains held and was not installed. Version probes are separate
from authenticated/live web-research acceptance; none was attempted.

## Regression and correction class

The class is **installed prefix without executable publication**. Native
package installation and its host publication/check must be one reviewable
path. A synthetic selected-install regression fails on the base with
`Unknown argument: --only`, then passes after this change. It runs the real
parser, selection, pin dispatch and report, stubbing only vendor installation.
It verifies exact selection, no implicit core/browser install, no profile
write, duplicate handling, invalid selections, null-hash refusal and a wrong
version refusal. Existing bootstrap tests retain checksum/native-floor checks.

Overturn this selection glue if an upstream-supported repository installer
already provides the same bounded repair interface, or a measured host repair
shows it cannot preserve pin verification, publication or inverse. Future
bootstrap pins remain independent currency decisions.

Follow-ups: qualify a Linux Poppler recipe before promoting `pdftotext`; retain
the existing uv sdist/dependency-locking limitation; audit other selected
prefixes for missing publication through the same native path. No wider
runtime/profile or MCP cleanup is included in this repair.
