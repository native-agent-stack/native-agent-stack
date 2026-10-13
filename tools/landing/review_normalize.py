#!/usr/bin/env python3
"""Write one normalized review for codex_gate.py's local review set (LOCAL_REVIEWS; tools/landing/README.md, "Local reviews").

The owner's direction of 2026-10-13: reviews run locally, and the ChatGPT connector cannot reach the organization's repository. Two
reviewers are read, each through its own supported output, and neither is changed:

  codex-review        `codex review` (codex-cli 0.162.1), which the co-op's codex_review_read.sh runs in a detached worktree at the head
                      against a base. Its session rollout holds the request, an EnteredReviewMode item with its target, and the result,
                      an ExitedReviewMode item whose review_output has findings (title, body, confidence_score, priority,
                      code_location) and overall_correctness (openai/codex@rust-v0.162.1 codex-rs/protocol/src/items.rs:173-183,
                      protocol.rs:3503-3545). The first session_meta line names the worktree (cwd), the commit it was at (git.commit_hash)
                      and the CLI version (cli_version).
  claude-code-review  Claude Code's official /code-review plugin (anthropics/claude-plugins-official@f359d43b,
                      plugins/code-review/commands/code-review.md), which posts ONE comment on the pull request in a fixed format
                      (:50-92): "### Code review", then "Found N issues:" with numbered issues, each followed by a link to the code at a full
                      commit SHA, or "No issues found. Checked for bugs and CLAUDE.md compliance." Every issue it posts passed its own
                      confidence filter of 80 or more (:20-26), so each is priority 1; no finer priority is invented. The gate treats
                      this arm as advisory until the CC's review-replay addendum measures it (arms E and F).

The normalized review is one JSON object with exactly these fields; a finding carries no prose body:
  {"reviewer": "codex-review" | "claude-code-review", "reviewer_version": "<text>", "head_sha": "<40 lower-case hex digits>",
   "completed": true | false, "findings": [{"priority": 0 | 1 | 2 | 3, "location": "<path>:<start>-<end>" or "", "title": "<text>"}]}
A codex-review also carries Codex's verdict, "overall_correctness", as Codex wrote it (rubric.md:85 fixes "patch is correct" | "patch is
incorrect", the wire type is a free String, protocol.rs:3507; null when the review was interrupted), and "overall_confidence_score" when
the result has one (protocol.rs:3509). The gate blocks on "patch is incorrect" and stops on any other value than those two.

completed is false when the reviewer gave no structured result: a Codex review interrupted (review_output null) or whose JSON did not parse
(Codex then keeps the text in overall_explanation and leaves findings empty and overall_correctness "", review.rs:188-208), or no plugin
comment since the run started (the plugin posts none for a closed, draft, trivial or already reviewed pull request, nor when no issue scored
80, README.md:157-167; code-review.md:11, :26). The gate stops on such a codex-review file (2) and notes such a plugin file as advisory.

The plugin's head: "the PR head at the time of the comment" is the head the caller read before the run (--head), which must still be the pull
request's head when the comment is read, the comment bound to the run by --since. Exit codes: 0 the file was written; 1 the input was refused
and nothing was written (the reason is printed, never a path, a body or a title); 2 usage.

usage:
  review_normalize.py codex-review --rollout <rollout.jsonl> [--head <sha>] --out <file>
  review_normalize.py claude-code-review --repo <owner/repo> --pr <n> --head <sha> --since <UTC time> --author <login>
                                         --reviewer-version <text> --out <file>
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
from collections import Counter
from datetime import datetime

SHA = re.compile(r"[0-9a-f]{40}")
LOGIN = re.compile(r"[A-Za-z0-9](-?[A-Za-z0-9])*")  # GitHub's login shape, at most 39 characters (README sources)
REPO = re.compile(r"[A-Za-z0-9](-?[A-Za-z0-9])*/[A-Za-z0-9._-]+")
VERDICTS = ("patch is correct", "patch is incorrect")  # the rubric's overall_correctness (codex-rs/prompts/templates/review/rubric.md:85)
HEADING = "### Code review"
FOUND = re.compile(r"Found (\d+) issues?:")
ITEM = re.compile(r"(\d+)\. (\S.*)")
LINK = re.compile(r"https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9._-]+/blob/[0-9a-f]{40}/([^\s#<>()\[\]]+)(?:#L(\d+)(?:-L(\d+))?)?")
# The plugin's comment and the pull request's head in one snapshot (every page: gh api --paginate needs $endCursor and pageInfo).
COMMENTS = ("query($owner: String!, $repo: String!, $pr: Int!, $endCursor: String) { repository(owner: $owner, name: $repo) { pullRequest(number: $pr) { "
            "headRefOid comments(first: 100, after: $endCursor) { pageInfo { hasNextPage endCursor } nodes { fullDatabaseId author { login } createdAt "
            "lastEditedAt body } } } } }")


class Refused(Exception):
    """The input cannot give a normalized review; the message is fixed text with values of a checked shape only."""


def when(text):
    moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError("a time without its offset")
    return moment


def where(path, root):
    """A finding's file relative to the reviewed worktree (the rollout's cwd), so no home path is written; another path keeps its form,
    with the home directory written as ~."""
    if isinstance(root, str) and os.path.isabs(root) and os.path.isabs(path) and os.path.commonpath([path, root]) == os.path.normpath(root):
        return os.path.relpath(path, root)
    home = os.path.expanduser("~")
    if home not in ("", "/", "~") and (path == home or path.startswith(home.rstrip("/") + "/")):
        return "~" + path[len(home.rstrip("/")):]
    return path


def codex_review(rollout, head=None):
    """The normalized review of one `codex review` session rollout, and a note for the summary line."""
    meta, entered, exited = None, [], []
    with open(rollout, "rb") as handle:
        for number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                line = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                raise Refused(f"line {number} of the rollout is not JSON") from None
            payload = line.get("payload") if isinstance(line, dict) else None
            if not isinstance(payload, dict):
                continue
            if line.get("type") == "session_meta" and meta is None:
                meta = payload
            item = payload.get("item")
            if line.get("type") == "event_msg" and payload.get("type") == "item_completed" and isinstance(item, dict):
                if item.get("type") == "EnteredReviewMode":
                    entered.append(item)
                elif item.get("type") == "ExitedReviewMode":
                    exited.append(item)
    if meta is None:
        raise Refused("the rollout has no session_meta line")
    if len(entered) != 1 or len(exited) != 1:
        raise Refused(f"the rollout holds {len(entered)} review requests and {len(exited)} review results; one review is needed")
    target = entered[0].get("target")
    kind = target.get("type") if isinstance(target, dict) else None
    if kind != "baseBranch":
        shown = kind if isinstance(kind, str) and re.fullmatch(r"[A-Za-z]{1,40}", kind) else "of another form"
        raise Refused(f"the review's target is {shown}, not baseBranch (the pull request's whole change against its base)")
    commit = (meta.get("git") or {}).get("commit_hash") if isinstance(meta.get("git") or {}, dict) else None
    if not isinstance(commit, str) or not SHA.fullmatch(commit):
        raise Refused("the rollout names no commit (session_meta git.commit_hash)")
    if head is not None and head != commit:
        raise Refused(f"the rollout reviewed {commit[:8]}, not --head {head[:8]}")
    version = meta.get("cli_version")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9A-Za-z.+-]{1,40}", version):
        raise Refused("the rollout's session_meta has no cli_version of the usual form")
    review = {"reviewer": "codex-review", "reviewer_version": f"codex-cli {version}", "head_sha": commit, "completed": False,
              "overall_correctness": None, "findings": []}
    output = exited[0].get("review_output")
    if output is None:
        return review, "the review was interrupted (review_output null)"
    if not isinstance(output, dict) or not isinstance(output.get("overall_correctness"), str) or not isinstance(output.get("findings"), list):
        raise Refused("the review result is not a review_output object")
    review["overall_correctness"] = output["overall_correctness"]  # verbatim: the gate decides on exactly what Codex wrote
    if "overall_confidence_score" in output:
        score = output["overall_confidence_score"]
        if type(score) not in (int, float) or not math.isfinite(score):
            raise Refused("the review result's overall_confidence_score is not a finite number")
        review["overall_confidence_score"] = score
    verdict = output["overall_correctness"].strip()
    if not verdict:
        return review, "the reviewer's JSON did not parse (empty overall_correctness, the fallback of review.rs:188-208)"
    root = meta.get("cwd")
    for number, finding in enumerate(output["findings"], 1):
        location = finding.get("code_location") if isinstance(finding, dict) else None
        lines = location.get("line_range") if isinstance(location, dict) else None
        if (not isinstance(finding, dict) or type(finding.get("priority")) is not int or not 0 <= finding["priority"] <= 3
                or not isinstance(finding.get("title"), str) or not isinstance(location, dict)
                or not isinstance(location.get("absolute_file_path"), str) or not isinstance(lines, dict)
                or type(lines.get("start")) is not int or type(lines.get("end")) is not int):
            raise Refused(f"finding {number} has no priority from 0 to 3, title or code_location")
        review["findings"].append({"priority": finding["priority"], "location":
                                   f"{where(location['absolute_file_path'], root)}:{lines['start']}-{lines['end']}", "title": finding["title"]})
    review["completed"] = True
    raw = output["overall_correctness"]
    return review, f"overall_correctness {raw!r}" if raw in VERDICTS else "overall_correctness of another form (the gate stops on it)"


def plugin_findings(body):
    """The findings of the plugin's comment (code-review.md:50-92): each issue is priority 1, located by its first link to the code."""
    lines = [line.strip() for line in body.replace("\r\n", "\n").split("\n") if line.strip()]
    if not lines or lines[0] != HEADING:
        raise Refused("the comment does not start with the plugin's heading")
    if len(lines) > 1 and lines[1].startswith("No issues found"):
        return []
    found = FOUND.fullmatch(lines[1]) if len(lines) > 1 else None
    if not found:
        raise Refused("the comment is neither the plugin's found-issues list nor its no-issues line")
    items = []
    for line in lines[2:]:
        item = ITEM.fullmatch(line)
        if item and int(item.group(1)) == len(items) + 1:
            items.append({"title": item.group(2), "own": LINK.findall(item.group(2)), "after": []})
        elif items:
            items[-1]["after"] += LINK.findall(line)
    if len(items) != int(found.group(1)) or not items:
        raise Refused(f"the comment announces {found.group(1)} issues and lists {len(items)}")
    findings = []
    for item in items:
        links = item["after"] or item["own"]
        location = ""
        if links:
            path, start, end = links[0]
            location = urllib.parse.unquote(path) + (f":{start}-{end}" if start and end else f":{start}" if start else "")
        findings.append({"priority": 1, "location": location, "title": item["title"]})
    return findings


def claude_review(repo, pr, head, since, author, version):
    """The normalized review of the plugin's comment on the pull request, and a note for the summary line."""
    owner, name = repo.split("/", 1)
    done = subprocess.run(["gh", "api", "graphql", "--paginate", "--slurp", "-f", f"query={COMMENTS}", "-f", f"owner={owner}",
                           "-f", f"repo={name}", "-F", f"pr={pr}"], capture_output=True, text=True)
    if done.returncode != 0:
        raise Refused(f"gh api graphql exited {done.returncode} (its output withheld)")
    try:
        heads, mine = set(), []
        for page in json.loads(done.stdout):
            pull = page["data"]["repository"]["pullRequest"]
            heads.add(pull["headRefOid"])
            for entry in pull["comments"]["nodes"]:
                login = (entry.get("author") or {}).get("login")  # a deleted account's comment has no author
                lines = [line.strip() for line in (entry.get("body") or "").split("\n") if line.strip()]
                if isinstance(login, str) and login.lower() == author.lower() and lines[:1] == [HEADING] and when(entry["createdAt"]) >= since:
                    mine.append(entry)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise Refused("the GraphQL reply is not the pull request with its comments") from None
    if heads != {head}:
        raise Refused(f"the pull request's head is not --head {head[:8]} now (it moved during the review, or --head was not the head)")
    review = {"reviewer": "claude-code-review", "reviewer_version": version, "head_sha": head, "completed": False, "findings": []}
    if not mine:
        return review, "no code-review comment by --author since --since"
    if len(mine) > 1:
        raise Refused(f"{len(mine)} code-review comments by --author since --since; one run posts one")
    if mine[0].get("lastEditedAt") is not None:
        raise Refused("the code-review comment was edited after it was posted")
    review["findings"] = plugin_findings(mine[0].get("body") or "")
    review["completed"] = True
    return review, f"comment {mine[0].get('fullDatabaseId')}" if re.fullmatch(r"[0-9]{1,20}", str(mine[0].get("fullDatabaseId"))) else "comment"


def write(review, out):
    """The file, written whole: a new file made by mkstemp (mode 0600) beside the target, then renamed over it."""
    text = json.dumps(review, indent=1, ensure_ascii=False) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=".review-normalize-", dir=os.path.dirname(os.path.abspath(out)))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, out)
    except BaseException:
        os.unlink(temporary)
        raise


def arguments(argv):
    parser = argparse.ArgumentParser(prog="review_normalize.py", description="Write one normalized review for codex_gate.py's LOCAL_REVIEWS.")
    reviewers = parser.add_subparsers(dest="reviewer", required=True)
    codex = reviewers.add_parser("codex-review", help="from a `codex review` session rollout")
    codex.add_argument("--rollout", required=True, help="the session rollout (.jsonl) of one `codex review` run")
    codex.add_argument("--head", help="the head the run was given; it must be the commit the rollout names")
    codex.add_argument("--out", required=True)
    claude = reviewers.add_parser("claude-code-review", help="from the /code-review plugin's comment on the pull request")
    claude.add_argument("--repo", required=True, help="owner/repo")
    claude.add_argument("--pr", required=True, type=int)
    claude.add_argument("--head", required=True, help="the pull request's head, read before the run")
    claude.add_argument("--since", required=True, help="when the run started, in UTC (date -u +%%FT%%TZ)")
    claude.add_argument("--author", required=True, help="the account that ran the plugin")
    claude.add_argument("--reviewer-version", required=True, help="the plugin's pin and the client's version")
    claude.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.head is not None and not SHA.fullmatch(args.head):
        parser.error("--head must be 40 lower-case hex digits")
    if args.reviewer == "claude-code-review":
        if not REPO.fullmatch(args.repo) or args.pr <= 0:
            parser.error("--repo must be owner/repo and --pr a positive number")
        if not LOGIN.fullmatch(args.author) or len(args.author) > 39:
            parser.error("--author must be a GitHub login")
        if not args.reviewer_version.strip() or "\n" in args.reviewer_version:
            parser.error("--reviewer-version must be one line of text")
        try:
            args.since = when(args.since)
        except ValueError:
            parser.error("--since must be a time with its offset, such as 2026-10-13T01:00:00Z")
    return args


def main(argv=None):
    args = arguments(argv)
    try:
        if args.reviewer == "codex-review":
            review, note = codex_review(args.rollout, args.head)
        else:
            review, note = claude_review(args.repo, args.pr, args.head, args.since, args.author, args.reviewer_version)
        write(review, args.out)
    except Refused as why:
        print(f"review_normalize: {args.reviewer}: refused: {why}; nothing written")
        return 1
    except Exception as error:  # an unreadable file or a failure of this script: one line with the class alone (a traceback names paths)
        print(f"review_normalize: {args.reviewer}: refused: {type(error).__name__}, details withheld; nothing written")
        return 1
    counts = Counter(finding["priority"] for finding in review["findings"])
    state = ("completed" if review["completed"] else "NOT completed (the gate stops on it)" if review["reviewer"] == "codex-review"
             else "NOT completed (advisory: the gate notes it)")
    print(f"review_normalize: {review['reviewer']} of {review['head_sha'][:8]}: {state}; {note}; findings P0 {counts[0]}, P1 {counts[1]}, "
          f"P2 {counts[2]}, P3 {counts[3]}; written to {os.path.basename(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
