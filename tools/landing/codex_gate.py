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
     (uet#47: 11 s; nas#939). A Running review is waited for until it is stale (CC correction #200, below).
  2  only with local reviews (below): a review file is unreadable or malformed, names another head, or did not complete.

CC correction #200 (2026-10-13): a review the summary shows running, with no connector activity after its start for
STALE_RUNNING_MINUTES, is stale and counts as unavailable (5), like the idle rule, never as a finished review: the transfer of
native-agent-stack to an organization cut the connector's access in the middle of a review, whose row stayed Running. Activity is a
connector note other than a summary, a connector reaction, or an edit of a summary; the start itself writes a summary edit and an eyes
reaction within seconds, so the age runs from the LAST activity.

Local reviews (2026-10-13, the owner's direction: reviews run locally, Codex through the gateway on the subscription pool, and the
connector cannot reach the organization's repository): when LOCAL_REVIEWS, or its alias CODEX_LOCAL_REVIEW, names normalized review
files (colon-separated; tools/landing/review_normalize.py writes them; the schema is in the README, "Local reviews"), the gate decides
from the files alone and calls nothing:
  2  a file cannot be read or is not a normalized review; a file names a head that is neither the read head (the third argument) nor a
     head the caller passed after it as carrying the read head's change (the landing scripts' lg_gate passes those); a codex-review did not
     complete, or its overall_correctness is not exactly "patch is correct" or "patch is incorrect" (fail closed); or no completed
     codex-review is listed (the required arm);
  4  otherwise, a codex-review says "patch is incorrect", whatever its findings' priorities, or has a finding of priority 0 or 1: a person
     decides (the CC adjudicates);
  0  otherwise; the P2 and P3 findings are printed as counts, for the pull request's Follow-ups.
The verdict: openai/codex@rust-v0.162.1 codex-rs/prompts/templates/review/rubric.md:85 fixes "overall_correctness": "patch is correct" |
"patch is incorrect", while the wire type is a free String (codex-rs/protocol/src/protocol.rs:3507); the mirror at 092d3acd6 holds the same
bytes of both files. The claude-code-review arm (the /code-review plugin) is ADVISORY until the CC's review-replay addendum measures it
(arms E and F): its issues are printed as a count, each scored 80 or more by the plugin's filter (the comment carries no score), and a run
that posted no comment (completed false: below a score of 80 the plugin does not proceed to its comment, code-review.md:26, and it skips a
pull request it already reviewed, :11) is noted with that citation; neither stops the gate. A malformed file, or one of another head,
stops it whatever its reviewer. A file is named in the output by its place in the list, never by its path, and no finding's text is printed.

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
       with LOCAL_REVIEWS: codex_gate.py <owner/repo> <pr> <read head> [<head carrying the read head's change> ...]
"""
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone

BOT = "chatgpt-codex-connector[bot]"  # the connector's login in the REST API
ACTOR = "chatgpt-codex-connector"  # the same account in GraphQL: a Bot, whose Actor.login has no [bot] suffix (measured on nas#975, 2026-10-11)
NOSTART_MINUTES = 10
# CC 2026-10-13 (correction #200): a review the summary shows running, with no connector note or reaction after its start
# for this long, is stale (the nas transfer to an organization cut the connector's access mid-review); it counts as
# unavailable (5), like the idle rule below, never as a finished review.
STALE_RUNNING_MINUTES = 90
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
# Local reviews (2026-10-13): the variables that name normalized review files (the second is the first's alias), the reviewers
# review_normalize.py writes for, and the normalized review's fields (README "Local reviews"); a finding carries no prose body.
LOCAL = ("LOCAL_REVIEWS", "CODEX_LOCAL_REVIEW")
REVIEWERS = ("codex-review", "claude-code-review")
REQUIRED = "codex-review"  # the required arm; claude-code-review is advisory until the CC's review-replay addendum measures it (arms E, F)
REVIEW_KEYS = frozenset({"reviewer", "reviewer_version", "head_sha", "completed", "findings"})
# A codex-review also carries Codex's verdict (rubric.md:85; protocol.rs:3507 a free String, null when the review was interrupted) and may
# carry its confidence (protocol.rs:3509 overall_confidence_score: f32).
CODEX_KEYS = REVIEW_KEYS | {"overall_correctness"}
CODEX_OPTIONAL = frozenset({"overall_confidence_score"})
CORRECT, INCORRECT = "patch is correct", "patch is incorrect"
FINDING_KEYS = frozenset({"priority", "location", "title"})
SHA = re.compile(r"[0-9a-f]{40}")


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


def local_review_files():
    """The files LOCAL_REVIEWS and its alias CODEX_LOCAL_REVIEW name (colon-separated, each list in order, empty names dropped), or None
    when both are unset or empty: the connector decides then, as before."""
    values = [os.environ.get(name, "") for name in LOCAL]
    if not any(values):
        return None
    return [path for value in values for path in value.split(":") if path]


def unique_keys(pairs):
    """An object whose keys are unique: json.loads keeps the last of a repeated key, so a second "completed" would override the first."""
    if len({key for key, _ in pairs}) != len(pairs):
        raise ValueError("a repeated key")
    return dict(pairs)


def no_constant(name):
    raise ValueError(f"{name} is not JSON")  # json.loads accepts NaN and Infinity unless parse_constant refuses them


def review_problem(review):
    """Why a parsed file is not a normalized review (README "Local reviews"), or None; the reasons are fixed text."""
    if not isinstance(review, dict) or not REVIEW_KEYS <= set(review):
        return "its fields are not reviewer, reviewer_version, head_sha, completed and findings"
    if review["reviewer"] not in REVIEWERS:
        return "its reviewer is not codex-review or claude-code-review"
    if review["reviewer"] == REQUIRED:
        if not CODEX_KEYS <= set(review) <= CODEX_KEYS | CODEX_OPTIONAL:
            return "its fields are not those of a codex-review: reviewer, reviewer_version, head_sha, completed, overall_correctness, findings"
        if review["overall_correctness"] is not None and not isinstance(review["overall_correctness"], str):
            return "its overall_correctness is not text or null"
        if "overall_confidence_score" in review and type(review["overall_confidence_score"]) not in (int, float):
            return "its overall_confidence_score is not a number"
    elif set(review) != REVIEW_KEYS:
        return "its fields are not those of a claude-code-review: reviewer, reviewer_version, head_sha, completed, findings"
    if not isinstance(review["reviewer_version"], str) or not review["reviewer_version"].strip():
        return "its reviewer_version is empty or not a string"
    if not isinstance(review["head_sha"], str) or not SHA.fullmatch(review["head_sha"]):
        return "its head_sha is not 40 lower-case hex digits"
    if not isinstance(review["completed"], bool):
        return "its completed is not true or false"
    if not isinstance(review["findings"], list):
        return "its findings are not a list"
    for number, finding in enumerate(review["findings"], 1):
        if not isinstance(finding, dict) or set(finding) != FINDING_KEYS or type(finding["priority"]) is not int \
                or not 0 <= finding["priority"] <= 3 or not isinstance(finding["location"], str) or not isinstance(finding["title"], str):
            return f"its finding {number} is not a priority 0 to 3 with a location and a title"
    return None


def local_gate(paths, read, heads):
    """The decision from the local review files alone (README "Local reviews"): one line, and 0, 2 or 4. Every file must be a normalized
    review of the read head or of a head the caller passed as carrying its change; every codex-review must have completed with a verdict
    of "patch is correct" or "patch is incorrect", and one must be listed. Then "patch is incorrect" or a P0 or P1 finding of a codex-review
    is 4; the claude-code-review arm is advisory (its issues and a missing comment are noted, never blocking)."""
    if not paths:
        print("Local reviews: LOCAL_REVIEWS names no file; stop")
        return 2
    if not read or not SHA.fullmatch(read) or not all(SHA.fullmatch(head) for head in heads):
        print("Local reviews: the read head and each head after it must be 40 lower-case hex digits; stop")
        return 2
    accepted, reviews = {read, *heads}, []
    for number, path in enumerate(paths, 1):
        which = f"review file {number} of {len(paths)}"  # by its place in the list, never by its path
        try:
            with open(path, "rb") as handle:
                review = json.loads(handle.read().decode("utf-8"), object_pairs_hook=unique_keys, parse_constant=no_constant)
        except (OSError, UnicodeDecodeError, ValueError):
            print(f"Local reviews: {which} cannot be read as JSON; stop")
            return 2
        problem = review_problem(review)
        if problem:
            print(f"Local reviews: {which} is not a normalized review: {problem}; stop")
            return 2
        if review["head_sha"] not in accepted:
            print(f"Local reviews: {which} ({review['reviewer']}) names commit {review['head_sha'][:8]}, which is neither the read head "
                  f"{read[:8]} nor a head carrying its change; stop")
            return 2
        if review["reviewer"] == REQUIRED and not review["completed"]:
            print(f"Local reviews: {which} ({review['reviewer']}) of {review['head_sha'][:8]} did not complete; stop")
            return 2
        if review["reviewer"] == REQUIRED and review["overall_correctness"] not in (CORRECT, INCORRECT):
            print(f"Local reviews: {which} (codex-review) of {review['head_sha'][:8]} has an overall_correctness that is not exactly "
                  f"patch is correct or patch is incorrect (rubric.md:85); stop")
            return 2
        reviews.append(review)
    required = [review for review in reviews if review["reviewer"] == REQUIRED]
    advisory = [review for review in reviews if review["reviewer"] != REQUIRED]
    if not required:
        print("Local reviews: no completed codex-review is listed (the required arm; claude-code-review is advisory); stop")
        return 2
    counts = Counter(finding["priority"] for review in required for finding in review["findings"])
    incorrect = sum(review["overall_correctness"] == INCORRECT for review in required)
    verdict = CORRECT if not incorrect else INCORRECT if len(required) == 1 else f"{INCORRECT} in {incorrect} of {len(required)}"
    names = ", ".join(review["reviewer"] for review in required)
    tail = f"P2 findings {counts[2]}, P3 findings {counts[3]} (for the Follow-ups)"
    notes = ""
    if advisory:
        issues = sum(len(review["findings"]) for review in advisory if review["completed"])
        missing = sum(not review["completed"] for review in advisory)
        notes = (f"; advisory, not blocking: claude-code-review issues {issues} (each scored 80 or more, code-review.md:26), "
                 f"runs without a comment {missing} (code-review.md:26, :11)")
    if incorrect or counts[0] or counts[1]:
        print(f"Local reviews: {names} of {read[:8]}: {verdict}, P0 findings {counts[0]}, P1 findings {counts[1]}; a person decides; {tail}{notes}")
        return 4
    print(f"Local reviews: {names} of {read[:8]}: {verdict}, no P0 or P1 finding; {tail}{notes}")
    return 0


def main(repo, pr, read=None, *same):
    files = local_review_files()
    if files is not None:  # the owner's direction of 2026-10-13: a local review set decides alone, and nothing is called
        return local_gate(files, read, same)
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
        start = max(now_running)
        # progress after the start: a non-summary connector note, a connector reaction, or an edit of a summary
        later = [created for _, bot, created, body, _ in notes if bot and created > start and SUMMARY not in body]
        later += [e[0] for _, _, edits in summaries for e in edits if e[0] > start]
        later += [when(r["created_at"]) for r in reactions if r["user"]["login"] == BOT and when(r["created_at"]) > start]
        last = max([start] + later)  # the start itself writes a summary edit and an eyes reaction within seconds
        age = (datetime.now(timezone.utc) - last).total_seconds() / 60
        if age >= STALE_RUNNING_MINUTES:
            print(f"Codex unavailable: a review shown running since {start:%Y-%m-%dT%H:%M:%SZ} has had no connector activity "
                  f"since {last:%Y-%m-%dT%H:%M:%SZ} ({age:.0f} min; stale); proceeding on the other reviews")
            return 5
        print(f"Codex review running since {start:%Y-%m-%dT%H:%M:%SZ}")
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
    # two or three arguments; with a local review set, also the heads lg_gate found to carry the read head's change
    if len(sys.argv) < 3 or (len(sys.argv) > 4 and local_review_files() is None):
        sys.exit(__doc__)
    try:
        code = main(*sys.argv[1:])
    except Exception as error:  # the landing scripts echo this output: a traceback prints file paths, gh's output can carry an address
        print(f"Codex gate error: {type(error).__name__}; details withheld")
        code = 4
    sys.exit(code)
