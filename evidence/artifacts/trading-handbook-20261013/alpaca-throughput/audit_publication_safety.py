"""Publication-safety scan: counts (never the matched text) of identifier-shaped and path-shaped tokens in the files given.
Classes: account_number_9plus_digits (digit runs of 9+ outside 40/64-hex digests; 10-digit 2026-era Unix seconds are counted apart as clock readings), paper_account_PA_shape, api_key_id_shape (PK/AK + 16-20 alphanumerics), uuid_shape, email_shape, ipv4_shape,
home_dir_literal, var_tmp_literal, run_user_literal, state_dir_literal, caller-supplied literals (--literal, matched case-insensitively), client_order_id_prefix_shape.
Exit 0 only when every file has zero matches for every class (--allow CLASS=N relaxes one class to at most N for named raw inputs).
usage: python3 audit_publication_safety.py [--literal TOKEN]... [--allow CLASS=N]... FILE [FILE...]"""
import json
import re
import sys
from pathlib import Path

# Published capacity.py blobs at these ancestor revisions, verified with
# git show <revision>:blueprints/us-equities/order-throughput/capacity.py.
# These bind this dated projection only; new source bindings need verification.
PUBLIC_CODE_BINDINGS = {
    ("facts", "capacity_py_sha256", "a1"):
        "91563bd337a50416584cc12e95eebbcc1b19cfdf34a428cdce71b2470b274f69",
    ("facts", "capacity_py_sha256", "a2"):
        "024797332ff367b76560c5c4495750d32b08143d5d4d824839eee333d3643567",
    ("facts", "harness_revision_a1"): "dbe7a8da1bb497570471e2b9d0dcfe56bbdc56e9",
    ("facts", "harness_revision_a2"): "d6056831b4e7324436f0ace2517066f708f86bf5",
}

HEX_DIGEST = re.compile(r"\b(?:[0-9a-fA-F]{64}|[0-9a-fA-F]{40})\b")
LONG_RUN = re.compile(r"(?<![0-9.])[0-9]{9,}(?![0-9])")
EPOCH_SECONDS = re.compile(r"^1[78][0-9]{8}$")      # 10 digits, 2026-era Unix seconds (1.70e9-1.89e9): a clock reading, not an account number

CLASSES = {
    "paper_account_PA_shape": re.compile(r"\bPA[0-9A-Z]{8,12}\b"),
    "api_key_id_shape": re.compile(r"\b(?:PK|AK|CK)[A-Z0-9]{16,20}\b"),
    "uuid_shape": re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
    "email_shape": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "ipv4_shape": re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
    "home_dir_literal": re.compile("/" + "home" + "/"),
    "var_tmp_literal": re.compile("/" + "var" + "/" + "tmp"),
    "run_user_literal": re.compile("/" + "run" + "/" + "user"),
    "state_dir_literal": re.compile("[.]" + "local" + "/" + "state"),
    "client_order_id_prefix_shape": re.compile(r"\bcap-[0-9]{8}t[0-9]{6}-[0-9a-f]{4,8}-"),
}


def json_identifier_errors(document):
    errors = []

    def inspect(text):
        if any(pattern.search(text) for pattern in CLASSES.values()):
            errors.append("publication policy refused text")
        runs = LONG_RUN.findall(HEX_DIGEST.sub(" ", text))
        if any(not EPOCH_SECONDS.match(run) for run in runs):
            errors.append("publication policy refused text")

    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                inspect(key)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str):
            inspect(value)

    visit(document)
    return errors


def projection_publication_errors(document):
    """#1090 blocker 1: private sources are name-only, never fingerprinted.

    Existing facts bindings identify published code, not receipts. All other
    seven-or-more-hex tokens are refused without values in diagnostics.
    """
    errors = json_identifier_errors(document)
    receipts = document.get("provenance", {}).get("private_receipts", [])
    if not isinstance(receipts, list) or any(
            not isinstance(row, dict) or set(row) != {"name"}
            or not isinstance(row.get("name"), str) for row in receipts):
        errors.append("private receipt citations must contain names only")

    def visit(value, path=()):
        if isinstance(value, dict):
            for key, child in value.items():
                if re.search(r"[0-9a-fA-F]{7,}", key):
                    errors.append("publication policy refused field")
                visit(child, (*path, key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, (*path, str(index)))
        elif isinstance(value, str) and re.search(r"[0-9a-fA-F]{7,}", value):
            if PUBLIC_CODE_BINDINGS.get(path) != value:
                errors.append("unpublished fingerprint in projection field")

    visit(document)
    return errors


def main(argv):
    literals, allow, files = [], {}, []
    i = 0
    while i < len(argv):
        if argv[i] == "--literal":
            literals.append(argv[i + 1])
            i += 2
        elif argv[i] == "--allow":
            name, count = argv[i + 1].split("=")
            allow[name] = int(count)
            i += 2
        else:
            files.append(argv[i])
            i += 1
    failed = False
    for path in files:
        text = Path(path).read_bytes().decode("utf-8", errors="replace")
        row = {}
        try:
            document = json.loads(text)
        except ValueError:
            document = None
        if document is not None:
            row["decoded_json_identifiers"] = len(json_identifier_errors(document))
        if isinstance(document, dict) and str(document.get("schema", "")).startswith("alpaca-throughput-evidence/"):
            row["projection_publication_policy"] = len(projection_publication_errors(document))
        for name, pattern in CLASSES.items():
            row[name] = len(pattern.findall(text))
        runs = LONG_RUN.findall(HEX_DIGEST.sub(" ", text))
        row["account_number_9plus_digits"] = sum(1 for run in runs if not EPOCH_SECONDS.match(run))
        row["epoch_seconds_clock_readings_allowed"] = sum(1 for run in runs if EPOCH_SECONDS.match(run))
        for number, token in enumerate(literals, 1):
            row[f"caller_literal_{number}"] = len(re.findall(re.escape(token), text, flags=re.I))
        bad = {k: v for k, v in row.items() if v > allow.get(k, 0) and k != "epoch_seconds_clock_readings_allowed"}
        failed = failed or bool(bad)
        shown = {k: v for k, v in row.items() if v}
        print(f"{'FAIL' if bad else 'OK  '} {path.rsplit('/', 1)[-1]} ({len(text.encode())} B) matches: {shown if shown else 'none'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
