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
import shutil
import subprocess

LAUNCH_SHA = "7ee83afc6f9197abc5e02181524449fce3be9947f75cb8f750eb4396a96275e4"
ISSUER_SHA = "8fb23913da2e17831c0fff67cb88c3e6310705467a5ae437974c7d7e645e9c2b"
PREDECESSOR = "d268be9228d21520c5bba7947471f3ea6e49873df3b75a05dc8a93c93f87a1c1"
VERSION = "readiness-sequencing-v3-lane-latch"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("unexpected_seq2_source_shape")
    return text.replace(old, new)


def rewrite_launch(text):
    if sha(text.encode()) != LAUNCH_SHA:
        raise ValueError("seq2_launcher_pin_mismatch")
    text = once(text, "STOP = Path.home() / '.local/state/native-agent-stack/alpaca-paper/STOP'",
        "HOST_STOP = Path.home() / '.local/state/native-agent-stack/alpaca-paper/STOP'\n"
        "STOP = HOST_STOP.parent / 'lane-b/STOP'\n"
        "from lane_latch import pending as latch_pending, mark as latch_mark, clear as latch_clear\n\n"
        "def stop_present():\n    return latch_pending(STOP, HOST_STOP)\n\n"
        "def assert_seq2_watchers_retired():\n"
        "    from seq2_retirement import assert_retired\n"
        "    try:\n        return assert_retired()\n"
        "    except (ValueError, OSError):\n        raise Refused('seq2_watchers_not_retired') from None")
    if text.count("if STOP.exists() or STOP.is_symlink():") != 2:
        raise ValueError("seq2_stop_admission_shape")
    text = text.replace("if STOP.exists() or STOP.is_symlink():", "if stop_present():")
    text = once(text, "PREDECESSOR_BUNDLE = 'c738f1439a3267dc19f99c2800ec85ff7c568bfcb1f345b1e237dfa002e95fec'",
                "PREDECESSOR_BUNDLE = '" + PREDECESSOR + "'")
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
        if prior.get('version') != 'lane-b-stage-latch-v1' or prior.get('trial') != active['trial']:
            raise Refused('lane_stop_ownership_mismatch')
        return 0
    save(receipt, latch_mark(STOP, HOST_STOP, active['trial']))
    return 0

'''
    text = text[:start] + replacement + text[end:]
    text = once(text, "        before = STOP.stat(follow_symlinks=False)\n", "")
    start = text.index("            after = STOP.stat(follow_symlinks=False)")
    end = text.index("            save(STATE/'completed'", start)
    text = text[:start] + "            owned = safe_json(instance / 'stop-hook.json')\n" + \
        "            receipt['stop_cleared'] = latch_clear(STOP, HOST_STOP, owned, active['trial'])\n" + text[end:]
    ast.parse(text)
    return text


def rewrite_issuer(text):
    if sha(text.encode()) != ISSUER_SHA:
        raise ValueError("seq2_issuer_pin_mismatch")
    text = once(text, "if launch.STOP.exists() or launch.STOP.is_symlink():", "if launch.stop_present():")
    return once(text, "def build(kind,trial,skip_reason=None):\n",
                "def build(kind,trial,skip_reason=None):\n    launch.assert_seq2_watchers_retired()\n")


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
is read-only. A human lane STOP is preserved. seq2 retirement is mandatory:
both generations otherwise watch the same GO files and can start together.

PREDECESSOR_BUNDLE is re-pinned to the actual seq2 manifest (d268be92) so genuine
same-state-root receipts carry forward without relabeling; c738f143 is not the
immediate predecessor of this version. Runtime and CONFIG bytes are compared.

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


def recut(source, output, source_commit):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or output.is_symlink() or output.is_relative_to(source):
        raise ValueError("new_bundle_destination_required")
    inventory = (source / "SHA256SUMS").read_bytes()
    if sha(inventory) != PREDECESSOR:
        raise ValueError("seq2_bundle_pin_mismatch")
    check = subprocess.run(["sha256sum", "--check", "--strict", "--quiet", "SHA256SUMS"], cwd=source)
    if check.returncode:
        raise ValueError("seq2_manifest_refused")
    launch = rewrite_launch((source / "launch.py").read_text())
    issuer = rewrite_issuer((source / "issue_go.py").read_text())
    old_root = embedded_unit_root(source / "units")
    # Reuse the frozen archive. Never mutate the original, even on failure.
    shutil.copytree(source, output, symlinks=False,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
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
    sums = "\n".join(sha((output / n).read_bytes()) + "  " + n for n in sorted(names)) + "\n"
    write(output / "SHA256SUMS", sums.encode())
    bundle_sha = sha(sums.encode())
    request = json.loads((source / "GO-BINDING-REQUEST.json").read_text())
    request.update(bundle_sha256=bundle_sha, deployment_glue_version=VERSION,
                   deployment_glue_commit=source_commit, predecessor_bundle_sha256=PREDECESSOR,
                   lane_stop="alpaca-paper/lane-b/STOP", host_stop="read-only operator kill switch",
                   runtime_and_config_bytes="identical to predecessor", unchanged_comparison=comparison,
                   unit_files=unit_names,
                   start_until_GO=False)
    write(output / "GO-BINDING-REQUEST.json", (json.dumps(request, indent=2, sort_keys=True) + "\n").encode())
    result = {"version": VERSION, "bundle_sha256": bundle_sha, "predecessor_bundle_sha256": PREDECESSOR,
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
    args = parser.parse_args()
    print(json.dumps(recut(args.source, args.output, args.source_commit), sort_keys=True))


if __name__ == "__main__":
    main()
