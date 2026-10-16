"""Retain eight named candidate dictionaries without changing any of their fields.

Source: tools/sota-convergence/lane_packets.py at caa224140, build_candidate
lines 299-313 and receipts_for lines 614-644. The producer emits pin and all
registered receipts. This transform only filters candidates by repository.
"""

import argparse
import json
from pathlib import Path


REPOSITORIES = frozenset({
    "https://github.com/ccusage/ccusage",
    "https://github.com/headroomlabs-ai/headroom",
    "https://github.com/rtk-ai/rtk",
    "https://github.com/atlassian-labs/mcp-compressor",
    "https://github.com/klavis-ai/klavis",
    "https://github.com/lockedinlabs-ai/agent-console",
    "https://github.com/ojuschugh1/sqz",
    "https://github.com/paritok-official/paritok-4b-v1",
})


def project(packet):
    if packet["catalog"] != "foundation" or packet["layer_id"] != "token-efficiency":
        raise ValueError("Expected the foundation/token-efficiency packet")
    selected = [row for row in packet["candidates"] if row["repository"] in REPOSITORIES]
    if len(selected) != len(REPOSITORIES) or {row["repository"] for row in selected} != REPOSITORIES:
        raise ValueError("Every selected repository must occur exactly once")
    return {
        "schema": "final-wave-delta-packet/2",
        "catalog": packet["catalog"],
        "layer_id": packet["layer_id"],
        "requirement": packet["requirement"],
        "generated_by": "project_packet.py",
        "generator_output": "generator-token-efficiency.json",
        "source_generator": "tools/sota-convergence/lane_packets.py at caa224140a2d04ba5f3d0ca320c487a75f9c9ea1",
        "selection": "Filter candidate dictionaries by the eight explicit repositories; retain every field, receipt and pin unchanged and preserve generator order. Other packet metadata remains in generator-token-efficiency.json.",
        "candidates": selected,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = project(json.loads(args.input.read_text()))
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"selected": len(result["candidates"]), "registered_receipts": {
        row["name"]: len(row.get("registered_receipts", [])) for row in result["candidates"]
    }}, sort_keys=True))


if __name__ == "__main__":
    main()
