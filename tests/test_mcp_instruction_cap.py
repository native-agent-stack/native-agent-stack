"""Tests for tools/adoption/mcp_instructions_length.py and the record that quotes its figures (docs/decisions/2026-10-12-mcp-instruction-cap.md, CPA-V-06).

The tool is run against a local stub endpoint that records every JSON-RPC method it receives and every request header; the record's figures are read back from the artifact's measurement.json and compared with
each other, with the record's text and with the settings templates.
"""

import contextlib
import hashlib
import http.client
import http.server
import importlib.util
import io
import json
import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))

import mcp_instructions_length as tool  # noqa: E402

ARTIFACT = ROOT / "evidence" / "artifacts" / "mcp-instruction-cap-20261012"
_spec = importlib.util.spec_from_file_location("source_constant_length", ARTIFACT / "source_constant_length.py")
source_constant_length = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(source_constant_length)
_probe_spec = importlib.util.spec_from_file_location("tools_list_lengths", ARTIFACT / "tools_list_lengths.py")
probe = importlib.util.module_from_spec(_probe_spec)
_probe_spec.loader.exec_module(probe)

MARKER = "--- Detailed tool routing follows. ---"
RECORD = ROOT / "docs" / "decisions" / "2026-10-12-mcp-instruction-cap.md"
MEASUREMENT = ARTIFACT / "measurement.json"
AUDIT = ARTIFACT / "audit-group-CPA-V-06.json"
ARTIFACT_README = ARTIFACT / "README.md"
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
                stub.requests.append({"method": payload.get("method"), "params": payload.get("params"), "headers": {k.lower(): v for k, v in self.headers.items()}})
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/mcp"
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True)

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


def initialize_result(instructions="x", protocol="2025-06-18"):
    return {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": protocol, "capabilities": {}, "serverInfo": {"name": "stub-memory", "version": "9.9.9"}, "instructions": instructions}}


def notification(text="a log line"):
    return {"jsonrpc": "2.0", "method": "notifications/message", "params": {"level": "info", "data": text}}


def sse(*messages):
    """An event stream of the messages, one event each (the framing of the stream, `event: message` and a blank line)."""
    return "".join(f"event: message\ndata: {json.dumps(message)}\n\n" for message in messages).encode()


class Scripted:
    """A one-endpoint MCP server whose answer to each POST comes from `script(payload, headers)`: (status, content type, body bytes, extra response headers). Every request is recorded."""

    def __init__(self, script):
        self.requests = []
        stub = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                headers = {k.lower(): v for k, v in self.headers.items()}
                stub.requests.append({"method": payload.get("method"), "params": payload.get("params"), "headers": headers})
                status, kind, body, extra = script(payload, headers)
                self.send_response(status)
                if kind:
                    self.send_header("Content-Type", kind)
                for name, value in (extra or {}).items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/mcp"
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


class Streaming:
    """A server whose reply to the first POST is an event stream that it writes in parts and keeps open until `release` is set (or 20 s pass): `first` at once, then, if `keepalive`, a comment every 50 ms."""

    def __init__(self, first: bytes, keepalive: bool = False):
        self.release = threading.Event()
        stub = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()                                  # no Content-Length: the body ends when the connection closes
                try:
                    self.wfile.write(first)
                    self.wfile.flush()
                    stop = time.monotonic() + 20
                    while not stub.release.is_set() and time.monotonic() < stop:
                        if keepalive:
                            self.wfile.write(b": keepalive\n\n")
                            self.wfile.flush()
                        time.sleep(0.05)
                except OSError:
                    pass

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/mcp"
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()


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

    def test_utf16_units_and_characters_outside_the_basic_plane_are_counted(self):
        """Review of #1052 at 641ca19f (P3): the full text is one UTF-16 unit longer than its code points; the unit has to be stated or allowed for."""
        text = "ab" + chr(0x1F4E5) + "cd"
        body, kind = result_body(text)
        with Stub(body, kind) as stub:
            data = json.loads(run(stub.url, "--json")[1])
            plain = run(stub.url)[1]
        self.assertEqual((data["characters"], data["utf16_units"], data["outside_bmp"], data["bytes"]), (5, 6, 1, 8))
        self.assertIn("5 characters, 6 UTF-16 units", plain)

    def test_the_protocol_version_is_the_one_the_server_answered_with(self):
        body, kind = result_body("x")
        with Stub(body, kind) as stub:
            self.assertEqual(json.loads(run(stub.url, "--json")[1])["protocol_version"], "2025-06-18")

    def test_detail_lines_are_counted_by_prefix_and_against_the_cap(self):
        """Review of #1052 at 641ca19f (P3): the bullet counts of the measurement come from the tool, as counts only."""
        detail = ["- `one` first line", "- `two` second line, longer than the first", "- `three` third", "a continuation line", "- `four` fourth"]
        text = "C" * 20 + MARKER + "\n" + "\n".join(detail)
        starts, at = [], len("C" * 20 + MARKER + "\n")
        for line in detail:
            if line.startswith("- `"):
                starts.append(at)
            at += len(line) + 1
        cap = starts[2] + 3                         # inside the third bullet
        body, kind = result_body(text)
        with Stub(body, kind) as stub:
            data = json.loads(run(stub.url, "--marker", MARKER, "--bullet", "- `", "--cap", str(cap), "--json")[1])
            other = json.loads(run(stub.url, "--marker", MARKER, "--bullet", "* ", "--json")[1])
            plain = run(stub.url, "--marker", MARKER, "--bullet", "- `", "--cap", str(cap))[1]
        self.assertEqual((data["bullets"], data["bullets_started_under_cap"], data["bullets_cut_by_cap"]), (4, 3, 1))
        self.assertEqual((other["bullets"], "bullets_started_under_cap" in other), (0, False), "no cap, no under-cap figures")
        self.assertIn("4 detail lines start with", plain)
        self.assertNotIn("three", plain, "counts only")

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
        self.assertTrue({"application/json", "text/event-stream"} <= {part.strip() for part in headers["accept"].split(",")}, "transports.mdx L88-L90: both content types are accepted")
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(stub.requests[0]["params"]["protocolVersion"], "2025-06-18")

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


class EventStreamTests(unittest.TestCase):
    """Review of #1052 at 7520907a2 (P2): a streamable-HTTP server may send requests and notifications on the event stream before the response to the POST
    (modelcontextprotocol/modelcontextprotocol@1f520964 docs/specification/2025-06-18/basic/transports.mdx L104-L106); the tool took the first JSON event and rejected it for having no `result`."""

    def characters(self, body: bytes, *extra):
        with Stub(body, "text/event-stream") as stub:
            code, out, err = run(stub.url, "--json", *extra)
        return code, (json.loads(out)["characters"] if code == 0 else out), err

    def test_a_notification_before_the_response_is_skipped(self):
        reply = initialize_result("y" * 17724)
        self.assertEqual(self.characters(sse(reply))[0:2], (0, 17724), "the response alone: the control")
        self.assertEqual(self.characters(sse(notification(), reply))[0:2], (0, 17724))
        self.assertEqual(self.characters(sse(notification(), notification("again"), reply))[0:2], (0, 17724))

    def test_a_server_request_with_the_same_id_and_a_response_to_another_id_are_not_the_response(self):
        wrong = {"jsonrpc": "2.0", "id": 7, "result": {"instructions": "WRONG" * 10, "serverInfo": {"name": "other"}}}
        ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
        impostor = {"jsonrpc": "2.0", "id": 1, "method": "sampling/createMessage", "result": {"instructions": "WRONG" * 10}}
        self.assertEqual(self.characters(sse(ping, impostor, wrong, initialize_result("z" * 33)))[0:2], (0, 33))
        for boolean in (True, False):
            self.assertEqual(self.characters(sse({"jsonrpc": "2.0", "id": boolean, "result": {"instructions": "WRONG"}}, initialize_result("z" * 33)))[0:2], (0, 33), "a boolean is not the id 1")

    def test_a_message_with_the_id_that_has_neither_a_result_nor_an_error_is_not_the_response(self):
        shapeless = {"jsonrpc": "2.0", "id": 1}
        self.assertEqual(self.characters(sse(shapeless, {"jsonrpc": "2.0", "id": 1, "params": {}}, initialize_result("s" * 17)))[0:2], (0, 17))
        code, out, err = self.characters(sse(shapeless))
        self.assertEqual(code, 2)
        self.assertIn("holds no response to the request", err)

    def test_an_event_is_dispatched_at_its_blank_line_whatever_the_line_ends_and_not_at_the_end_of_the_stream(self):
        """A stream the server keeps open, so that only the blank line (LF or CRLF) can end the event: the answer comes at once. (A bare CR as the last byte received waits for the next byte, as universal-newline
        decoding does: an event that a server ends with CR CR and then leaves open is read at the next byte or the end of the stream, and the CR line ends are covered on a stream that ends.)"""
        message = json.dumps(initialize_result("l" * 66))
        for label, ends in {"LF": "\n", "CRLF": "\r\n"}.items():
            with self.subTest(label), Streaming((": hello" + ends + ends + "event: message" + ends + "data: " + message + ends + ends).encode()) as stub:
                started = time.monotonic()
                code, out, err = run(stub.url, "--json", "--timeout", "10")
                elapsed = time.monotonic() - started
            self.assertEqual((code, err, json.loads(out)["characters"]), (0, "", 66))
            self.assertLess(elapsed, 5)

    def test_the_event_stream_format_is_read_as_the_format_has_it(self):
        message = json.dumps(initialize_result("w" * 44))
        half = len(message) // 2
        variants = {
            "CRLF line ends": ("event: message\r\ndata: " + message + "\r\n\r\n").encode(),
            "CR line ends": ("event: message\rdata: " + message + "\r\r").encode(),
            "no space after the colon": ("data:" + message + "\n\n").encode(),
            "a comment, other fields and an empty priming event first": (": keepalive\n\nid: 1\nretry: 5000\ndata:\n\nevent: message\nid: 2\ndata: " + message + "\n\n").encode(),
            "the message split over two data lines": ("data: " + message[:half] + "\ndata: " + message[half:] + "\n\n").encode(),
            "no blank line after the last event": ("data: " + message + "\n").encode(),
            "an event that is not JSON first": ("data: not json\n\ndata: " + message + "\n\n").encode(),
        }
        for label, body in variants.items():
            with self.subTest(label):
                if label == "the message split over two data lines":
                    pretty = json.dumps(initialize_result("w" * 44), indent=1).split("\n")
                    body = ("".join("data: " + line + "\n" for line in pretty) + "\n").encode()
                self.assertEqual(self.characters(body)[0:2], (0, 44))

    def test_a_stream_without_the_response_or_with_an_error_is_unreadable_with_a_fixed_message(self):
        error = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": SECRET}}
        for label, body, message in (("only notifications", sse(notification(SECRET), notification(SECRET)), "the reply holds no response to the request"),
                                     ("an error response", sse(notification(), error), "the server answered with a JSON-RPC error"), ("an empty stream", b"", "the reply holds no response to the request"),
                                     ("a result that is not an object", sse({"jsonrpc": "2.0", "id": 1, "result": SECRET}), "the reply is not an initialize result")):
            with self.subTest(label):
                code, out, err = self.characters(body)
                self.assertEqual((code, err), (2, f"mcp_instructions_length: {message}\n"))
                self.assertNotIn(SECRET, out + err)

    def test_a_batch_is_read_for_the_response_to_the_request(self):
        with Stub(json.dumps([notification(), initialize_result("b" * 21)]).encode(), "application/json") as stub:
            self.assertEqual(json.loads(run(stub.url, "--json")[1])["characters"], 21)

    def test_the_stream_is_not_read_to_its_end(self):
        """The server keeps the stream open after the response (it SHOULD close it, transports.mdx L110, but may not): the answer comes without waiting for the close."""
        with Streaming(sse(notification(), initialize_result("o" * 55))) as stub:
            started = time.monotonic()
            code, out, err = run(stub.url, "--json", "--timeout", "10")
            elapsed = time.monotonic() - started
        self.assertEqual((code, err, json.loads(out)["characters"]), (0, "", 55))
        self.assertLess(elapsed, 5, "the tool waited for the stream to close")

    def test_a_stream_that_never_answers_is_cut_by_the_timeout_even_while_it_keeps_sending(self):
        with Streaming(sse(notification()), keepalive=True) as stub:
            started = time.monotonic()
            code, out, err = run(stub.url, "--timeout", "1")
            elapsed = time.monotonic() - started
        self.assertEqual((code, out), (2, ""))
        self.assertIn("did not finish its reply in time", err)
        self.assertLess(elapsed, 8)

    def test_a_reply_or_a_line_longer_than_the_limit_is_refused(self):
        with mock.patch.object(tool, "MAX_REPLY", 2000), mock.patch.object(tool, "MAX_LINE", 400):
            body, _ = result_body("q" * 3000)
            with Stub(body, "application/json") as stub:
                code, out, err = run(stub.url)
            self.assertEqual((code, out), (2, ""))
            self.assertIn("longer than 16 MiB", err)
            with Stub(b": padding\n" * 300 + sse(initialize_result("q")), "text/event-stream") as stub:
                code, out, err = run(stub.url)
            self.assertEqual((code, out), (2, ""))
            self.assertIn("longer than 16 MiB", err)
            with Stub(("data: " + "q" * 500 + "\n\n").encode(), "text/event-stream") as stub:
                code, out, err = run(stub.url)
            self.assertEqual((code, out), (2, ""))
            self.assertIn("longer than 1 MiB", err)
            with Stub(sse(notification(), initialize_result("q" * 60)), "text/event-stream") as stub:
                self.assertEqual(run(stub.url)[0], 0, "inside the limits a reply of the same shape is read")


class EndpointInputTests(unittest.TestCase):
    """Review of #1052 at 7520907a2 (P3): `urlsplit` raised ValueError for a malformed URL, outside the handled exceptions, instead of the documented exit 2."""

    def test_a_malformed_url_is_exit_two_with_a_fixed_message_that_does_not_echo_it(self):
        invalid, no_host = "mcp_instructions_length: the URL is not valid\n", "mcp_instructions_length: the URL is not http or https with a host\n"
        for url, expected in (("http://[" + SECRET, invalid), ("http://127.0.0.1:99999/mcp", invalid), ("http://127.0.0.1:" + SECRET + "/mcp", invalid), ("http://", no_host), ("http:///mcp", no_host),
                              ("", no_host), ("mcp", no_host), ("127.0.0.1:1/mcp", no_host), ("ws://127.0.0.1:1/mcp", no_host), ("file:///etc/hostname", no_host)):
            with self.subTest(url=url[:30]):
                code, out, err = run(url, "--timeout", "2")
                self.assertEqual((code, out, err), (2, "", expected))
        code, out, err = run("http://127.0.0.1:1/mcp\r\nX-Injected: " + SECRET, "--timeout", "2")
        self.assertEqual((code, out), (2, ""))
        self.assertTrue(err.startswith("mcp_instructions_length:"))
        self.assertNotIn(SECRET, err)

    def test_a_failure_inside_the_http_library_is_exit_two_too(self):
        failures = {"a bad status line": http.client.BadStatusLine("x"), "a short read": http.client.IncompleteRead(b"ab", 5), "an invalid URL": http.client.InvalidURL("x"),
                    "a reset": ConnectionResetError("x"), "a timeout": TimeoutError("x"), "a value error": ValueError(SECRET)}
        for label, error in failures.items():
            with self.subTest(label), mock.patch.object(tool.urllib.request, "urlopen", side_effect=error):
                code, out, err = run("http://127.0.0.1:1/mcp")
                self.assertEqual((code, out), (2, ""))
                self.assertTrue(err.startswith("mcp_instructions_length:"))
                self.assertNotIn(SECRET, err)

    def test_a_reply_that_is_not_utf8_is_exit_two(self):
        with Stub(b"\xff\xfe\xfd", "application/json") as stub:
            code, out, err = run(stub.url)
        self.assertEqual((code, out), (2, ""))
        with Stub(b"data: \xff\xfe\n\n", "text/event-stream") as stub:
            code, out, err = run(stub.url)
        self.assertEqual((code, out), (2, ""))


class ProbeTests(unittest.TestCase):
    """tools_list_lengths.py: the lifecycle, the headers of the requests after initialize (Review of #1052 at 7520907a2, P3: it carried the session id but not `MCP-Protocol-Version`, which transports.mdx L240-L250
    makes a MUST for every request after initialize), pages, and the same reading of an event stream as the tool."""

    def server(self, protocol="2025-03-26", session="session-1", stream=False, pages=1, tools_event_first=False):
        names = [f"tool_{n}" for n in range(3 * pages)]
        lengths = {name: 10 * (n % 3) + 6 for n, name in enumerate(names)}

        def script(payload, headers):
            method = payload.get("method")
            extra = {"Mcp-Session-Id": session} if (session and method == "initialize") else {}
            if method == "notifications/initialized":
                return 202, None, b"", None
            if method == "initialize":
                message = initialize_result("x", protocol)
            else:
                page = int((payload.get("params") or {}).get("cursor") or 0)
                tools = [{"name": name, "description": "A" * lengths[name]} for name in names[3 * page:3 * page + 3]]
                if page == 0:
                    tools.append({"name": "tool_secret", "description": SECRET})
                result = {"tools": tools}
                if page + 1 < pages:
                    result["nextCursor"] = str(page + 1)
                message = {"jsonrpc": "2.0", "id": payload["id"], "result": result}
            if stream or (tools_event_first and method == "tools/list"):
                return 200, "text/event-stream", sse(notification(), message), extra
            return 200, "application/json", json.dumps(message).encode(), extra
        return Scripted(script)

    def probe(self, url, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = probe.main([url, *args])
        return code, out.getvalue(), err.getvalue()

    def test_the_lifecycle_is_initialize_the_initialized_notification_then_tools_list_with_the_negotiated_version_and_the_session(self):
        with self.server() as stub:
            code, out, err = self.probe(stub.url, "--json")
            requests = stub.requests
        self.assertEqual((code, err), (0, ""))
        self.assertEqual([r["method"] for r in requests], ["initialize", "notifications/initialized", "tools/list"])
        first, *later = [r["headers"] for r in requests]
        self.assertNotIn("mcp-protocol-version", first)
        self.assertNotIn("mcp-session-id", first)
        for headers in later:
            self.assertEqual(headers.get("mcp-protocol-version"), "2025-03-26", "the version the server answered with, not the one asked for")
            self.assertEqual(headers.get("mcp-session-id"), "session-1")
        self.assertEqual(json.loads(out), {"tools": 4, "description_characters": 6 + 16 + 26 + len(SECRET), "median": 26, "max": len(SECRET),
                                           "largest": [["tool_secret", len(SECRET)], ["tool_2", 26], ["tool_1", 16], ["tool_0", 6]]})
        self.assertEqual(requests[0]["params"]["protocolVersion"], "2025-06-18")
        self.assertEqual(requests[2]["params"], {})

    def test_without_a_session_the_header_is_not_sent_and_the_version_header_still_is(self):
        with self.server(session=None, protocol="2025-06-18") as stub:
            code, _, err = self.probe(stub.url)
            later = [r["headers"] for r in stub.requests[1:]]
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(later and all("mcp-session-id" not in h and h.get("mcp-protocol-version") == "2025-06-18" for h in later))

    def test_the_pages_of_the_listing_are_followed(self):
        with self.server(pages=3) as stub:
            code, out, err = self.probe(stub.url, "--json")
            listing = [r for r in stub.requests if r["method"] == "tools/list"]
        self.assertEqual((code, err, json.loads(out)["tools"]), (0, "", 10))
        self.assertEqual([r["params"] for r in listing], [{}, {"cursor": "1"}, {"cursor": "2"}])

    def test_events_before_the_response_are_skipped_for_every_request(self):
        for options in ({"stream": True}, {"tools_event_first": True}):
            with self.subTest(options), self.server(**options) as stub:
                code, out, err = self.probe(stub.url, "--json")
            self.assertEqual((code, err, json.loads(out)["tools"]), (0, "", 4))

    def test_only_counts_are_printed(self):
        with self.server() as stub:
            for extra in ((), ("--json",)):
                code, out, err = self.probe(stub.url, *extra)
                self.assertEqual(code, 0)
                self.assertNotIn(SECRET, out + err)
                self.assertNotIn("AAAA", out + err)

    def test_an_unreadable_endpoint_is_exit_two_with_a_fixed_message(self):
        def failing(payload, headers):
            return 500, "text/plain", SECRET.encode(), None
        with Scripted(failing) as stub:
            code, out, err = self.probe(stub.url)
        self.assertEqual((code, out), (2, ""))
        self.assertTrue(err.startswith("tools_list_lengths:"))
        self.assertNotIn(SECRET, err)
        for url in ("http://[" + SECRET, "http://127.0.0.1:1/mcp"):
            code, out, err = self.probe(url, "--timeout", "2")
            self.assertEqual((code, out), (2, ""))
            self.assertNotIn(SECRET, err)

    def test_a_listing_that_never_ends_is_refused(self):
        def endless(payload, headers):
            method = payload.get("method")
            if method == "notifications/initialized":
                return 202, None, b"", None
            message = initialize_result("x") if method == "initialize" else {"jsonrpc": "2.0", "id": payload["id"], "result": {"tools": [], "nextCursor": "again"}}
            return 200, "application/json", json.dumps(message).encode(), None
        with Scripted(endless) as stub:
            code, out, err = self.probe(stub.url)
            pages = [r for r in stub.requests if r["method"] == "tools/list"]
        self.assertEqual((code, out), (2, ""))
        self.assertIn("more pages", err)
        self.assertEqual(len(pages), probe.MAX_PAGES)


class SourceConstantTests(unittest.TestCase):
    """source_constant_length.py reads a Rust string constant the way the compiler does: escapes, and a backslash at the end of a line."""

    SOURCE = ('// a comment\npub const MEMORY: &str = "\\\nHello\\n\\\n   world \\"quoted\\" back\\\\slash \\\n  tail" ;\nconst OTHER: &str = "no";\n')

    def run_script(self, text, *args):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "server.rs"
            path.write_text(text, encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = source_constant_length.main(["x", str(path), *args])
        return code, out.getvalue(), err.getvalue()

    def test_escapes_and_line_continuations_are_resolved(self):
        expected = 'Hello\nworld "quoted" back\\slash tail'
        self.assertEqual(source_constant_length.constant_text(self.SOURCE.replace('tail" ;', 'tail";'), "MEMORY"), expected)

    def test_it_prints_counts_a_hash_and_the_core_around_a_marker_and_never_the_text(self):
        text = "x" * 10 + "--- marker ---" + "\\n" + chr(0x1F4E5) * 2
        source = 'pub const MEMORY: &str = "' + text + '";\n'
        code, out, err = self.run_script(source, "MEMORY", "--marker", "--- marker ---")
        self.assertEqual((code, err), (0, ""))
        data = json.loads(out)
        resolved = "x" * 10 + "--- marker ---" + "\n" + chr(0x1F4E5) * 2
        self.assertEqual((data["characters"], data["utf16_units"], data["outside_bmp"]), (len(resolved), len(resolved) + 2, 2))
        self.assertEqual((data["core"], data["detail"]), (10, len(resolved) - 10 - len("--- marker ---")))
        self.assertEqual(data["sha256_16"], hashlib.sha256(resolved.encode()).hexdigest()[:16])
        self.assertNotIn("xxxxxxxxxx", out)

    def test_an_unresolved_escape_or_a_missing_constant_is_exit_two(self):
        code, out, err = self.run_script('pub const MEMORY: &str = "caf\\u{e9}";\n', "MEMORY")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("not resolved", err)
        code, out, err = self.run_script('pub const MEMORY: &str = "x";\n', "ABSENT")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("not found", err)


class RecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(MEASUREMENT.read_text(encoding="utf-8"))
        cls.record = RECORD.read_text(encoding="utf-8")
        cls.runs = cls.data["runs"]

    def test_the_measurement_is_the_output_of_the_scripts_and_is_internally_consistent(self):
        """Review of #1052 at 641ca19f (P3): measurement.json holds the verbatim output of each command, and every figure the record quotes is read from it or derived by the test."""
        ins = self.runs["instructions"]["output"]
        self.assertEqual(self.data["schema"], 2)
        self.assertEqual(ins["core"] + len(ins["marker"]) + ins["detail"], ins["characters"], "the core, the marker and the detail make the text")
        self.assertEqual(ins["utf16_units"] - ins["characters"], ins["outside_bmp"], "a character outside the Basic Multilingual Plane is two UTF-16 units")
        self.assertEqual(ins["cap"], self.data["client"]["default_cap_characters"])
        self.assertIs(ins["over_the_cap"], False, "the tool's own boolean: the part that must reach the model is inside the cap")
        self.assertEqual(ins["must_reach_the_model"], ins["core"])
        self.assertLessEqual(ins["core"], self.data["upstream_lines"]["core_limit_characters"], "the server's own test pins the marker at or before character 2,048")
        self.assertEqual((ins["bullets"], ins["bullets_started_under_cap"], ins["bullets_cut_by_cap"]), (23, 3, 1))
        self.assertGreater(self.data["audit_claim"]["block_characters"], ins["core"])
        self.assertLess(self.data["audit_claim"]["block_characters"], ins["characters"], "the audit's figure is neither the core nor the whole text")
        self.assertEqual(self.runs["tools_list"]["output"]["tools"], ins["bullets"], "one routing bullet per tool")

    def test_the_running_server_serves_the_constant_in_the_pinned_source(self):
        ins = self.runs["instructions"]["output"]
        src = self.runs["source_constant_v2_6_3"]["output"]
        old = self.runs["source_constant_mirror_pin"]["output"]
        for field in ("characters", "utf16_units", "outside_bmp", "sha256_16", "core", "detail"):
            self.assertEqual(ins[field], src[field], field)
        self.assertEqual(ins["version"], self.data["ai_memory"]["running_version"])
        self.assertNotEqual(old["sha256_16"], src["sha256_16"], "the mirror's manifest pin is an earlier text")
        self.assertEqual(old["core"], src["core"])
        self.assertLess(old["characters"], src["characters"])

    def test_the_record_quotes_the_figures_of_the_measurement(self):
        ins = self.runs["instructions"]["output"]
        tools = self.runs["tools_list"]["output"]
        old = self.runs["source_constant_mirror_pin"]["output"]
        cap = ins["cap"]
        for figure in (ins["characters"], ins["utf16_units"], ins["bytes"], ins["core"], ins["detail"], ins["characters"] - cap, ins["utf16_units"] - cap, tools["description_characters"],
                       tools["median"], tools["max"], old["characters"]):
            self.assertIn(f"{figure:,}", self.record, figure)
        self.assertIn(ins["sha256_16"], self.record)
        self.assertIn(self.data["measured_at_utc"], self.record)
        self.assertIn(ins["version"], self.record)
        self.assertIn(f"{self.data['audit_claim']['block_characters']:,}", self.record)

    def test_the_record_states_the_unit_of_its_character_counts_and_the_protocol_versions(self):
        """Review of #1052 at 641ca19f (P3): the units and the source's protocol default."""
        for needle in ("Unicode code points", "UTF-16 code units", "U+1F4E5", "2024-11-05", "L6275", "2025-06-18"):
            self.assertIn(needle, self.record, needle)

    def test_the_record_cites_the_revision_the_figures_come_from(self):
        """Review of #1052 at 641ca19f (P2): the figures are those of ai-memory 2.6.3 (385b81ea), so the cited lines are that revision's; the 2.6.0 mirror pin is named only as the earlier text."""
        for cite in ("CHANGELOG.md` L65", "L1522", "385b81ea95f7b73ede7146d0ae606c4caa7b43c1", "L169-L172", "L6276", "L8163-L8189", "3deb873687379f0c199a69fdaccc65f0865f7a29", "tag v2.6.3"):
            self.assertIn(cite, self.record, cite)
        self.assertEqual(self.data["ai_memory"]["source_revision"], "385b81ea95f7b73ede7146d0ae606c4caa7b43c1")
        self.assertEqual(self.data["upstream_lines"]["core_test"], "8163-8189")
        for line in self.record.splitlines():
            if "89bd8ded" in line:
                self.assertTrue(any(word in line for word in ("manifest pin", "mirror's", "2.6.0")), f"89bd8ded may only appear as the earlier pin: {line[:80]}")
        self.assertNotIn("L8087-L8112", self.record, "the lines of the 2.6.0 revision")

    def test_the_settings_templates_do_not_set_the_knob_unless_it_fits_the_whole_block(self):
        """The decision is that the knob stays unset. If a later change sets it, the value must be at least the measured whole-text length (and the record must be superseded)."""
        whole = self.runs["instructions"]["output"]["utf16_units"]   # the larger of the two units: a knob below it cuts the text in either
        for path in sorted((ROOT / "adoption").rglob("*.json")) + sorted((ROOT / "adoption").rglob("*.template.*")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for found in re.finditer(KNOB + r'"?\s*[:=]\s*"?(\d+)', text):
                self.assertGreaterEqual(int(found.group(1)), whole, f"{path.relative_to(ROOT)} sets {KNOB} below the measured block")

    def test_the_audit_group_is_retained_and_says_what_the_record_says_it_said(self):
        """Review of #1052 at f17cb3a0 (P2): the audit artifact the record cites must be in the repository."""
        retained = json.loads(AUDIT.read_text(encoding="utf-8"))
        self.assertEqual(retained["group"]["id"], "CPA-V-06")
        self.assertNotIn("sha256", retained["source"], "the full file stays private: no digest of it is published")
        self.assertEqual(retained["source"]["file"], "converged.json")
        claims = {c["claim"]: c for c in retained["group"]["claims"]}
        block = claims["The block is 4,122 characters"]
        self.assertEqual(block["status"], "not re-checked")
        self.assertIn(f"{self.data['audit_claim']['block_characters']:,}", block["claim"])
        self.assertIn("audit-group-CPA-V-06.json", self.record)

    def test_every_64_hex_digest_the_change_publishes_is_the_hash_of_a_file_it_publishes(self):
        """Review of #1052 at 7520907a2 (P1): the excerpt and the record published the sha256 of the audit's full file, which is private; a digest is published only with the bytes it names. Every 64-hex string in the
        record, the artifact and the tool is the sha256 of a file the registry holds."""
        registry = json.loads((ROOT / "manifests" / "evidence.json").read_text(encoding="utf-8"))
        published = {row["sha256"] for row in registry["files"]}
        paths = [RECORD, MEASUREMENT, AUDIT, ARTIFACT_README, ROOT / "tools" / "adoption" / "mcp_instructions_length.py", Path(__file__)]
        paths += sorted(path for path in ARTIFACT.iterdir() if path.suffix in (".py", ".json", ".md"))
        for path in paths:
            for digest in re.findall(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", path.read_text(encoding="utf-8")):
                self.assertIn(digest, published, f"{path.relative_to(ROOT)} publishes a digest that is not the sha256 of a published file")
        for name in ("sha256", "sha256_full", "source_sha256", "file_sha256"):
            self.assertNotIn(f'"{name}"', AUDIT.read_text(encoding="utf-8"))

    def test_the_ledger_prefix_is_cited_by_its_field_and_a_public_revision_and_is_not_taken_for_the_files_hash(self):
        """Review of #1052 at 7520907a2 (P3): `ec575b95c0558750` is the start of the ledger's `head_sha256` field, not of the file's sha256; the record says which, and at which public revision."""
        ledger_path = ROOT / "catalogs" / "saturation" / "ledger.json"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        self.assertRegex(ledger["head_sha256"], r"^[0-9a-f]{64}$")
        for needle in ("`head_sha256` field of", "catalogs/saturation/ledger.json", "489b26328", "ec575b95c0558750", "the file's own sha256 begins"):
            self.assertIn(needle, self.record.replace("\n  ", " "), needle)
        file_prefix = hashlib.sha256(ledger_path.read_bytes()).hexdigest()[:16]
        self.assertNotEqual(file_prefix, "ec575b95c0558750", "the cited prefix is the field's, so the record must not call it the file's")
        text = self.record.replace("\n  ", " ")
        field_prefix = re.search(r"`head_sha256` field of `catalogs/saturation/ledger.json` began `([0-9a-f]{16})`", text).group(1)
        stated_file_prefix = re.search(r"the file's own sha256 begins `([0-9a-f]{16})`", text).group(1)
        self.assertNotEqual(field_prefix, stated_file_prefix, "the field's prefix and the file's are two different things")

    def test_the_record_states_the_repositorys_rule_and_attributes_nothing_to_a_person(self):
        """Review of #1052 at 7520907a2 (P3): the paraphrase of a direction without a date; the repository's own rule is cited instead."""
        self.assertNotIn("owner", self.record.lower())
        self.assertIn("AGENTS.md", self.record)
        self.assertIn("Never rebuild or fork what an upstream already ships", self.record)
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Never rebuild or fork what an upstream already ships", agents, "the quoted sentence is still the repository's")

    def test_the_record_cites_the_transport_rules_it_relies_on_at_the_pinned_revision(self):
        for needle in ("1f520964b295d58494d944f2aea8a5ab51c79f77", "transports.mdx", "L84-L110", "L104-L106", "L240-L250", "reads the stream event by event", "fixed message"):
            self.assertIn(needle, self.record.replace("\n  ", " ").replace("\n   ", " "), needle)
        self.assertNotIn("L124-L126", self.record, "those lines describe the optional GET stream, not the response to a POST")

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
