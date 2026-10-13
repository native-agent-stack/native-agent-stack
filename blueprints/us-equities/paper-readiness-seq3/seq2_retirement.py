"""Read-only generation retirement proof. Never stop, enable or signal a unit."""
import subprocess

STAGES = ("record", "scan", "pre", "pre-skip", "sip", "lev1", "lev2", "lev4", "edge2", "edge8", "iex")
PATHS = tuple("paper-ready-" + stage + "-8c95a50d-seq2.path" for stage in STAGES)


def assert_retired():
    result = subprocess.run(["systemctl", "--user", "show", "--no-pager",
        "--property=Id,LoadState,ActiveState,UnitFileState", *PATHS], capture_output=True, text=True)
    if result.returncode:
        raise ValueError("seq2_retirement_inventory_unavailable")
    rows = []
    for block in result.stdout.strip().split("\n\n"):
        fields = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
        rows.append(fields)
    if len(rows) != len(PATHS) or {r.get("Id") for r in rows} != set(PATHS):
        raise ValueError("seq2_retirement_inventory_incomplete")
    if any(r.get("ActiveState") != "inactive" or r.get("UnitFileState") not in ("disabled", "masked")
           or r.get("LoadState") not in ("loaded", "masked") for r in rows):
        raise ValueError("seq2_watchers_not_retired")
    return rows
