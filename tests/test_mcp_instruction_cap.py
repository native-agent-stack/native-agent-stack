"""Tests for tools/adoption/mcp_instructions_length.py and the record that quotes its figures (docs/decisions/2026-10-12-mcp-instruction-cap.md, CPA-V-06).

The tool is run against a local stub endpoint that records every JSON-RPC method it receives and every request header; the record's figures are read back from the artifact's measurement.json and compared with
each other, with the record's text and with the settings templates.
"""

import contextlib
import hashlib
import http.server
import io
import json
import re
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))

import mcp_instructions_length as tool  # noqa: E402

MARKER = "--- Detailed tool routing follows. ---"
RECORD = ROOT / "docs" / "decisions" / "2026-10-12-mcp-instruction-cap.md"
MEASUREMENT = ROOT / "evidence" / "artifacts" / "mcp-instruction-cap-20261012" / "measurement.json"
KNOB = "CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH"
SECRET = "SENTINEL-instruction-text-must-never-be-printed"


class Stub:
    """A one-endpoint MCP server: answers `initialize` with a prepared body and records what it was sent."""

    def __init__(self, body: bytes, content_type: str = "application/json", status: int = 200):
        self.requests = []
        stub = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                stub.requests.append({"method": payload.get("method"), "headers": {k.lower(): v for k, v in self.headers.items()}})
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/mcp"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def result_body(instructions, name="stub-memory", version="9.9.9", event_stream=False):
    result = {"protocolVersion": "2025-06-18", "capabilities": {}, "serverInfo": {"name": name, "version": version}}
    if instructions is not None:
        result["instructions"] = instructions
    message = json.dumps({"jsonrpc": "2.0", "id": 1, "result": result})
    return (f"event: message\ndata: {message}\n\n".encode() if event_stream else message.encode()), ("text/event-stream" if event_stream else "application/json")


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = tool.main(list(args))
    return code, out.getvalue(), err.getvalue()


def text_with_marker(core, detail):
    return "C" * (core - 1) + "\n" + MARKER + "\n" + "D" * detail


class ToolTests(unittest.TestCase):
    def test_it_prints_the_lengths_the_hash_and_the_core_and_detail_around_the_marker(self):
        text = text_with_marker(1000, 3000) + SECRET
        body, kind = result_body(text)
        with Stub(body, kind) as stub:
            code, out, err = run(stub.url, "--marker", MARKER, "--json")
        self.assertEqual((code, err), (0, ""))
        data = json.loads(out)
        self.assertEqual((data["server"], data["version"]), ("stub-memory", "9.9.9"))
        self.assertEqual((data["characters"], data["bytes"]), (len(text), len(text.encode())))
        self.assertEqual(data["sha256_16"], hashlib.sha256(text.encode()).hexdigest()[:16])
        self.assertEqual((data["core"], data["detail"]), (1000, len(text) - 1000 - len(MARKER)))

    def test_bytes_and_characters_differ_for_non_ascii_text(self):
        body, kind = result_body(("caf" + chr(0xE9) + " ") * 10)
        with Stub(body, kind) as stub:
            data = json.loads(run(stub.url, "--json")[1])
        self.assertEqual((data["characters"], data["bytes"]), (50, 60))

    def test_the_reply_may_be_an_event_stream(self):
        body, kind = result_body("x" * 123, event_stream=True)
        with Stub(body, kind) as stub:
            data = json.loads(run(stub.url, "--json")[1])
        self.assertEqual(data["characters"], 123)

    def test_the_text_is_never_printed_and_the_request_is_one_initialize_without_a_credential(self):
        body, kind = result_body(f"{SECRET} {MARKER} {SECRET}")
        with Stub(body, kind) as stub:
            for extra in ((), ("--json",), ("--marker", MARKER, "--cap", "10")):
                code, out, err = run(stub.url, *extra)
                self.assertNotIn(SECRET, out + err)
            methods = [r["method"] for r in stub.requests]
            headers = stub.requests[0]["headers"]
        self.assertEqual(set(methods), {"initialize"}, "no tool is listed or called")
        self.assertFalse({"authorization", "cookie", "x-api-key", "mcp-session-id"} & set(headers))

    def test_the_cap_is_compared_with_the_core_when_there_is_a_marker_and_with_the_whole_text_without_one(self):
        body, kind = result_body(text_with_marker(1987, 15699))
        with Stub(body, kind) as stub:
            within = run(stub.url, "--marker", MARKER, "--cap", "4096")
            whole = run(stub.url, "--cap", "4096")
            tight = run(stub.url, "--marker", MARKER, "--cap", "1986")
            exact = run(stub.url, "--marker", MARKER, "--cap", "1987")
            absent = run(stub.url, "--marker", "no such marker", "--cap", "4096")
        self.assertEqual(within[0], 0)
        self.assertIn("within the cap", within[1])
        self.assertEqual(whole[0], 1, "without a marker the whole text must fit")
        self.assertEqual(tight[0], 1)
        self.assertEqual(exact[0], 0, "a core of exactly the cap fits")
        self.assertEqual(absent[0], 1, "a marker that is not in the text leaves the whole text as the part that must reach the model")
        self.assertIn("marker is not in the text", absent[1])

    def test_a_server_without_instructions_has_length_zero(self):
        body, kind = result_body(None)
        with Stub(body, kind) as stub:
            code, out, _ = run(stub.url, "--cap", "4096", "--json")
        self.assertEqual(code, 0)
        self.assertEqual((json.loads(out)["characters"], json.loads(out)["over_the_cap"]), (0, False))

    def test_an_unreadable_endpoint_ends_the_run_with_exit_two_and_a_fixed_message(self):
        cases = {"an HTTP error": Stub(SECRET.encode(), "text/plain", status=500), "not JSON-RPC": Stub(SECRET.encode(), "application/json"),
                 "an error reply": Stub(json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": -1, "message": SECRET}}).encode())}
        for label, stub in cases.items():
            with self.subTest(label), stub:
                code, out, err = run(stub.url)
                self.assertEqual((code, out), (2, ""))
                self.assertNotIn(SECRET, err)
                self.assertTrue(err.startswith("mcp_instructions_length:"))
        for url in ("file:///etc/hostname", "ftp://127.0.0.1/mcp", "http://127.0.0.1:1/mcp"):
            with self.subTest(url):
                code, out, err = run(url, "--timeout", "2")
                self.assertEqual((code, out), (2, ""))


class RecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(MEASUREMENT.read_text(encoding="utf-8"))
        cls.record = RECORD.read_text(encoding="utf-8")

    def test_the_measurement_is_internally_consistent(self):
        ins = self.data["instructions"]
        self.assertEqual(ins["core"] + len(ins["marker"]) + ins["detail"], ins["characters"], "the core, the marker and the detail make the text")
        self.assertEqual(self.data["over_the_cap"], ins["characters"] - self.data["cap"])
        self.assertEqual(self.data["cap"], self.data["client"]["default_cap_characters"])
        self.assertLessEqual(ins["core"], self.data["upstream_design"]["core_limit_characters"], "the server's own test pins the marker at or before character 2,048")
        self.assertEqual(self.data["the_part_that_must_reach_the_model_is_over_the_cap"], ins["core"] > self.data["cap"])
        self.assertGreater(self.data["audit_claim"]["block_characters"], ins["core"])
        self.assertLess(self.data["audit_claim"]["block_characters"], ins["characters"], "the audit's figure is neither the core nor the whole text")

    def test_the_record_quotes_the_figures_of_the_measurement(self):
        ins = self.data["instructions"]
        for figure in (ins["characters"], ins["bytes"], ins["core"], ins["detail"], self.data["over_the_cap"], self.data["tools_list"]["description_characters"], self.data["tools_list"]["median"],
                       self.data["tools_list"]["max"]):
            self.assertIn(f"{figure:,}", self.record, figure)
        self.assertIn(ins["sha256_16"], self.record)
        self.assertIn(self.data["measured_at_utc"], self.record)
        self.assertIn(self.data["server"]["version"], self.record)
        self.assertIn(f"{self.data['audit_claim']['block_characters']:,}", self.record)

    def test_the_record_cites_the_pinned_upstream_lines(self):
        for cite in ("CHANGELOG.md` L65", "L1522", "89bd8ded3c1ab8b769cf99417d038ed0364403c8", "L169-L172", "L8087-L8112", "3deb873687379f0c199a69fdaccc65f0865f7a29"):
            self.assertIn(cite, self.record)

    def test_the_settings_templates_do_not_set_the_knob_unless_it_fits_the_whole_block(self):
        """The decision is that the knob stays unset. If a later change sets it, the value must be at least the measured whole-text length (and the record must be superseded)."""
        whole = self.data["instructions"]["characters"]
        for path in sorted((ROOT / "adoption").rglob("*.json")) + sorted((ROOT / "adoption").rglob("*.template.*")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for found in re.finditer(KNOB + r'"?\s*[:=]\s*"?(\d+)', text):
                self.assertGreaterEqual(int(found.group(1)), whole, f"{path.relative_to(ROOT)} sets {KNOB} below the measured block")

    def test_the_audit_group_is_retained_and_says_what_the_record_says_it_said(self):
        """Review of #1052 at f17cb3a0 (P2): the audit artifact the record cites must be in the repository."""
        retained = json.loads((MEASUREMENT.parent / "audit-group-CPA-V-06.json").read_text(encoding="utf-8"))
        self.assertEqual(retained["group"]["id"], "CPA-V-06")
        self.assertRegex(retained["source"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertIn(retained["source"]["sha256"], self.record)
        claims = {c["claim"]: c for c in retained["group"]["claims"]}
        block = claims["The block is 4,122 characters"]
        self.assertEqual(block["status"], "not re-checked")
        self.assertIn(f"{self.data['audit_claim']['block_characters']:,}", block["claim"])
        self.assertIn("audit-group-CPA-V-06.json", self.record)

    def test_the_record_names_the_layer_inputs_it_consumed_and_they_are_still_what_the_catalogs_say(self):
        """Review of #1052 at f17cb3a0 (P1): AGENTS.md asks for the resolution protocol's inputs before a comparison; the record names them, and this fails when a catalog moves under it."""
        foundation = json.loads((ROOT / "catalogs" / "landscape" / "foundation.json").read_text(encoding="utf-8"))
        layer = next(entry for entry in foundation["layers"] if entry["layer_id"] == "durable-memory")
        self.assertEqual((layer["decision"], layer["verdict_status"], layer["checked_at"]), ("keep_but_compare", "recorded", "2026-09-22"))
        waves = (ROOT / "catalogs" / "sota-convergence" / "layer-verdict-waves.json").read_text(encoding="utf-8")
        self.assertNotIn("durable-memory", waves, "a wave now names the layer: read it and update the record's protocol section")
        ledger = json.loads((ROOT / "catalogs" / "saturation" / "ledger.json").read_text(encoding="utf-8"))
        covering = sorted(((sweep["date"], sweep["sweep_id"], entry) for sweep in ledger["sweeps"] for entry in sweep.get("layers", [])
                           if (entry["catalog"], entry["layer_id"]) == ("foundation", "durable-memory") and sweep.get("status") == "completed"), key=lambda row: row[:2])
        date, sweep_id, entry = covering[-1]
        self.assertEqual(sweep_id, "landscape-sweep-20260929", "a later sweep covers the layer: read its survivors and update the record")
        for survivor in entry["survived"]:
            self.assertIn(survivor["repo"].replace("https://github.com/", ""), self.record)
        self.assertEqual(len(entry["reopen"]), 5)
        for needle in ("keep_but_compare", sweep_id, "no wave", "bounded delta", "adjudicates none"):
            self.assertIn(needle, self.record.replace("No wave", "no wave").replace("Bounded delta", "bounded delta"), needle)

    def test_the_tool_is_named_where_the_record_says_it_is(self):
        self.assertTrue((ROOT / "tools" / "adoption" / "mcp_instructions_length.py").is_file())
        self.assertIn("tools/adoption/mcp_instructions_length.py", self.record)
        self.assertTrue((MEASUREMENT.parent / "tools_list_lengths.py").is_file())
        self.assertIn("tools_list_lengths.py", self.record)


if __name__ == "__main__":
    unittest.main()
