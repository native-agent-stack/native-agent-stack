"""Derive lane-scoped seq3 glue from the verified immutable seq2 packet.

No installation, GO issuance, credential or broker call. Frozen runtime and
CONFIG bytes are copied unchanged; changed glue and units receive new hashes.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ISSUER_SHA = "8fb23913da2e17831c0fff67cb88c3e6310705467a5ae437974c7d7e645e9c2b"
VERSION = "readiness-sequencing-v3-lane-latch"
REPLAY_SOURCES = ("test_wiring.py", "test_go_issuer.py", "test_sequencing.py", "test_unit_contracts.py", "test_data_wiring.py")
REPLAY_DIRECTORY = "blueprints/us-equities/paper-open-e2e/seq2-replay/"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def inventory_rows(raw):
    rows = {}
    for line in raw.decode("utf-8").splitlines():
        if not re.fullmatch(r"[0-9a-f]{64}  .+", line):
            raise ValueError("predecessor_inventory_schema")
        digest, name = line.split("  ", 1)
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or path.as_posix() != name or name in rows:
            raise ValueError("predecessor_inventory_schema")
        rows[name] = digest
    return rows


def replay_inventory(path, expected_sha256):
    """Authenticate the separate CC record, then its exact landed git blobs.

    The expected hash is an authority input, never learned from the source
    directory. Git's supported blob reader supplies the bytes; no network,
    credential loader, source rewrite or git mutation is performed.
    """
    path = Path(path)
    if not isinstance(expected_sha256, str) or not re.fullmatch("[0-9a-f]{64}", expected_sha256):
        raise ValueError("replay_inventory_digest_required")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1048576:
        raise ValueError("replay_inventory_regular_file_required")
    raw = path.read_bytes()
    if sha(raw) != expected_sha256:
        raise ValueError("replay_inventory_hash_mismatch")
    text = raw.decode("utf-8")
    commits = re.findall(r"^- \*\*Source commit:\*\* native-agent-stack main ([0-9a-f]{40})\b", text, re.M)
    directories = re.findall(r"^- \*\*Directory:\*\* ([^\s]+)", text, re.M)
    rows = re.findall(r"^\| (test_[a-z_]+\.py) \| ([0-9]+) \| ([0-9a-f]{64}) \|$", text, re.M)
    if (len(commits) != 1 or directories != [REPLAY_DIRECTORY] or len(rows) != len(REPLAY_SOURCES)
            or {name for name, _, _ in rows} != set(REPLAY_SOURCES)):
        raise ValueError("replay_inventory_schema")
    commit = commits[0]
    repository = Path(__file__).resolve().parents[3]
    environment = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_OPTIONAL_LOCKS="0")
    landed = subprocess.run(["git", "-C", str(repository), "merge-base", "--is-ancestor", commit, "HEAD"],
                            capture_output=True, env=environment)
    if landed.returncode:
        raise ValueError("replay_inventory_commit_not_landed")
    blobs, files = {}, {}
    for name, size, digest in rows:
        git_path = REPLAY_DIRECTORY + name
        result = subprocess.run(["git", "-C", str(repository), "cat-file", "blob", commit + ":" + git_path],
                                capture_output=True, env=environment)
        if result.returncode or len(result.stdout) != int(size) or sha(result.stdout) != digest:
            raise ValueError("replay_inventory_git_mismatch")
        blobs[name] = result.stdout
        files[name] = {"repository_path": git_path, "bytes": int(size), "sha256": digest}
    return raw, blobs, {"record": path.name, "record_sha256": expected_sha256,
                        "commit": commit, "files": files,
                        "provenance": "first authenticated git provenance; not original seq2 seal membership"}


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("unexpected_seq2_source_shape")
    return text.replace(old, new)


def rewrite_launch(text, predecessor_sha256=None, launcher_sha256=None):
    if not isinstance(predecessor_sha256, str) or not re.fullmatch("[0-9a-f]{64}", predecessor_sha256):
        raise ValueError("predecessor_digest_required")
    if not isinstance(launcher_sha256, str) or not re.fullmatch("[0-9a-f]{64}", launcher_sha256):
        raise ValueError("launcher_digest_required")
    if sha(text.encode()) != launcher_sha256:
        raise ValueError("seq2_launcher_pin_mismatch")
    text = once(text, "STOP = Path.home() / '.local/state/native-agent-stack/alpaca-paper/STOP'",
        "HOST_STOP = Path.home() / '.local/state/native-agent-stack/alpaca-paper/STOP'\n"
        "STOP = HOST_STOP.parent / 'lane-b/STOP'\n"
        "from lane_latch import pending as latch_pending, mark as latch_mark, clear as latch_clear\n\n"
        "def stop_present():\n    return latch_pending(STOP, HOST_STOP, STATE / 'instances')\n\n"
        "def assert_seq2_watchers_retired():\n"
        "    from seq2_retirement import assert_retired\n"
        "    try:\n        return assert_retired()\n"
        "    except (ValueError, OSError):\n        raise Refused('seq2_watchers_not_retired') from None")
    if text.count("if STOP.exists() or STOP.is_symlink():") != 2:
        raise ValueError("seq2_stop_admission_shape")
    text = text.replace("if STOP.exists() or STOP.is_symlink():", "if stop_present():")
    assignments = [node for node in ast.parse(text).body if isinstance(node, ast.Assign)
                   and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                   and node.targets[0].id == "PREDECESSOR_BUNDLE"]
    if len(assignments) != 1:
        raise ValueError("predecessor_assignment_shape")
    text = once(text, ast.get_source_segment(text, assignments[0]),
                "PREDECESSOR_BUNDLE = " + repr(predecessor_sha256))
    start, end = text.index("def stop_mark(stage):"), text.index("def recover_stage(stage):")
    replacement = '''def stop_mark(stage):
    active_path = STATE / 'active' / (stage + '.json')
    if not active_path.is_file():
        return 0
    active = safe_json(active_path)
    receipt = Path(active['instance']) / 'stop-hook.json'
    # A repeated stop/recover hook cannot overwrite the original ownership.
    if receipt.exists() or receipt.is_symlink():
        prior = safe_json(receipt)
        if prior.get('version') != 'private-stage-hook-v2' or prior.get('trial') != active['trial']:
            raise Refused('lane_stop_ownership_mismatch')
        return 0
    # Human lane/host STOPs are read-only, even if replaced at cleanup time.
    if STOP.exists() or STOP.is_symlink() or HOST_STOP.exists() or HOST_STOP.is_symlink():
        proof = {'version':'private-stage-hook-v2','trial':active['trial'],'created_by_hook':False}
    else:
        proof = latch_mark(Path(active['instance']) / '.stage-hook-latch', active['trial'])
    save(receipt, proof)
    return 0

'''
    text = text[:start] + replacement + text[end:]
    text = once(text, "        before = STOP.stat(follow_symlinks=False)\n", "")
    start = text.index("            after = STOP.stat(follow_symlinks=False)")
    end = text.index("            save(STATE/'completed'", start)
    text = text[:start] + "            owned = safe_json(instance / 'stop-hook.json')\n" + \
        "            receipt['stop_cleared'] = latch_clear(instance / '.stage-hook-latch', owned, active['trial'])\n" + text[end:]
    ast.parse(text)
    return text


def rewrite_issuer(text):
    if sha(text.encode()) != ISSUER_SHA:
        raise ValueError("seq2_issuer_pin_mismatch")
    text = once(text, "if launch.STOP.exists() or launch.STOP.is_symlink():", "if launch.stop_present():")
    return once(text, "def build(kind,trial,skip_reason=None):\n",
                "def build(kind,trial,skip_reason=None):\n"
                "    from lane_latch import assert_issuer_python\n"
                "    try:\n        assert_issuer_python()\n"
                "    except ValueError:\n        raise launch.Refused('issuer_python_3_12_required') from None\n"
                "    launch.assert_seq2_watchers_retired()\n")


def embedded_unit_root(units):
    files = sorted(Path(units).iterdir())
    if len(files) != 22 or any(p.suffix not in (".path", ".service") or p.is_symlink() for p in files):
        raise ValueError("seq2_unit_inventory_changed")
    return unit_root_from_bytes({path.name: path.read_bytes() for path in files})


def unit_root_from_bytes(units):
    roots = set()
    if len(units) != 22 or any(Path(name).suffix not in (".path", ".service") for name in units):
        raise ValueError("seq2_unit_inventory_changed")
    for name, raw in units.items():
        lines = raw.decode("utf-8").splitlines()
        working = [x.split("=", 1)[1] for x in lines if x.startswith("WorkingDirectory=")]
        if Path(name).suffix == ".service" and len(working) != 1:
            raise ValueError("unit_embedded_root_missing")
        for value in working:
            root = Path(value)
            if not root.is_absolute() or ".." in root.parts or any(c.isspace() for c in value):
                raise ValueError("unit_embedded_root_unsafe")
            roots.add(value)
    if len(roots) != 1:
        raise ValueError("unit_embedded_roots_differ")
    root = Path(roots.pop())
    for name, raw in units.items():
        if Path(name).suffix == ".service":
            starts = [x for x in raw.decode("utf-8").splitlines() if x.startswith("ExecStart=")]
            if len(starts) != 1 or str(root) + "/" not in starts[0]:
                raise ValueError("unit_start_not_bound_to_embedded_root")
    return root


def rewrite_unit(text, old_root, new_root):
    # The redundant touch hook also writes HOST STOP and changes its metadata.
    lines = text.splitlines()
    removed = sum(line.startswith("ExecStopPost=/usr/bin/bash -c '") and "/usr/bin/touch" in line for line in lines)
    text = "\n".join(line for line in lines if not (
        line.startswith("ExecStopPost=/usr/bin/bash -c '") and "/usr/bin/touch" in line)) + "\n"
    text = text.replace("WorkingDirectory=" + str(old_root) + "\n", "WorkingDirectory=" + str(new_root) + "\n")
    text = text.replace(str(old_root) + "/", str(new_root) + "/").replace("-seq2", "-seq3")
    text = text.replace("before touching the global latch", "before creating the owned lane latch")
    if "/usr/bin/touch" in text or "alpaca-paper/STOP" in text:
        raise ValueError("global_stop_unit_writer_remains")
    return text, removed


def operational_notes():
    return """# Sequencing v3: retirement is an activation prerequisite

Keep the issuer paused. With zero active trials and no pending GO, first stop
and disable --now ALL 11 paper-ready-{record,scan,pre,pre-skip,sip,lev1,lev2,lev4,
edge2,edge8,iex}-8c95a50d-seq2.path units. Check every old service is inactive,
the state active directory is empty, and every ready GO.sha256 is absent.
Record systemctl --user show output proving all 11 old paths disabled/inactive.
Send that retirement receipt to the CC and WAIT for CC install authorization.
Only then install/verify the 22 seq3 files and enable/arm their 11 paths, with
zero active trials and no GO. Co-op restarts its issuer against the new binding.

Stage end calls stop-mark then recover only; there is NO touch hook. Host STOP
and lane-b/STOP are read-only. Only a private per-trial .stage-hook-latch in
the mode0700 instance directory may be automatically created/cleared. Admission
honors both operator paths and every outstanding private marker. seq2 retirement is mandatory:
both generations otherwise watch the same GO files and can start together.

PREDECESSOR_BUNDLE is re-pinned to the expected immediate predecessor supplied
from its sealed private binding, so genuine same-state-root receipts carry
forward without relabeling. No private digest is hard-coded in public source.
Runtime and CONFIG bytes are compared, and every replay source is inventoried.

prepare_units.py is deliberately removed; it generated obsolete HOST touches.
Retained test/proof inputs are non-runtime SYN/historical evidence, never
commands for installation. Use this procedure instead of predecessor docs.
"""


def unchanged_comparison(source, output):
    counts = {}
    for folder in ("frozen", "configs"):
        before = {p.relative_to(source).as_posix(): p for p in (source / folder).rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo")}
        after = {p.relative_to(output).as_posix(): p for p in (output / folder).rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo")}
        if set(before) != set(after) or any(p.read_bytes() != after[name].read_bytes() for name, p in before.items()):
            raise ValueError("frozen_runtime_or_config_changed")
        counts["frozen_files" if folder == "frozen" else "config_files"] = len(before)
    return {**counts, "equal": True}


def write(path, raw):
    if path.exists():
        path.chmod(0o600)
    path.write_bytes(raw)
    path.chmod(0o400)


def recut(source, output, source_commit, *, predecessor_sha256=None,
          replay_inventory_path=None, replay_inventory_sha256=None):
    if not isinstance(predecessor_sha256, str) or not re.fullmatch("[0-9a-f]{64}", predecessor_sha256):
        raise ValueError("predecessor_digest_required")
    if (replay_inventory_path is None) != (replay_inventory_sha256 is None):
        raise ValueError("replay_inventory_pair_required")
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or output.is_symlink() or output.is_relative_to(source):
        raise ValueError("new_bundle_destination_required")
    inventory = (source / "SHA256SUMS").read_bytes()
    if sha(inventory) != predecessor_sha256:
        raise ValueError("seq2_bundle_pin_mismatch")
    expected = inventory_rows(inventory)
    record_raw, replay_blobs, provenance = None, {}, None
    if replay_inventory_path is not None:
        record_raw, replay_blobs, provenance = replay_inventory(replay_inventory_path, replay_inventory_sha256)
        for name, raw in replay_blobs.items():
            if name in expected and expected[name] != sha(raw):
                raise ValueError("replay_inventory_source_conflict")
            expected[name] = sha(raw)
    if not set(REPLAY_SOURCES) <= expected.keys():
        raise ValueError("predecessor_replay_source_not_in_manifest")
    check = subprocess.run(["sha256sum", "--check", "--strict", "--quiet", "SHA256SUMS"],
                           cwd=source, capture_output=True)
    if check.returncode:
        raise ValueError("seq2_manifest_refused")
    if "launch.py" not in expected:
        raise ValueError("launcher_inventory_binding_missing")
    # This envelope was always separate from the runtime inventory. Capture it
    # once and require copy identity; no claim of runtime-seal authentication.
    request_raw = (source / "GO-BINDING-REQUEST.json").read_bytes()
    shutil.copytree(source, output, symlinks=False,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
    verified = {}
    for name, digest in expected.items():
        path = output / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("copied_bytes_not_in_sealed_inventory")
        raw = path.read_bytes()
        if sha(raw) != digest:
            raise ValueError("copied_bytes_not_in_sealed_inventory")
        if name in replay_blobs and raw != replay_blobs[name]:
            raise ValueError("copied_replay_bytes_mismatch")
        verified[name] = raw
    if (output / "GO-BINDING-REQUEST.json").read_bytes() != request_raw:
        raise ValueError("binding_envelope_copy_changed")
    units = {name.removeprefix("units/"): raw for name, raw in verified.items() if name.startswith("units/")}
    if {p.name for p in (output / "units").iterdir()} != set(units):
        raise ValueError("seq2_unit_inventory_changed")
    old_root = unit_root_from_bytes(units)
    # From here on, transformations and digests consume this verified snapshot,
    # never a second read of mutable output bytes.
    payloads = dict(verified)
    output.chmod(0o700)
    (output / "units").chmod(0o700)

    def emit(name, raw):
        payloads[name] = raw
        write(output / name, raw)

    emit("launch.py", rewrite_launch(verified["launch.py"].decode(), predecessor_sha256,
                                    expected["launch.py"]).encode())
    emit("issue_go.py", rewrite_issuer(verified["issue_go.py"].decode()).encode())
    for name in ("lane_latch.py", "seq2_retirement.py"):
        emit(name, Path(__file__).with_name(name).read_bytes())
    obsolete = output / "prepare_units.py"
    if obsolete.exists():
        obsolete.unlink()
    payloads.pop("prepare_units.py", None)
    for name in ("GO-PROCEDURE.md", "DEPLOYMENT.md"):
        emit(name, operational_notes().encode())
    # Authenticated replay files retain their exact landed bytes. dry_run
    # adapts the historical unit contract in memory, never in this inventory.
    if record_raw is None:
        contracts = "test_unit_contracts.py"
        text = verified[contracts].decode().replace("-seq2", "-seq3")
        text = text.replace("self.assertEqual(len(hooks),3)", "self.assertEqual(len(hooks),2)")
        text = text.replace("self.assertIn('touch --no-dereference',hooks[1])", "self.assertNotIn('touch','\\n'.join(hooks))")
        text = text.replace("hooks[2].endswith", "hooks[1].endswith")
        emit(contracts, text.encode())
    removed, unit_names = 0, []
    for name, raw in sorted(units.items()):
        body, count = rewrite_unit(raw.decode(), old_root, output)
        if str(old_root) + "/" in body:
            raise ValueError("old_unit_root_survives_relocation")
        removed += count
        renamed = name.replace("-seq2", "-seq3")
        (output / "units" / name).rename(output / "units" / renamed)
        payloads.pop("units/" + name)
        emit("units/" + renamed, body.encode())
        unit_names.append(renamed)
    if removed != 8 or len(unit_names) != 22:
        raise ValueError("seq2_unit_inventory_changed")
    (output / "units").chmod(0o500)
    counts = {}
    for folder, field in (("frozen", "frozen_files"), ("configs", "config_files")):
        names = {name for name in verified if name.startswith(folder + "/")}
        actual = {p.relative_to(output).as_posix() for p in (output / folder).rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo")}
        if actual != names or any(payloads[name] != verified[name] for name in names):
            raise ValueError("frozen_runtime_or_config_changed")
        counts[field] = len(names)
    comparison = {**counts, "equal": True}
    if record_raw is not None:
        emit("REPLAY-INVENTORY.md", record_raw)
    names = sorted(payloads)
    sums = "\n".join(sha(payloads[name]) + "  " + name for name in names) + "\n"
    expected_inventory = sums.encode()
    write(output / "SHA256SUMS", expected_inventory)
    # Re-reading is verification only: changed output can never become the
    # preimage of a newly certified digest. Refuse before any success receipt.
    final_check = subprocess.run(["sha256sum", "--check", "--strict", "--quiet", "-"],
                                 cwd=output, capture_output=True, input=expected_inventory)
    if final_check.returncode or (output / "SHA256SUMS").read_bytes() != expected_inventory:
        raise ValueError("generated_bundle_manifest_refused")
    bundle_sha = sha(expected_inventory)
    request = json.loads(request_raw)
    request.update(bundle_sha256=bundle_sha, deployment_glue_version=VERSION,
                   deployment_glue_commit=source_commit,
                   predecessor_bundle_sha256=predecessor_sha256,
                   predecessor_receipt_origin_sha256=predecessor_sha256,
                   issuer_python={"implementation": "CPython", "version": [3, 12],
                                  "asserted_before": "readiness or GO writing"},
                   lane_stop="alpaca-paper/lane-b/STOP", host_stop="read-only operator kill switch",
                   runtime_and_config_bytes="identical to predecessor", unchanged_comparison=comparison,
                   unit_files=unit_names, start_until_GO=False)
    if provenance is not None:
        request["replay_inventory"] = provenance
    request_bytes = (json.dumps(request, indent=2, sort_keys=True) + "\n").encode()
    write(output / "GO-BINDING-REQUEST.json", request_bytes)
    result = {"version": VERSION, "bundle_sha256": bundle_sha, "predecessor_bundle_sha256": predecessor_sha256,
              "source_commit": source_commit, "files": len(names), "units": unit_names,
              "removed_global_touch_hooks": removed, "runtime_and_configs_unchanged": comparison["equal"],
              "unchanged_comparison": comparison, "GO_BINDING_REQUEST_sha256": sha(request_bytes),
              "installed": False, "orders": "NOT_RUN"}
    if provenance is not None:
        result["replay_inventory"] = provenance
    write(output / "RECUT-RECEIPT.json", (json.dumps(result, indent=2, sort_keys=True) + "\n").encode())
    output.chmod(0o500)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--predecessor-sha256", required=True, help="expected digest from the sealed private binding")
    parser.add_argument("--replay-inventory", type=Path, help="separate CC-authenticated git replay record")
    parser.add_argument("--replay-inventory-sha256", help="expected record hash from the CC")
    args = parser.parse_args()
    result = recut(args.source, args.output, args.source_commit,
                   predecessor_sha256=args.predecessor_sha256,
                   replay_inventory_path=args.replay_inventory,
                   replay_inventory_sha256=args.replay_inventory_sha256)
    print(json.dumps({k: v for k, v in result.items() if k != "predecessor_bundle_sha256"}, sort_keys=True))


if __name__ == "__main__":
    main()
