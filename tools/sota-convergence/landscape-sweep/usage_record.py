#!/usr/bin/env python3
"""Measure a sweep run's per-child Claude usage and write the sanitized record the saturation ledger binds.

  usage_record.py --transcript-dir <session>/subagents/workflows/<run id> --out child-usage-<run id>.json
                  [--require-effort max] [--repo-root .]
  usage_record.py --raw-output child-usage-stdout.json --exit-code N --out ...   (wrap output captured earlier)
  # Completed changed-key reruns require an independently proven pair list, its exact contract and journal:
                  [--supersession-proof PROOF --supersession-contract CONTRACT --supersession-journal JOURNAL]

Runs this checkout's vendored examples/claude-native/workflows/child-usage.mjs (node) over the run's transcripts,
which Claude Code keeps under <config dir>/projects/<project>/<session id>/subagents/workflows/<run id>/, and
writes {schema_version, measurement, child_usage} in the shape of
evidence/artifacts/landscape-sweep-20260923-attempts/child-usage-*.json:
  measurement  tool, tool_commit (null when the tool differs from HEAD), tool_sha256, command, exit_code,
               raw_output_sha256 (of the unsanitized stdout), measured_at_utc, note, post_processing when applicable
  child_usage  the post-processed output with transcript_dir rewritten to <session-transcripts>/subagents/workflows/<run id>
The ledger needs child_usage.status "complete" for a completed sweep, reads workflow_run from the last segment of
transcript_dir, and requires lost_workers to equal the incomplete children. An attempt the runtime re-ran under the
same call key (after a usage-limit pause) is under child_usage.superseded_attempts, not a lost child. Before
sanitizing, this wrapper also links children whose issues include "no result entry in journal" to later complete
attempts with the same label, using the journal order that child-usage.mjs summarizeRun preserves in children.
Precondition: sweep.js issues one logical call per label per run; runtime retries may produce multiple attempts.
Without an explicit proven pair list, a label with more than one complete child remains ambiguous and is never
linked. The optional explicit path validates the proof/contract/journal hashes, native started/result identities,
same-label completed children, temporal order and a measured max-only terminal, including explicitly proved
completed replacement chains. Its provenance retains all
three input hashes and the processor hash; no native record or usage counter is changed. The ordinary record carries neither call keys
nor timestamps, so linking observes only a missing result and a later complete same-label attempt. These attempts
keep their superseded_by and observed reason; their usage already counts in by_resolved_model and is never added again. With no
incomplete children or superseded usage_issues left, status becomes complete and reason counts the new links.
An effort mismatch of a superseded attempt is covered only by its same-label re-run completed at the required
effort. measurement.exit_code and raw_output_sha256 remain the tool's raw result; post_processing names the
links and covered mismatches, including source_status, source_reason, linked_agent_ids, covered_agent_ids and
covered_effort_mismatches. multi_model_children is recomputed over the remaining children after a move.
Refuses to write (exit 3) when the
sanitized record still matches a scripts/validate.py PRIVATE_CONTENT pattern. Exit 1, with the record still written
(a stopped run keeps it as a lower bound), when the post-processed usage is incomplete, when the raw tool exit
cannot be explained by these recoveries, or when an uncovered attempt ran at another effort than --require-effort.
The summary raw_exit_code is the tool's exit code and exit_code is the wrapper's. Every worker of this lane runs at effort max; convert.py retains
uncovered effort_deviations and make_result.py checks them. The summary also names the children whose WebSearch
calls the session's cap refused (child_usage.web_search, measured by child-usage.mjs); convert.py --usage makes each a
web_search_capped retained failure.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sweep_common import REPO_ROOT, private_content, private_findings, sha256_bytes, write_json  # noqa: E402

TOOL = "examples/claude-native/workflows/child-usage.mjs"
MARKER = "/subagents/workflows/"
NOTE = ("Per-request provider usage of the Claude workflow children, from the retained native transcripts (message "
        "ids counted once). web_search counts each child's WebSearch calls and those the session's WebSearch cap "
        "refused (capped). The GPT-6 jobs are Codex usage, retained per job in the run's returns (raw and "
        "gpt6_usage); the two counters are never summed.")
SAME_LABEL_REASON = "no result entry; a later complete attempt with the same label returned; call keys not compared"
EXPLICIT_REASON = "completed attempt superseded by the proven later same-label changed-key rerun"


def measured_at_required_effort(attempt: dict, required: str = "max") -> bool:
    """Affirmative per-request measurement, never an effort set with unknown requests hidden in it."""
    return (isinstance(attempt, dict) and attempt.get("efforts") == [required]
            and type(attempt.get("requests")) is int and attempt["requests"] > 0
            and type(attempt.get("unknown_effort_requests")) is int and attempt["unknown_effort_requests"] == 0)


def known_attempt_effort(attempt: dict) -> bool:
    """A completed attempt needs effort measurements; an interrupted zero-request attempt has none to lose."""
    efforts = attempt.get("efforts")
    return (type(attempt.get("unknown_effort_requests")) is int and attempt["unknown_effort_requests"] == 0
            and type(attempt.get("requests")) is int and attempt["requests"] >= 0
            and (attempt["requests"] > 0 and isinstance(efforts, list) and bool(efforts)
                 and all(isinstance(effort, str) and bool(effort.strip()) for effort in efforts) or
                 attempt.get("complete") is False and attempt["requests"] == 0))


def proven_supersessions(output: dict, proof_path: Path, contract_path: Path, journal_path: Path,
                        required: str) -> tuple:
    """Validate the caller-supplied post-run proof against its contract, journal and measured children.

    This consumes a proof; it does not infer supersession, recompute native call keys or change native state.
    """
    proof_bytes, contract_bytes, journal_bytes = (path.read_bytes() for path in
                                                 (proof_path, contract_path, journal_path))
    proof, contract = json.loads(proof_bytes), json.loads(contract_bytes)
    if not isinstance(proof, dict) or not isinstance(contract, dict):
        raise ValueError("supersession proof and contract must be objects")
    run = str(output.get("transcript_dir") or "").rstrip("/").rsplit("/", 1)[-1]
    native, prefix = proof.get("nativeRun"), proof.get("originalPrefix")
    if not isinstance(native, dict) or not isinstance(prefix, dict):
        raise ValueError("supersession proof needs nativeRun and originalPrefix objects")
    if (proof.get("status") != "proved-actual-resumed-run" or native.get("status") != "completed"
            or native.get("runId") != run or contract.get("workflow") != run
            or proof.get("reexecutedResultEqualsNative") is not True
            or prefix.get("byteEqual") is not True):
        raise ValueError("supersession proof does not establish this completed resumed run")
    if (proof.get("contractSha256") != sha256_bytes(contract_bytes)
            or proof.get("finalJournalSha256") != sha256_bytes(journal_bytes)):
        raise ValueError("supersession proof contract or journal hash mismatch")
    pairs, calls, reruns = proof.get("supersessionPairs"), contract.get("calls"), proof.get("reruns")
    if (not isinstance(pairs, list) or not pairs or not isinstance(calls, list) or not isinstance(reruns, list)
            or len(pairs) != len(calls) or len(pairs) != len(reruns)
            or not all(isinstance(row, dict) for row in [*pairs, *calls, *reruns])):
        raise ValueError("supersession proof needs one pair and rerun for every contract call")
    if required != "max" and any(call.get("require_actual_later_complete_max_child") is True for call in calls):
        raise ValueError("the bound supersession contract requires max effort")
    children = output.get("children") or []
    measured_ids = [c.get("agent_id") for c in children if isinstance(c, dict) and c.get("agent_id")]
    if len(set(measured_ids)) != len(measured_ids):
        raise ValueError("supersession summary repeats a measured child identity")
    by_id = {c.get("agent_id"): (i, c) for i, c in enumerate(children) if isinstance(c, dict)}
    starts, results = {}, {}
    for index, line in enumerate(journal_bytes.decode("utf-8").splitlines()):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("supersession journal has a non-object row")
        if row.get("type") == "started":
            identity = (row.get("key"), row.get("label"), index)
            if row.get("agentId") in starts:
                raise ValueError("supersession journal repeats a started agent identity")
            starts[row.get("agentId")] = identity
        elif row.get("type") == "result":
            agent_id, key = row.get("agentId"), row.get("key")
            start = starts.get(agent_id)
            if start is None or start[0] != key or start[2] >= index:
                raise ValueError("supersession result did not follow its started identity")
            if (agent_id, key) in results:
                raise ValueError("supersession journal repeats a result identity")
            results[(agent_id, key)] = index
    old_ids, new_ids = set(), set()
    replacements, terminal_by_label = {}, {}
    for pair in pairs:
        fields = ("label", "superseded_agent_id", "superseded_key", "superseded_by_agent_id", "superseded_by_key")
        if not all(isinstance(pair.get(field), str) and pair[field] for field in fields):
            raise ValueError("supersession pair lacks an identity, label or key")
        label, old, old_key, new, new_key = (pair[field] for field in fields)
        if old in old_ids or new in new_ids or old == new or old_key == new_key:
            raise ValueError("supersession pairs repeat an identity or do not change the call key")
        old_ids.add(old)
        new_ids.add(new)
        replacements[old] = new
        plan = next((c for c in calls if c.get("label") == label and c.get("original_agent_id") == old
                     and c.get("original_key") == old_key), None)
        rerun = next((r for r in reruns if r.get("label") == label and r.get("agentId") == new
                      and r.get("key") == new_key and r.get("supersedesAgentId") == old
                      and r.get("supersedesKey") == old_key), None)
        if (plan is None or rerun is None or rerun.get("transcriptPromptEqual") is not True
                or rerun.get("nativeResultPresent") is not True):
            raise ValueError("supersession pair is absent from the contract or proved reruns")
        approved = plan.get("approved_rerun_key")
        if ((approved is not None and approved != new_key)
                or (approved is None and (plan.get("new_key_must_be_computed_from_actual_max_discovery") is not True
                                         or rerun.get("keyKind") != "dynamic-recomputed"))):
            raise ValueError("supersession rerun key is neither approved nor proved dynamic")
        for agent_id, key in [(old, old_key), (new, new_key)]:
            start = starts.get(agent_id)
            if start is None or start[:2] != (key, label) or (agent_id, key) not in results:
                raise ValueError("supersession pair does not bind native started and result identities")
            if start[2] >= results[(agent_id, key)]:
                raise ValueError("supersession result did not follow its started identity")
        if results[(old, old_key)] >= starts[new][2]:
            raise ValueError("supersession rerun did not start after its completed original")
        if old not in by_id or new not in by_id:
            raise ValueError("supersession pair has no measured child")
        old_index, original = by_id[old]
        new_index, replacement = by_id[new]
        if (old_index >= new_index or original.get("complete") is not True or replacement.get("complete") is not True
                or original.get("label") != label or replacement.get("label") != label):
            raise ValueError("supersession needs measured complete same-label children and a later rerun")
        if not known_attempt_effort(original):
            raise ValueError("supersession original has missing or unknown request effort measurements")
    # A proved repair may supersede a completed mixed-effort replacement. Every edge stays explicit; only the
    # terminal child establishes required-effort coverage, and repeated labels must resolve to one terminal.
    for pair in pairs:
        target, seen = pair["superseded_agent_id"], set()
        while target in replacements:
            if target in seen:
                raise ValueError("supersession pairs contain a cycle")
            seen.add(target)
            target = replacements[target]
        terminal = by_id[target][1]
        if not measured_at_required_effort(terminal, required):
            raise ValueError("supersession chain does not end at measured required effort")
        label = pair["label"]
        if label in terminal_by_label and terminal_by_label[label] != target:
            raise ValueError("same-label supersession pairs have ambiguous terminals")
        terminal_by_label[label] = target
    for label, terminal_id in terminal_by_label.items():
        authorized = {pair[field] for pair in pairs if pair["label"] == label
                      for field in ("superseded_agent_id", "superseded_by_agent_id")}
        completed = [child for child in children if isinstance(child, dict)
                     and child.get("complete") is True and child.get("label") == label]
        if any(child.get("agent_id") not in authorized for child in completed):
            raise ValueError("completed same-label child is outside the proven supersession chain")
        active = [child["agent_id"] for child in completed if child["agent_id"] not in old_ids]
        if active != [terminal_id]:
            raise ValueError("supersession label does not have exactly one authorized active terminal")
    return pairs, {"proof_sha256": sha256_bytes(proof_bytes), "contract_sha256": sha256_bytes(contract_bytes),
                   "journal_sha256": sha256_bytes(journal_bytes), "processor_sha256": sha256_bytes(Path(__file__).read_bytes()),
                   "pairs": pairs}


def superseded_at_required_effort(attempt: dict, output: dict, required: str = "max") -> bool:
    """Whether this attempt's superseded_by chain ends at a complete same-label re-run at `required` effort.

    Follow agent ids, never just a repeated label; an absent target, another label or a cycle covers nothing.
    Native same-key retries and explicit completed replacements can both chain; even a complete intermediate
    attempt must follow its superseded_by edge before terminal required-effort coverage is established.
    """
    if not isinstance(attempt, dict):
        return False
    label = attempt.get("label") or attempt.get("child") or attempt.get("agent_id")
    if not label:
        return False
    attempts = [*(output.get("children") or []), *(output.get("superseded_attempts") or [])]
    # Native mismatch rows name a label, not a source identity. Resolve them to retained measured attempts
    # before deciding coverage; a bare mismatch's effort set is not request accounting.
    sources = ([attempt] if attempt.get("agent_id") else
               [c for c in attempts if isinstance(c, dict) and c.get("label") == label
                and c.get("efforts") == attempt.get("efforts")
                and c.get("superseded_by") == attempt.get("superseded_by")])
    if not sources or not all(known_attempt_effort(c) for c in sources):
        return False
    by_id = {c["agent_id"]: c for c in attempts if isinstance(c, dict) and c.get("agent_id")}
    seen = {attempt.get("agent_id")}
    target_id = attempt.get("superseded_by")
    while target_id and target_id not in seen:
        seen.add(target_id)
        target = by_id.get(target_id)
        if not target or (target.get("label") or target.get("agent_id")) != label:
            return False
        if target.get("superseded_by"):
            if not known_attempt_effort(target):
                return False
            target_id = target["superseded_by"]
            continue
        if target.get("complete") is True:
            return measured_at_required_effort(target, required)
        target_id = target.get("superseded_by")
    return False


def post_process(output: dict, required: str, explicit_pairs=(), explicit_provenance=None) -> dict:
    """Link no-result attempts in journal order, assuming one logical call per label per run.

    A label with multiple complete children is ambiguous unless the caller supplies validated explicit pairs.
    Call keys are not available in the native summary; explicit pairs are checked against the bound journal.
    """
    children = output.get("children") or []
    complete_counts = Counter(c.get("label") for c in children if isinstance(c, dict) and c.get("complete") is True)
    linked, retained = [], []
    replacements = {pair["superseded_agent_id"]: pair["superseded_by_agent_id"] for pair in explicit_pairs}
    for i, child in enumerate(children):
        if isinstance(child, dict) and child.get("agent_id") in replacements:
            linked.append(dict(child, superseded_by=replacements[child["agent_id"]], reason=EXPLICIT_REASON))
            continue
        if (not isinstance(child, dict) or child.get("complete") is True or not child.get("label")
                or "no result entry in journal" not in (child.get("issues") or [])
                or complete_counts[child["label"]] != 1):
            retained.append(child)
            continue
        later = next((c for c in children[i + 1:] if isinstance(c, dict) and c.get("complete") is True
                      and c.get("label") == child["label"] and c.get("agent_id")
                      and c["agent_id"] != child.get("agent_id")), None)
        if later:
            linked.append(dict(child, superseded_by=later["agent_id"], reason=SAME_LABEL_REASON))
        else:
            retained.append(child)
    source_status = output["status"]
    source_reason = output.get("reason")
    if linked:
        output["children"] = retained
        output["superseded_attempts"] = [*(output.get("superseded_attempts") or []), *linked]
        output["multi_model_children"] = [c.get("label") or c.get("agent_id") for c in retained
                                          if isinstance(c, dict) and len(c.get("resolved_models") or []) > 1]
        incomplete = sum(not isinstance(c, dict) or c.get("complete") is not True for c in retained)
        uncounted = sum(bool(c.get("usage_issues")) for c in output["superseded_attempts"] if isinstance(c, dict))
        output["status"] = "incomplete" if incomplete or uncounted else "complete"
        gaps = [f"{incomplete} child(ren) incomplete" if incomplete else None,
                f"{uncounted} superseded attempt(s) with usage_issues" if uncounted else None]
        description = ("attempt(s) linked with explicit proven supersession" if explicit_pairs else
                       f"incomplete attempt(s) linked to later complete same-label attempts: {SAME_LABEL_REASON}")
        output["reason"] = (f"{len(linked)} {description}; "
                            + ("; ".join(g for g in gaps if g) or "every remaining child is complete"))
    # The raw tool's mismatches name labels, not agent ids. Bind each newly linked finding to its re-run before
    # filtering; other mismatches with that label (including an unsuperseded non-max attempt) remain uncovered.
    mismatches = [dict(item) if isinstance(item, dict) else item for item in output.get("effort_mismatches") or []]
    for child in linked:
        finding = next((item for item in mismatches if isinstance(item, dict) and not item.get("superseded_by")
                        and item.get("child") == (child.get("label") or child.get("agent_id"))
                        and item.get("efforts") == child.get("efforts")), None)
        if finding is not None:
            finding["superseded_by"] = child["superseded_by"]
    covered, uncovered = [], []
    for item in mismatches:
        (covered if superseded_at_required_effort(item, output, required) else uncovered).append(item)
    if "effort_mismatches" in output:
        output["effort_mismatches"] = uncovered
    attempts = [*(output.get("children") or []), *(output.get("superseded_attempts") or [])]
    covered_ids = [c["agent_id"] for c in attempts if isinstance(c, dict) and c.get("agent_id")
                   and c.get("efforts") != [required] and superseded_at_required_effort(c, output, required)]
    name = ("link_proven_completed_attempts_and_incomplete_retries" if explicit_pairs else
            "link_incomplete_children_to_later_complete_same_label")
    return {"name": name, "linked_attempts": len(linked),
            "effort_mismatches_covered": len(covered), "source_status": source_status, "source_reason": source_reason,
            "linked_agent_ids": [c.get("agent_id") for c in linked], "covered_agent_ids": covered_ids,
            "covered_effort_mismatches": covered,
            **({"explicit_supersession": explicit_provenance} if explicit_provenance is not None else {})}


def sanitize_transcript_dir(path: str) -> str:
    text = str(path).rstrip("/")
    if MARKER in text:
        return "<session-transcripts>" + MARKER + text.split(MARKER, 1)[1]
    return "<session-transcripts>/" + text.rsplit("/", 1)[-1]


def tool_commit(repo_root: Path) -> str | None:
    def git(*args):
        try:
            return subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True, check=False)
        except OSError:
            return None
    head = git("rev-parse", "HEAD")
    changed = git("diff", "--quiet", "HEAD", "--", TOOL)
    if head is None or head.returncode != 0 or changed is None or changed.returncode != 0:
        return None
    return head.stdout.strip()


def record(raw: bytes, exit_code: int, command: str, repo_root: Path, measured_at: str | None = None,
           required_effort: str = "max", supersession_proof: Path = None,
           supersession_contract: Path = None, supersession_journal: Path = None) -> dict:
    output = json.loads(raw)
    if not isinstance(output, dict) or "status" not in output:
        raise ValueError("child-usage output is not a run summary (no status)")
    output = dict(output)
    supplied = (supersession_proof, supersession_contract, supersession_journal)
    if any(path is not None for path in supplied) and not all(path is not None for path in supplied):
        raise ValueError("explicit supersession requires the proof, contract and native journal")
    pairs, provenance = proven_supersessions(output, *supplied, required_effort) if all(supplied) else ((), None)
    processing = post_process(output, required_effort, pairs, provenance)
    output["transcript_dir"] = sanitize_transcript_dir(output.get("transcript_dir") or "")
    return {"schema_version": 1,
            "measurement": {"tool": f"native-agent-stack {TOOL}", "tool_commit": tool_commit(repo_root),
                            "tool_sha256": sha256_bytes((repo_root / TOOL).read_bytes()), "command": command,
                            "exit_code": exit_code, "raw_output_sha256": sha256_bytes(raw),
                            "measured_at_utc": measured_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "note": NOTE, "post_processing": processing},
            "child_usage": output}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--transcript-dir", help="the run's transcript directory (the Workflow tool prints it)")
    source.add_argument("--raw-output", type=Path, help="child-usage.mjs stdout captured earlier")
    parser.add_argument("--exit-code", type=int, help="with --raw-output: the tool's exit code")
    parser.add_argument("--require-effort", default="max", help="child-usage.mjs --require-effort (default max)")
    parser.add_argument("--supersession-proof", type=Path, help="proven post-run supersessionPairs (never inferred)")
    parser.add_argument("--supersession-contract", type=Path, help="the exact contract bound by the proof")
    parser.add_argument("--supersession-journal", type=Path, help="the exact native journal bound by the proof")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    repo = args.repo_root.resolve()
    try:
        if args.transcript_dir:
            done = subprocess.run(["node", str(repo / TOOL), args.transcript_dir, "--require-effort", args.require_effort],
                                  capture_output=True, check=False)
            if not done.stdout.strip():
                raise ValueError(f"child-usage.mjs printed nothing (exit {done.returncode}): "
                                 f"{done.stderr.decode('utf-8', 'replace').strip()[:300]}")
            raw, code, run_dir = done.stdout, done.returncode, args.transcript_dir
        else:
            if args.exit_code is None:
                raise ValueError("--raw-output needs --exit-code")
            raw, code = args.raw_output.read_bytes(), args.exit_code
            run_dir = json.loads(raw).get("transcript_dir") or ""
        command = f"node {TOOL} {sanitize_transcript_dir(run_dir)} --require-effort {args.require_effort}"
        document = record(raw, code, command, repo, required_effort=args.require_effort,
                          supersession_proof=args.supersession_proof, supersession_contract=args.supersession_contract,
                          supersession_journal=args.supersession_journal)
        findings = private_findings(document, private_content(repo))
    except (ValueError, OSError) as error:
        print(f"usage_record.py: {error}", file=sys.stderr)
        return 2
    if findings:
        print("refusing to write: possible private content (text not shown):", file=sys.stderr)
        for pointer, kind in findings:
            print(f"  {pointer}: {kind}", file=sys.stderr)
        return 3
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.out, document)
    usage = document["child_usage"]
    children = usage.get("children") or []
    mismatches = usage.get("effort_mismatches") or []
    attempts = [*children, *(usage.get("superseded_attempts") or [])]
    off = any(isinstance(c, dict) and not measured_at_required_effort(c, args.require_effort)
              and not superseded_at_required_effort(c, usage, args.require_effort) for c in attempts)
    processing = document["measurement"]["post_processing"]
    recovered = processing["linked_attempts"] or processing["effort_mismatches_covered"]
    wrapper_code = 0 if (usage.get("status") == "complete" and not mismatches and not off
                         and (code == 0 or code == 1 and recovered)) else 1
    print(json.dumps({"out": str(args.out), "status": usage.get("status"), "raw_exit_code": code, "exit_code": wrapper_code,
                      "workflow_run": usage["transcript_dir"].rsplit("/", 1)[-1], "children": len(children),
                      "incomplete": [c.get("label") for c in children if isinstance(c, dict) and c.get("complete") is not True],
                      "superseded_attempts": [c.get("label") for c in usage.get("superseded_attempts") or []
                                              if isinstance(c, dict)],
                      # A superseded attempt whose usage by_resolved_model cannot count makes the status incomplete.
                      "superseded_usage_issues": {c.get("label") or c.get("agent_id"): c["usage_issues"]
                                                  for c in usage.get("superseded_attempts") or []
                                                  if isinstance(c, dict) and c.get("usage_issues")},
                      "effort_mismatches": mismatches,
                      "web_search": usage.get("web_search")},
                     indent=1))
    return wrapper_code


if __name__ == "__main__":
    raise SystemExit(main())
