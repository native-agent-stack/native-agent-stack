# Pillow 13.0.0 security repin research

Observed 2026-10-20 from clean NAS da5549584abb3c95f0c90d7aa0d948b2f72c7876 on wave/pillow-13. Research was written before any lock changed. Current result: all five native locks now pin Pillow 13.0.0; Round 3 controls supersede the historical failed attempts below. Scope is exactly the five active locks in the assignment. No runtime, broker or provider acceptance is claimed.

## Release and advisory evidence

PyPI https://pypi.org/pypi/pillow/json reports latest 13.0.0, Requires-Python >=3.11. Its last 12.x release is 12.3.0, uploaded 2026-07-01T11:53:27Z; 13.0.0 first uploaded 2026-10-16T22:15:24Z. No 12.3.1 or other non-major fixed release exists in its complete release map. GitHub https://api.github.com/repos/python-pillow/Pillow/tags?per_page=15 independently lists 13.0.0 followed by 12.3.0 (then 12.2.0); release https://github.com/python-pillow/Pillow/releases/tag/13.0.0 was published 2026-10-16T22:37:44Z. Tag commit: 293218ad059d994baf1777d882911bed6a49704a. These observations corroborate, rather than assume, the coordinator's report.

The following ranges are verbatim from each GitHub global advisory API record, fetched 2026-10-20. All nine first_patched_version fields are 13.0.0, so both 12.3.0 and the older retained Lumibot pin require scrutiny; changing to another 12.x release cannot close the active findings.

| Advisory | Affected range | First patched | Mechanism |
| --- | --- | --- | --- |
| [GHSA-462x-pgg6-55fp](https://github.com/advisories/GHSA-462x-pgg6-55fp) | >= 8.2.0, < 13.0.0 | 13.0.0 | Pillow tiled-TIFF decoder reads past tile buffer in copy4 (Unpack.c:1290) |
| [GHSA-58r4-6rv3-gfh8](https://github.com/advisories/GHSA-58r4-6rv3-gfh8) | <= 12.3.0 | 13.0.0 | Pillow: Out-of-bounds access in _imagingmorph on a zero-width image |
| [GHSA-65qm-jvmh-6pqg](https://github.com/advisories/GHSA-65qm-jvmh-6pqg) | >= 9.2.0, < 13.0.0 | 13.0.0 | Pillow: GIF seek keeps rejected size after DecompressionBombError, allowing DoS |
| [GHSA-8g5g-8vmr-9782](https://github.com/advisories/GHSA-8g5g-8vmr-9782) | <= 12.3.0 | 13.0.0 | Pillow: Heap buffer overflow in ImagingJpegDecode |
| [GHSA-c6hw-5grf-ff96](https://github.com/advisories/GHSA-c6hw-5grf-ff96) | >= 8.1.0, < 13.0.0 | 13.0.0 | Pillow: OOB read in TiffDecode.c tile and RGBA paths leaks heap memory into pixels |
| [GHSA-p4wg-p73j-c528](https://github.com/advisories/GHSA-p4wg-p73j-c528) | >= 5.1.0, < 13.0.0 | 13.0.0 | Pillow: Unbounded recursion parsing a PDF page tree or trailer chain (incomplete fix for CVE-2026-42310) |
| [GHSA-pchr-8j38-3x4p](https://github.com/advisories/GHSA-pchr-8j38-3x4p) | <= 12.3.0 | 13.0.0 | Pillow: TIFF encoder ColorMap plane-size mismatch causes a heap out-of-bounds read |
| [GHSA-q45j-58j2-45rg](https://github.com/advisories/GHSA-q45j-58j2-45rg) | >= 5.3.0, < 13.0.0 | 13.0.0 | Pillow: TiffDecode returns uninitialized memory as pixels for short JPEG strips |
| [GHSA-vx6w-vv9f-6gvg](https://github.com/advisories/GHSA-vx6w-vv9f-6gvg) | >= 2.3.0, <= 12.3.0 | 13.0.0 | Pillow: EPS load(scale) lets Ghostscript render past the decompression bomb limit |

API source pattern: https://api.github.com/advisories/GHSA-462x-pgg6-55fp (substitute each complete ID above). All nine queries returned HTTP 200. This is an advisory-database comparison, not reachability evidence and not a full-repository scanner result.

## Breaking changes and release changelog

Sources: https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html and https://api.github.com/repos/python-pillow/Pillow/releases/tags/13.0.0 . At the tag, https://github.com/python-pillow/Pillow/blob/13.0.0/CHANGES.rst explicitly redirects versions 11.1.0 and newer to GitHub Releases; that release body is the current changelog, not the old 11.0 section of CHANGES.rst.

Completed removals: Python 3.10; saving mode I directly as PNG (convert to I;16 explicitly); Image.fromarray(mode=...) when it changes the data type (palette/color-space interpretation remains supported); Image.Image.get_child_images moves to ImageFile.ImageFile; Image._show; ImageCms.ImageCmsProfile.product_name/product_info; ExifTags.IFD.Makernote (use MakerNote); undocumented GifImagePlugin._save_netpbm. New deprecations, not removals in 13: IM format (15.0), JpegImageFile.load_djpeg (14.0), ImageQt.align8to32.

API/behavior changes: premultiplied RGBa/La ImageColor.getcolor results; first duplicate TIFF tag wins; small ICO defaults to its own size, invalid requested sizes raise ValueError. RGBA/LA resizing now respects reducing_gap (including thumbnail's default), so exact output pixels may change. ImageOps pad/expand preserve transparency; APNG frames with distinct palettes become RGB(A); PNG bits no longer pads PLTE; corrected FITS endian handling, 16-bit conversion/filter/drawing/offset, masked two-band histograms, variance rounding, GIF missing duration, PSD offsets, XBM comments, and noncontiguous Arrow export (ValueError). ImageSequence restores position on failure and TIFF/tobytes encoders clean up deterministically. Additional release changes include stricter corrupt/truncated-file validation and decompression-bomb bounds; do not promise byte-identical image output.

Additions: MKS2013/MKS2021 resamplers; getxmp(strip_namespaces=...); PSDraw.text(escape=...); palette ImageOps invert/posterize/solarize; path-like font files. Python >=3.11 is mandatory; 3.15 becomes official, PyPy 3.12 wheels join PyPy 3.11. All consumer targets (3.12.3 / 3.12 / 3.13) meet the floor. PyPI files, rather than assumed wheel coverage, will supply all pinned hashes.

Bundled/native changes from the release's Dependencies/Other changes: libjpeg-turbo 3.2.0, libtiff 4.7.2, HarfBuzz 14.5.0, raqm 0.11.0, xz 5.8.4; FriBiDi dependency/test version 1.0.17 is not a bundled FriBiDi library. Pillow's vendored FriBiDi shim is MIT-CMU, not LGPL; FriBiDi itself is not shipped in the wheels. OpenJPEG receives uclouvain/openjpeg#1621 (OSV-2025-219) with a corrected patch application. Linux/macOS OpenJPEG, libtiff, FreeType and LittleCMS now compile with -O2; PNG/JPEG/WebP/AVIF already did. FreeType links the bundled HarfBuzz on all wheel platforms, potentially changing glyph rendering. Ghostscript 10.8.0 and nasm 3.02 changes are build/test tooling, not a claim that Ghostscript ships in the wheel. Free-threaded critical sections and AVIF GIL behavior change. Source building would use host libraries; this work does not rebuild them.

## Seven-pin scope audit

.github/osv-scanner-lockfiles.json explicitly includes all five assigned active locks. Its excluded[] already contains blueprints/us-equities/engine-trials/spy-one-zero-20260926/lumibot/lockcheck/lumibot.lock (failed historical trial, not a live install input) and evidence/artifacts/trading-2604-aiohttp-repin-20261020/published-f451-trading-2604-runtime.lock (byte-identical historical published input, not an install input). Neither is in lockfiles[] and neither is passed to the ordinary or frozen scanner invocation in .github/workflows/security-scan.yml. Both are outside the authorized five-lock scope and remain unchanged. No extra scanned affected pin was found among these seven; the requested scope-stop condition is not triggered. No ignore or exclusion is added to solve Pillow findings.

## Consumer compatibility and package metadata

Local .py searches in all five consumers found no direct PIL import. Package sources below were read from their exact PyPI wheels (plus Matplotlib's GitHub tag), not inferred from this absence. The metadata requirements have no upper bound below 13.

| Consumer | Pillow dependency path and metadata | Assessment |
| --- | --- | --- |
| portfolio-risk requirements-libs.lock | cvxportfolio 1.5.1 / quantstats 0.0.81 / seaborn -> matplotlib 3.11.2 -> pillow>=9 | Plot/image save path uses RGBA frombuffer/fromarray without data-type override. No removed call found. Quantitative library use does not depend on I-mode PNG. Plot/font pixels can differ. Python 3.13 meets floor. |
| worker OpenHands requirements.lock | SDK/tools wheels 1.49.6 -> SDK pillow>=12.3.0; tools -> browser-use 0.11.9 -> pillow>=11.2.1 and reportlab 4.4.4 -> pillow>=9.0.0 | SDK image_resize.py calls open/thumbnail(LANCZOS)/save and converts JPEG to RGB where needed. Browser screenshots/GIF overlays use open/resize/ImageDraw/fonts; ReportLab ImageReader uses open/convert/tobytes. All APIs survive. RGBA/LA thumbnail output and text rendering can change; opaque screenshots remain supported. Python 3.13 meets floor. |
| trading uv.lock | mlflow 3.16.1 -> matplotlib<4, locked 3.11.2 -> pillow>=9 | Same Matplotlib image path. No removed API identified; numeric/trading pins remain fixed. Exact project Python ==3.12.3 is required for native relock/check, not a Python 3.13 substitute. Native host acceptance does not transfer. |
| hftbacktest requirements.lock | hftbacktest 2.4.4 -> matplotlib 3.11.2 -> pillow>=9; hftbacktest -> holoviews -> bokeh 3.9.2 (also via panel) -> pillow>=7.1.0 | Bokeh screenshot export open/convert(RGBA)/crop/resize survives; Image.transform handles RGB(A) arrays. Arbitrary I-array-to-PNG user inputs now fail upstream, but this lane's L1 numeric fixture uses no such path. No change required to simulation APIs. Python 3.12 meets floor. |
| OpenHands example requirements.lock | SDK 1.50.1 -> pillow>=12.3.0; tools -> browser-use 0.11.13 -> pillow>=11.2.1; browser-use -> reportlab 5.0.1 -> pillow>=9.0.0 | Same SDK image_resize implementation and screenshot/PDF APIs; no removed API found. Alpha thumbnail/glyph output is not promised identical. Python 3.13 meets floor. |

Primary metadata: https://pypi.org/pypi/matplotlib/3.11.2/json ; https://pypi.org/pypi/bokeh/3.9.2/json ; https://pypi.org/pypi/openhands-sdk/1.49.6/json ; https://pypi.org/pypi/openhands-sdk/1.50.1/json ; https://pypi.org/pypi/browser-use/0.11.9/json ; https://pypi.org/pypi/browser-use/0.11.13/json ; https://pypi.org/pypi/reportlab/4.4.4/json ; https://pypi.org/pypi/reportlab/5.0.1/json ; https://pypi.org/pypi/mlflow/3.16.1/json . Each parent permits >=13, none requires <13. Source files: matplotlib/image.py (imsave lines 1600-1729) and backend_agg.py, bokeh/io/export.py and core/property/visual.py; browser_use/agent/gif.py, browser/python_highlights.py, browser/video_recorder.py; openhands/sdk/llm/utils/image_resize.py; reportlab/lib/utils.py (ImageReader), graphics/renderPM.py and pdfgen/pdfimages.py. For Matplotlib: https://github.com/matplotlib/matplotlib/blob/v3.11.2/lib/matplotlib/image.py ; SDK source pins fcc102a697874d54a357e36004e02c95040dbdc0 and 1e1390acc8788346ba4804c34323284009bf3f5e in https://github.com/OpenHands/software-agent-sdk . This is source_review compatibility evidence; tests must qualify the repin separately.

## Required regeneration and binding method

Read-only precedent: https://github.com/seathatflowsinourveins/native-agent-stack/pull/1265 ; commit 151f1e459f3ccd8263cb1d666e0299693163c6e7, including its non-lock diff, lock hash changes, retained-copy naming correction and PR body. Use uv lock for the trading project, uv pip compile for the three compile-based requirements files, and the worker's documented pinned workspace relock/export plus pins.json wheel append. portfolio-risk's recorded compile command is in evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/1-candidate-libs-execution.json: --python CPython3.13 --generate-hashes --no-header. hftbacktest and the example record their commands in their headers.

Worker source is OpenHands/software-agent-sdk@fcc102a, whose root pyproject.toml has exclude-newer='7 days' and two package-specific cutoffs. Pillow 13.0.0 is only four days old. Reproduction must report a cooldown refusal, or a necessary Pillow-only cutoff exception explicitly, rather than silently disabling all cutoffs. No older fixed release can satisfy it. Tool source: astral-sh/uv@0.12.22 (70fe1196a546e49148a73b1c592b2f74c33af80e), docs/concepts/projects/sync.md, export.md and resolution.md; https://github.com/astral-sh/uv/blob/0.12.22/docs/concepts/resolution.md . Trading lock revision 5 was last generated by uv 0.13.1; using 0.12 rewrites revision, so reproduce with 0.13.1 if available through supported scratch installation.

Binding search found worker pins.json; scanner inventory digests; trading install/accept scripts, scheduled_trial.sh and source-hashes.json, test_scheduled_trial.py, README current claims, final-stack.json source hash, and manifests/evidence.json for every changed/added file. Preserve all dated measurements and their original digests. If a frozen source binds a changed lock, retain exact old bytes under pinned-at-da554958.source.txt and repoint only that reference without changing the measured hash; published trading pairs use published-<digest-prefix>-trading-2604-runtime.lock with inventory excluded evidence registration only when necessary. Never name an evidence-only retained requirements copy requirements*.txt. Keep the prior f451 fixture unchanged.

Convergence command: python3 -B scripts/validate_convergence.py --all-recorded. Evidence/manifest and final-stack checks accompany scripts/validate.py, and consumer test modules include tests.test_trading_2604_migration, tests.test_trading_2604_lock, tests.test_runtime_worker_openhands, tests.test_openhands_lock_binding, tests.test_sim_crosscheck_hftbacktest and tests.test_gap_wave_ledger. Test skips are not runtime acceptance. Local osv-scanner is absent on PATH at research time; compare all nine advisory ranges offline or leave the networked full scan to CI, respecting allowed network hosts.

## Layer-resolution boundary

Consumed docs/decisions/2026-10-11-layer-resolution-protocol.md, catalogs/landscape/us-equities.json, layer-verdict-waves.json and saturation/ledger.json. This is the assigned security delta to existing consumers, not a new tool/runtime/strategy comparison or a FINAL-layer selection. Existing portfolio-risk and worker unresolved sweep survivors are not adjudicated by a Pillow repin. The new evidence is the nine 2026-10-20 advisories and the pinned 13.0 release; bounded next action is native lock regeneration and binding/test validation only.

## Historical Round 1 finding before repository lock edits (superseded)

The worker is BLOCKED under the unchanged documented workspace relock/export contract. The pinned upstream workspace's dev group includes streamlit>=1.49.1. Its upstream uv.lock pins Streamlit 1.63.0; PyPI https://pypi.org/pypi/streamlit/1.63.0/json requires pillow<13,>=7.1.0. Latest Streamlit 1.66.0 also requires pillow<13,>=9.2.0 (https://pypi.org/pypi/streamlit/1.66.0/json). uv lock resolves every workspace dependency group, even though uv export --package openhands-tools does not ship Streamlit. This is an additional workspace constraint, separate from the shipped parent table above.

Reproduced with scratch uv 0.13.1 and the recipe's exact uv 0.12.17: uv lock --upgrade-package pillow==13.0.0 fails exit 1, reporting streamlit>=1.49.1 depends on pillow>=7.1.0,<13. The no-Pillow-upgrade control resolves 419 packages successfully. A diagnostic --no-config attempt also fails on the same Streamlit cap, so disabling security cutoffs cannot solve it and was not adopted. The current worker export remains untouched. Removing Streamlit from upstream's dev group, overriding its published Pillow metadata, or switching the worker to pip compile would change the prescribed method; none was adopted. The four independent locks can be delivered, but the repo-wide OSV blocker is not closed.

The existing LiteLLM scratch cutoff correction is 2026-08-10T00:00:00Z, not the upstream July20 cap: blueprints/runtime-workers/openhands/research.md:455-466 records it. A trial first reproduced the 7-day Pillow cooldown refusal, then the old LiteLLM cap refusal, then the substantive Streamlit incompatibility with the documented corrections and a Pillow-only cutoff of 2026-10-21T00:00:00Z. No cutoff or upstream dependency modification is committed.


## Historical Round 2 override attempt (2026-10-20, superseded)

The builder subsequently authorized the scratch-only rule-6 Pillow override. It resolves under uv 0.12.17, but the frozen export reintroduces six previously removed non-Linux entries, including cryptography 48.0.1 on Darwin, and changes 333 same-version markers. The prior no-override failure above is retained as chronology; the final blocker is the unsafe export, not resolver failure. The candidate is rejected, the worker remains unchanged, and the final verdict is BLOCKED. See blueprints/runtime-workers/openhands/research.md, section Runtime lock pillow relock (2026-10-20), and WORKER-BLOCKER.json in the external packet for exact output, hash and marker classification. No override is committed into runtime metadata.

## Round 3 correction: reproduced control and accepted worker (2026-10-20)

The preceding BLOCKED attempt is superseded. Its no-override diagnostic also
added the new Pillow cutoff before reproducing the baseline. Historical-cutoff
controls with uv 0.12.17 now reproduce September 27 (02d0a7f0...), the eleven-pin
MCP export (a3303759...), and CURRENT worker (6045a575...) byte for byte. Original
PR #1265 retained resolver commands/output confirm a native relock, not surgery.
Only after that control existed were the approved override and Pillow cutoff
added. Native lock/export succeeds with 412 packages, 336 exported entries and
Pillow 13.0.0; all other blocks are unchanged. New worker SHA256:
cae6845caac95336e4ba09e88b10956905476c6b90cb5fe1b71f0253f5d17f84. All 17 selected hashes match PyPI.
See blueprints/runtime-workers/openhands/research.md#runtime-lock-pillow-relock-2026-10-20
and external WORKER-RELOCK.json for commands, output and hashes. Scope remains
the recipe venv, not the image's PyInstaller binary or grader.

## Round 4: stacked on accepted certifi head (2026-10-21)

This dated section supersedes the original base/current-lock and retained-copy
instructions above for the stacked publication. Parent is exactly
eb898b558afbaa36b3d7a69b1f8c6cbfa91cbd2b. Old wave/pillow-13 / bd861172 stays
a reference; none of its locks was merged. Each of the five native tools
started from the accepted certifi bytes. No sixth shared lock was found.
Pillow 12.3.0 -> 13.0.0 is the only parsed package delta; certifi 2026.10.19
blocks remain byte-identical to the accepted parent in all five locks.

Trading uv 0.13.1 output 52f17cf0799be010152b0cb432ccd1a6e96b30be0cd01d7b7adc5629f02c07f9
normalizes timestamps to milliseconds (astral-sh/uv@0.13.1,
crates/uv-distribution-types/src/file.rs:32-56; crates/uv-lock/src/lock/mod.rs
uses Timestamp::from_millisecond). #1266 commit 1328f121 instead recorded
PyPI JSON precision. The wave builder explicitly authorized restoring exactly
the two certifi timestamps at uv.lock:254 and :256 to parent bytes. This is
native pillow content, reviewed certifi timestamp precision preserved, as #1266 recorded them.
Final trading SHA256: 9d8350a6773437a6890808c5b6ae61d98d305021b16ea0a4b4e753dd2f4f6223.
Only those two lines differ from the native output; the certifi block is
byte-identical to eb898b55; parsed parent/final comparison changes Pillow only.
Both uv 0.13.1 and 0.12.17 pass --no-config lock --check --offline with the
exact scratch CPython 3.12.3, UV_NO_CONFIG unset and unchanged default cache.
The other four native exports are adopted without edits or other movements.

The worker native control first reproduces the accepted certifi export
096f6255391e56270df7843cb6739d1e373012d6a54e38d7fd7813e0b9e6a96a.
Only then are the identical authorized override and Pillow cutoff applied.
The current worker method, hashes and unchanged rule-6/turn-back/F18 record
are in blueprints/runtime-workers/openhands/research.md, 2026-10-21 section.

Retained-copy decision: reuse #1266's 13 reviewed published-* files for
da554958 inputs, unchanged. Do not duplicate bd861172's old-byte snapshots.
Retain each of the five distinct eb898b55 inputs once under historical/on-1266/
with published-<hash>.source.txt names. Relocate only the matching five current
paths in the frozen certifi repin receipt; keep its hashes, observations and
claims unchanged. This follows docs/decisions/2026-10-06-application-input-binding-amendment.md.
No scanner exclusion or advisory ignore is added. The trading installer admits
the exact accepted certifi pair as an additional migration input, never
acceptance; its regression fails with exit 73 before that admission is added.

Sources: https://github.com/astral-sh/uv/blob/0.13.1/crates/uv-distribution-types/src/file.rs
; https://github.com/astral-sh/uv/blob/0.13.1/crates/uv-lock/src/lock/mod.rs
; https://github.com/seathatflowsinourveins/native-agent-stack/commit/1328f121
; https://pypi.org/pypi/certifi/2026.10.19/json .
The wave builder's timestamp exception changes no version, artifact hash,
constraint, native host acceptance or existing required-check policy.
