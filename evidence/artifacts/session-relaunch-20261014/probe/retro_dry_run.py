"""Retro dry run (a simulation, not a measured relaunch): the roster the snapshot timer would have written at 06:40:30Z,
reconstructed from command-center/CC-AFTER-RESTART-20261014.md (old session ids) and launch.log (the CC's id), decided and
rendered by session_relaunch.py against this host's real journal boots, with no session alive (as at 12:49Z)."""
import datetime as dt, importlib.util, json, re, sys, tempfile
from pathlib import Path
spec = importlib.util.spec_from_file_location("R", sys.argv[1]); R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
example = json.loads(Path(sys.argv[2]).read_text())
tmp = Path(tempfile.mkdtemp(prefix="ccnp-retro-", dir="/var/tmp"))
config = R.load_config(Path(tmp / "c.json")) if (tmp / "c.json").write_text(json.dumps(dict(example, state_dir=str(tmp / "state"), handoff_dir=str(tmp / "cc")))) else None
# argv[4]: the private roster rows, [[name, old session id, cwd], ...] in launch order (kept in the state directory: the ids
# are local session identifiers and are not published).
rows = json.loads(Path(sys.argv[4]).read_text())
sessions = [{"name": n, "kind": "interactive", "sessionId": s, "cwd": c, "pid": None, "startedAt": None, "status": "busy"} for n, s, c in rows]
prev = "a84c7d5283d54dee8de81e0c792dcaa0"
R.cmd_snapshot(config, boot_id=prev, sessions=sessions, at=dt.datetime(2026, 10, 14, 6, 40, 30, tzinfo=dt.timezone.utc))
boots, this = R.read_boots(), R.current_boot_id()
at = R.boot_window(boots, this)[0] + dt.timedelta(seconds=30)
d = R.plan(config, boot_id=this, at=at, boots=boots, alive_rows=[])
print(json.dumps({"action": d["action"], "order": [r["name"] for r, _ in d["launch"]], "left": [r["name"] for r in d["left"]]}))
text = R.handoff_text(config, at=at, prev=d["prev"], prev_end=d["prev_end"], this_start=d["this_start"], launch=d["launch"], left=d["left"], alive=d["alive"])
uuid = re.compile(r"([0-9a-f]{8})-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}")
published = uuid.sub(r"\1…", text.replace(str(Path.home()), "~"))
Path(sys.argv[3]).write_text(re.sub(r"-home-[^-/]+-", "-home-<user>-", published))
