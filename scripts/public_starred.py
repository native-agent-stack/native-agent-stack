"""Allowlisted public-star refresh through the installed GitHub CLI.

The public endpoint is inherited from the committed snapshot. GitHub CLI owns
authentication and pagination; this module never reads authentication files or
records raw API responses. The weekly path writes only external review state.

Primary interface: cli/cli v2.102.0 pkg/cmd/api/api.go (--paginate --slurp),
GitHub REST 2022-11-28 GET /users/{username}/starred.
"""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
from urllib.parse import urlsplit


STARS = "catalogs/convergence-practice/public-starred.json"
PUBLIC_FIELDS = (
    "archived", "default_branch", "description", "fork", "license_metadata",
    "pushed_at", "repository", "topics", "url",
)
REVIEW_FIELDS = (
    "disposition", "disposition_status", "decision_manifest", "first_observed_at",
    "disposition_checked_at", "layer_keys", "seed_refs", "evidence_refs",
    "verdict_refs", "verdict_follow_up", "reason", "convergence_manifest",
)
REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]+\Z")
ENDPOINT = re.compile(r"/users/[A-Za-z0-9][A-Za-z0-9-]{0,38}/starred\Z")
SNAPSHOT_NAME = "public-starred.latest.json"
JOURNAL_NAME = "newstars-journal.json"


def snapshot_time(value):
    """Parse retained UTC observation dates; reject missing/ambiguous dates."""
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("invalid public-star observation date") from error
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            result = result.replace(tzinfo=timezone.utc)
    else:
        raise ValueError("public-star observation date is required")
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError("public-star observation date must be UTC")
    return result.astimezone(timezone.utc)


def _now(value=None):
    if value is not None:
        return snapshot_time(value)
    result = subprocess.run(
        ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise ValueError("UTC clock command failed")
    return snapshot_time(result.stdout.strip())


def _stamp(value):
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _repository_key(value):
    if not isinstance(value, str) or not REPOSITORY.fullmatch(value):
        raise ValueError("invalid public repository identity")
    return value.lower()


def _rows(snapshot):
    rows = snapshot.get("repositories")
    if not isinstance(rows, list):
        raise ValueError("public-star snapshot requires a repository array")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("public-star repository row must be an object")
        key = _repository_key(row.get("repository"))
        if key in result:
            raise ValueError("duplicate public repository identity")
        result[key] = row
    if snapshot.get("count") != len(rows):
        raise ValueError("public-star snapshot count disagrees with repository rows")
    return result


def _open_regular(path, mode):
    flags = os.O_NOFOLLOW | os.O_NONBLOCK
    if mode == "r":
        flags |= os.O_RDONLY
    else:
        flags |= os.O_RDWR | os.O_CREAT
        if mode == "a+":
            flags |= os.O_APPEND
    descriptor = os.open(path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("public-star state and questions resources must be regular files")
        return os.fdopen(descriptor, mode, encoding="utf-8")
    except BaseException:
        os.close(descriptor)
        raise


def _read(path):
    try:
        with _open_regular(path, "r") as source:
            value = json.load(source)
    except (OSError, ValueError) as error:
        raise ValueError("cannot read public-star snapshot or notification journal") from error
    if not isinstance(value, dict):
        raise ValueError("public-star snapshot or notification journal must be an object")
    return value


def _is_pending(row):
    disposition = row.get("disposition")
    return (
        isinstance(disposition, str) and disposition.strip().upper() == "PENDING"
    ) or (
        disposition is None and str(row.get("disposition_status", "")).upper().startswith("PENDING")
    )


def validate_pending_age(snapshot, now=None):
    """Fail if PENDING survived more than seven days since first observation.

    Refresh time cannot replace a row's retained first observation. Legacy rows
    without that field use the snapshot's retained observation date.
    """
    current = _now(now)
    retrieved = snapshot_time(snapshot.get("retrieved_at"))
    if retrieved > current:
        raise ValueError("public-star snapshot observation date is in the future")
    expired = []
    for row in _rows(snapshot).values():
        observed = _observation(row, snapshot, current)
        if _is_pending(row) and current - observed > timedelta(days=7):
            expired.append(row["repository"])
    if expired:
        raise ValueError("PENDING public-star entries older than 7 days: " + ", ".join(sorted(expired)))


def _observation(row, snapshot, current):
    retrieved = snapshot_time(snapshot.get("retrieved_at"))
    observed = snapshot_time(row.get("first_observed_at", snapshot.get("retrieved_at")))
    if retrieved > current or observed > current:
        raise ValueError("public-star observation date is in the future")
    if observed > retrieved:
        raise ValueError("public-star first observation is newer than its containing snapshot")
    return observed


def _endpoint(snapshot):
    value = snapshot.get("endpoint")
    if not isinstance(value, str):
        raise ValueError("public-star snapshot requires its recorded public endpoint")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https" or parsed.netloc != "api.github.com"
        or not ENDPOINT.fullmatch(parsed.path) or parsed.query != "per_page=100"
        or parsed.fragment
    ):
        raise ValueError("public-star endpoint must be the recorded GitHub public users endpoint")
    return parsed.path.lstrip("/") + "?" + parsed.query


def _fetch(endpoint):
    try:
        result = subprocess.run(
            ["gh", "api", endpoint, "--hostname", "github.com", "--method", "GET",
             "--paginate", "--slurp", "--header", "Accept: application/vnd.github+json",
             "--header", "X-GitHub-Api-Version: 2022-11-28"],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError as error:
        raise ValueError("GitHub CLI (gh) was not found on PATH") from error
    if result.returncode:
        # Raw stderr can carry data outside the public allowlist; do not echo it.
        raise ValueError(f"GitHub public-stars request failed (exit {result.returncode})")
    try:
        pages = json.loads(result.stdout)
    except ValueError as error:
        raise ValueError("GitHub public-stars response is not valid paginated JSON") from error
    if not isinstance(pages, list) or not pages or any(not isinstance(page, list) for page in pages):
        raise ValueError("GitHub public-stars response must be an outer array of page arrays")
    return [row for page in pages for row in page]


def _normalize(raw_rows):
    rows, filtered, seen = [], 0, set()
    for raw in raw_rows:
        if not isinstance(raw, dict) or not isinstance(raw.get("private"), bool):
            raise ValueError("GitHub repository lacks an explicit public/private boundary")
        if raw["private"] or raw.get("visibility", "public") != "public":
            filtered += 1
            continue
        repository = raw.get("full_name")
        key = _repository_key(repository)
        if key in seen:
            raise ValueError("duplicate public repository across GitHub pages")
        seen.add(key)
        url = raw.get("html_url")
        if url != "https://github.com/" + repository:
            raise ValueError("GitHub repository URL does not match its public identity")
        for field in ("archived", "fork"):
            if not isinstance(raw.get(field), bool):
                raise ValueError("GitHub repository boolean metadata is malformed")
        if not isinstance(raw.get("default_branch"), str) or not raw["default_branch"]:
            raise ValueError("GitHub repository default branch is malformed")
        if raw.get("description") is not None and not isinstance(raw["description"], str):
            raise ValueError("GitHub repository description is malformed")
        pushed = raw.get("pushed_at")
        if pushed is not None:
            snapshot_time(pushed)
        topics = raw.get("topics", [])
        if not isinstance(topics, list) or any(not isinstance(topic, str) for topic in topics):
            raise ValueError("GitHub repository topics are malformed")
        license_record = raw.get("license")
        if license_record is not None and not isinstance(license_record, dict):
            raise ValueError("GitHub repository license metadata is malformed")
        license_metadata = license_record.get("spdx_id") if license_record else None
        if license_metadata is not None and not isinstance(license_metadata, str):
            raise ValueError("GitHub repository SPDX identifier is malformed")
        rows.append({
            "archived": raw["archived"], "default_branch": raw["default_branch"],
            "description": raw.get("description"), "fork": raw["fork"],
            "license_metadata": license_metadata, "pushed_at": pushed,
            "repository": repository, "topics": sorted(set(topics)), "url": url,
        })
    return rows, filtered


def _build(baseline, raw_rows, now, previous=None):
    canonical = _rows(baseline)
    retained = _rows(previous) if previous is not None else {}
    rows, filtered = _normalize(raw_rows)
    for row in rows:
        key = _repository_key(row["repository"])
        authority = canonical.get(key)
        if authority is not None:
            row.update({field: authority[field] for field in REVIEW_FIELDS if field in authority})
        else:
            row.update(disposition="NEEDS-EVIDENCE: new public star requires sourced scope review",
                       disposition_status="NEEDS-EVIDENCE")
        dates = [now]
        for snapshot, source_row in ((baseline, authority), (previous, retained.get(key))):
            if snapshot is not None and source_row is not None:
                observed = _observation(source_row, snapshot, now)
                dates.append(observed)
        row["first_observed_at"] = _stamp(min(dates))
    snapshot = {
        "count": len(rows), "endpoint": baseline["endpoint"], "fields_allowlisted": True,
        "filtered_nonpublic_count": filtered, "kind": "public_starred",
        "repositories": rows, "retrieved_at": _stamp(now), "schema_version": 1,
    }
    for field in ("convergence_manifest", "convergence_status"):
        if field in baseline:
            snapshot[field] = baseline[field]
    return snapshot


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".public-starred-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, indent=2, sort_keys=True, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _display_path(path, root):
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        try:
            return "~/" + path.relative_to(Path.home()).as_posix()
        except ValueError:
            return str(path)


def _unreviewed(row):
    if row is None or _is_pending(row):
        return True
    disposition = row.get("disposition")
    return not isinstance(disposition, str) or not disposition.strip() or disposition.upper().startswith("NEEDS-EVIDENCE")


def _notify(questions, notification, count, snapshot, now, root, pending=()):
    marker = f"<!-- public-starred-newstars:{notification} -->"
    with _open_regular(questions, "a+") as output:
        fcntl.flock(output, fcntl.LOCK_EX)
        output.seek(0)
        if marker in output.read():
            return False
        output.seek(0, os.SEEK_END)
        output.write(f"\n## NEWSTARS {count}\n\nas_of={_stamp(now)} "
                     f"file={_display_path(snapshot, root)}\n"
                     "Queue requires a sourced disposition PR; canonical review decisions clear it.\n"
                     + ("Repositories: " + ", ".join(pending) + "\n" if pending else "")
                     + f"{marker}\n")
        output.flush()
        os.fsync(output.fileno())
    return True


def refresh_public_stars(root, *, output=None, state_dir=None, questions=None, now=None):
    """Refresh once into an explicit output or an external weekly review queue.

    State mode never writes the checkout. It prepares a durable notification
    journal before append and recognizes an already appended marker on retry.
    """
    root = Path(root).resolve()
    if (output is None) == (state_dir is None):
        raise ValueError("choose an explicit catalog output or an external state directory")
    if state_dir is None and questions is not None:
        raise ValueError("questions posting requires external state mode")
    current = _now(now)
    baseline_path = root / STARS
    baseline = _read(baseline_path)
    endpoint = _endpoint(baseline)
    for row in _rows(baseline).values():
        _observation(row, baseline, current)
    state_path = Path(state_dir).resolve() if state_dir is not None else None
    questions_input = Path(questions) if questions is not None else None
    if questions_input is not None and questions_input.is_symlink():
        raise ValueError("lane questions path cannot be a symlink")
    questions_path = questions_input.resolve() if questions_input is not None else None
    if state_path is not None:
        if questions_path is None:
            raise ValueError("external state refresh requires its lane questions file")
        if state_path.is_relative_to(root) or questions_path.is_relative_to(root):
            raise ValueError("weekly star state and lane questions must be outside the checkout")
        if questions_path.is_relative_to(state_path) or state_path.is_relative_to(questions_path):
            raise ValueError("lane questions and star state must use separate paths")
        if state_path.exists() and not state_path.is_dir():
            raise ValueError("public-star state path must be a directory")
        if questions_path.exists() and not questions_path.is_file():
            raise ValueError("lane questions path must be a file")
        for name in (SNAPSHOT_NAME, JOURNAL_NAME, ".public-starred.lock"):
            resource = state_path / name
            if resource.is_symlink():
                raise ValueError("public-star state resources cannot be symlinks")
            if resource.exists() and not resource.is_file():
                raise ValueError("public-star state resources must be files")
        state_path.mkdir(parents=True, exist_ok=True)
        target = state_path / SNAPSHOT_NAME
        lock = _open_regular(state_path / ".public-starred.lock", "r+")
    else:
        target = Path(output)
        if not target.is_absolute():
            target = root / target
        target = target.resolve()
        lock = nullcontext()
    with lock as held:
        if state_path is not None:
            fcntl.flock(held, fcntl.LOCK_EX)
        previous = _read(target) if state_path is not None and target.exists() else None
        if previous is not None:
            for row in _rows(previous).values():
                _observation(row, previous, current)
        journal_path = state_path / JOURNAL_NAME if state_path is not None else None
        journal = _read(journal_path) if journal_path is not None and journal_path.exists() else {}
        replayed = False
        if journal_path is not None and journal.get("notification_state") == "prepared":
            notification = journal.get("notification_id")
            count = journal.get("newstars_count")
            if not isinstance(notification, str) or not re.fullmatch(r"[0-9a-f]{64}", notification):
                raise ValueError("prepared new-stars journal requires its notification identity")
            if type(count) is not int or count < 0:
                raise ValueError("prepared new-stars journal requires its nonnegative count")
            observed = snapshot_time(journal.get("retrieved_at"))
            if observed > current:
                raise ValueError("prepared new-stars journal observation is in the future")
            replayed = _notify(questions_path, notification, count, target, observed, root,
                               journal.get("pending_repositories", []))
            journal["notification_state"] = "posted"
            _write_json(journal_path, journal)
        snapshot = _build(baseline, _fetch(endpoint), current, previous)
        canonical, live = _rows(baseline), _rows(snapshot)
        added = sorted(set(live) - set(canonical))
        if journal_path is not None:
            prior_queue = journal.get("pending_repositories", [])
            if not isinstance(prior_queue, list) or any(not isinstance(key, str) for key in prior_queue):
                raise ValueError("new-stars notification journal queue is malformed")
            prior_queue = {_repository_key(key) for key in prior_queue}
            generations = journal.get("review_generations", {})
            retained = journal.get("pending_observations", {})
            if not isinstance(generations, dict) or any(
                    not isinstance(key, str) or type(value) is not int or value < 1
                    for key, value in generations.items()) or not isinstance(retained, dict):
                raise ValueError("new-stars notification journal observations or generations are malformed")
            generations = dict(generations)
            prior_rows = _rows(previous) if previous is not None else {}
            queue = sorted(key for key in set(live) | prior_queue | set(canonical) | set(prior_rows)
                           if _unreviewed(canonical.get(key)))
            pending = {}
            for key in queue:
                source = live.get(key) or retained.get(key) or prior_rows.get(key) or canonical.get(key)
                if not isinstance(source, dict) or _repository_key(source.get("repository")) != key:
                    raise ValueError("unresolved new-stars journal entry requires its retained observation")
                row = {field: source[field] for field in PUBLIC_FIELDS + REVIEW_FIELDS if field in source}
                fallback = baseline["retrieved_at"] if key in canonical else (
                    previous["retrieved_at"] if key in prior_rows else snapshot["retrieved_at"])
                dates = [current, snapshot_time(row.get("first_observed_at", fallback))]
                if key in retained:
                    dates.append(_observation(retained[key], journal, current))
                if any(observed > current for observed in dates):
                    raise ValueError("retained public-star observation date is in the future")
                row["first_observed_at"] = _stamp(min(dates))
                if key in live:
                    live[key]["first_observed_at"] = row["first_observed_at"]
                pending[key] = row
                if key not in prior_queue:
                    generations[key] = generations.get(key, 0) + 1
                elif key not in generations:
                    generations[key] = 1
            observation = [{"repository": key, "first_observed_at": pending[key]["first_observed_at"],
                            "generation": generations[key],
                            "canonical_review": {field: canonical[key][field] for field in REVIEW_FIELDS
                                                 if field != "first_observed_at" and field in canonical[key]}
                            if key in canonical else None} for key in queue]
            notification = hashlib.sha256(json.dumps(observation, sort_keys=True).encode()).hexdigest()
            journal = {"schema_version": 1, "pending_repositories": queue,
                       "pending_observations": pending, "review_generations": generations,
                       "notification_id": notification, "notification_state": "prepared",
                       "newstars_count": len(queue), "retrieved_at": _stamp(current)}
        _write_json(target, snapshot)
        report = {"status": "refreshed", "count": snapshot["count"], "new_count": len(added),
                  "retrieved_at": snapshot["retrieved_at"], "snapshot": _display_path(target, root),
                  "snapshot_sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
        if journal_path is not None:
            _write_json(journal_path, journal)
            posted = _notify(questions_path, notification, len(queue), target, current, root, queue)
            journal["notification_state"] = "posted"
            _write_json(journal_path, journal)
            report.update(queued_count=len(queue), newstars_posted=posted or replayed,
                          notification_id=notification)
        return report
