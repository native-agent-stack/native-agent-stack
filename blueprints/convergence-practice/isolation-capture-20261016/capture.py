"""Record native bytes privately, then publish explicit byte-mask derivatives.

Reference: CPython v3.13.16 Doc/library/subprocess.rst, Popen standard-stream
file handles, wait/returncode, and binary-mode output. No text decoder runs on
captured streams. This is a bounded evidence recorder, not a sandbox.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def record(root, name, argv, cwd, environment, timeout=180):
    """Never reuse a capture name; native stdout/stderr go straight to files."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        raise ValueError("invalid capture name")
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = root / name
    target.mkdir(mode=0o700)  # existing captures are immutable inputs
    start = datetime.now(timezone.utc).isoformat()
    before = time.monotonic()
    metadata = {"schema_version": 1, "name": name, "argv": list(map(str, argv)),
                "cwd": str(Path(cwd).resolve()), "environment": environment,
                "started_at_utc": start, "timeout_seconds": timeout}
    save_json(target / "invocation.json", metadata)
    os.chmod(target / "invocation.json", 0o600)
    streams = {}
    try:
        for key in ("stdout", "stderr"):
            fd = os.open(target / (key + ".bin"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            streams[key] = os.fdopen(fd, "wb")
        process = subprocess.Popen(metadata["argv"], cwd=cwd, env=environment,
                                   stdin=subprocess.DEVNULL, **streams)
        timed_out = False
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            code = process.wait()
    finally:
        for stream in streams.values():
            stream.close()
    metadata.update(exit_code=code, timed_out=timed_out,
                    finished_at_utc=datetime.now(timezone.utc).isoformat(),
                    elapsed_seconds=round(time.monotonic() - before, 6))
    metadata["streams"] = {}
    for key in ("stdout", "stderr"):
        raw = (target / (key + ".bin")).read_bytes()
        metadata["streams"][key] = {"bytes": len(raw), "sha256": digest(raw)}
    save_json(target / "record.json", metadata)
    os.chmod(target / "record.json", 0o600)
    return metadata


def mask_bytes(raw, replacements):
    """One simultaneous literal substitution; bytes outside matches are exact."""
    pairs = {key.encode(): value.encode() for key, value in replacements.items()}
    if any(not key for key in pairs):
        raise ValueError("empty mask source")
    if any(not re.fullmatch(rb"<[A-Z][A-Z0-9_]*>", value) for value in pairs.values()):
        raise ValueError("mask destinations must be marked placeholders")
    if len(set(pairs.values())) != len(pairs):
        raise ValueError("mask destinations must be distinct")
    if not pairs:
        return raw
    pattern = re.compile(b"|".join(re.escape(key) for key in sorted(pairs, key=lambda x: (-len(x), x))))
    return pattern.sub(lambda match: pairs[match.group()], raw)


def masked_text(text, replacements):
    return mask_bytes(text.encode("utf-8"), replacements).decode("utf-8")


def render(capture_dir, replacements):
    """Verify private originals first; no private digest enters the result."""
    capture_dir = Path(capture_dir)
    metadata = json.loads((capture_dir / "record.json").read_text())
    if metadata.get("schema_version") != 1 or metadata["name"] != capture_dir.name:
        raise ValueError("capture metadata identity mismatch")
    if type(metadata["exit_code"]) is not int:
        raise ValueError("capture must contain a native integer return code")
    if metadata["timed_out"]:
        raise ValueError("timed-out capture cannot be published as a completed run")
    result = {}
    public = {"schema_version": 1, "kind": "masked_native_capture",
              "capture_name": metadata["name"],
              "private_raw_reference": metadata["name"],
              "masking": {"rule": "capture.py:mask_bytes", "mode": "simultaneous literal byte replacement",
                          "placeholders": sorted(replacements.values()),
                          "raw_reference_policy": "Private capture is named only; raw hashes stay private."},
              "argv": [masked_text(value, replacements) for value in metadata["argv"]],
              "cwd": masked_text(metadata["cwd"], replacements),
              "environment": {key: masked_text(value, replacements)
                              for key, value in metadata["environment"].items()},
              "started_at_utc": metadata["started_at_utc"],
              "finished_at_utc": metadata["finished_at_utc"],
              "elapsed_seconds": metadata["elapsed_seconds"],
              "exit_code": metadata["exit_code"], "streams": {}}
    for key in ("stdout", "stderr"):
        raw = (capture_dir / (key + ".bin")).read_bytes()
        expected = metadata["streams"][key]
        if len(raw) != expected["bytes"] or digest(raw) != expected["sha256"]:
            raise ValueError("private capture bytes do not match recorder metadata")
        masked = mask_bytes(raw, replacements)
        filename = metadata["name"] + "." + key + ".txt"
        result[filename] = masked
        public["streams"][key] = {"path": filename, "bytes": len(masked),
                                   "sha256": digest(masked), "hash_scope": "published bytes"}
    result[metadata["name"] + ".json"] = (json.dumps(public, indent=2) + "\n").encode()
    return result


def publish(raw_dir, rules_path, output):
    raw_dir, output = Path(raw_dir), Path(output)
    replacements = json.loads(Path(rules_path).read_text())
    output.mkdir(parents=True, exist_ok=True)
    produced = []
    for capture_dir in sorted(raw_dir.iterdir()):
        if not capture_dir.is_dir():
            continue
        for name, raw in render(capture_dir, replacements).items():
            path = output / name
            if path.exists() and path.read_bytes() != raw:
                raise ValueError("refusing to overwrite a different derivative")
            path.write_bytes(raw)
            produced.append(name)
    return produced


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    files = publish(args.raw_dir, args.rules, args.out)
    print(json.dumps({"status": "published", "files": len(files)}))


if __name__ == "__main__":
    main()
