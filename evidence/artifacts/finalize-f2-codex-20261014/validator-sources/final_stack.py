# Verbatim selected definitions: native-agent-stack@252babe4040e39173cc178317c67699371806df6 scripts/final_stack.py

VERSION = r"v?(?P<version>\d+(?:\.\d+)+(?:[A-Za-z][0-9A-Za-z]*)?(?:[-.+~][0-9A-Za-z]+)*)"

COMMIT = r"(?P<commit>[0-9a-f]{40})"

COMMIT_PATTERN = re.compile(COMMIT)

PIN_FORMS = tuple(re.compile(form) for form in (
    VERSION, COMMIT, VERSION + " @ " + COMMIT, VERSION + "; source " + COMMIT))

UNPINNED = "unpinned"

def parse_pin(text) -> dict:
    """{"pin_parsed": {"version", "commit"}} for a pin in one of PIN_FORMS, else {"pin_parse": "unpinned"} for the
    text 'unpinned' or {"pin_parse": "unparsed"}."""
    if text == UNPINNED:
        return {"pin_parse": UNPINNED}
    if isinstance(text, str):
        for form in PIN_FORMS:
            match = form.fullmatch(text)
            if match:
                groups = match.groupdict()
                return {"pin_parsed": {"version": groups.get("version"), "commit": groups.get("commit")}}
    return {"pin_parse": "unparsed"}

def complete_final_pin(text, run: dict) -> bool:
    """FINAL uses the complete recorded run identity, not shared-field drift matching.

    A supplied commit must be present in runs[]. A receipt cannot drop a
    recorded commit and rely on a matching release name instead.
    """
    parsed = parse_pin(text).get("pin_parsed")
    canonical = run.get("pin_parsed")
    if not parsed or not canonical:
        return False
    if canonical.get("commit"):
        if parsed.get("commit") != canonical["commit"]:
            return False
    elif parsed.get("commit"):
        return False
    return all(canonical.get(key) == value for key, value in parsed.items() if value is not None)
