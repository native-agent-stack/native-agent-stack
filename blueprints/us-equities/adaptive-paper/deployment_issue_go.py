"""Co-op issuer entrypoint; delegates all validity and single-use checks."""
from paper_deployment import main

if __name__ == "__main__":
    from runtime_lock import runtime_read_lock
    with runtime_read_lock():
        raise SystemExit(main())
