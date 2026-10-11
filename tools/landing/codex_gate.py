#!/usr/bin/env python3
"""Codex review gate for the CC landing scripts (corrections #122 and #123, 2026-10-09).

Prints one status line. Exit codes:
  0  the connector finished a review that STARTED at or after the PR's latest review trigger, and no review is running;
  3  a review is running, or none that started since the latest trigger has finished (poll again);
  4  the latest review ended in a state other than Completed (a person decides), or the gate itself failed: any exception
     prints one fixed line naming only its class, never a traceback (which prints file paths) or gh's output (#975 P2);
  5  Codex is unavailable: since the latest trigger it posted a usage-limit or account notice, or showed no
     activity at all for NOSTART_MINUTES (the landing proceeds on its other reviews and logs this line).
     Measured 2026-10-09: the connector answered "You have reached your Codex usage limits" at 22:42:34Z (uet#51)
     and started nothing on nas#885 after its 22:44:17Z ready mark, while it starts within seconds when available
     (uet#47: 11 s; nas#939). A Running review is always waited for.

Sources (the connector's own summary comment, read on uet#47 and nas#939 on 2026-10-09):
  - the comment marked <!-- codex-pull-request-review-summary --> holds one table row per review,
    with status "Running since <time>" or "Completed <time>";
  - reviews start when a PR is opened for review, when a draft is marked ready, and on an
    "@codex review" or "@codex security review" comment;
  - the connector reacts +1 once all reviews finish with no findings, and comments when it has suggestions.
Why: uet#40 (correction #122) and uet#47 (correction #123) merged while a Codex review was running.

#975 (Codex P1 at af9d1901, 2026-10-11): a completion is counted only for a review that started at or after the latest trigger.
A review that was running when the trigger came and finished after it is not the requested review, and before, its completion
time alone passed the gate in the gap before the new review's Running row appeared. The connector edits ONE summary comment in
place (measured 2026-10-11 on nas#974, #975, #979 and #994: a row "Running since <start>" | commit | trigger kind becomes
"Completed <end>", and the next review rewrites the row), so a Completed row carries no start. The start comes from the comment's
own revisions (GraphQL IssueComment.userContentEdits, whose `diff` held the whole body of each revision on those PRs): the latest
earlier revision that shows the same row (its other cells: review kind, commit, trigger kind) Running. The +1 reaction counts only
at or after such a start; a connector review or its no-findings comment names no request and counts for nothing. Without such a
revision nothing is attributed (fail closed: exit 3, or 5 when the connector shows no activity).

usage: codex_gate.py <owner/repo> <pr>
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone

BOT = "chatgpt-codex-connector[bot]"
NOSTART_MINUTES = 10
SUMMARY = "codex-pull-request-review-summary"
UNAVAILABLE = re.compile(r"reached your Codex usage limits|create a Codex account", re.I)
ROW = re.compile(r"\*\*(?P<status>[A-Za-z][A-Za-z ]*)\*\*[^|]*?datetime=\"(?P<time>[^\"]+)\"")
TRIGGER = re.compile(r"^\s*@codex (security )?review\b")
# The revisions of the PR's comments, every page of comments (gh api --paginate: a GraphQL query takes $endCursor and fetches pageInfo),
# each comment's 100 newest revisions (GitHub returns them newest first; a review takes two), keyed by databaseId, the REST comment's id.
EDITS = ("query($owner: String!, $repo: String!, $pr: Int!, $endCursor: String) { repository(owner: $owner, name: $repo) { pullRequest(number: $pr) { "
         "comments(first: 100, after: $endCursor) { pageInfo { hasNextPage endCursor } nodes { databaseId userContentEdits(first: 100) { nodes { editedAt diff } } } } } } }")


def gh(path):
    out = subprocess.run(["gh", "api", "--paginate", "--slurp", path],
                         capture_output=True, text=True, check=True).stdout
    pages = json.loads(out)
    return [item for page in pages for item in page]


def when(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def rows(body):
    """(row, status, time) for each summary-table row; row is the row's other cells (review kind, commit, trigger kind)."""
    found = []
    for line in (body or "").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        for i, cell in enumerate(cells):
            m = ROW.search(cell)
            if m:
                found.append((tuple(cells[:i] + cells[i + 1:]), m["status"].strip(), when(m["time"])))
                break
    return found


def revisions(repo, pr):
    """{REST comment id: its recorded bodies, oldest first} for the PR's comments."""
    owner, name = repo.split("/", 1)
    out = subprocess.run(["gh", "api", "graphql", "--paginate", "--slurp", "-f", f"query={EDITS}",
                          "-f", f"owner={owner}", "-f", f"repo={name}", "-F", f"pr={pr}"],
                         capture_output=True, text=True, check=True).stdout
    found = {}
    for page in json.loads(out):
        for c in page["data"]["repository"]["pullRequest"]["comments"]["nodes"]:
            edits = sorted(((when(n["editedAt"]), n.get("diff") or "") for n in c["userContentEdits"]["nodes"]), key=lambda edit: edit[0])
            found[c["databaseId"]] = [body for _, body in edits]
    return found


def running(status):
    return status.lower().startswith("running")


def main(repo, pr):
    head = json.loads(subprocess.run(["gh", "api", f"repos/{repo}/pulls/{pr}"],
                                     capture_output=True, text=True, check=True).stdout)
    comments = gh(f"repos/{repo}/issues/{pr}/comments?per_page=100")
    timeline = gh(f"repos/{repo}/issues/{pr}/timeline?per_page=100")

    triggers = [when(head["created_at"])]
    triggers += [when(e["created_at"]) for e in timeline if e.get("event") == "ready_for_review"]
    triggers += [when(c["created_at"]) for c in comments
                 if c["user"]["login"] != BOT and TRIGGER.match(c.get("body") or "")]
    trigger = max(triggers)

    summaries = [c for c in comments if c["user"]["login"] == BOT and SUMMARY in (c.get("body") or "")]
    current = [r for c in summaries for r in rows(c["body"])]
    now_running = [t for _, s, t in current if running(s)]
    if now_running:
        print(f"Codex review running since {max(now_running):%Y-%m-%dT%H:%M:%SZ}")
        return 3
    reviews, begun = [], []  # (status, time, start) of each current row; every start at or after the trigger
    recorded = revisions(repo, pr) if summaries else {}
    for c in summaries:
        bodies = recorded.get(c["id"], []) + [c["body"]]
        starts = [(row, t) for body in bodies for row, s, t in rows(body) if running(s)]
        begun += [t for _, t in starts if t >= trigger]
        for row, s, t in rows(c["body"]):
            reviews.append((s, t, next((start for r, start in reversed(starts) if r == row), None)))
    ours = [(s, t) for s, t, start in reviews if start is not None and start >= trigger]
    done = [t for s, t in ours if s.lower().startswith("completed")]
    if begun:  # the all-reviews-finished +1, once a review for this trigger has started
        done += [when(r["created_at"]) for r in gh(f"repos/{repo}/issues/{pr}/reactions?per_page=100")
                 if r["user"]["login"] == BOT and r["content"] == "+1" and when(r["created_at"]) >= min(begun)]
    if done:
        print(f"Codex review finished at {max(done):%Y-%m-%dT%H:%M:%SZ} after the latest trigger "
              f"{trigger:%Y-%m-%dT%H:%M:%SZ}")
        return 0
    if ours:
        s, t = max(ours, key=lambda x: x[1])
        print(f"Codex review ended '{s}' at {t:%Y-%m-%dT%H:%M:%SZ}; not Completed")
        return 4
    notices = [when(c["created_at"]) for c in comments
               if c["user"]["login"] == BOT and UNAVAILABLE.search(c.get("body") or "")
               and when(c["created_at"]) >= trigger]
    if notices:
        print(f"Codex unavailable: usage-limit or account notice at {max(notices):%Y-%m-%dT%H:%M:%SZ} "
              f"after the trigger {trigger:%Y-%m-%dT%H:%M:%SZ}; proceeding on the other reviews")
        return 5
    activity = [when(c["created_at"]) for c in comments if c["user"]["login"] == BOT and when(c["created_at"]) >= trigger]
    activity += [when(r["created_at"]) for r in gh(f"repos/{repo}/issues/{pr}/reactions?per_page=100")
                 if r["user"]["login"] == BOT and when(r["created_at"]) >= trigger]
    idle = (datetime.now(timezone.utc) - trigger).total_seconds() / 60
    if not activity and idle >= NOSTART_MINUTES:
        print(f"Codex unavailable: no connector activity in {idle:.0f} min since the trigger "
              f"{trigger:%Y-%m-%dT%H:%M:%SZ}; proceeding on the other reviews")
        return 5
    earlier = [t for s, t, start in reviews if t >= trigger and (start is None or start < trigger)]
    if earlier:
        print(f"no Codex review finished since the latest trigger {trigger:%Y-%m-%dT%H:%M:%SZ} (the review that ended at "
              f"{max(earlier):%Y-%m-%dT%H:%M:%SZ} did not start after it)")
        return 3
    print(f"no Codex review finished since the latest trigger {trigger:%Y-%m-%dT%H:%M:%SZ}")
    return 3


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    try:
        code = main(sys.argv[1], sys.argv[2])
    except Exception as error:  # the landing scripts echo this output: a traceback prints file paths, gh's output can carry an address
        print(f"Codex gate error: {type(error).__name__}; details withheld")
        code = 4
    sys.exit(code)
