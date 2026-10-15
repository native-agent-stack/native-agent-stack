"""Offline public-contract tests for the 2026-10-11 record and ADDENDUM-01.

All writable fixtures use /var/tmp and are removed. No model is contacted.
Run with the existing P1 requirements-scoring.lock environment.
"""
from __future__ import annotations

import hashlib
import ast
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

P1 = Path(__file__).resolve().parents[1] / "blueprints/native-skill-practice/p1"
sys.path.insert(0, str(P1))
try:
    import numpy as np
    from scipy import stats
except ImportError as exc:
    raise unittest.SkipTest("Use the hash-locked P1 scoring environment") from exc
import jev_trading_cases as cases


def private_attestation_fixture(directory):
    root = Path(directory)
    records = {}
    for name in ("addendum", "codex", "claude", "sdk_amendment", "models_page"):
        path = root / (name + ".md")
        path.write_text("private synthetic provenance " + name)
        records[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    proof = {"source_sha256": cases.SOURCE_PINS, "addendum": records["addendum"],
             "two_family_reads": {name: records[name] for name in ("codex", "claude")},
             "sdk": {"version": "0.7.2", "wheel_sha256": "0a961148187d52e18276ed7f2d02617cfac48e3b97673cb631a8749397d43d1e",
                     "amendment": records["sdk_amendment"]}, "models_page": records["models_page"]}
    path = root / "private-proof.json"
    path.write_text(json.dumps(proof))
    return path, proof


class CaseTests(unittest.TestCase):
    def test_content_pins_match_published_frozen_source_reproduction(self):
        path = P1.parents[2] / "evidence/artifacts/jev-trading-build-20261015/frozen-source-check.json"
        retained = json.loads(path.read_text())
        self.assertEqual(cases.CONTENT_PINS,
                         {name: row["content_sha256"] for name, row in retained["sets"].items()})
        self.assertEqual(retained["source_sha256"], cases.SOURCE_PINS)

    def test_builder_requires_the_record_source_pins_and_library_versions(self):
        with mock.patch.object(cases, "version", return_value="different"):
            with self.assertRaisesRegex(ValueError, "dependency pin"):
                cases.require_dependencies()
        with mock.patch.object(cases, "read_pinned", side_effect=AssertionError("must not read")):
            with self.assertRaisesRegex(ValueError, "frozen source"):
                cases.build_frozen_sets({})

    def test_duplicate_ids_unknown_labels_and_empty_text_rejected(self):
        for rows in ([cases.Case(0, "x", "neutral"), cases.Case(0, "y", "neutral")],
                     [cases.Case(0, "x", "unsupported")], [cases.Case(-1, "x", "neutral")],
                     [cases.Case(0, "\u00a0", "neutral")]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                cases.assemble("TFN", [], rows)

    def test_unicode_exclusion_and_frozen_lists_fail_closed(self):
        train = [cases.Case(0, "same\u00a0text", "bearish"),
                 cases.Case(1, "different", "bullish")]
        scored = [cases.Case(0, " same text ", "neutral")]
        pack = cases.assemble("TFN", train, scored)
        self.assertEqual([r.id for r in pack.training], [1])
        self.assertEqual(pack.manifest()["ids"]["excluded_training"], [0])
        pins = {"training": "463f2998327eb3a694145e6014444480b2235be84aa6cfd57871cc64f1cd816c",
                "scored": "d0bca111f8628137adc4c16f123496dcdd1d590d06cb5d9acd68b39fe656fb97",
                "final_training": "080a9ed428559ef602668b4c00f114f1a11c3f6b02a435f0bdc154578e4d7f22"}
        cases.verify_lists(pack, pins)
        with self.assertRaisesRegex(ValueError, "id-list pin"):
            cases.verify_lists(pack, {**pins, "final_training": "0" * 64})

    def test_source_pin_rejects_changed_bytes_before_decode(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as directory:
            path = Path(directory) / "input.txt"
            path.write_bytes(b"bad\xff")
            with self.assertRaisesRegex(ValueError, "source pin"):
                cases.read_pinned(path, "0" * 64)
            self.assertEqual(path.read_bytes(), b"bad\xff")

    def test_option_order_matches_record_and_duplicates_stay(self):
        self.assertEqual(cases.option_order("TFN", 0), ["bearish", "neutral", "bullish"])
        self.assertEqual(cases.option_order("FOMC", 0), ["neutral", "dovish", "hawkish"])
        rows = [cases.Case(80, "duplicate", "neutral"), cases.Case(90, "duplicate", "hawkish")]
        pack = cases.assemble("FOMC", [], rows)
        self.assertEqual(len(pack.scored), 2)
        self.assertEqual(pack.manifest()["clusters"], {"count": 1, "duplicate_texts": 1,
                         "duplicate_rows": 2, "conflicting_labels": 1, "representatives": [80]})


class MetricsTests(unittest.TestCase):
    def test_ece_uses_frozen_sorted_argmax_on_a_tie(self):
        import jev_trading_scoring as s
        answer = s.prediction({"bearish": 0.4, "bullish": 0.4, "neutral": 0.2}, cases.LABELS["TFN"], "bullish")
        pack = cases.assemble("TFN", [], [cases.Case(0, "Synthetic tied answer.", "bullish")])
        self.assertEqual(answer.label, "bullish")
        self.assertAlmostEqual(s.arm_metrics(pack, {0: answer})["ece"], 0.4)

    def test_paired_ece_interval_uses_frozen_sorted_argmax(self):
        import jev_trading_scoring as s
        labels = cases.LABELS["TFN"]
        first = s.prediction({"bearish": 0.4, "bullish": 0.4, "neutral": 0.2}, labels, "bullish")
        second = s.prediction({"bearish": 0.1, "bullish": 0.8, "neutral": 0.1}, labels, "bullish")
        pack = cases.assemble("TFN", [], [cases.Case(i, f"Synthetic tie {i}.", "bullish") for i in range(2)])
        result = s.paired_metrics(pack, {i: first for i in range(2)}, {i: second for i in range(2)})
        for field in ("point", "low", "high"):
            self.assertAlmostEqual(result["ece"][field], 0.2, msg=field)

    def test_unordered_baseline_has_no_first_position_diagnostic(self):
        import jev_trading_scoring as s
        pack = cases.assemble("TFN", [], [cases.Case(0, "synthetic", "neutral")])
        value = s.prediction({"bearish": 0.1, "bullish": 0.1, "neutral": 0.8}, cases.LABELS["TFN"])
        report = s.arm_metrics(pack, {0: value}, ordered_options=False)
        self.assertEqual(report["first_position"], {"status": "NOT_APPLICABLE"})

    def test_empty_scored_population_rejected(self):
        import jev_trading_scoring as s
        with self.assertRaisesRegex(ValueError, "empty scored"):
            s.arm_metrics(cases.assemble("TFN", [], []), {})

    def test_cluster_intervals_match_independent_sklearn_resampling(self):
        import jev_trading_scoring as s
        labels = cases.LABELS["TFN"]
        rows = [cases.Case(0, "same", "bearish"), cases.Case(1, "same", "neutral"),
                cases.Case(2, "different", "bullish"), cases.Case(3, "third", "neutral")]
        pack = cases.assemble("TFN", [], rows)
        a = {i: s.prediction(dict(zip(labels, p)), labels) for i, p in enumerate(
            ((0.6, 0.2, 0.2), (0.4, 0.3, 0.3), (0.1, 0.8, 0.1), (0.1, 0.2, 0.7)))}
        b = {i: s.prediction(dict(zip(labels, (0.2, 0.5, 0.3))), labels) for i in range(4)}
        real_bootstrap = s.stats.bootstrap
        def independent_check(data, statistic, **kwargs):
            for draw in ([0, 0, 2], [0, 1, 2], [2, 2, 2]):
                ids = [j for group in draw for j in ([0, 1], [2], [3])[group]]
                oracle = []
                for arm in (a, b):
                    # This public arm calculation uses sklearn point metrics;
                    # unique synthetic IDs preserve repeated resampled rows.
                    repeated = cases.assemble("TFN", [], [cases.Case(k, f"draw {k}", rows[i].label) for k, i in enumerate(ids)])
                    values = s.arm_metrics(repeated, {k: arm[i] for k, i in enumerate(ids)})
                    oracle.append([values[m] for m in ("macro_f1", "brier", "ece")])
                np.testing.assert_allclose(statistic(np.array(draw)), np.array(oracle[0]) - oracle[1], atol=1e-14)
            return real_bootstrap(data, statistic, **kwargs)
        with mock.patch.object(s.stats, "bootstrap", side_effect=independent_check):
            s.paired_metrics(pack, a, b)

    def test_record_worked_example_and_failure_inclusive_population(self):
        import jev_trading_scoring as scoring
        labels = cases.LABELS["FPB-50"]
        truth = [labels[i] for i in (0, 0, 1, 1, 1, 2, 2, 2)]
        values = [(0.7, 0.2, 0.1), (0.45, 0.45, 0.1), (0.05, 0.85, 0.1),
                  (0.2, 0.55, 0.25), None, (0.1, 0.25, 0.65), (0.05, 0.05, 0.9), (0.15, 0.55, 0.3)]
        rows = [cases.Case(i, f"synthetic {i}", label) for i, label in enumerate(truth)]
        answers = {i: scoring.prediction(dict(zip(labels, p)), labels) if p else None
                   for i, p in enumerate(values)}
        report = scoring.arm_metrics(cases.assemble("FPB-50", [], rows), answers)
        self.assertAlmostEqual(report["macro_f1"], 37 / 45)
        self.assertAlmostEqual(report["brier"], 101 / 350)
        self.assertAlmostEqual(report["ece"], 31 / 140)
        self.assertAlmostEqual(report["sensitivity"]["brier"], 403 / 1200)
        self.assertEqual(report["coverage"]["row_rate"], 7 / 8)
        self.assertTrue(report["incomplete"])
        self.assertFalse(report["calibration_rankable"])

    def test_probability_validation_and_exact_one_percent_boundary(self):
        import jev_trading_scoring as scoring
        labels = cases.LABELS["TFN"]
        for bad in ({"bearish": 1.0}, dict(zip(labels, (0.8, 0.8, -0.6))),
                    dict(zip(labels, (float("nan"), 0, 1))), dict(zip(labels, (0.5, 0.5, 0.1)))):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                scoring.prediction(bad, labels)
        answer = scoring.prediction(dict(zip(labels, (0.5, 0.5, 0))), labels)
        self.assertEqual(answer.label, "bearish")
        pack = cases.assemble("TFN", [], [cases.Case(i, f"item {i}", "bearish") for i in range(100)])
        outputs = {i: answer for i in range(1, 100)}
        self.assertFalse(scoring.arm_metrics(pack, outputs)["incomplete"])
        outputs.pop(1)
        self.assertTrue(scoring.arm_metrics(pack, outputs)["incomplete"])

    def test_cluster_bootstrap_call_and_representative_no_substitution(self):
        import jev_trading_scoring as scoring
        labels = cases.LABELS["FOMC"]
        rows = [cases.Case(0, "duplicate", "dovish"), cases.Case(1, "duplicate", "hawkish"),
                cases.Case(2, "other", "neutral"), cases.Case(3, "last", "dovish")]
        pack = cases.assemble("FOMC", [], rows)
        a = {r.id: scoring.prediction({l: float(l == r.label) for l in labels}, labels) for r in rows}
        b = {i: scoring.prediction(dict(zip(labels, (0.1, 0.1, 0.8))), labels) for i in (1, 2, 3)}
        calls = []
        real = scoring.stats.bootstrap
        def spy(data, statistic, **kw):
            calls.append((len(data[0]), kw.copy(), kw["rng"].bit_generator.state))
            return real(data, statistic, **kw)
        with mock.patch.object(scoring.stats, "bootstrap", side_effect=spy):
            result = scoring.paired_metrics(pack, a, b)
        n, kw, rng = calls[0]
        self.assertEqual(n, 3)
        self.assertEqual((kw["paired"], kw["method"], kw["n_resamples"], kw["confidence_level"]),
                         (True, "percentile", 10000, 0.95))
        self.assertEqual(rng, np.random.default_rng(20261011).bit_generator.state)
        self.assertEqual(result["shared_ids"], [1, 2, 3])
        self.assertEqual(result["representative_ids"], [2, 3])
        self.assertEqual(result["mcnemar"]["only_first_correct"], 1)
        self.assertEqual(result["mcnemar"]["p_value"], 1.0)
        self.assertAlmostEqual(result["macro_f1"]["point"], 5 / 6)


class BeatsTests(unittest.TestCase):
    def test_all_pairs_subset_not_run_and_interval_boundaries(self):
        import jev_trading_scoring as s
        pairs = {b: {"status": "RAN", "macro_f1": {"low": 0.01, "high": 0.2},
                     "brier": {"low": -0.2, "high": 0.0}} for b in s.BASELINES["TFN"]}
        canaries = {"date_shift": {"status": "COUNTS_ONLY"}, "entity_mask": {"status": "NOT_RUN"}}
        result = s.beats("jev-1.14.0", "TFN", False, pairs, canaries)
        self.assertTrue(result["beats"])
        for metric, endpoint, value in (("macro_f1", "low", 0.0), ("brier", "high", 0.0001),
                                        ("macro_f1", "low", None), ("brier", "high", float("nan"))):
            changed = json.loads(json.dumps(pairs))
            changed["finbert"][metric][endpoint] = value
            self.assertFalse(s.beats("jev-1.14.0", "TFN", False, changed, canaries)["beats"])
        pairs["clm-8b"] = {"status": "NOT_RUN", "reason": "no GPU window"}
        subset = s.beats("jev-1.14.0", "TFN", False, pairs, canaries)
        self.assertEqual(subset["label"], "beats the baselines that ran (3 of 4)")
        self.assertEqual(subset["not_run"], ["clm-8b"])
        self.assertEqual(subset["not_run_count"], 1)
        self.assertFalse(s.beats("jev-1.14.0", "TFN", True, pairs, canaries)["beats"])
        all_absent = {b: {"status": "NOT_RUN"} for b in pairs}
        self.assertFalse(s.beats("jev-1.14.0", "TFN", False, all_absent, canaries)["beats"])
        with self.assertRaises(ValueError):
            s.beats("jev-latest", "TFN", False, pairs, canaries)
        with self.assertRaises(ValueError):
            s.beats("jev-1.14.0", "TFN", False, {"finbert": pairs["finbert"]}, canaries)

    def test_canary_failure_missing_report_and_harness_not_pooled(self):
        import jev_trading_scoring as s
        pairs = {b: {"status": "RAN", "macro_f1": {"low": 0.01, "high": 0.2},
                     "brier": {"low": -0.2, "high": 0.0}} for b in s.BASELINES["FOMC"]}
        for canaries in ({}, {"date_shift": {"status": "NOT_RUN"}, "entity_mask": {"status": "FAIL"}}):
            self.assertFalse(s.beats("jev-1.13.0", "FOMC", False, pairs, canaries)["beats"])
        sets = {name: {"beats": True, "ran_count": 1} for name in cases.LABELS}
        self.assertTrue(s.harness_beats(sets)["beats"])
        sets["TFN"]["beats"] = False
        self.assertFalse(s.harness_beats(sets)["beats"])
        with self.assertRaises(ValueError):
            s.harness_beats({"TFN": sets["TFN"]})
        sets["TFN"]["ran_count"] = 0
        self.assertTrue(s.harness_beats(sets)["beats"])
        for result in sets.values():
            result["ran_count"] = 0
        self.assertFalse(s.harness_beats(sets)["beats"])


class CanaryTests(unittest.TestCase):
    def test_date_subset_pins_and_measured_leftover_year_invariant(self):
        import jev_trading_canaries as c
        pack = cases.assemble("TFN", [], [cases.Case(0, "Jan. 5 2008", "neutral")])
        with self.assertRaisesRegex(ValueError, "subset id-list"):
            c.freeze_dates(pack, frozen=True)
        self.assertEqual(c.freeze_dates(pack, frozen=False)["shifted_matches"], 1)
        with mock.patch.object(c, "shift_dates", return_value={"matches": 1, "leftover_years": 1}):
            with self.assertRaisesRegex(ValueError, "left a year"):
                c.freeze_dates(pack, frozen=False)
        fomc = cases.assemble("FOMC", [], [cases.Case(0, "Jan. 5", "neutral")])
        with self.assertRaisesRegex(ValueError, "FOMC"):
            c.freeze_dates(fomc, frozen=True)

    def test_date_shift_worked_examples_preserve_form_and_guard_years(self):
        import jev_trading_canaries as c
        examples = {"31 March 2008": "29 March 2010", "March 23 , 2009": "March 21 , 2011",
            "5 Jan. 2008": "2 Jan. 2010", "Sept. 5 2008": "Sep. 3 2010",
            "29 February 2008": "26 February 2010", "Jan. 5": "Jan. 3", "1st April": "30th March",
            "31.12.2008": "29.12.2010", "3/15/2008": "3/13/2010",
            "March 1-31, 2008": "February 27-March 29, 2010",
            "January 1-5, 2008": "December 29, 2009-January 2, 2010",
            "March 3rd to 5th": "March 1st to 3rd"}
        for before, after in examples.items():
            with self.subTest(before=before):
                result = c.shift_dates(before)
                self.assertEqual(result["text"], after)
                self.assertEqual(result["shifted"], 1)
                self.assertEqual(result["leftover_years"], 0)
        for text in ("2026-02-31", "31.04.2008", "Feb 27-29 2007", "5 March. 2008", "3/5.2008", "29 February"):
            with self.subTest(text=text):
                self.assertEqual(c.shift_dates(text)["text"], text)
                self.assertEqual(c.shift_dates(text)["unchanged"], 1)
        for text in ("March 31, 2008", "Jan. 5, 2008", "$JD Jan 31 P", "12/10", "march 5"):
            self.assertEqual(c.shift_dates(text)["matches"], 0)
        self.assertEqual(hashlib.sha256(c.DATE_PATTERN.encode()).hexdigest(),
                         "4c708d21f7e2c866af594ff7fde7e7367c011b2283919f69ed031dd1974efcb2")

    def test_audit_exact_fixed_n_invalid_is_recovery(self):
        import jev_trading_canaries as c
        self.assertEqual(c.audit_result([True] * 32 + [False] * 249)["status"], "PASS")
        self.assertEqual(c.audit_result([True] * 32 + [None] + [False] * 248)["status"], "FAIL")
        self.assertEqual(c.audit_result([False] * 280)["status"], "NO_VERDICT")
        self.assertEqual(c.audit_result([False] * 282)["status"], "NO_VERDICT")


class BaselineTests(unittest.TestCase):
    def test_head_requires_all_classes_before_fit(self):
        import jev_trading_baselines as b
        pack = cases.assemble("TFN", [cases.Case(0, "first", "bearish"), cases.Case(1, "second", "bullish")], [])
        with self.assertRaisesRegex(ValueError, "all labels"):
            b.fit_head(pack, lambda texts: np.zeros((len(texts), 2048)))

    def test_native_factories_use_pinned_local_only_upstream_loaders(self):
        import jev_trading_baselines as b
        transformers = mock.Mock()
        model = transformers.AutoModelForSequenceClassification.from_pretrained.return_value.eval.return_value
        model.config.id2label = {0: "positive", 1: "negative", 2: "neutral"}
        sentence = mock.Mock()
        with mock.patch.dict(sys.modules, {"torch": mock.Mock(), "transformers": transformers,
                                           "sentence_transformers": sentence}):
            b.finbert_native()
            expected = {"revision": "0bc2ac10dda6", "local_files_only": True}
            transformers.AutoTokenizer.from_pretrained.assert_called_once_with("ProsusAI/finbert", **expected)
            transformers.AutoModelForSequenceClassification.from_pretrained.assert_called_once_with("ProsusAI/finbert", **expected)
            model.config.id2label = {0: "wrong"}
            with self.assertRaises(ValueError):
                b.finbert_native()
            b.nemotron_native("cpu")
            call = sentence.SentenceTransformer.call_args
            self.assertEqual(call.args, ("nvidia/Nemotron-3-Embed-1B-BF16",))
            self.assertEqual(call.kwargs["revision"], "c0c9fea93ea424587517f2c59e20db9f1d6bf615")
            self.assertTrue(call.kwargs["local_files_only"])

    def test_haiku_rejects_unfrozen_parameters_prices_and_invalid_usage(self):
        import jev_trading_baselines as b
        config = {"model": "claude-haiku-5-5", "workload": "synthetic-haiku", "pricing_sha256": "a" * 64,
            "credential_runner": True, "estimate_usd": 1.6608, "cap_usd": 3.3216,
            "input_per_million": 0.10, "output_per_million": 0.50,
            "parameters": {"temperature": 0, "max_tokens": 200}, "run_order": ["FPB-50/raw"]}
        for key, value in (("model", "alias"), ("credential_runner", False), ("workload", ""),
                           ("pricing_sha256", "bad"), ("run_order", []), ("cap_usd", 1),
                           ("input_per_million", -1), ("output_per_million", float("inf")),
                           ("parameters", {"max_tokens": 200}), ("parameters", {"temperature": 0, "max_tokens": 201}),
                           ("parameters", {"temperature": 0, "max_tokens": 200, "inference_geo": "us"})):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                b.HaikuBudget({**config, key: value})
        budget = b.HaikuBudget(config)
        with self.assertRaisesRegex(ValueError, "estimate"):
            b.HaikuBudget({**config, "estimate_usd": 2, "cap_usd": 4})
        with self.assertRaises(ValueError):
            budget.reserve(-1)
        self.assertTrue(budget.reserve(1000))
        with self.assertRaisesRegex(ValueError, "invalid usage"):
            budget.record(-1, 0)
        budget.unknown()
        self.assertTrue(budget.reserve(1000))
        with self.assertRaisesRegex(ValueError, "cap exceeded"):
            budget.record(40_000_000, 0)

    def test_finbert_mapping_and_fomc_refusal(self):
        import jev_trading_baselines as b
        result = b.finbert_prediction([0.6, 0.3, 0.1], "TFN")
        self.assertEqual(result.label, "bullish")
        self.assertEqual(result.probabilities, {"bearish": 0.3, "bullish": 0.6, "neutral": 0.1})
        with self.assertRaisesRegex(ValueError, "no FOMC label map"):
            b.finbert_prediction([0.6, 0.3, 0.1], "FOMC")

    def test_head_fits_raw_excluded_training_once_and_freezes_bytes(self):
        import jev_trading_baselines as b
        rows = [cases.Case(i, f"training {i}", cases.LABELS["TFN"][i % 3]) for i in range(9)]
        rows.append(cases.Case(9, "held out", "bearish"))
        pack = cases.assemble("TFN", rows, [cases.Case(0, "held out", "bullish")])
        seen = []
        def embed(texts):
            seen.append(texts)
            values = np.zeros((len(texts), 2048))
            for i in range(len(texts)):
                values[i, i % 3] = 1
            return values
        head = b.fit_head(pack, embed)
        self.assertNotIn("held out", seen[0])
        self.assertEqual(head.estimator.max_iter, 1000)
        self.assertEqual(head.estimator.random_state, 20261011)
        self.assertEqual(head.sha256, hashlib.sha256(head.artifact).hexdigest())
        head.predict(["raw"])
        head.predict(["masked"])
        self.assertEqual(len(seen), 3)
        with self.assertRaisesRegex(ValueError, "2048"):
            b.fit_head(pack, lambda texts: np.zeros((len(texts), 3)))

    def test_haiku_gate_cap_and_clm_gpu_boundary(self):
        import jev_trading_baselines as b
        with self.assertRaises(ValueError):
            b.HaikuBudget({})
        config = {"model": "claude-haiku-5-5", "workload": "synthetic-haiku",
                  "pricing_sha256": "a" * 64, "credential_runner": True,
                  "estimate_usd": 1.6608, "cap_usd": 3.3216,
                  "input_per_million": 0.10, "output_per_million": 0.50,
                  "parameters": {"temperature": 0, "max_tokens": 200},
                  "run_order": ["FPB-50/raw", "TFN/raw", "FOMC/raw"]}
        budget = b.HaikuBudget(config)
        self.assertTrue(budget.reserve(1000))
        budget.record(1000, 200)
        self.assertAlmostEqual(float(budget.spent), 0.0002)
        budget.spent = budget.cap
        self.assertFalse(budget.reserve(1000))
        self.assertEqual(b.clm_status(None)["status"], "NOT_RUN")
        self.assertEqual(b.clm_status("b" * 64)["status"], "READY")


class JevBudgetTests(unittest.TestCase):
    def test_preflight_checks_per_model_and_combined_bound(self):
        from jev_trading_budget import JevBudget
        models = ("jev-1.14.0", "jev-1.13.0")
        budget = JevBudget({m: 9204 for m in models}, max_attempts=5)
        self.assertEqual(budget.snapshot()["cap_usd"], "0.773136000")
        with self.assertRaisesRegex(ValueError, "preflight"):
            JevBudget({m: 9205 for m in models}, max_attempts=5)
        with self.assertRaises(ValueError):
            JevBudget({models[0]: 1}, max_attempts=5)

    def test_unknown_sdk_attempts_remain_reserved_until_cap_stop(self):
        from jev_trading_budget import JevBudget
        models = ("jev-1.14.0", "jev-1.13.0")
        budget = JevBudget({m: 100 for m in models}, max_attempts=5)
        calls = 0
        for _ in range(30):
            if not budget.reserve(models[0]):
                break
            calls += 1
            budget.unknown(models[0])
        self.assertEqual(calls, 28)
        report = budget.snapshot()
        self.assertLessEqual(float(report["upper_bound_usd"]), 0.773136)
        self.assertLessEqual(float(report["models"][models[0]]["upper_bound_usd"]), 0.386568)
        self.assertFalse(budget.reserve(models[0]))
        self.assertIsNone(report["usd"])

    def test_usage_and_retry_reconciliation_preserve_reservations(self):
        from jev_trading_budget import JevBudget
        models = ("jev-1.14.0", "jev-1.13.0")
        budget = JevBudget({m: 10 for m in models}, max_attempts=5)
        self.assertTrue(budget.reserve(models[0]))
        self.assertEqual(budget.record(models[0], 100, 2), "VALID")
        report = budget.snapshot()["models"][models[0]]
        self.assertEqual(report["known_input_tokens"], 100)
        self.assertEqual(report["reserved_input_tokens"], 2 * 65536)
        self.assertTrue(budget.reserve(models[0]))
        self.assertEqual(budget.record(models[0], 1001, 0), "TOKEN_BOUND_STOP")
        self.assertFalse(budget.reserve(models[0]))


class TransportTests(unittest.TestCase):
    def test_scored_rejects_changed_content_with_unchanged_ids(self):
        from dataclasses import replace
        import jev_trading_run as r
        packs = {name: cases.assemble(name, [cases.Case(i, f"training {name} {i}", label)
                 for i, label in enumerate(cases.LABELS[name])], pack.scored)
                 for name, pack in r.synthetic_sets().items()}
        frozen = {name: pack.manifest() for name, pack in packs.items()}
        ids = {name: {part: manifest["id_sha256"][part] for part in ("training", "final_training", "scored")}
               for name, manifest in frozen.items()}
        content = {name: manifest["content_sha256"] for name, manifest in frozen.items()}
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d, \
             mock.patch.dict(r.ID_PINS, ids, clear=True), \
             mock.patch.object(cases, "CONTENT_PINS", content, create=True), \
             mock.patch.object(r, "freeze_dates", return_value={}), mock.patch.object(r, "latency_sample", return_value=[]):
            path, _ = private_attestation_fixture(d)
            transport = mock.Mock(is_fake=False)
            r.preregistration(packs, "SCORED", transport, {}, path)
            for part in ("scored", "original_training", "training"):
                rows = getattr(packs["TFN"], part)
                for field in ("label", "text"):
                    replacement = ("bullish" if rows[0].label != "bullish" else "bearish") if field == "label" else rows[0].text + " changed"
                    changed_row = replace(rows[0], **{field: replacement})
                    changed_pack = replace(packs["TFN"], **{part: (changed_row,) + rows[1:]})
                    self.assertEqual(changed_pack.manifest()["id_sha256"], frozen["TFN"]["id_sha256"])
                    with self.subTest(part=part, field=field), self.assertRaisesRegex(ValueError, "content"):
                        r.preregistration({**packs, "TFN": changed_pack}, "SCORED", transport, {}, path)
            transport.evaluate.assert_not_called()

    def test_partial_receipt_keeps_haiku_exposure_after_two_completed_calls(self):
        from decimal import Decimal
        import jev_trading_run as r
        gate = {"model": "claude-haiku-5-5", "workload": "synthetic-partial-haiku", "pricing_sha256": "a" * 64,
            "credential_runner": True, "estimate_usd": "1.6608", "cap_usd": "3.3216",
            "input_per_million": "0.10", "output_per_million": "0.50",
            "parameters": {"temperature": 0, "max_tokens": 200}, "run_order": ["TFN/raw", "TFN/date_shift"]}
        for interruption in (KeyboardInterrupt, SystemExit):
            with self.subTest(interruption=interruption.__name__), tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
                calls = []
                def adapter(name, row):
                    calls.append(row.id)
                    if len(calls) == 3:
                        raise interruption()
                    return {"choice": "neutral", "probabilities": {label: 0.8 if label == "neutral" else 0.1 for label in cases.LABELS[name]},
                            "input_tokens": 100, "output_tokens": 10}
                adapter.token_bound = lambda name, row: 1000
                out = Path(d) / "partial"
                receipt = r.run(r.synthetic_sets(), out, r.FakeTransport(), evidence_class="SYN", command=["test"],
                    baseline_adapters={"haiku": adapter},
                    baseline_meta={"TFN": {"haiku": {"status": "RAN", "pin": r.PINS["haiku"], "gate": gate}}})
                self.assertEqual((receipt["status"], receipt["exit_code"], calls), ("PARTIAL", 1, [0, 1, 2]))
                self.assertFalse((out / "report.json").exists())
                journal = [json.loads(line) for line in (out / "calls.jsonl").read_text().splitlines()]
                self.assertEqual(sum(row["model"] == "haiku" for row in journal), 2)
                self.assertTrue("haiku_spend" in receipt, "partial receipt lost Haiku exposure")
                spend = receipt["haiku_spend"]
                self.assertEqual(spend["workload"], gate["workload"])
                self.assertEqual(Decimal(spend["known_usd"]), Decimal("0.00003"))
                self.assertEqual(Decimal(spend["reserved_usd"]), Decimal("0.0002"))
                self.assertEqual(Decimal(spend["upper_bound_usd"]), Decimal("0.00023"))
                self.assertEqual(Decimal(spend["cap_usd"]), Decimal("3.3216"))
                self.assertEqual(Decimal(spend["open_reservation_usd"]), Decimal("0.0002"))
                self.assertEqual(spend["uncertain_calls"], 1)
                self.assertTrue(spend["interrupted_call"])
                self.assertIsNone(spend["usd"])
                self.assertEqual(json.loads((out / "receipt.json").read_text())["haiku_spend"], spend)

    def test_failed_preflight_receipt_has_no_haiku_exposure(self):
        import jev_trading_run as r
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
            receipt = r.run({}, Path(d) / "failed", r.FakeTransport(), evidence_class="SYN", command=["test"])
            self.assertEqual(receipt["status"], "FAILED")
            self.assertEqual(receipt.get("haiku_spend"), {"status": "NOT_RUN"})

    def test_jev_retry_uncertainty_is_visible_in_each_arm_cost(self):
        import jev_trading_run as r
        from jev_trading_budget import JevBudget
        fake = r.FakeTransport()
        original = fake.evaluate
        def retried(request):
            return {**original(request), "_sdk_retry_count": 1}
        fake.evaluate = retried
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d, \
             mock.patch.object(r, "JevBudget", side_effect=lambda planned, **kw: JevBudget(planned, max_attempts=5)):
            out = Path(d) / "retried"
            r.run(r.synthetic_sets(), out, fake, evidence_class="SYN", command=["test"])
            report = json.loads((out / "report.json").read_text())
            self.assertIsNone(report["jev_spend"]["usd"])
            for sets in report["models"].values():
                for result in sets.values():
                    self.assertFalse(result["cost"]["usage_complete"])
                    self.assertIsNone(result["cost"]["usd"])
                    self.assertGreater(result["cost"]["known_input_tokens"], 0)

    def test_private_proof_requires_sdk_amendment_and_models_capture(self):
        from jev_trading_custody import verify_attestation
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as directory:
            path, proof = private_attestation_fixture(directory)
            for field in ("amendment", "wheel_sha256", "version"):
                changed = {**proof, "sdk": {key: value for key, value in proof["sdk"].items() if key != field}}
                path.write_text(json.dumps(changed))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    verify_attestation(path)

    def test_pending_sets_have_no_acquisition_or_admission(self):
        import jev_trading_run as r
        transport = mock.Mock(is_fake=True)
        result = r.preregistration(r.synthetic_sets(), "SYN", transport, {})
        self.assertEqual(set(result["case_sets"]), {"FPB-50", "TFN", "FOMC"})
        self.assertEqual(set(result["pending_sets"]), {"SEC-8K", "openFDA"})
        for row in result["pending_sets"].values():
            self.assertEqual(row["status"], "NOT_RUN")
            self.assertIn("clock", row["reason"])
        self.assertIn("Item 6.06", result["pending_sets"]["SEC-8K"]["reason"])
        self.assertEqual(result["entity_mask"]["status"], "NOT_RUN")
        self.assertEqual(result["audits"]["status"], "NOT_RUN")
        transport.evaluate.assert_not_called()

    def test_jev_usage_above_context_ceiling_stops_and_is_not_known_spend(self):
        import jev_trading_run as r
        fake = r.FakeTransport()
        original = fake.evaluate
        def over_ceiling(request):
            response = original(request)
            response["usage"]["input_tokens"] = 65537
            return response
        fake.evaluate = over_ceiling
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
            out = Path(d) / "jev-ceiling"
            receipt = r.run(r.synthetic_sets(), out, fake, evidence_class="SYN", command=["test"])
            self.assertEqual(len(fake.calls), 2)
            self.assertEqual(receipt["status"], "COMPLETE_WITH_FAILURES")
            report = json.loads((out / "report.json").read_text())
            self.assertIsNone(report["jev_spend"]["usd"])
            self.assertIsNone(report["jev_spend"]["upper_bound_usd"])
            self.assertEqual(report["jev_spend"]["known_input_tokens"], 0)
            for sets in report["models"].values():
                for result in sets.values():
                    self.assertEqual(result["cost"]["known_input_tokens"], 0)
            journal = [json.loads(line) for line in (out / "calls.jsonl").read_text().splitlines()]
            self.assertTrue(all(row["outcome"] in ("TOKEN_BOUND_STOP", "CAP_STOP") for row in journal))

    def test_unknown_haiku_usage_keeps_its_budget_reservation(self):
        # GPT full1's 619-call timeout witness, also exercised with malformed usage.
        from decimal import Decimal
        import jev_trading_run as r
        gate = {"model": "claude-haiku-5-5", "workload": "synthetic-review-budget", "pricing_sha256": "a" * 64,
            "credential_runner": True, "estimate_usd": "1.6608", "cap_usd": "3.3216",
            "input_per_million": "0.10", "output_per_million": "0.50",
            "parameters": {"temperature": 0, "max_tokens": 200},
            "run_order": ["FPB-50/raw", "TFN/raw", "TFN/date_shift", "FOMC/raw"]}
        packs = r.synthetic_sets()
        packs["FPB-50"] = cases.assemble("FPB-50", [], [
            cases.Case(i, f"Synthetic budget bulletin {i}.", cases.LABELS["FPB-50"][i % 3]) for i in range(600)])
        for mode in ("timeout", "malformed"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
                calls = []
                def unavailable(name, row):
                    calls.append((name, row.id))
                    if mode == "timeout":
                        raise TimeoutError("synthetic response unavailable after processing")
                    return {"input_tokens": "invalid", "output_tokens": 1}
                unavailable.token_bound = lambda name, row: 64000
                meta = {name: {"haiku": {"status": "RAN", "pin": "claude-haiku-5-5", "gate": gate}} for name in cases.LABELS}
                out = Path(d) / "run"
                r.run(packs, out, r.FakeTransport(), evidence_class="SYN", command=["synthetic-budget-probe"],
                      baseline_adapters={"haiku": unavailable}, baseline_meta=meta)
                report = json.loads((out / "report.json").read_text())
                admitted = len(calls) * Decimal("0.0065")
                self.assertLessEqual(admitted, Decimal(gate["cap_usd"]))
                self.assertEqual(len(calls), 511)
                self.assertEqual(Decimal(report["haiku_spend"]["reserved_usd"]), admitted)
                self.assertIsNone(report["haiku_spend"]["usd"])
                self.assertTrue(report["haiku_spend"]["stopped"])

    def test_model_minus_baseline_direction_is_preserved_by_run(self):
        import jev_trading_run as r
        class PerfectFake(r.FakeTransport):
            def evaluate(self, request):
                self.calls.append(request)
                labels = sorted(request["questions"]["label"]["criteria"])
                row_id = int(request["state"].split()[3].rstrip("."))
                chosen = labels[row_id % 3]
                return {"model": request["model"], "usage": {"input_tokens": 40, "output_tokens": 12},
                        "answers": {"label": {"type": "choice", "choice": chosen, "confidence": 1.0,
                            "probabilities": {label: float(label == chosen) for label in labels}}}}
        def baseline(name, row):
            return r.prediction({label: 1 / 3 for label in cases.LABELS[name]}, cases.LABELS[name])
        meta = {name: {"nemotron": {"status": "RAN", "pin": r.PINS["nemotron"]}} for name in cases.LABELS}
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
            out = Path(d) / "direction"
            result = r.run(r.synthetic_sets(), out, PerfectFake(), evidence_class="SYN", command=["test"],
                           baseline_adapters={"nemotron": baseline}, baseline_meta=meta)
            self.assertEqual(result["exit_code"], 0)
            report = json.loads((out / "report.json").read_text())
            for model in r.MODELS:
                for name in cases.LABELS:
                    pair = report["models"][model][name]["pairs"]["nemotron"]
                    self.assertAlmostEqual(pair["macro_f1"]["point"], 5 / 6)
                    self.assertAlmostEqual(pair["brier"]["point"], -2 / 3)
                    self.assertGreater(pair["macro_f1"]["low"], 0)
                    self.assertLess(pair["brier"]["high"], 0)

    def test_native_runner_parent_scope_is_checked_without_reading_any_store(self):
        import jev_trading_custody as custody
        source = custody.ROOT / "tools/credentials/credential_run.py"
        valid = ["python3", str(source), "typesafe", "--", "python3", "owning-scored-runner.py"]
        with mock.patch.object(custody.os, "environ", {"TYPESAFE_API_KEY": ""}), \
             mock.patch.object(custody, "_parent_processes", return_value=iter([(valid, custody.ROOT)])):
            custody.require_credential_run()
        for invalid in (["python3", str(source), "other", "--", "typesafe"],
                        ["python3", str(source), "typesafe", "--check"]):
            with mock.patch.object(custody.os, "environ", {"TYPESAFE_API_KEY": ""}), \
                 mock.patch.object(custody, "_parent_processes", return_value=iter([(invalid, custody.ROOT)])):
                with self.assertRaises(PermissionError):
                    custody.require_credential_run()

    def test_jev_token_bound_stops_later_calls_without_successful_scores(self):
        import jev_trading_run as r
        fake = r.FakeTransport()
        original = fake.evaluate
        def over_bound(request):
            response = original(request)
            response["usage"]["input_tokens"] = 1001
            return response
        fake.evaluate = over_bound
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
            out = Path(d) / "jev-bound"
            receipt = r.run(r.synthetic_sets(), out, fake, evidence_class="SYN", command=["test"])
            self.assertEqual(len(fake.calls), 2, "one over-bound response stops each model's remaining schedule")
            self.assertEqual(receipt["status"], "COMPLETE_WITH_FAILURES")
            report = json.loads((out / "report.json").read_text())
            self.assertLessEqual(float(report["jev_spend"]["upper_bound_usd"]), 0.773136)
            self.assertTrue(all(v["metrics"]["incomplete"] for sets in report["models"].values() for v in sets.values()))

    def test_private_attestation_is_verified_without_exporting_private_digests(self):
        import jev_trading_run as r
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
            root = Path(d)
            records = {}
            for name in ("addendum", "codex", "claude", "sdk_amendment", "models_page"):
                path = root / (name + ".md")
                path.write_text("private fixture " + name)
                records[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            proof = {"source_sha256": cases.SOURCE_PINS, "addendum": records["addendum"],
                     "two_family_reads": {name: records[name] for name in ("codex", "claude")},
                     "sdk": {"version": "0.7.2", "wheel_sha256": "0a961148187d52e18276ed7f2d02617cfac48e3b97673cb631a8749397d43d1e",
                             "amendment": records["sdk_amendment"]}, "models_page": records["models_page"]}
            spec = root / "private-preregistration.json"
            spec.write_text(json.dumps(proof))
            with mock.patch.object(r, "verify_lists"), mock.patch.object(r, "verify_content"), mock.patch.object(r, "freeze_dates", return_value={}), \
                 mock.patch.object(r, "latency_sample", return_value=[]):
                result = r.preregistration(r.synthetic_sets(), "SCORED", mock.Mock(is_fake=False), {}, spec)
                encoded = json.dumps(result)
                for record in records.values():
                    self.assertNotIn(record["sha256"], encoded)
                (root / "addendum.md").write_text("changed private bytes")
                with self.assertRaisesRegex(ValueError, "private record"):
                    r.preregistration(r.synthetic_sets(), "SCORED", mock.Mock(is_fake=False), {}, spec)

    def test_sdk_adapter_delegates_to_the_pinned_native_transport(self):
        import jev_trading_run as r
        request = r.jev_request("TFN", cases.Case(0, "synthetic", "neutral"), "jev-1.14.0")
        payload = r.FakeTransport().evaluate(request)
        with mock.patch.object(r, "require_credential_run"), \
             mock.patch.object(r, "_native_sdk_call", return_value=(payload, None, 0.1, 2)) as call:
            response = r.TypeSafeSDK().evaluate(request)
        call.assert_called_once_with(request)
        self.assertEqual(response["model"], "jev-1.14.0")
        self.assertEqual(response["_sdk_retry_count"], 2)

    def test_billable_haiku_failures_consume_reservations_before_dispatch(self):
        import jev_trading_run as r
        gate = {"model": "claude-haiku-5-5", "workload": "synthetic-haiku", "pricing_sha256": "a" * 64,
            "credential_runner": True, "estimate_usd": 1.6608, "cap_usd": 3.3216,
            "input_per_million": 0.10, "output_per_million": 0.50,
            "parameters": {"temperature": 0, "max_tokens": 200}, "run_order": ["TFN/raw", "TFN/date_shift"]}
        calls = []
        def timed_out(name, row):
            calls.append(row.id)
            raise TimeoutError("synthetic ambiguous billable failure")
        timed_out.token_bound = lambda name, row: 16_000_000
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
            receipt = r.run(r.synthetic_sets(), Path(d) / "reservation", r.FakeTransport(), evidence_class="SYN", command=["test"],
                baseline_adapters={"haiku": timed_out},
                baseline_meta={"TFN": {"haiku": {"status": "RAN", "pin": "claude-haiku-5-5", "gate": gate}}})
            self.assertEqual(receipt["status"], "COMPLETE_WITH_FAILURES")
            self.assertEqual(calls, [0, 1], "two uncertain charges exhaust the available third-call allowance")

    def test_haiku_first_cap_stop_latches_across_conditions_and_sets(self):
        import jev_trading_run as r
        gate = {"model": "claude-haiku-5-5", "workload": "synthetic-haiku", "pricing_sha256": "a" * 64,
            "credential_runner": True, "estimate_usd": 1.6608, "cap_usd": 3.3216,
            "input_per_million": 0.10, "output_per_million": 0.50,
            "parameters": {"temperature": 0, "max_tokens": 200},
            "run_order": ["FPB-50/raw", "FPB-50/date_shift", "TFN/raw", "TFN/date_shift", "FOMC/raw"]}
        called = []
        def adapter(name, row):
            called.append((name, row.id))
            return {"choice": "neutral", "probabilities": {label: 0.8 if label == "neutral" else 0.1 for label in cases.LABELS[name]},
                    "input_tokens": 100, "output_tokens": 10}
        adapter.token_bound = lambda name, row: 40_000_000 if name == "FPB-50" and row.id == 0 else 1000
        meta = {name: {"haiku": {"status": "RAN", "pin": "claude-haiku-5-5", "gate": gate}} for name in cases.LABELS}
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
            out = Path(d) / "latched"
            receipt = r.run(r.synthetic_sets(), out, r.FakeTransport(), evidence_class="SYN", command=["test"],
                            baseline_adapters={"haiku": adapter}, baseline_meta=meta)
            self.assertEqual(receipt["status"], "COMPLETE_WITH_FAILURES")
            self.assertEqual(called, [], "the first stopped row makes every later row uncalled")
            journal = [json.loads(line) for line in (out / "calls.jsonl").read_text().splitlines()]
            self.assertTrue(all(row["outcome"] == "CAP_STOP" for row in journal if row["model"] == "haiku"))

    def test_scored_start_outside_credential_runner_has_no_scored_receipt(self):
        import jev_trading_run as r
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d, mock.patch.object(r.os, "environ", {}):
            out = Path(d) / "unauthorized"
            fake = r.FakeTransport()
            with self.assertRaisesRegex(PermissionError, "credential_run"):
                r.run(r.synthetic_sets(), out, fake, evidence_class="SCORED", command=["test"])
            self.assertEqual(fake.calls, [])
            self.assertFalse(out.exists())

    def test_fake_haiku_gate_order_and_malformed_usage_are_retained_safely(self):
        import jev_trading_run as r
        gate = {"model": "claude-haiku-5-5", "workload": "synthetic-haiku", "pricing_sha256": "a" * 64,
            "credential_runner": True, "estimate_usd": 1.6608, "cap_usd": 3.3216,
            "input_per_million": 0.10, "output_per_million": 0.50,
            "parameters": {"temperature": 0, "max_tokens": 200},
            "run_order": ["FPB-50/raw", "FPB-50/date_shift", "TFN/raw", "TFN/date_shift", "FOMC/raw"]}
        seen = []
        def fake_haiku(name, row):
            seen.append((name, row.id))
            return {"choice": "neutral", "probabilities": {label: 0.8 if label == "neutral" else 0.1 for label in cases.LABELS[name]},
                    "input_tokens": "untrusted usage text" if len(seen) == 1 else 100, "output_tokens": 10}
        fake_haiku.token_bound = lambda name, row: 1000
        meta = {name: {"haiku": {"status": "RAN", "pin": "claude-haiku-5-5", "gate": gate}} for name in cases.LABELS}
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
            out = Path(d) / "haiku-fake"
            receipt = r.run(r.synthetic_sets(), out, r.FakeTransport(), evidence_class="SYN", command=["test"],
                            baseline_adapters={"haiku": fake_haiku}, baseline_meta=meta)
            self.assertEqual(receipt["status"], "COMPLETE_WITH_FAILURES")
            self.assertEqual(len(seen), 29)
            self.assertEqual(seen[:10], [("FPB-50", i) for i in range(9)] + [("FPB-50", 0)])
            self.assertNotIn("untrusted usage text", (out / "calls.jsonl").read_text())
            report = json.loads((out / "report.json").read_text())
            self.assertIsNone(report["haiku_spend"]["usd"])
            self.assertAlmostEqual(float(report["haiku_spend"]["known_usd"]), 28 * 0.000015)
            self.assertAlmostEqual(float(report["haiku_spend"]["reserved_usd"]), 0.0002)
            self.assertEqual(report["haiku_spend"]["uncertain_calls"], 1)
            self.assertEqual(report["models"]["jev-1.14.0"]["TFN"]["pairs"]["haiku"]["probability_comparison"],
                             "self-reported vs returned probabilities")

    def test_receipt_schema_rejects_missing_fields_states_and_commands(self):
        import jev_trading_run as r
        receipt = {"schema_version": 1, "kind": "run", "evidence_class": "SYN", "status": "FAILED",
                   "command": ["SYN-test"], "exit_code": 1, "input_sha256": {}, "output_sha256": {}}
        r.validate_receipt(receipt)
        for key, value in (("schema_version", 2), ("kind", "unknown"), ("evidence_class", "unknown"),
                           ("status", "unknown"), ("command", []), ("exit_code", "1")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                r.validate_receipt({**receipt, key: value})

    def test_http_invalid_model_stops_before_any_key_read_or_socket(self):
        import jev_trading_run as r
        with mock.patch.object(r.os, "environ", {}), mock.patch("socket.socket", side_effect=AssertionError("network forbidden")):
            with self.assertRaisesRegex(ValueError, "versioned Jev model"):
                r.TypeSafeSDK().evaluate({"model": "jev-latest"})

    def test_haiku_workload_config_cannot_change_between_sets(self):
        import jev_trading_run as r
        gate = {"model": "claude-haiku-5-5", "workload": "synthetic-haiku", "pricing_sha256": "a" * 64,
            "credential_runner": True, "estimate_usd": 1.6608, "cap_usd": 3.3216,
            "input_per_million": 0.10, "output_per_million": 0.50,
            "parameters": {"temperature": 0, "max_tokens": 200},
            "run_order": ["FPB-50/raw", "FPB-50/date_shift", "TFN/raw", "TFN/date_shift"]}
        adapter = mock.Mock()
        adapter.token_bound.return_value = 1000
        meta = {name: {"haiku": {"status": "RAN", "pin": "claude-haiku-5-5", "gate": {**gate, "workload": name}}}
                for name in ("FPB-50", "TFN")}
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
            fake = r.FakeTransport()
            receipt = r.run(r.synthetic_sets(), Path(d) / "different", fake, evidence_class="SYN", command=["test"],
                            baseline_adapters={"haiku": adapter}, baseline_meta=meta)
            self.assertEqual(receipt["status"], "FAILED")
            self.assertEqual(fake.calls, [])
            adapter.assert_not_called()

    def test_haiku_declared_order_must_equal_actual_order_before_calls(self):
        import jev_trading_run as r
        gate = {"model": "claude-haiku-5-5", "workload": "synthetic-haiku", "pricing_sha256": "a" * 64,
            "credential_runner": True, "estimate_usd": 1.6608, "cap_usd": 3.3216,
            "input_per_million": 0.10, "output_per_million": 0.50,
            "parameters": {"temperature": 0, "max_tokens": 200}, "run_order": ["TFN/raw"]}
        adapter = mock.Mock()
        adapter.token_bound.return_value = 1000
        meta = {"TFN": {"haiku": {"status": "RAN", "pin": "claude-haiku-5-5", "gate": gate}}}
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
            fake = r.FakeTransport()
            receipt = r.run(r.synthetic_sets(), Path(d) / "wrong-order", fake, evidence_class="SYN", command=["test"],
                            baseline_adapters={"haiku": adapter}, baseline_meta=meta)
            self.assertEqual(receipt["status"], "FAILED")
            self.assertEqual(fake.calls, [])
            adapter.assert_not_called()

    def test_http_contract_has_only_standard_headers_and_no_alias(self):
        # The selected SDK owns its headers. This checks the adopted transport
        # seam without creating a client, reading a key, or opening a socket.
        tree = ast.parse((P1 / "jev_trading_run.py").read_text())
        self.assertFalse(any(isinstance(node, ast.ImportFrom) and (node.module or "").startswith("urllib")
                             for node in ast.walk(tree)))
        source = P1.parents[2] / "tools/sota-convergence/gap_crosswalk.py"
        vendor = ast.parse(source.read_text())
        call = next(node for node in vendor.body if isinstance(node, ast.FunctionDef) and node.name == "call")
        policy = next(node for node in ast.walk(call) if isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Name) and node.func.id == "RetryPolicy")
        values = {keyword.arg: ast.literal_eval(keyword.value) for keyword in policy.keywords}
        self.assertEqual(values["max_retries"], 4)
        self.assertEqual(values["http_statuses"], {429, 529})
        self.assertFalse(values["api_connection_error"])
        self.assertFalse(values["api_timeout_error"])
        client = next(node for node in ast.walk(call) if isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Name) and node.func.id == "TypeSafeClient")
        self.assertNotIn("headers", {keyword.arg for keyword in client.keywords})

    def test_scored_preregistration_guards_without_invoking_any_transport(self):
        import jev_trading_run as r
        packs = r.synthetic_sets()
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as directory, \
             mock.patch.object(r, "verify_lists"), mock.patch.object(r, "verify_content"), mock.patch.object(r, "freeze_dates", return_value={}), \
             mock.patch.object(r, "latency_sample", return_value=[]):
            path, proof = private_attestation_fixture(directory)
            transport = mock.Mock(is_fake=False)
            r.preregistration(packs, "SCORED", transport, {}, path)
            for key, value in (("addendum", {}), ("source_sha256", {}), ("two_family_reads", {}),
                               ("sdk", {}), ("models_page", {})):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    path.write_text(json.dumps({**proof, key: value}))
                    r.preregistration(packs, "SCORED", transport, {}, path)
            path.write_text(json.dumps(proof))
            for meta in ({"TFN": {"nemotron": {"status": "RAN", "pin": "bad", "head_sha256": "f" * 64}}},
                         {"TFN": {"nemotron": {"status": "RAN", "pin": r.PINS["nemotron"]}}},
                         {"TFN": {"clm-8b": {"status": "RAN", "pin": r.PINS["clm-8b"]}}},
                         {"TFN": {"haiku": {"status": "RAN", "pin": r.PINS["haiku"]}}},
                         {"TFN": {"finbert": {"status": "NOT_RUN"}}}):
                with self.subTest(meta=meta), self.assertRaises(ValueError):
                    r.preregistration(packs, "SCORED", transport, meta, path)
            with self.assertRaises(ValueError):
                r.preregistration(packs, "SYN", transport, {})
            with self.assertRaises(ValueError):
                r.preregistration(packs, "SCORED", r.FakeTransport(), {}, path)
            with self.assertRaises(ValueError):
                r.preregistration({"TFN": packs["TFN"]}, "SCORED", transport, {}, path)
            transport.evaluate.assert_not_called()

    def test_partial_receipt_preserves_collision_and_existing_empty_directory(self):
        import jev_trading_run as r
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
            existing = Path(d) / "existing"
            existing.mkdir()
            fake = r.FakeTransport()
            with self.assertRaises(FileExistsError):
                r.run(r.synthetic_sets(), existing, fake, evidence_class="SYN", command=["test"])
            self.assertEqual(fake.calls, [])
            out = Path(d) / "collision"
            original = fake.evaluate
            def collision(request):
                (out / "report.json").write_text("preserve this peer artifact")
                return original(request)
            fake.evaluate = collision
            receipt = r.run(r.synthetic_sets(), out, fake, evidence_class="SYN", command=["test"])
            self.assertEqual(receipt["status"], "PARTIAL")
            self.assertEqual((out / "report.json").read_text(), "preserve this peer artifact")

    def test_response_shapes_usage_and_safe_error_retention(self):
        import jev_trading_run as r
        request = r.jev_request("TFN", cases.Case(0, "synthetic", "neutral"), "jev-1.14.0")
        base = r.FakeTransport().evaluate(request)
        for changed in (None, {**base, "answers": {}}, {**base, "usage": {"input_tokens": -1}},
                        {**base, "answers": {"label": {"type": "refusal"}}}):
            self.assertIsNone(r.parse_response(changed, "jev-1.14.0", "TFN")[0])
        invalid_choice = json.loads(json.dumps(base))
        invalid_choice["answers"]["label"]["choice"] = "outside"
        self.assertEqual(r.parse_response(invalid_choice, "jev-1.14.0", "TFN")[1], "MALFORMED")
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
            fake = r.FakeTransport()
            fake.evaluate = mock.Mock(side_effect=RuntimeError("untrusted detail must not be retained"))
            out = Path(d) / "errors"
            receipt = r.run(r.synthetic_sets(), out, fake, evidence_class="SYN", command=["test"])
            self.assertEqual(receipt["status"], "COMPLETE_WITH_FAILURES")
            self.assertNotIn("untrusted detail", "".join(p.read_text() for p in out.iterdir()))
            report = json.loads((out / "report.json").read_text())
            self.assertFalse(report["harness_beats"]["jev-1.14.0"]["beats"])
            self.assertEqual(report["models"]["jev-1.14.0"]["TFN"]["metrics"]["failures"], 9)

    def test_latency_nearest_rank_sample_and_cost_oracle(self):
        import jev_trading_run as r
        report = r.latency_report(list(range(1, 301)))
        self.assertEqual([report["milliseconds"][key]["point"] for key in ("p50", "p95", "p99")], [150, 285, 297])
        pack = cases.assemble("TFN", [], [cases.Case(i, f"row {i}", "neutral") for i in range(350)])
        self.assertEqual(r.latency_sample(pack), np.random.default_rng(20261011).choice(350, 300, replace=False).tolist())
        self.assertEqual(str(9204 * 1000 * r.PRICE_PER_TOKEN), "0.386568000")
        with self.assertRaisesRegex(ValueError, "requires 300"):
            r.latency_sample(r.synthetic_sets()["TFN"])
        with self.assertRaises(ValueError):
            r.latency_report([float("nan")])

    def test_request_version_options_and_response_mismatch_fail_closed(self):
        import jev_trading_run as r
        row = cases.Case(0, "synthetic bulletin", "neutral")
        request = r.jev_request("TFN", row, "jev-1.14.0")
        self.assertEqual(list(request["questions"]["label"]["criteria"]), ["bearish", "neutral", "bullish"])
        self.assertEqual(list(json.loads(r.wire_bytes(request))["questions"]["label"]["criteria"]),
                         ["bearish", "neutral", "bullish"])
        with self.assertRaises(ValueError):
            r.jev_request("TFN", row, "jev-latest")
        transport = r.FakeTransport()
        response = transport.evaluate(request)
        self.assertIsNotNone(r.parse_response(response, "jev-1.14.0", "TFN")[0])
        response["model"] = "jev-1.13.0"
        parsed, status = r.parse_response(response, "jev-1.14.0", "TFN")
        self.assertIsNone(parsed)
        self.assertEqual(status, "MODEL_MISMATCH")
        response["model"] = "jev-1.14.0"
        response["answers"]["label"]["probabilities"]["bearish"] = float("nan")
        self.assertEqual(r.parse_response(response, "jev-1.14.0", "TFN")[1], "MALFORMED")

    def test_syn_preregistration_precedes_every_call_and_both_models_share_requests(self):
        import jev_trading_run as r
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
            out = Path(d) / "run"
            fake = r.FakeTransport()
            original = fake.evaluate
            def checked(request):
                self.assertTrue((out / "preregistration.json").is_file())
                return original(request)
            fake.evaluate = checked
            with mock.patch("socket.socket", side_effect=AssertionError("network forbidden")):
                receipt = r.run(r.synthetic_sets(), out, fake, evidence_class="SYN", command=["SYN-test"])
            self.assertEqual(receipt["exit_code"], 0)
            self.assertEqual(receipt["evidence_class"], "SYN")
            r.validate_receipt(receipt)
            report = json.loads((out / "report.json").read_text())
            self.assertEqual(set(report["models"]), {"jev-1.14.0", "jev-1.13.0"})
            self.assertEqual(set(report["model_parity"]), set(cases.LABELS))
            self.assertTrue(all(p["reported_only"] for p in report["model_parity"].values()))
            grouped = {model: [dict(q, model="same") for q in fake.calls if q["model"] == model]
                       for model in r.MODELS}
            self.assertEqual(grouped[r.MODELS[0]], grouped[r.MODELS[1]])
            for path, pin in receipt["output_sha256"].items():
                self.assertEqual(hashlib.sha256((out / path).read_bytes()).hexdigest(), pin)
            before = (out / "receipt.json").read_bytes()
            calls = [json.loads(line) for line in (out / "calls.jsonl").read_text().splitlines()]
            for call in calls:
                self.assertEqual(hashlib.sha256(call["request_wire"].encode()).hexdigest(), call["request_sha256"])
                self.assertEqual(list(json.loads(call["request_wire"])["questions"]["label"]["criteria"]),
                                 cases.option_order(call["set"], call["id"]))
            with self.assertRaises(FileExistsError):
                r.run(r.synthetic_sets(), out, fake, evidence_class="SYN", command=["rerun"])
            self.assertEqual((out / "receipt.json").read_bytes(), before)

    def test_missing_baseline_adapter_is_rejected_before_calls(self):
        import jev_trading_run as r
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
            fake = r.FakeTransport()
            result = r.run(r.synthetic_sets(), Path(d) / "bad", fake, evidence_class="SYN", command=["test"],
                           baseline_meta={"TFN": {"nemotron": {"status": "RAN", "pin": r.PINS["nemotron"]}}})
            self.assertEqual(result["exit_code"], 1)
            self.assertEqual(fake.calls, [])

    def test_changed_preregistration_stops_before_the_next_call(self):
        import jev_trading_run as r
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
            out = Path(d) / "mutated"
            fake = r.FakeTransport()
            original = fake.evaluate
            def change(request):
                response = original(request)
                (out / "preregistration.json").write_text("{}\n")
                return response
            fake.evaluate = change
            result = r.run(r.synthetic_sets(), out, fake, evidence_class="SYN", command=["test"])
            self.assertEqual(result["status"], "PARTIAL")
            self.assertEqual(len(fake.calls), 1)

    def test_invalid_registration_no_calls_and_partial_run_retained(self):
        import jev_trading_run as r
        with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-test-") as d:
            fake = r.FakeTransport()
            result = r.run(r.synthetic_sets(), Path(d) / "bad", fake, evidence_class="SYN", command=["test"],
                           baseline_meta={"TFN": {"finbert": {"status": "NOT_RUN"}}})
            self.assertEqual(result["exit_code"], 1)
            self.assertEqual(fake.calls, [])
            self.assertEqual(result["status"], "FAILED")
            def interrupted(request):
                raise KeyboardInterrupt()
            fake.evaluate = interrupted
            partial = r.run(r.synthetic_sets(), Path(d) / "partial", fake, evidence_class="SYN", command=["test"])
            self.assertEqual(partial["status"], "PARTIAL")
            self.assertTrue((Path(d) / "partial/preregistration.json").exists())
            self.assertTrue((Path(d) / "partial/receipt.json").exists())
            with self.assertRaises(ValueError):
                r.validate_receipt({**partial, "output_sha256": {"x": "not-a-digest"}})


class SourceEvidenceTests(unittest.TestCase):
    def test_metric_source_citations_reference_implementations(self):
        root = P1.parents[2]
        source = json.loads((root / "evidence/artifacts/jev-trading-build-20261015/source-review.json").read_text())
        for name, filename in (("f1_score", "_classification.py"), ("brier_score_loss", "_classification.py"),
                               ("train_test_split", "_split.py"), ("bootstrap", "_resampling.py")):
            with self.subTest(name=name):
                self.assertEqual(source["installed_sources"][name]["file"], filename)


if __name__ == "__main__":
    unittest.main()
