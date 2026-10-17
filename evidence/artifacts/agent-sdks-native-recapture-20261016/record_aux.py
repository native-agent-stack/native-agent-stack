"""Privately capture repository checks with CPython 3.13 subprocess and byte I/O.

Raw output and its digest stay private; publish only masked derivatives.
"""
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def main():
    private, name, cwd, *command = sys.argv[1:]
    root = Path(private).resolve()
    if not name.replace('-', '').isalnum():
        raise ValueError('name must be alphanumeric with dashes')
    root.mkdir(parents=True, exist_ok=True)
    log = root / (name + '.log')
    if log.exists():
        raise FileExistsError('never overwrite an earlier capture')
    start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with log.open('wb') as handle:
        rc = subprocess.run(command, cwd=cwd, stdout=handle, stderr=subprocess.STDOUT).returncode
    end = datetime.datetime.now(datetime.timezone.utc).isoformat()
    row = dict(name=name, command=command, cwd=cwd, exit_code=rc, started=start, ended=end,
               log=log.name, raw_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
    with (root / 'checks.jsonl').open('a') as handle:
        handle.write(json.dumps(row) + '\n')
    print(name, 'exit', rc)
    return rc


if __name__ == '__main__':
    sys.exit(main())
