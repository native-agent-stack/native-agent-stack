"""A loopback stand-in for the Messages API (for readdeny_probe.py): no credential, no network beyond 127.0.0.1, no model.
A command spec may carry "tool" (default Bash) and then is that tool's input.

Adapted from api-actions-20261008/harness/cc_mock.py (same wire format). Each conversation that offers the Bash tool
gets the next command of --commands as a Bash tool call, one per turn, then a final text answer. The client sends each
command's tool_result back in the next request, so the request log is the measurement record.

  mock_messages_api.py --port N --log requests.jsonl --commands commands.json
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ARGS = None
COMMANDS: list = []
LOCK = threading.Lock()
STATE = {"requests": 0}
DROP_HEADERS = {"x-api-key", "authorization", "cookie"}


def offered(body: dict) -> list:
    return [t.get("name") for t in body.get("tools") or [] if isinstance(t, dict)]


def bash_calls(body: dict) -> int:
    n = 0
    for message in body.get("messages") or []:
        if message.get("role") == "assistant" and isinstance(message.get("content"), list):
            n += sum(1 for b in message["content"] if isinstance(b, dict) and b.get("type") == "tool_use")
    return n


def plan_reply(body: dict) -> dict:
    if "Bash" in offered(body):
        i = bash_calls(body)
        if i < len(COMMANDS):
            spec = dict(COMMANDS[i])
            tool = spec.pop("tool", "Bash")
            if tool == "Bash":
                spec.setdefault("description", f"sandbox probe {i}")
            return {"type": "tool_use", "name": tool, "input": spec}
    return {"type": "text", "text": "probe done; the loopback stand-in answered and no model was called."}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _record(self, body):
        headers = {k.lower(): v for k, v in self.headers.items() if k.lower() not in DROP_HEADERS}
        with LOCK:
            STATE["requests"] += 1
            n = STATE["requests"]
            with open(ARGS.log, "a") as fh:
                fh.write(json.dumps({"n": n, "method": self.command, "path": self.path, "headers": headers,
                                     "body": body}) + "\n")
        return n

    def do_GET(self):
        self._record(None)
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("content-length") or 0))
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            body = {"unparsed_bytes": len(raw)}
        n = self._record(body)
        if not self.path.startswith("/v1/messages") or "count_tokens" in self.path:
            payload = json.dumps({"input_tokens": 100} if "count_tokens" in self.path else {}).encode()
            self.send_response(200 if "count_tokens" in self.path else 404)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        reply = plan_reply(body)
        msg_id = f"msg_m1_{n:04d}"
        model = body.get("model", "unknown")
        u = {"input_tokens": 40 + n, "output_tokens": 12, "cache_creation_input_tokens": 0,
             "cache_read_input_tokens": 0, "service_tier": "standard"}
        if reply["type"] == "tool_use":
            block = {"type": "tool_use", "id": f"toolu_m1_{n:04d}", "name": reply["name"], "input": reply["input"]}
            stop = "tool_use"
        else:
            block = {"type": "text", "text": reply["text"]}
            stop = "end_turn"
        if not body.get("stream"):
            payload = json.dumps({"id": msg_id, "type": "message", "role": "assistant", "model": model,
                                  "content": [block], "stop_reason": stop, "stop_sequence": None, "usage": u}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.end_headers()

        def event(name, data):
            self.wfile.write(f"event: {name}\ndata: {json.dumps(data)}\n\n".encode())
            self.wfile.flush()

        event("message_start", {"type": "message_start", "message": {
            "id": msg_id, "type": "message", "role": "assistant", "model": model, "content": [],
            "stop_reason": None, "stop_sequence": None, "usage": dict(u, output_tokens=1)}})
        if block["type"] == "tool_use":
            event("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {
                "type": "tool_use", "id": block["id"], "name": block["name"], "input": {}}})
            event("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {
                "type": "input_json_delta", "partial_json": json.dumps(block["input"])}})
        else:
            event("content_block_start", {"type": "content_block_start", "index": 0,
                                          "content_block": {"type": "text", "text": ""}})
            event("content_block_delta", {"type": "content_block_delta", "index": 0,
                                          "delta": {"type": "text_delta", "text": block["text"]}})
        event("content_block_stop", {"type": "content_block_stop", "index": 0})
        event("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                                "usage": {"output_tokens": u["output_tokens"]}})
        event("message_stop", {"type": "message_stop"})


def main() -> int:
    global ARGS, COMMANDS
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--log", required=True)
    p.add_argument("--commands", required=True)
    ARGS = p.parse_args()
    COMMANDS = json.load(open(ARGS.commands))
    server = ThreadingHTTPServer(("127.0.0.1", ARGS.port), Handler)
    print("listening", ARGS.port, flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
