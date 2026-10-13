#!/usr/bin/env python3
"""Bridge native hcom status JSON to the existing loopback Loki publisher.

Sources: aannoo/hcom v0.7.27 (2c5f343b), src/commands/list.rs:355;
grafana/loki v3.7.8, docs/sources/reference/loki-http-api.md (JSON push).
This is metadata glue, not a transcript reader or agent runner. Private registry
input may be the native census's canonical_roots and parent map; no paths leave.

Identity: `hcom list` needs no hcom identity. An explicit `--name` takes hcom's
error-propagating path, so a name with no live instance exits 1 with "Instance
'<name>' not found" (aannoo/hcom@b2a7c192, the v0.7.28 mirror,
src/bootstrap.rs:25-30, src/identity.rs:58), while an omitted name falls back to
an optional lookup (src/commands/list.rs:213-234). The bridge therefore passes
`--name` only when the caller supplies one.

Prompt state (the command center's STUCK signal): `hcom term --json` prints one
compact JSON object per responding PTY instance, with `name`, `ready`,
`prompt_empty`, `input_text` and the screen `lines` (src/commands/help.rs:803,
src/commands/term.rs:211,370-373), and for an instance that does not answer the
plain line `[<name>] not responding (port <port>)`, still exiting 0 when any
instance answered (src/commands/term.rs:365-384). Each line is decoded on its own,
so one silent instance never hides the others. Only the `prompt_empty` boolean is
read; `prompt_has_text` leaves as true, false or "unknown" (no answer, no PTY,
or hcom term failed). Screen lines and input text can hold owner keystrokes; they
are never exported. Gate contexts such as `tui:prompt-has-text` are hcom's
listening-gate states (src/instance_lifecycle.rs:588-600, src/delivery.rs:2147).

Names: `hcom list` reports the tagged display name `{tag}-{name}` as `name` and the
instance name as `base_name` (src/commands/list.rs:353,370; src/identity.rs:107-113).
`hcom term` and the lanes' OTel `ecosystem.lane` use the instance name, so prompt
state joins on `base_name`; a registry-only row strips its lane prefix the same way.

Freshness: after each published snapshot the bridge can send one OTLP gauge,
`agent_stack_lanes.records`, to the OTel Collector's OTLP/HTTP receiver in the JSON
Protobuf Encoding (open-telemetry/opentelemetry-proto v1.7.0 docs/specification.md,
"JSON Protobuf Encoding": lowerCamelCase fields, 64-bit integers as decimal strings).
The Collector's Prometheus exporter drops the series five minutes after its last
point (opentelemetry-collector-contrib v0.162.0 exporter/prometheusexporter/README.md:29),
so Prometheus can alert with absent_over_time when snapshots stop.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request

from progress import loki_push_url

IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}")
THREAD = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
CONTEXT = re.compile(r"(?:tool:[A-Za-z0-9_.:-]{1,64}|tui:[a-z0-9-]{1,40}|startup|resume|idle|waiting|)")
OTLP_METRICS = re.compile(r"http://127\.0\.0\.1:([0-9]{1,5})/v1/metrics")
UNKNOWN = "unknown"
GAUGE = "agent_stack_lanes.records"


def text(value, pattern=IDENTIFIER, fallback=UNKNOWN):
    return value if isinstance(value, str) and pattern.fullmatch(value) else fallback


def natural(value):
    return value if type(value) is int and 0 <= value <= 2**53 else None


def bare_name(name, lane):
    """The instance name inside an hcom display name `{tag}-{name}` whose tag is the registry lane."""
    if lane != UNKNOWN and name.startswith(lane + "-") and IDENTIFIER.fullmatch(name[len(lane) + 1:]):
        return name[len(lane) + 1:]
    return name


def prompt_states(output):
    """Map instance name -> True/False (prompt holds text) from `hcom term --json`; only the boolean is kept."""
    states = {}
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            # Blank separators and "[<name>] not responding (port N)" lines; never echoed.
            continue
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if not isinstance(item, dict):
            continue
        name = text(item.get("name"), fallback="")
        empty = item.get("prompt_empty")
        if name and type(empty) is bool:
            states[name] = not empty
    return states


def snapshot(native, registry=None, prompts=None):
    if not isinstance(native, list):
        raise ValueError("hcom list must return a JSON array")
    prompts = prompts or {}
    roots = (registry or {}).get("canonical_roots", [])
    known = {}
    for root in roots:
        identity = text(root.get("root_id"), THREAD)
        if identity != UNKNOWN:
            lane, name = text(root.get("lane")), text(root.get("name"))
            known[identity] = {"identity": identity, "lane": lane, "name": name,
                               "base_name": bare_name(name, lane), "client": "codex",
                               "status": UNKNOWN, "status_context": "",
                               "status_age_seconds": None, "unread_count": None,
                               "tag": None, "prompt_has_text": UNKNOWN,
                               "registered_root": True}
    for row in native:
        if not isinstance(row, dict):
            continue
        identity = text(row.get("session_id"), THREAD)
        if identity == UNKNOWN:
            continue
        previous = known.get(identity, {})
        name = text(row.get("name"))
        base_name = text(row.get("base_name"), fallback=name)
        known[identity] = dict(previous, identity=identity, name=name, base_name=base_name,
                               lane=previous.get("lane", name),
                               client=text(row.get("tool")),
                               status=text(row.get("status")),
                               status_context=text(row.get("status_context"), CONTEXT, "omitted"),
                               status_age_seconds=natural(row.get("status_age_seconds")),
                               unread_count=natural(row.get("unread_count")),
                               tag=text(row.get("tag"), fallback=None),
                               prompt_has_text=prompts.get(base_name, UNKNOWN),
                               registered_root=previous.get("registered_root", False))
    return sorted(known.values(), key=lambda row: (row["lane"], row["identity"]))


def payload(rows, now_ns):
    # One stream per identity; fields are selected native metadata only. The
    # timestamp belongs to this observation, not to the lane's last model turn.
    return {"streams": [
        {"stream": {"service_name": "agent-stack-lanes", "record_kind": "hcom",
                    "identity": row["identity"]},
         "values": [[str(now_ns + i), json.dumps(dict(row, observed_unix=now_ns / 1e9),
                                                   separators=(",", ":"))]]}
        for i, row in enumerate(rows)]}


def gauge_payload(records, now_ns):
    """OTLP/HTTP JSON for one gauge point: the number of records the snapshot published."""
    resource = [{"key": "service.name", "value": {"stringValue": "agent-stack-lanes"}},
                {"key": "service.instance.id", "value": {"stringValue": "hcom-status"}}]
    point = {"asInt": str(records), "timeUnixNano": str(now_ns)}
    return {"resourceMetrics": [{"resource": {"attributes": resource}, "scopeMetrics": [{
        "scope": {"name": "hcom_status"},
        "metrics": [{"name": GAUGE, "description": "hcom status records in the last published snapshot",
                     "gauge": {"dataPoints": [point]}}]}]}]}


def otlp_metrics_url(value):
    match = OTLP_METRICS.fullmatch(value) if isinstance(value, str) else None
    if not match or not 0 < int(match.group(1)) < 65536:
        raise ValueError("OTLP metrics URL must be http://127.0.0.1:<port>/v1/metrics")
    return value


def identity_args(name):
    return ["--name", name] if name else []


def read_prompts(hcom_bin, name):
    """Prompt booleans; {} (every row "unknown") when hcom has no PTY view. List status still publishes."""
    try:
        result = subprocess.run([hcom_bin, "term", "--json", *identity_args(name)],
                                capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"hcom term unavailable ({type(error).__name__}); prompt state unknown", file=sys.stderr)
        return {}
    if result.returncode != 0:
        print(f"hcom term exited {result.returncode}; prompt state unknown", file=sys.stderr)
        return {}
    return prompt_states(result.stdout)


def post(url, body, expected):
    request = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status not in expected:
            raise ValueError(f"{url} answered {response.status}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hcom-bin", default="hcom")
    parser.add_argument("--name", help="optional hcom identity; listing needs none, and an unknown name fails hcom")
    parser.add_argument("--registry", type=Path,
                        help="private canonical-roots JSON; absent registration is not inferred")
    parser.add_argument("--loki-url", default="http://127.0.0.1:21300/loki/api/v1/push")
    parser.add_argument("--otlp-url", help="OTel Collector OTLP/HTTP metrics URL for the freshness gauge")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()
    url = loki_push_url(args.loki_url)
    otlp = otlp_metrics_url(args.otlp_url) if args.otlp_url else None
    result = subprocess.run([args.hcom_bin, "list", "--json", *identity_args(args.name)],
                            capture_output=True, text=True, timeout=10, check=True)
    registry = json.loads(args.registry.read_text()) if args.registry and args.registry.is_file() else None
    rows = snapshot(json.loads(result.stdout), registry, read_prompts(args.hcom_bin, args.name))
    if args.push:
        now = time.time_ns()
        post(url, payload(rows, now), (204,))
        if otlp:
            post(otlp, gauge_payload(len(rows), now), (200,))
        print(json.dumps({"status": "published", "records": len(rows)}))
    else:
        print(json.dumps(rows))


if __name__ == "__main__":
    main()
