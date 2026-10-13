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


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


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
    roots = set()
    files = sorted(Path(units).iterdir())
    if len(files) != 22 or any(p.suffix not in (".path", ".service") or p.is_symlink() for p in files):
        raise ValueError("seq2_unit_inventory_changed")
    for path in files:
        lines = path.read_text().splitlines()
        working = [x.split("=", 1)[1] for x in lines if x.startswith("WorkingDirectory=")]
        if path.suffix == ".service" and len(working) != 1:
            raise ValueError("unit_embedded_root_missing")
        for value in working:
            root = Path(value)
            if not root.is_absolute() or ".." in root.parts or any(c.isspace() for c in value):
                raise ValueError("unit_embedded_root_unsafe")
            roots.add(value)
    if len(roots) != 1:
        raise ValueError("unit_embedded_roots_differ")
    root = Path(roots.pop())
    for path in files:
        if path.suffix == ".service":
            starts = [x for x in path.read_text().splitlines() if x.startswith("ExecStart=")]
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


def recut(source, output, source_commit, *, predecessor_sha256=None):
    if not isinstance(predecessor_sha256, str) or not re.fullmatch("[0-9a-f]{64}", predecessor_sha256):
        raise ValueError("predecessor_digest_required")
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or output.is_symlink() or output.is_relative_to(source):
        raise ValueError("new_bundle_destination_required")
    inventory = (source / "SHA256SUMS").read_bytes()
    if sha(inventory) != predecessor_sha256:
        raise ValueError("seq2_bundle_pin_mismatch")
    check = subprocess.run(["sha256sum", "--check", "--strict", "--quiet", "SHA256SUMS"], cwd=source)
    if check.returncode:
        raise ValueError("seq2_manifest_refused")
    launcher_entries = [line.split("  ", 1)[0] for line in inventory.decode().splitlines()
                        if line.endswith("  launch.py")]
    if len(launcher_entries) != 1:
        raise ValueError("launcher_inventory_binding_missing")
    # Reuse the frozen archive. Never mutate the original, even on failure.
    shutil.copytree(source, output, symlinks=False,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
    # Source verification is not a use-time binding. Adopt the reader's
    # verified fix: authenticate every copied row against the inventory
    # captured above, before rewriting or certifying any destination bytes.
    for line in inventory.decode().splitlines():
        digest, name = line.split("  ", 1)
        copied = output / name
        if copied.is_symlink() or not copied.is_file() or sha(copied.read_bytes()) != digest:
            raise ValueError("copied_bytes_not_in_sealed_inventory")
    launch = rewrite_launch((output / "launch.py").read_text(), predecessor_sha256, launcher_entries[0])
    issuer = rewrite_issuer((output / "issue_go.py").read_text())
    old_root = embedded_unit_root(output / "units")
    output.chmod(0o700)
    # The predecessor is read-only. Only our newly copied unit directory needs
    # write permission to relocate filenames; restore it before returning.
    (output / "units").chmod(0o700)
    write(output / "launch.py", launch.encode())
    write(output / "issue_go.py", issuer.encode())
    helper = Path(__file__).with_name("lane_latch.py")
    write(output / "lane_latch.py", helper.read_bytes())
    write(output / "seq2_retirement.py", helper.with_name("seq2_retirement.py").read_bytes())
    obsolete = output / "prepare_units.py"
    if obsolete.exists():
        obsolete.unlink()
    for name in ("GO-PROCEDURE.md", "DEPLOYMENT.md"):
        write(output / name, operational_notes().encode())
    contracts = output / "test_unit_contracts.py"
    if contracts.exists():
        text = contracts.read_text().replace("-seq2", "-seq3")
        text = text.replace("self.assertEqual(len(hooks),3)", "self.assertEqual(len(hooks),2)")
        text = text.replace("self.assertIn('touch --no-dereference',hooks[1])", "self.assertNotIn('touch','\\n'.join(hooks))")
        text = text.replace("hooks[2].endswith", "hooks[1].endswith")
        write(contracts, text.encode())
    removed, unit_names = 0, []
    for path in sorted((output / "units").glob("*")):
        if path.suffix not in (".path", ".service"):
            raise ValueError("unexpected_unit_file")
        body, count = rewrite_unit(path.read_text(), old_root, output)
        if str(old_root) + "/" in body:
            raise ValueError("old_unit_root_survives_relocation")
        removed += count
        renamed = path.with_name(path.name.replace("-seq2", "-seq3"))
        path.rename(renamed)
        write(renamed, body.encode())
        unit_names.append(renamed.name)
    if removed != 8 or len(unit_names) != 22:
        raise ValueError("seq2_unit_inventory_changed")
    (output / "units").chmod(0o500)
    comparison = unchanged_comparison(source, output)
    # Preserve the strict runtime inventory scope, add the latch helper and
    # relocate all renamed units. The binding request is a separate envelope.
    names = [line.split("  ", 1)[1] for line in inventory.decode().splitlines()]
    names = [n for n in names if n != "prepare_units.py" and "__pycache__" not in Path(n).parts and not n.endswith((".pyc", ".pyo"))]
    names = [n.replace("-seq2", "-seq3") if n.startswith("units/") else n for n in names]
    names.extend(["lane_latch.py", "seq2_retirement.py"])
    for name in REPLAY_SOURCES:
        if not (output / name).is_file() or (output / name).is_symlink():
            raise ValueError("replay_source_missing")
        if name not in names:
            names.append(name)
    sums = "\n".join(sha((output / n).read_bytes()) + "  " + n for n in sorted(names)) + "\n"
    write(output / "SHA256SUMS", sums.encode())
    bundle_sha = sha(sums.encode())
    request = json.loads((output / "GO-BINDING-REQUEST.json").read_text())
    request.update(bundle_sha256=bundle_sha, deployment_glue_version=VERSION,
                   deployment_glue_commit=source_commit, predecessor_bundle_sha256=predecessor_sha256,
                   issuer_python={"implementation": "CPython", "version": [3, 12],
                                  "asserted_before": "readiness or GO writing"},
                   lane_stop="alpaca-paper/lane-b/STOP", host_stop="read-only operator kill switch",
                   runtime_and_config_bytes="identical to predecessor", unchanged_comparison=comparison,
                   unit_files=unit_names,
                   start_until_GO=False)
    write(output / "GO-BINDING-REQUEST.json", (json.dumps(request, indent=2, sort_keys=True) + "\n").encode())
    result = {"version": VERSION, "bundle_sha256": bundle_sha, "predecessor_bundle_sha256": predecessor_sha256,
              "source_commit": source_commit, "files": len(names), "units": unit_names,
              "removed_global_touch_hooks": removed, "runtime_and_configs_unchanged": comparison["equal"],
              "unchanged_comparison": comparison,
              "GO_BINDING_REQUEST_sha256": sha((output / "GO-BINDING-REQUEST.json").read_bytes()),
              "installed": False, "orders": "NOT_RUN"}
    write(output / "RECUT-RECEIPT.json", (json.dumps(result, indent=2, sort_keys=True) + "\n").encode())
    output.chmod(0o500)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--predecessor-sha256", required=True, help="expected digest from the sealed private binding")
    args = parser.parse_args()
    result = recut(args.source, args.output, args.source_commit,
                   predecessor_sha256=args.predecessor_sha256)
    print(json.dumps({k: v for k, v in result.items() if k != "predecessor_bundle_sha256"}, sort_keys=True))


if __name__ == "__main__":
    main()
