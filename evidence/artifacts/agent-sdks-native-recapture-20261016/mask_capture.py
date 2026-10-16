"""Deterministic literal path masking; never filter or summarize native output.

Reference: CPython 3.13 bytes.replace and pathlib.Path.read_bytes/write_bytes.
The private native input remains unchanged. Only output bytes are hashed.
The caller supplies the private scratch root; it is not stored in public output.
"""
import argparse
import hashlib
import json
from pathlib import Path

MARKER = b"<SCRATCH_ARM>"


def mask(raw: bytes, scratch_root: bytes) -> bytes:
    """Replace one exact private path token, preserving every other byte."""
    if not scratch_root.startswith(b"/") or scratch_root == b"/":
        raise ValueError("scratch root must be a non-root absolute path")
    if b"\x00" in scratch_root or MARKER in scratch_root:
        raise ValueError("invalid scratch root")
    return raw.replace(scratch_root, MARKER)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--private-checks", type=Path)
    parser.add_argument("--checkout-root", type=Path)
    parser.add_argument("--packet-root", type=Path)
    args = parser.parse_args()
    root = args.private_root.resolve()
    out = args.out.resolve()
    if out == root or root in out.parents or out in root.parents:
        raise ValueError("output must be separate from the private native capture")
    rows = [json.loads(line) for line in (root / "steps.jsonl").read_text().splitlines()]
    if [row["n"] for row in rows] != list(range(1, 12)):
        raise ValueError("expected eleven recorded steps; do not fabricate a replacement")
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for row in rows:
        raw_path = (root / row["log"]).resolve()
        if not raw_path.is_relative_to(root):
            raise ValueError("native log escapes the private capture")
        raw = raw_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["log_sha256"]:
            raise ValueError("private native capture integrity mismatch")
        output = mask(raw, bytes(root))
        name = f"output-{row['n']:02d}.txt"
        (out / name).write_bytes(output)
        command = mask(row["command"].encode(), bytes(root)).decode()
        records.append({
            **{k: row[k] for k in ("n", "phase", "exit_code", "started", "ended", "seconds")},
            "command_with_marked_placeholders": command,
            "cwd_relative_to_SCRATCH_ARM": row["cwd"],
            "output": name,
            "output_sha256": hashlib.sha256(output).hexdigest(),
            "output_bytes": len(output),
            "capture_class": "deterministically_masked_native_capture",
            "private_capture_name": row["log"],
            "masking_rule": "mask_capture.py: mask(); literal private scratch-root bytes -> <SCRATCH_ARM>; every other byte preserved",
            "masking_test": "test_mask_capture.py",
            "co_op_private_reproduction": "pending",
        })
    receipt = {
        "kind": "masked_native_recapture",
        "status": "pending_co_op_private_reproduction",
        "private_capture": "agent-sdks replacement sequential run; steps.jsonl and logs/; raw digests private only",
        "commands": records,
        "limits": [
            "Preserves existing command rc/times; does not execute any vendor command",
            "Native initialize response is captured verbatim; production/adoption-window F2 remains GAP",
            "Closed-environment bootstrap and binary byte identity have their own source/capture references",
            "Fixture-based SDK tests are local integration, not provider or comparative A6 evidence",
        ],
    }
    (out / "runtime-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if args.private_checks:
        checks = []
        replacements = [(bytes(root), MARKER)]
        for path, marker in ((args.checkout_root, b'<REVIEW_CHECKOUT>'),
                             (args.packet_root, b'<PACKET_SCRATCH>'),
                             (args.private_checks, b'<PRIVATE_CHECKS>')):
            if path:
                replacements.append((bytes(path.resolve()), marker))

        def masked_aux(raw):
            for old, new in replacements:
                raw = raw.replace(old, new)
            return raw

        check_root = args.private_checks.resolve()
        for line in (check_root / 'checks.jsonl').read_text().splitlines():
            row = json.loads(line)
            raw_path = (check_root / row['log']).resolve()
            if not raw_path.is_relative_to(check_root):
                raise ValueError('check output escapes private capture')
            raw = raw_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != row['raw_sha256']:
                raise ValueError('check output integrity mismatch')
            output = masked_aux(raw)
            name = row['name'] + '.txt'
            (out / name).write_bytes(output)
            checks.append({
                'name': row['name'], 'exit_code': row['exit_code'],
                'started': row['started'], 'ended': row['ended'],
                'command_with_marked_placeholders': [masked_aux(arg.encode()).decode() for arg in row['command']],
                'cwd_with_marked_placeholders': masked_aux(row['cwd'].encode()).decode(),
                'capture_class': 'deterministically_masked_native_capture',
                'private_capture_name': row['log'], 'output': name,
                'output_sha256': hashlib.sha256(output).hexdigest(),
                'masking_rule': 'mask_capture.py: masked_aux(); literal root replacements only',
                'masking_test': 'test_mask_capture.py', 'co_op_private_reproduction': 'pending',
            })
        (out / 'check-receipts.json').write_text(json.dumps(checks, indent=2) + '\n')
    print("Prepared eleven full native masked outputs; no private digests exported")


if __name__ == "__main__":
    main()
