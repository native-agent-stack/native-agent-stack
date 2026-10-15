"""Independent contract checks for the dated routing/proposal artifacts.

Checks completeness against the pinned source bytes, existing decisions and
native builder allowlist. It does not run any upstream project or model.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from public_starred import PUBLIC_FIELDS, REVIEW_FIELDS  # noqa: E402


def read(name):
    return json.loads((HERE / name).read_text())


def main():
    checks = []
    snapshot = read("public-starred.refreshed.json")
    canonical = json.loads((ROOT / "catalogs/convergence-practice/public-starred.json").read_text())
    historical = read("historical-undecided.json")
    index = read("jev-inventory.json")
    upstream = read("upstream-sources.json")
    routing = read("routing.json")["repositories"]
    proposal = read("manifest-proposal.json")["rows"]
    contexts = read("layer-contexts.json")["layers"]
    protocol = read("protocol.json")
    c = {r["repository"].lower(): r for r in canonical["repositories"]}
    live = {r["repository"].lower() for r in snapshot["repositories"]}
    prior = set(historical["undecided_identities"])
    assert len(live) == 380 and len(c) == 373
    assert len(live - set(c)) == 7 and not set(c) - live
    assert len(prior & set(c)) == 26 and len(prior - set(c)) == 7
    checks.append("native snapshot and historical identity reconciliation")
    for row in snapshot["repositories"]:
        assert set(row) <= set(PUBLIC_FIELDS + REVIEW_FIELDS)
        assert not any(key in row for key in ("owner", "permissions", "private", "token", "account"))
    checks.append("native builder public/review field allowlist; no raw API row")
    index_text = (HERE / "upstream/awesome-jev-projects.README.md").read_text()
    source_names = {m.lower() for m in re.findall(
        r"^- \[\*\*[^\n]*?\*\*\]\(https://github.com/([\w.-]+/[\w.-]+)\)", index_text, re.M)}
    assert len(source_names) == 864
    organization_names = {r["repository"].lower() for r in upstream["typesafe_public_organization"]["repositories"]}
    expected = source_names | organization_names | {"logicrw/awesome-jev-projects"} | prior | (live - set(c))
    actual = {r["repository"] for r in routing}
    assert expected == actual and len(routing) == len(actual) == 908
    assert {r["repository"] for r in proposal} == actual and len(proposal) == 908
    assert len(index["repositories"]) == len({r["repository"] for r in index["repositories"]}) == 875
    checks.append("all pinned project, organization, anchor and historical identities covered exactly once")
    for row in routing:
        assert row["citations"] and row["layer_context_refs"]
        assert row["layers"] and all(layer in contexts for layer in row["layers"])
        if row["repository"] in c:
            previous = c[row["repository"]]
            assert row["canonical_layer_keys"] == previous["layer_keys"]
            assert row["disposition"] == ("OUT-OF-SCOPE" if previous["disposition_status"] == "OUT-OF-SCOPE" else "already adjudicated")
        assert row["disposition"] in ("seed for next sweep", "already adjudicated", "OUT-OF-SCOPE")
    checks.append("existing scope dispositions and canonical layer keys preserved; every row cited and contextualized")
    by_repo = {r["repository"]: r for r in routing}
    assert by_repo["jev-chat/jev-chat-windows"]["disposition"] == "OUT-OF-SCOPE"
    assert by_repo["cmaintz/jev-triage"]["layers"] == ["foundation:git-github-automation"]
    assert by_repo["ethanalgox/jev-trading"]["layers"] == ["us-equities:research-factors-ml"]
    final = json.loads((ROOT / "catalogs/landscape/final-stack.json").read_text())
    assert len(final["layers"]) == 35 and not any(r["terminal_state"] == "FINAL" for r in final["layers"])
    assert not any(r["label"] == "FINAL" or r["install"] or r["invoke"] for r in proposal)
    trial = {r["repository"]: r for r in proposal if r["label"] == "TRIAL"}
    assert set(trial) == {"microsoft/playwright", "typesafe-ai/skills", "typesafe-ai/typesafe-sdk-python"}
    assert trial["typesafe-ai/typesafe-sdk-python"]["pin"] == "f078f1e208a0d885154dc758344ae4fce77ac168"
    assert trial["typesafe-ai/skills"]["pin"] == "65a39f393687675ce170e6094757de20370365b9"
    assert all(re.search(r"[0-9a-f]{40}", r["pin"]) for r in trial.values())
    checks.append("no FINAL promotion, installation or invocation; retained TRIAL role pins only")
    for layer in contexts.values():
        assert layer["latest_completed_sweep"]
        assert layer["covering_sweeps"][-1]["ref"] == layer["latest_completed_sweep"]["ref"]
    research = contexts["us-equities:research-factors-ml"]
    carried = {r["repository"] for r in research["cumulative_unresolved_survivors"]}
    assert "lightgbm-org/lightgbm" in carried
    assert "microsoft/rd-agent" not in carried
    rd = next(r for r in research["latest_candidate_adjudications"] if r["repository"] == "microsoft/rd-agent")
    assert rd["outcome"] == "refuted" and rd["sweep_id"] == "landscape-sweep-20260926"
    checks.append("latest layer covering sweep and substantive carry-forward versus later refutation")
    for path, seal in protocol["inputs"].items():
        raw = (ROOT / path).read_bytes()
        assert len(raw) == seal["bytes"] and hashlib.sha256(raw).hexdigest() == seal["sha256"]
    checks.append("every consumed public input reproduces its recorded SHA256 and size")
    for source in upstream["sources"]:
        assert re.fullmatch(r"[a-f0-9]{40}", source["commit"])
        assert (HERE / source["capture"]).is_file()
    for entry in index["repositories"]:
        if "line" in entry:
            assert entry["repository"] in index_text.splitlines()[entry["line"] - 1].lower() or entry["repository"] == "logicrw/awesome-jev-projects"
    checks.append("fixed public upstream pins and per-project line witnesses")
    result = {"kind": "local_integration", "checks": checks, "passed": len(checks), "failed": 0,
              "rows": len(routing), "consumed_input_seals": len(protocol["inputs"]),
              "boundary": "Offline record consistency only; no candidate screen, model or upstream E2E execution"}
    (HERE / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
