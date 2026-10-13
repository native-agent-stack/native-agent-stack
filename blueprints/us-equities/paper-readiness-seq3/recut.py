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
        "def stop_present():\n    return latch_pending(STOP, HOST_STOP)")
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
    return once(text, "if launch.STOP.exists() or launch.STOP.is_symlink():", "if launch.stop_present():")


def rewrite_unit(text, old_root, new_root):
    # The redundant touch hook also writes HOST STOP and changes its metadata.
    lines = text.splitlines()
    removed = sum(line.startswith("ExecStopPost=/usr/bin/bash -c '") and "/usr/bin/touch" in line for line in lines)
    text = "\n".join(line for line in lines if not (
        line.startswith("ExecStopPost=/usr/bin/bash -c '") and "/usr/bin/touch" in line)) + "\n"
    text = text.replace(str(old_root), str(new_root)).replace("-seq2", "-seq3")
    text = text.replace("before touching the global latch", "before creating the owned lane latch")
    if "/usr/bin/touch" in text or "alpaca-paper/STOP" in text:
        raise ValueError("global_stop_unit_writer_remains")
    return text, removed


def write(path, raw):
    if path.exists():
        path.chmod(0o600)
    path.write_bytes(raw)
    path.chmod(0o400)


def recut(source, output, source_commit):
    source, output = Path(source).resolve(), Path(output).absolute()
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
    # Reuse the frozen archive. Never mutate the original, even on failure.
    shutil.copytree(source, output, symlinks=False)
    # The predecessor is read-only. Only our newly copied unit directory needs
    # write permission to relocate filenames; restore it before returning.
    (output / "units").chmod(0o700)
    write(output / "launch.py", launch.encode())
    write(output / "issue_go.py", issuer.encode())
    helper = Path(__file__).with_name("lane_latch.py")
    write(output / "lane_latch.py", helper.read_bytes())
    removed, unit_names = 0, []
    for path in sorted((output / "units").glob("*")):
        if path.suffix not in (".path", ".service"):
            raise ValueError("unexpected_unit_file")
        body, count = rewrite_unit(path.read_text(), source, output)
        removed += count
        renamed = path.with_name(path.name.replace("-seq2", "-seq3"))
        path.rename(renamed)
        write(renamed, body.encode())
        unit_names.append(renamed.name)
    if removed != 8 or len(unit_names) != 22:
        raise ValueError("seq2_unit_inventory_changed")
    (output / "units").chmod(0o500)
    # Preserve the strict runtime inventory scope, add the latch helper and
    # relocate all renamed units. The binding request is a separate envelope.
    names = [line.split("  ", 1)[1] for line in inventory.decode().splitlines()]
    names = [n.replace("-seq2", "-seq3") if n.startswith("units/") else n for n in names]
    names.append("lane_latch.py")
    sums = "\n".join(sha((output / n).read_bytes()) + "  " + n for n in sorted(names)) + "\n"
    write(output / "SHA256SUMS", sums.encode())
    bundle_sha = sha(sums.encode())
    request = json.loads((source / "GO-BINDING-REQUEST.json").read_text())
    request.update(bundle_sha256=bundle_sha, deployment_glue_version=VERSION,
                   deployment_glue_commit=source_commit, predecessor_bundle_sha256=PREDECESSOR,
                   lane_stop="alpaca-paper/lane-b/STOP", host_stop="read-only operator kill switch",
                   runtime_and_config_bytes="identical to predecessor", unit_files=unit_names,
                   start_until_GO=False)
    write(output / "GO-BINDING-REQUEST.json", (json.dumps(request, indent=2, sort_keys=True) + "\n").encode())
    result = {"version": VERSION, "bundle_sha256": bundle_sha, "predecessor_bundle_sha256": PREDECESSOR,
              "source_commit": source_commit, "files": len(names), "units": unit_names,
              "removed_global_touch_hooks": removed, "runtime_and_configs_unchanged": True,
              "GO_BINDING_REQUEST_sha256": sha((output / "GO-BINDING-REQUEST.json").read_bytes()),
              "installed": False, "orders": "NOT_RUN"}
    write(output / "RECUT-RECEIPT.json", (json.dumps(result, indent=2, sort_keys=True) + "\n").encode())
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
