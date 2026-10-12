"""Co-op issuer entrypoint; delegates all validity and single-use checks."""
import json
from paper_deployment import LABEL, main

if __name__ == "__main__":
    try:
        from runtime_lock import runtime_read_lock
        with runtime_read_lock():
            code = main()
    except Exception as exc:
        print(json.dumps({**LABEL, "status": "refused", "reason": type(exc).__name__}))
        code = 2
    raise SystemExit(code)
