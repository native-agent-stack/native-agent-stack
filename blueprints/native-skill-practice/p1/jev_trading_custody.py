"""Private proof verification and the native credential-runner start boundary.

No store, inventory, /proc/*/environ or credential file is read here. The parent
check uses process metadata and the public runner's parse_args contract only.
Source: tools/credentials/credential_run.py parse_args / run_command at the
reviewed repository revision. Private digests never leave verify_attestation().
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re

from jev_trading_cases import SOURCE_PINS

ROOT = Path(__file__).resolve().parents[3]
SDK_VERSION = "0.7.2"
SDK_WHEEL_SHA256 = "0a961148187d52e18276ed7f2d02617cfac48e3b97673cb631a8749397d43d1e"
ADDENDUM_REFERENCE = "coordination/trading-cc/specs/jev-trading-20261015/JEV-HARNESS-ADDENDUM-01.md"
DIGEST = re.compile(r"[0-9a-f]{64}")


def _load_public_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parent_processes():
    pid, seen = os.getppid(), set()
    while pid > 1 and pid not in seen and len(seen) < 32:
        seen.add(pid)
        directory = Path("/proc") / str(pid)
        if directory.stat().st_uid != os.getuid():
            return
        argv = directory.joinpath("cmdline").read_bytes().split(b"\0")
        argv = [word.decode("utf-8", errors="replace") for word in argv if word]
        yield argv, directory.joinpath("cwd").resolve()
        # Linux proc_pid_stat(5): fields after the final ')' start with state,
        # then PPID. Command names may contain spaces and parentheses.
        pid = int(directory.joinpath("stat").read_text().rsplit(")", 1)[1].split()[1])


def require_credential_run():
    """Refuse before any SCORED output or key value is consumed.

    This checks the native runner scope for an accidental out-of-runner start;
    it is not authentication against a hostile process owned by the same user.
    The actual inventory/store authorization remains the native runner's job.
    """
    if "TYPESAFE_API_KEY" not in os.environ:
        raise PermissionError("SCORED start requires credential_run typesafe")
    source = ROOT / "tools/credentials/credential_run.py"
    runner = _load_public_module(source, "jev_public_credential_parser")
    expected = hashlib.sha256(source.read_bytes()).digest()
    try:
        for argv, cwd in _parent_processes():
            for index, argument in enumerate(argv):
                if Path(argument).name != "credential_run.py":
                    continue
                candidate = Path(argument)
                if not candidate.is_absolute():
                    candidate = cwd / candidate
                if hashlib.sha256(candidate.read_bytes()).digest() != expected:
                    continue
                request = runner.parse_args(argv[index + 1:])
                if request and request[0] == "typesafe" and not request[2] and request[3]:
                    return
    except (OSError, ValueError, runner.UsageError):
        pass
    raise PermissionError("SCORED start requires a verified credential_run typesafe parent")


def _private_file(path, *, outside=False):
    path = Path(path).resolve()
    if path.name in {".claude.json", ".env"} or path.suffix == ".env":
        raise ValueError("private record must be provenance, never a credential file")
    if outside and path.is_relative_to(ROOT):
        raise ValueError("private record must remain outside the repository")
    return path


def _verified_record(record, *, outside=False):
    if not isinstance(record, dict) or not isinstance(record.get("sha256"), str) or not DIGEST.fullmatch(record["sha256"]):
        raise ValueError("private record requires a path and verification digest")
    try:
        path = _private_file(record["path"], outside=outside)
        data = path.read_bytes()
    except (KeyError, TypeError, OSError):
        raise ValueError("private record is unavailable") from None
    if hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise ValueError("private record changed after its private pin")
    # The public projection contains names/paths only. Even a digest-shaped
    # filename is suppressed; no absolute home path or private proof is copied.
    reference = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else "<PRIVATE>/" + path.name
    reference = DIGEST.sub("<private-digest-omitted>", reference)
    return {"path": reference, "verified": True}


def verify_attestation(path):
    if not isinstance(path, (str, Path)):
        raise ValueError("scored attestation must name a private provenance file")
    try:
        document = json.loads(_private_file(path, outside=True).read_text())
    except (OSError, ValueError):
        raise ValueError("private attestation cannot be read") from None
    if document.get("source_sha256") != SOURCE_PINS:
        raise ValueError("frozen source attestation mismatch")
    addendum = _verified_record(document.get("addendum"), outside=True)
    reviews = document.get("two_family_reads", {})
    if not isinstance(reviews, dict) or set(reviews) != {"codex", "claude"}:
        raise ValueError("two-family private review records required")
    review_records = {family: _verified_record(record, outside=True) for family, record in reviews.items()}
    sdk = document.get("sdk", {})
    if sdk.get("version") != SDK_VERSION or sdk.get("wheel_sha256") != SDK_WHEEL_SHA256:
        raise ValueError("SDK attestation must match the adopted pinned transport")
    amendment = _verified_record(sdk.get("amendment"))
    models = _verified_record(document.get("models_page"))
    return {"authorization_record": addendum, "review_records": review_records,
            "sdk": {"version": SDK_VERSION, "wheel_sha256": SDK_WHEEL_SHA256, "amendment_record": amendment},
            "models_page_record": models}
