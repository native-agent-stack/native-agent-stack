"""Generated fixtures for the native JSONL adapters; no runtime home access.

Contracts: Pi@04566631 docs/{json,session-format,message-types}.md;
OpenCode@53d1eabb cli/cmd/run.ts and @4d9678a7 core/src/tool/mcp.ts.
These tests establish parser behavior, not a native model execution receipt.
"""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/skill-usage"))
import runtime_usage
from skill_usage import skillmd_hits

NAMES = {"codebase-design", "diagnosing-bugs"}
PRIVATE = "/private/fixture-user/secret"


def pi_start(call, tool="read", args=None):
    return {"type": "tool_execution_start", "toolCallId": call,
            "toolName": tool, "args": args if args is not None else {"path": f"{PRIVATE}/codebase-design/SKILL.md"}}


def pi_end(call, tool="read", error=False):
    return {"type": "tool_execution_end", "toolCallId": call,
            "toolName": tool, "isError": error,
            "result": {"content": [{"type": "text", "text": PRIVATE}]}}


def pi_message(role, content, **fields):
    return {"type": "message", "id": "private-entry-id", "parentId": None,
            "message": {"role": role, "content": content, **fields}}


def opencode(call, tool="skill", inputs=None, status="completed", session="private-session"):
    return {"type": "tool_use", "sessionID": session,
            "part": {"id": "private-part-" + call, "sessionID": session,
                     "type": "tool", "callID": call, "tool": tool,
                     "state": {"status": status,
                               "input": inputs if inputs is not None else {"name": "codebase-design"},
                               "output": PRIVATE}}}


def exported_message(*events, session="private-session", role="assistant"):
    return {"info": {"id": "private-message", "sessionID": session, "role": role},
            "parts": [event["part"] for event in events]}


class RuntimeUsageTests(unittest.TestCase):
    def test_completed_role_vendor_reads_and_native_loader_are_counted_and_attributed(self):
        vendor = "test-driven-development"
        pi = self.log("vendor-pi.jsonl", [{"type": "session", "id": "vendor-session"},
            pi_start("vendor-read", args={"path": f"/fixture/skills/{vendor}/SKILL.md"}), pi_end("vendor-read"),
            pi_start("context-read", args={"path": "/fixture/skills/context-mode/SKILL.md"}), pi_end("context-read")])
        native = self.log("vendor-opencode.jsonl", [opencode("vendor-skill", inputs={"name": vendor}),
            opencode("not-a-skill", inputs={"name": "unknown-private-name"}),
            opencode("failed-vendor", inputs={"name": "using-superpowers"}, status="error")])
        reports = self.scan(("pi", pi), ("opencode", native))
        self.assertEqual(reports["pi"]["successful_skill_uses"], {vendor: 1, "context-mode": 1})
        self.assertEqual(reports["opencode"]["successful_skill_uses"], {vendor: 1})
        self.assertEqual(reports["pi"]["skill_source_attribution"][vendor],
                         "obra/superpowers@bb92a77741419a4ab5f06e711a283343f1ada0c3")
        self.assertNotIn("unknown-private-name", json.dumps(reports))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def log(self, name, records):
        path = self.directory / name
        path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
                        encoding="utf-8")
        return path

    def scan(self, *logs):
        return runtime_usage.scan(logs, NAMES, skillmd_hits=skillmd_hits)

    def test_pi_stream_and_persisted_results_deduplicate_across_log_copies(self):
        records = [
            {"type": "session", "id": "private-session"},
            pi_start("private-call"), pi_end("private-call"), pi_end("private-call"),
            pi_message("assistant", [{"type": "toolCall", "id": "private-call", "name": "read",
                                      "arguments": {"path": f"{PRIVATE}/codebase-design/SKILL.md"}}],
                       stopReason="toolUse"),
            pi_message("toolResult", [], toolCallId="private-call", toolName="read", isError=False),
            pi_start("private-mcp", "mcp__headroom__get_stats", {}),
            pi_end("private-mcp", "mcp__headroom__get_stats"),
        ]
        first = self.log("stream.jsonl", records)
        second = self.log("copy.jsonl", records)
        hardlink = self.directory / "hardlink.jsonl"
        os.link(first, hardlink)
        row = self.scan(("pi", first), ("pi", second), ("pi", first), ("pi", hardlink))["pi"]
        self.assertEqual(row["logs_scanned"], 2)
        self.assertEqual(row["sessions_measured"], 1)
        self.assertEqual(row["completed_tool_calls"], 2)
        self.assertEqual(row["successful_skill_uses"], {"codebase-design": 1})
        self.assertEqual(row["successful_mcp_calls"], {"headroom": 1})
        self.assertEqual(row["orphan_results"], 0)

    def test_pi_call_ids_are_scoped_to_the_native_session(self):
        records = []
        for session in ["private-first", "private-second", "private-first"]:
            records.extend([{"type": "session", "id": session}, pi_start("reused"), pi_end("reused")])
        row = self.scan(("pi", self.log("sessions.jsonl", records)))["pi"]
        self.assertEqual(row["sessions_measured"], 2)
        self.assertEqual(row["completed_tool_calls"], 2)

    def test_pi_session_messages_need_an_own_complete_assistant_tool_call(self):
        records = [
            {"type": "session", "id": "private-session"},
            pi_message("assistant", [{"type": "toolCall", "id": "own", "name": "read",
                                      "arguments": {"path": f"{PRIVATE}/codebase-design/SKILL.md"}}],
                       stopReason="toolUse"),
            pi_message("toolResult", [{"type": "text", "text": "mcp__headroom__get_stats"}],
                       toolCallId="own", toolName="read", isError=False),
            {"type": "message_start", "message": {"role": "assistant", "stopReason": "pending",
             "content": [{"type": "toolCall", "id": "partial", "name": "read", "arguments": {}}]}},
            pi_message("assistant", [{"type": "toolCall", "id": "pending", "name": "read", "arguments": {}}],
                       stopReason="pending"),
            pi_end("partial"), pi_end("pending"), pi_end("no-own-call"),
            pi_message("system", [{"type": "toolCall", "id": "system", "name": "read", "arguments": {}}]),
            pi_end("system"),
        ]
        row = self.scan(("pi", self.log("session.jsonl", records)))["pi"]
        self.assertEqual(row["completed_tool_calls"], 1)
        self.assertEqual(row["successful_skill_uses"], {"codebase-design": 1})
        self.assertEqual(row["successful_mcp_calls"], {})
        self.assertEqual(row["orphan_results"], 4)

    def test_pi_malformed_failed_pending_and_orphan_results_are_reported(self):
        records = [{"type": "session", "id": "private-session"},
                   pi_start("failed"), pi_end("failed", error=True),
                   pi_start("nested-error"), pi_end("nested-error"),
                   pi_start("pending"), pi_end("orphan")]
        records[4]["result"]["isError"] = True
        path = self.log("broken.jsonl", records)
        with path.open("ab") as stream:
            stream.write(b'{broken\nnull\n[]\n{"bad":"\xff"}\n')
        row = self.scan(("pi", path))["pi"]
        self.assertEqual(row["parse_errors"], 4)
        self.assertEqual(row["completed_tool_calls"], 0)
        self.assertEqual(row["failed_tool_calls"], 2)
        self.assertEqual(row["pending_tool_calls"], 1)
        self.assertEqual(row["orphan_results"], 1)

    def test_split_pi_logs_can_be_passed_in_either_order(self):
        header = {"type": "session", "id": "private-session"}
        start = self.log("start.jsonl", [header, pi_start("split")])
        end = self.log("end.jsonl", [header, pi_end("split")])
        for logs in [[("pi", start), ("pi", end)], [("pi", end), ("pi", start)]]:
            with self.subTest(logs=[path.name for _, path in logs]):
                row = self.scan(*logs)["pi"]
                self.assertEqual(row["completed_tool_calls"], 1)
                self.assertEqual(row["orphan_results"], 0)
                self.assertEqual(row["pending_tool_calls"], 0)

    def test_conflicting_pi_call_identity_is_not_attributed(self):
        records = [{"type": "session", "id": "private-session"},
                   pi_start("mismatch"), pi_end("mismatch", "mcp__headroom__get_stats"),
                   pi_start("disagreement"), pi_end("disagreement"),
                   pi_message("toolResult", [], toolCallId="disagreement", toolName="read", isError=True)]
        row = self.scan(("pi", self.log("conflict.jsonl", records)))["pi"]
        self.assertEqual(row["completed_tool_calls"], 0)
        self.assertEqual(row["conflicting_tool_calls"], 1)
        self.assertEqual(row["failed_tool_calls"], 1)

    def test_opencode_native_successes_and_server_sanitization(self):
        records = [opencode("skill"),
                   opencode("read", "read", {"filePath": f"{PRIVATE}/diagnosing-bugs/SKILL.md"}),
                   opencode("hyphen", "context-mode_ctx_execute", {}),
                   opencode("underscore", "codebase_memory_search_graph", {}),
                   opencode("mcp", "headroom_get_stats", {}),
                   opencode("unknown", "private_customer_secret_tool", {}),
                   opencode("empty", "headroom_", {}),
                   opencode("prefix", "headroomish_tool", {})]
        row = self.scan(("opencode", self.log("opencode.jsonl", records)))["opencode"]
        self.assertEqual(row["completed_tool_calls"], 8)
        self.assertEqual(row["successful_skill_uses"], {"codebase-design": 1, "diagnosing-bugs": 1})
        self.assertEqual(row["successful_mcp_calls"], {"codebase-memory": 1, "context-mode": 1, "headroom": 1})

    def test_opencode_deduplicates_session_calls_but_preserves_distinct_sessions(self):
        first = self.log("first.jsonl", [opencode("reuse"), opencode("reuse")])
        second = self.log("second.jsonl", [opencode("reuse"), opencode("reuse", session="another-private-session")])
        row = self.scan(("opencode", first), ("opencode", second))["opencode"]
        self.assertEqual(row["sessions_measured"], 2)
        self.assertEqual(row["completed_tool_calls"], 2)

    def test_opencode_requires_own_tool_use_envelope_and_successful_state(self):
        mentioned = opencode("text-mention")
        mentioned["type"] = "text"
        child = opencode("child")
        child["part"]["sessionID"] = "different-private-session"
        metadata_error = opencode("tool-error")
        metadata_error["part"]["state"]["metadata"] = {"isError": True}
        records = [mentioned, child, metadata_error, opencode("failed", status="error"),
                   opencode("pending", status="pending"), opencode("running", status="running")]
        row = self.scan(("opencode", self.log("states.jsonl", records)))["opencode"]
        self.assertEqual(row["completed_tool_calls"], 0)
        self.assertEqual(row["successful_skill_uses"], {})
        self.assertEqual(row["failed_tool_calls"], 2)
        self.assertEqual(row["pending_tool_calls"], 2)
        self.assertEqual(row["orphan_results"], 1)

    def test_skill_reads_require_the_native_path_argument_and_exact_filename(self):
        pi = [{"type": "session", "id": "private-session"}]
        for call, tool, args in [
            ("notes", "read", {"path": "/ordinary/file", "notes": f"{PRIVATE}/codebase-design/SKILL.md"}),
            ("backup", "read", {"path": f"{PRIVATE}/codebase-design/SKILL.md.bak"}),
            ("bash", "bash", {"command": f"cat {PRIVATE}/codebase-design/SKILL.md"}),
            ("unknown", "read", {"path": f"{PRIVATE}/unknown-private-skill/SKILL.md"}),
        ]:
            pi.extend([pi_start(call, tool, args), pi_end(call, tool)])
        pi.extend([pi_start("mcp-unknown", "mcp__private_customer__secret", {}),
                   pi_end("mcp-unknown", "mcp__private_customer__secret")])
        oc = [opencode("wrong-key", "read", {"path": f"{PRIVATE}/codebase-design/SKILL.md"}),
              opencode("unknown", inputs={"name": "unknown-private-skill"}),
              opencode("mention", inputs={"name": "ordinary", "notes": "codebase-design"})]
        result = self.scan(("pi", self.log("mentions.jsonl", pi)),
                           ("opencode", self.log("oc-mentions.jsonl", oc)))
        for row in result.values():
            self.assertEqual(row["successful_skill_uses"], {})
            self.assertEqual(row["successful_mcp_calls"], {})

    def test_invalid_tool_shapes_are_diagnostic_instead_of_crashing(self):
        pi = [pi_start("bad-args", args=[]),
              {"type": "message", "message": {"role": "assistant", "content": None}},
              {"type": "tool_execution_end", "toolCallId": ["bad-id"], "isError": False}]
        oc = [{"type": "tool_use", "part": None},
              {"type": "tool_use", "part": {"type": "tool", "state": []}},
              opencode("bad-input", inputs=[])]
        result = self.scan(("pi", self.log("invalid-pi.jsonl", pi)),
                           ("opencode", self.log("invalid-oc.jsonl", oc)))
        for row in result.values():
            self.assertEqual(row["completed_tool_calls"], 0)
            self.assertEqual(row["invalid_records"], 3)

    def test_lf_framing_and_public_report_keep_private_content_in_place(self):
        records = [{"type": "session", "id": "private-session"}, pi_start("private-call"), pi_end("private-call")]
        records[-1]["result"]["content"][0]["text"] = "private-text\u2028private-paragraph\u2029" + PRIVATE
        path = self.log("private-filename.jsonl", records)
        before = path.read_bytes()
        self.log("unrequested.jsonl", [opencode("unrequested")])
        with patch.object(Path, "home", side_effect=AssertionError("runtime home discovery is forbidden")):
            result = self.scan(("pi", path))
        self.assertEqual(result["pi"]["parse_errors"], 0)
        self.assertEqual(result["pi"]["completed_tool_calls"], 1)
        self.assertFalse(result["pi"]["organic_use_measured"])
        self.assertEqual(result["pi"]["evidence_class"], "prompted_or_unclassified_native_invocation")
        self.assertNotIn("organic_skill_uses", result["pi"])
        self.assertEqual(path.read_bytes(), before)
        public = json.dumps(result)
        for secret in [PRIVATE, "private-session", "private-call", "private-text", "private-filename", str(path)]:
            self.assertNotIn(secret, public)
        self.assertNotIn("opencode", result)

    def test_non_string_native_discriminators_are_reported_without_crashing(self):
        invalid_state = opencode("bad-state")
        invalid_state["part"]["state"]["status"] = []
        pi = [{"type": []},
              pi_message("assistant", [], stopReason={"private": "invalid"})]
        oc = [{"type": []}, invalid_state]
        result = self.scan(("pi", self.log("types-pi.jsonl", pi)),
                           ("opencode", self.log("types-oc.jsonl", oc)))
        for row in result.values():
            self.assertEqual(row["invalid_records"], 2)
            self.assertEqual(row["completed_tool_calls"], 0)

    def test_input_rejections_and_io_errors_do_not_disclose_paths(self):
        directory = self.directory / "private-directory.jsonl"
        directory.mkdir()
        target = self.log("private-source.jsonl", [])
        link = self.directory / "private-link.jsonl"
        link.symlink_to(target)
        for runtime, path in [("other", target), ("pi", directory), ("pi", link),
                              ("pi", self.directory / "private-missing.jsonl"),
                              ("pi", self.directory / "private-extension.txt")]:
            with self.subTest(runtime=runtime, name=path.name):
                with self.assertRaises(ValueError) as caught:
                    self.scan((runtime, path))
                self.assertNotIn("private", str(caught.exception))
                self.assertNotIn(str(path), str(caught.exception))
        with patch.object(Path, "open", side_effect=OSError(PRIVATE)):
            with self.assertRaisesRegex(ValueError, "cannot read runtime log") as caught:
                self.scan(("pi", target))
        self.assertNotIn(PRIVATE, str(caught.exception))

    def test_native_export_completed_calls_deduplicate_and_remain_private(self):
        skill, mcp = opencode("export-skill"), opencode("export-mcp", "headroom_get_stats", {})
        document = {"info": {"id": "private-session", "directory": PRIVATE, "title": PRIVATE},
                    "messages": [exported_message(skill, mcp, skill),
                                 exported_message(opencode("failed", status="error"),
                                                  opencode("pending", status="running"))]}
        original = json.dumps(document, sort_keys=True)
        with patch.object(Path, "open", side_effect=AssertionError("exports must stay in memory")):
            row = runtime_usage.scan_opencode_export(document, NAMES, skillmd_hits=skillmd_hits)
        self.assertEqual(row["sessions_measured"], 1)
        self.assertEqual(row["completed_tool_calls"], 2)
        self.assertEqual(row["successful_skill_uses"], {"codebase-design": 1})
        self.assertEqual(row["successful_mcp_calls"], {"headroom": 1})
        self.assertEqual(row["failed_tool_calls"], 1)
        self.assertEqual(row["pending_tool_calls"], 1)
        self.assertEqual(row["logs_scanned"], 0)
        self.assertEqual(row["source_format"], "native_opencode_export_in_memory")
        self.assertEqual(row["native_exports_measured"], 1)
        self.assertFalse(row["organic_use_measured"])
        self.assertEqual(json.dumps(document, sort_keys=True), original)
        for secret in [PRIVATE, "private-session", "private-message", "export-skill", "export-mcp"]:
            self.assertNotIn(secret, json.dumps(row))

    def test_native_export_foreign_messages_and_parts_never_count(self):
        foreign_part = opencode("foreign-part", session="other-private-session")
        forged_part = opencode("foreign-message")
        missing_session = opencode("missing-part-session")
        missing_session["part"].pop("sessionID")
        document = {"info": {"id": "private-session"},
                    "messages": [exported_message(foreign_part),
                                 exported_message(forged_part, session="other-private-session"),
                                 exported_message(missing_session)]}
        row = runtime_usage.scan_opencode_export(document, NAMES, skillmd_hits=skillmd_hits)
        self.assertEqual(row["completed_tool_calls"], 0)
        self.assertEqual(row["successful_skill_uses"], {})
        self.assertEqual(row["orphan_results"], 2)
        self.assertEqual(row["invalid_records"], 1)

    def test_native_export_rejects_malformed_envelopes_and_skips_malformed_messages(self):
        envelopes = [None, [], {}, {"info": []}, {"info": {}},
                     {"info": {"id": []}, "messages": []},
                     {"info": {"id": "private-session"}, "messages": {}},
                     {"info": {"id": ""}, "messages": []}]
        for document in envelopes:
            with self.subTest(document=document):
                with self.assertRaisesRegex(ValueError, "invalid native export") as caught:
                    runtime_usage.scan_opencode_export(document, NAMES, skillmd_hits=skillmd_hits)
                self.assertNotIn("private-session", str(caught.exception))
        document = {"info": {"id": "private-session"},
                    "messages": [None, {"parts": []}, {"info": {}, "parts": []},
                                 {"info": {"sessionID": "private-session", "role": "assistant"}, "parts": None},
                                 {"info": {"sessionID": "private-session", "role": "assistant"}, "parts": [None]},
                                 exported_message(opencode("fake-user-tool"), role="user")]}
        row = runtime_usage.scan_opencode_export(document, NAMES, skillmd_hits=skillmd_hits)
        self.assertEqual(row["completed_tool_calls"], 0)
        self.assertEqual(row["invalid_records"], 6)


if __name__ == "__main__":
    unittest.main()
