#!/usr/bin/env python3
"""Codex review gate for the CC landing scripts (corrections #122 and #123, 2026-10-09).

Prints one status line. Exit codes:
  0  the connector finished a review of the read head or of the current head that STARTED at or after the PR's latest review
     trigger, and no review is running;
  3  a review is running (a Running row, or the connector's eyes reaction on the PR), none of the read head or the current head
     that started since the latest trigger has finished, or a summary's newest revision is not its body (poll again);
  4  the latest review ended in a state other than Completed, the summary comment was last edited by an account other than the
     connector (a person decides), or the gate itself failed: any exception prints one fixed line naming only its class, never a
     traceback (which prints file paths) or gh's output (#975 P2);
  5  Codex is unavailable: since the latest trigger it posted a usage-limit or account notice, or showed no
     activity at all for NOSTART_MINUTES (the landing proceeds on its other reviews and logs this line).
     Measured 2026-10-09: the connector answered "You have reached your Codex usage limits" at 22:42:34Z (uet#51)
     and started nothing on nas#885 after its 22:44:17Z ready mark, while it starts within seconds when available
     (uet#47: 11 s; nas#939). A Running review is always waited for.

Sources (the connector's own summary comment, read on uet#47 and nas#939 on 2026-10-09, and captured from nas#975 on 2026-10-11 in
tests/fixtures/landing/codex-summary-comment.json, whose body has sha256 1236fe48…):
  - the comment marked <!-- codex-pull-request-review-summary --> holds one table row per review: the review kind, its status
    "Running since <time>" or "Completed <time>", the reviewed commit's short SHA and the trigger kind;
  - reviews start when a PR is opened for review, when a draft is marked ready, and on an
    "@codex review" or "@codex security review" comment;
  - "Codex reacts with 👀 while any review is running, comments if it has suggestions, and reacts with 👍 once all reviews finish
    with no findings" (the comment's own footer).
Why: uet#40 (correction #122) and uet#47 (correction #123) merged while a Codex review was running.

#975 (Codex P1 at af9d1901, 2026-10-11): a completion is counted only for a review that started at or after the latest trigger.
A review that was running when the trigger came and finished after it is not the requested review, and before, its completion
time alone passed the gate in the gap before the new review's Running row appeared. The connector edits ONE summary comment in
place (measured 2026-10-11 on nas#974, #975, #979 and #994: a row "Running since <start>" | commit | trigger kind becomes
"Completed <end>", and the next review rewrites the row), so a Completed row carries no start. The start comes from the comment's
own revisions (GraphQL IssueComment.userContentEdits, whose `diff` held the whole body of each revision on those PRs): the latest
revision, at or before the completion, that shows the same row (its other cells: review kind, commit, trigger kind) Running. The +1
reaction counts only at or after such a start; a connector review or its no-findings comment names no request and counts for
nothing. Without such a revision nothing is attributed (fail closed: exit 3, or 5 when the connector shows no activity).

#975 round 4 (the CC's micro, the GPT micro and Codex at 761810d7):
  - P2-1: the comments, each summary's body and its revisions are ONE GraphQL query (before, the body came from REST and the
    revisions from a second call, and a review that started between the two reads was paired with the earlier completion: exit 0 for
    a completion before the trigger). A summary whose newest revision is not its body spans an edit and gives 3, so the body and
    its revisions are one state, and a completion pairs only with a start at or before it (trigger <= start <= completion). The
    query runs before the REST reads of the triggers and reactions, so a trigger or a reaction that comes between the reads is newer
    than every start in the snapshot (fail closed).
  - P3-3: the attributed row's commit cell must be a prefix of the read head (the third argument) or of the current head; a review of
    another commit (a force-push after it) is not this landing's review (exit 3).
  - P3-5: comments are read with fullDatabaseId (BigInt, a string), not databaseId (Int; the ids passed 2^31).
  - P3-6: a revision counts only when the connector made it, and a summary last edited by another account stops (exit 4).
  - The connector's eyes reaction on the PR counts as Running (its footer, above).
  - GPT P2: an edit of a summary, or a row's time, at or after the trigger is connector activity, so a completion that cannot be
    attributed stays 3 and never turns into "no connector activity" (5) after NOSTART_MINUTES.

usage: codex_gate.py <owner/repo> <pr> [<read head>]
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone

BOT = "chatgpt-codex-connector[bot]"  # the connector's login in the REST API
ACTOR = "chatgpt-codex-connector"  # the same account in GraphQL: a Bot, whose Actor.login has no [bot] suffix (measured on nas#975, 2026-10-11)
NOSTART_MINUTES = 10
SUMMARY = "codex-pull-request-review-summary"
UNAVAILABLE = re.compile(r"reached your Codex usage limits|create a Codex account", re.I)
ROW = re.compile(r"\*\*(?P<status>[A-Za-z][A-Za-z ]*)\*\*[^|]*?datetime=\"(?P<time>[^\"]+)\"")
TRIGGER = re.compile(r"^\s*@codex (security )?review\b")
COMMIT = re.compile(r"`?(?P<sha>[0-9a-f]{7,40})`?")  # the row's commit cell: the reviewed commit's short SHA, in backticks
# The PR's comments in one query: every page (gh api --paginate: a GraphQL query takes $endCursor and fetches pageInfo), each comment's
# author, time, body and 100 newest revisions (GitHub returns them newest first; a review takes two) with each revision's editor.
COMMENTS = ("query($owner: String!, $repo: String!, $pr: Int!, $endCursor: String) { repository(owner: $owner, name: $repo) { pullRequest(number: $pr) { "
            "comments(first: 100, after: $endCursor) { pageInfo { hasNextPage endCursor } nodes { fullDatabaseId author { __typename login } createdAt body "
            "userContentEdits(first: 100) { nodes { editedAt diff editor { __typename login } } } } } } } }")


def gh(path):
    out = subprocess.run(["gh", "api", "--paginate", "--slurp", path],
                         capture_output=True, text=True, check=True).stdout
    pages = json.loads(out)
    return [item for page in pages for item in page]


def when(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def connector(actor):
    """True for the connector's own account: a Bot with its login (a User could hold the bare login; REST's [bot] form it cannot)."""
    return bool(actor) and actor.get("__typename") == "Bot" and actor.get("login") == ACTOR


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


def comments(repo, pr):
    """The PR's comments as one snapshot: (id, is the connector, created, body, revisions), revisions (edited, by the connector,
    body) oldest first."""
    owner, name = repo.split("/", 1)
    out = subprocess.run(["gh", "api", "graphql", "--paginate", "--slurp", "-f", f"query={COMMENTS}",
                          "-f", f"owner={owner}", "-f", f"repo={name}", "-F", f"pr={pr}"],
                         capture_output=True, text=True, check=True).stdout
    found = []
    for page in json.loads(out):
        for c in page["data"]["repository"]["pullRequest"]["comments"]["nodes"]:
            edits = sorted(((when(n["editedAt"]), connector(n.get("editor")), n.get("diff") or "") for n in c["userContentEdits"]["nodes"]),
                           key=lambda edit: edit[0])
            found.append((c.get("fullDatabaseId"), connector(c.get("author")), when(c["createdAt"]), c.get("body") or "", edits))
    return found


def commit_of(row):
    """The row's commit cell, or None."""
    return next((m["sha"] for m in (COMMIT.fullmatch(cell) for cell in row) if m), None)


def reviewed(row, heads):
    sha = commit_of(row)
    return sha is not None and any(head.startswith(sha) for head in heads)


def running(status):
    return status.lower().startswith("running")


def main(repo, pr, read=None):
    notes = comments(repo, pr)  # first: what comes after this snapshot is newer than every start in it
    pull = json.loads(subprocess.run(["gh", "api", f"repos/{repo}/pulls/{pr}"],
                                     capture_output=True, text=True, check=True).stdout)
    timeline = gh(f"repos/{repo}/issues/{pr}/timeline?per_page=100")
    reactions = gh(f"repos/{repo}/issues/{pr}/reactions?per_page=100")
    heads = [head for head in (read, pull["head"]["sha"]) if head]

    triggers = [when(pull["created_at"])]
    triggers += [when(e["created_at"]) for e in timeline if e.get("event") == "ready_for_review"]
    triggers += [created for _, bot, created, body, _ in notes if not bot and TRIGGER.match(body)]
    trigger = max(triggers)

    summaries = [(ident, body, edits) for ident, bot, _, body, edits in notes if bot and SUMMARY in body]
    for ident, body, edits in summaries:
        if edits and not edits[-1][1]:
            print(f"Codex review summary {ident} was last edited at {edits[-1][0]:%Y-%m-%dT%H:%M:%SZ} by an account other than the "
                  "connector; a person decides")
            return 4
        if edits and edits[-1][2] != body:  # the newest revision is the body (measured on nas#975); otherwise the read spans an edit
            print(f"Codex review summary {ident}: its newest revision, at {edits[-1][0]:%Y-%m-%dT%H:%M:%SZ}, is not its body (read "
                  "during an edit); poll again")
            return 3
    current = [r for _, body, _ in summaries for r in rows(body)]
    now_running = [t for _, s, t in current if running(s)]
    if now_running:
        print(f"Codex review running since {max(now_running):%Y-%m-%dT%H:%M:%SZ}")
        return 3
    eyes = [when(r["created_at"]) for r in reactions if r["user"]["login"] == BOT and r["content"] == "eyes"]
    if eyes:
        print(f"Codex review running: the connector's eyes reaction is on the pull request since {max(eyes):%Y-%m-%dT%H:%M:%SZ}")
        return 3
    reviews, begun, seen = [], [], []  # (row, status, time, start) of each current row; each start of a review of our heads at or
    # after the trigger; each time a revision or a row of a summary shows (connector activity)
    for _, body, edits in summaries:
        bodies = [text for _, bot, text in edits if bot] + [body]
        seen += [edited for edited, bot, _ in edits if bot] + [t for text in bodies for _, _, t in rows(text)]
        starts = [(row, t) for text in bodies for row, s, t in rows(text) if running(s)]
        begun += [t for row, t in starts if t >= trigger and reviewed(row, heads)]
        for row, s, t in rows(body):
            reviews.append((row, s, t, max((start for r, start in starts if r == row and start <= t), default=None)))
    attributed = [(row, s, t) for row, s, t, start in reviews if start is not None and start >= trigger]
    ours = [(s, t) for row, s, t in attributed if reviewed(row, heads)]
    done = [t for s, t in ours if s.lower().startswith("completed")]
    if begun:  # the all-reviews-finished +1, once a review of our heads has started for this trigger
        done += [when(r["created_at"]) for r in reactions
                 if r["user"]["login"] == BOT and r["content"] == "+1" and when(r["created_at"]) >= min(begun)]
    if done:
        print(f"Codex review finished at {max(done):%Y-%m-%dT%H:%M:%SZ} after the latest trigger "
              f"{trigger:%Y-%m-%dT%H:%M:%SZ}")
        return 0
    if ours:
        s, t = max(ours, key=lambda x: x[1])
        print(f"Codex review ended '{s}' at {t:%Y-%m-%dT%H:%M:%SZ}; not Completed")
        return 4
    other = [(t, commit_of(row)) for row, s, t in attributed]
    if other:
        t, sha = max(other, key=lambda x: x[0])
        print(f"no Codex review of the read head or the current head finished since the latest trigger {trigger:%Y-%m-%dT%H:%M:%SZ} "
              f"(the review that ended at {t:%Y-%m-%dT%H:%M:%SZ} was of commit {sha or 'unknown'})")
        return 3
    notices = [created for _, bot, created, body, _ in notes if bot and UNAVAILABLE.search(body) and created >= trigger]
    if notices:
        print(f"Codex unavailable: usage-limit or account notice at {max(notices):%Y-%m-%dT%H:%M:%SZ} "
              f"after the trigger {trigger:%Y-%m-%dT%H:%M:%SZ}; proceeding on the other reviews")
        return 5
    activity = [created for _, bot, created, _, _ in notes if bot and created >= trigger]
    activity += [when(r["created_at"]) for r in reactions if r["user"]["login"] == BOT and when(r["created_at"]) >= trigger]
    activity += [t for t in seen if t >= trigger]
    idle = (datetime.now(timezone.utc) - trigger).total_seconds() / 60
    if not activity and idle >= NOSTART_MINUTES:
        print(f"Codex unavailable: no connector activity in {idle:.0f} min since the trigger "
              f"{trigger:%Y-%m-%dT%H:%M:%SZ}; proceeding on the other reviews")
        return 5
    earlier = [t for _, s, t, start in reviews if t >= trigger and (start is None or start < trigger)]
    if earlier:
        print(f"no Codex review finished since the latest trigger {trigger:%Y-%m-%dT%H:%M:%SZ} (the review that ended at "
              f"{max(earlier):%Y-%m-%dT%H:%M:%SZ} did not start after it)")
        return 3
    print(f"no Codex review finished since the latest trigger {trigger:%Y-%m-%dT%H:%M:%SZ}")
    return 3


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    try:
        code = main(*sys.argv[1:])
    except Exception as error:  # the landing scripts echo this output: a traceback prints file paths, gh's output can carry an address
        print(f"Codex gate error: {type(error).__name__}; details withheld")
        code = 4
    sys.exit(code)
