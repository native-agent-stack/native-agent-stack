"""Publication-safety scan: counts (never the matched text) of identifier-shaped and path-shaped tokens in the files given.
Classes: account_number_9plus_digits (digit runs of 9+ outside 40/64-hex digests; 10-digit 2026-era Unix seconds are counted apart as clock readings), paper_account_PA_shape, api_key_id_shape (PK/AK + 16-20 alphanumerics), uuid_shape, email_shape, ipv4_shape,
home_dir_literal, var_tmp_literal, run_user_literal, state_dir_literal, caller-supplied literals (--literal, matched case-insensitively), client_order_id_prefix_shape.
Exit 0 only when every file has zero matches for every class (--allow CLASS=N relaxes one class to at most N for named raw inputs).
usage: python3 audit_publication_safety.py [--literal TOKEN]... [--allow CLASS=N]... FILE [FILE...]"""
import re
import sys

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
        text = open(path, "rb").read().decode("utf-8", errors="replace")
        row = {}
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
