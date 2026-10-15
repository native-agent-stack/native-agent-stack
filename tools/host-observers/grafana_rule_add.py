#!/usr/bin/env python3
"""Add or remove one alert rule in a Grafana alert provisioning file, with a backup and a check that the file keeps the shape Grafana loads.

  grafana_rule_add.py check  FILE
  grafana_rule_add.py add    FILE SPEC.json [--group NAME] [--backup-dir DIR]
  grafana_rule_add.py remove FILE UID [--group NAME] [--backup-dir DIR]

FILE is the provisioning file of a rule group (apiVersion 1, `groups[].rules[]`), JSON written the way json.dumps(indent=2) writes it. SPEC.json holds one rule in the same shape.
check   verifies the file: unique rule uids, the same key set on every rule, `condition` naming a query, every query naming a datasource, a `for` and an interval that parse.
add     refuses a uid that exists, a rule that fails the same checks, or a group that does not exist; it writes FILE.bak-<UTC> (mode 0600) first, in --backup-dir when given (use a directory
        outside Grafana's provisioning directory), and replaces FILE by rename (mode kept).
remove  is the inverse and writes a backup the same way. Both print the rule count before and after and whether the file reads back byte-identically after a load and dump (when it does not, the
        diff includes a reformat of the whole file, which is said).
Grafana reads file-provisioned alert rules at start, so a restart of the Grafana service (or the admin reload) is what makes a change live; this tool does not do that.
"""
import copy
import datetime
import json
import os
import re
import sys

REQUIRED = {"uid", "title", "condition", "data", "noDataState", "execErrState", "for", "isPaused", "dashboardUid", "panelId", "labels", "annotations"}
DUR = re.compile(r"^(\d+(\.\d+)?(s|m|h))+$|^0$")


def load(path):
    text = open(path).read()
    return text, json.loads(text)


def dump(doc):
    return json.dumps(doc, indent=2) + "\n"


def problems(doc):
    """Return a list of problems with the document; empty means it keeps the shape the other rules have."""
    out = []
    if doc.get("apiVersion") != 1:
        out.append("apiVersion is not 1")
    seen, keysets = {}, set()
    for g in doc.get("groups", []):
        if not DUR.match(str(g.get("interval", ""))):
            out.append(f"group {g.get('name')}: interval {g.get('interval')!r} does not parse")
        for r in g.get("rules", []):
            uid = r.get("uid")
            if uid in seen:
                out.append(f"duplicate uid {uid}")
            seen[uid] = g.get("name")
            missing = REQUIRED - set(r)
            if missing:
                out.append(f"rule {uid}: missing {sorted(missing)}")
            keysets.add(frozenset(r))
            refids = [d.get("refId") for d in r.get("data", [])]
            if r.get("condition") not in refids:
                out.append(f"rule {uid}: condition {r.get('condition')!r} is not one of the queries {refids}")
            for d in r.get("data", []):
                if not d.get("datasourceUid"):
                    out.append(f"rule {uid}: query {d.get('refId')} has no datasourceUid")
            if not DUR.match(str(r.get("for", ""))):
                out.append(f"rule {uid}: for {r.get('for')!r} does not parse")
    if len(keysets) > 1:
        out.append(f"the rules do not all have the same key set ({len(keysets)} different sets)")
    return out


def backup_and_replace(path, new_text, backup_dir=None):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    old = open(path).read()
    n = 0
    while True:   # two changes within one second must not overwrite or refuse each other's backup
        bak = os.path.join(backup_dir or os.path.dirname(path) or ".", os.path.basename(path)) + f".bak-{stamp}" + (f"-{n}" if n else "")
        try:
            fd = os.open(bak, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            break
        except FileExistsError:
            n += 1
    with os.fdopen(fd, "w") as f:
        f.write(old)
    mode = os.stat(path).st_mode & 0o777
    tmp = f"{path}.tmp-{os.getpid()}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    # os.open's mode is narrowed by the caller's umask; the file keeps the mode it had, so a Grafana running as another user can still read it. Mechanism, at its pin (python/cpython@v3.13.16, tag commit
    # cbc944f4bc59): Doc/library/os.rst:1272-1275 "When computing mode, the current umask value is first masked out" (os.open) and :1027-1030 os.fchmod(fd, mode), "equivalent to os.chmod(fd, mode)". That chmod
    # is not narrowed by the umask (the umask applies when a file is created) is POSIX chmod(2), which has no mirror here; it is measured first-hand by the umask 0077 regression of alert_tools_selftest.py (a 0644
    # file stays 0644; without this call it becomes 0600).
    os.fchmod(fd, mode)
    with os.fdopen(fd, "w") as f:
        f.write(new_text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return bak


def find_group(doc, name):
    for g in doc["groups"]:
        if name is None or g["name"] == name:
            return g
    raise KeyError(f"no group {name}")


def main(argv):
    if len(argv) < 3 or argv[1] not in ("check", "add", "remove"):
        print(__doc__)
        return 2
    cmd, path = argv[1], argv[2]
    group = argv[argv.index("--group") + 1] if "--group" in argv else None
    backup_dir = argv[argv.index("--backup-dir") + 1] if "--backup-dir" in argv else None
    text, doc = load(path)
    roundtrip = dump(doc) == text
    n_before = sum(len(g["rules"]) for g in doc["groups"])
    if cmd == "check":
        pr = problems(doc)
        print(f"{path}: {n_before} rules in {len(doc['groups'])} group(s); reads back identically: {roundtrip}")
        print("\n".join("PROBLEM: " + p for p in pr) or "no problems")
        return 1 if pr else 0
    if cmd == "add":
        if len(argv) < 4:
            print(__doc__)
            return 2
        spec = json.load(open(argv[3]))
        new = copy.deepcopy(doc)
        if any(r["uid"] == spec.get("uid") for g in new["groups"] for r in g["rules"]):
            print(f"refused: uid {spec.get('uid')} already exists")
            return 1
        try:
            find_group(new, group)["rules"].append(spec)
        except KeyError as ex:
            print(f"refused: {ex.args[0]}")
            return 1
        pr = problems(new)
        if pr:
            print("refused:\n" + "\n".join("  " + p for p in pr))
            return 1
    else:
        uid = argv[3]
        new = copy.deepcopy(doc)
        g = find_group(new, group) if group else None
        groups = [g] if g else new["groups"]
        removed = 0
        for gg in groups:
            keep = [r for r in gg["rules"] if r["uid"] != uid]
            removed += len(gg["rules"]) - len(keep)
            gg["rules"] = keep
        if removed != 1:
            print(f"refused: uid {uid} found {removed} times")
            return 1
    new_text = dump(new)
    bak = backup_and_replace(path, new_text, backup_dir)
    n_after = sum(len(g["rules"]) for g in new["groups"])
    print(f"{cmd}: {n_before} -> {n_after} rules; backup {bak}; the original read back identically before the change: {roundtrip}" + ("" if roundtrip else " (the diff includes a reformat of the whole file)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
