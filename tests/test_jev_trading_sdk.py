"""Pinned vendor SDK on its native MockTransport; synthetic markers, no sockets."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

P1 = Path(__file__).resolve().parents[1] / "blueprints/native-skill-practice/p1"
sys.path.insert(0, str(P1))
try:
    import typesafe_sdk
    import httpx2
    import jev_trading_run as run
except ImportError as error:
    if os.environ.get("JEV_TRADING_REQUIRE_SDK") == "1":
        raise
    raise unittest.SkipTest("requires the qualified typesafe-sdk 0.7.2 and P1 numeric environment") from error


class NativeSDKTests(unittest.TestCase):
    def exercise(self, statuses):
        self.assertEqual(typesafe_sdk.__version__, "0.7.2")
        body = run.jev_request("TFN", run.Case(0, "invented financial bulletin", "neutral"), "jev-1.14.0")
        payload = run.FakeTransport().evaluate(body)
        requests = []
        native = typesafe_sdk.TypeSafeClient
        def handler(request):
            requests.append(request)
            status = statuses[len(requests) - 1]
            data = payload if status == 200 else {"error": "synthetic retry fixture"}
            return httpx2.Response(status, headers={"Content-Type": "application/json", "Retry-After": "999"},
                                   stream=httpx2.ByteStream(json.dumps(data).encode()))
        def factory(**kwargs):
            return native(transport=httpx2.MockTransport(handler), **kwargs)
        # This marker is not a credential. The native MockTransport consumes
        # every attempt in-process; the surrounding test run has no network.
        with mock.patch.object(run.os, "environ", {"TYPESAFE_API_KEY": "synthetic-key"}), \
             mock.patch.object(run, "require_credential_run"), \
             mock.patch.object(typesafe_sdk, "TypeSafeClient", side_effect=factory), \
             mock.patch("time.sleep") as sleep, \
             mock.patch("socket.socket", side_effect=AssertionError("no socket permitted")):
            try:
                transport = run.TypeSafeSDK()
                transport.prepare()
                result = transport.evaluate(body)
            except typesafe_sdk.TypeSafeAPIError as error:
                result = error
        return body, result, requests, sleep

    def test_native_429_529_retries_preserve_pinned_model_and_option_order(self):
        body, result, requests, sleep = self.exercise([429, 529, 200])
        self.assertEqual(result["model"], "jev-1.14.0")
        self.assertEqual(result["_sdk_retry_count"], 2)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])
        for request in requests:
            self.assertEqual(json.loads(request.content), body)
            self.assertEqual(list(json.loads(request.content)["questions"]["label"]["criteria"]), ["bearish", "neutral", "bullish"])
            self.assertEqual(str(request.url), "https://api.typesafe.ai/v1/systemone")
            self.assertEqual(request.headers["User-Agent"], "typesafe-sdk/0.7.2")
            self.assertFalse(any("danger" in name.lower() for name in request.headers))

    def test_retry_exhaustion_has_five_attempts_and_no_connection_retry(self):
        _, result, requests, sleep = self.exercise([429] * 5)
        self.assertIsInstance(result, typesafe_sdk.TypeSafeAPIError)
        self.assertEqual(len(requests), 5)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2, 4, 8])

    def test_non_retryable_status_stops_after_one_attempt(self):
        _, result, requests, sleep = self.exercise([500])
        self.assertIsInstance(result, typesafe_sdk.TypeSafeAPIError)
        self.assertEqual(len(requests), 1)
        sleep.assert_not_called()
