# Public input bytes for the model-routes custody tests

Retrieved 2026-10-16 by unkeyed public HTTP. These inert text fixtures retain
exact upstream bytes so the tests run offline. They are not installed, imported,
executed or read as instructions. No deployed package, private directory,
credential store or unretained response is a fixture input.

| Fixture | Published repository and pin | Original path |
| --- | --- | --- |
| `omniroute-package.json.txt` | `diegosouzapw/OmniRoute@c1e30b7676975feb298b49eff6ff58923c04b89e` | `package.json` |
| `omniroute-codex.ts.txt` | same | `open-sse/config/providers/registry/codex/index.ts` |
| `omniroute-muse-code.ts.txt` | same | `open-sse/config/providers/registry/muse-code/index.ts` |
| `omniroute-shared.ts.txt` | same | `open-sse/config/providers/shared.ts` |
| `omniroute-museCode.ts.txt` | same | `open-sse/config/museCode.ts` |
| `omniroute-requestDefaults.ts.txt` | same | `src/lib/providers/requestDefaults.ts` |
| `omniroute-LICENSE.txt` | same | `LICENSE` (MIT) |
| `claude-api-SKILL.md.txt` | `anthropics/skills@dbd4588f9e1033efb41dad4bef2f7947c8993d44` | `skills/claude-api/SKILL.md` |
| `claude-api-models.md.txt` | same | `skills/claude-api/shared/models.md` |
| `claude-api-LICENSE.txt` | same | `skills/claude-api/LICENSE.txt` (Apache 2.0) |

Source URL form:
`https://raw.githubusercontent.com/<repository>/<full pin>/<original path>`.
The copyright and permission notices are retained in the corresponding license
files; the source bytes are unmodified.

Two deployed source hashes differ from the public OmniRoute release. They still
have reproducible public inputs already retained in #1177:

- The Codex registry equals `omniroute-codex.ts.txt` with the nine published
  excerpt lines 69–77 from `deployed-source-review.json` inserted before the
  release's line 69. The test verifies all retained excerpt lines against the
  reconstructed bytes, then checks the digest.
- `reasoningSuffix.ts` is entirely present as contiguous excerpt lines 1–60 in
  that record. Joining them with LF and a terminal LF reproduces its bytes.

The proposed ledger predecessor is recomputed from the public ledger at the run
pin using its pinned `saturation_ledger.py`; the requirement and platform hashes
use that same pinned algorithm. No digest value is accepted merely because it
appears in a second record or in a fixed allowlist.
