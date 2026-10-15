"""Named, isolated guard mutations. CPython unittest + bubblewrap; no live writes.

Each mutant is mounted over ONE source file in its own child mount namespace.
The host source is hashed before/after, and scratch is removed per mutant. A
syntax/import failure is an invalid campaign result, not a killed guard.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

P1 = Path(__file__).resolve().parent
ROOT = P1.parents[2]

# id, module suffix, exact old text, replacement, named public-contract test
MUTANTS = [
    ("dependency_pin", "cases", "if installed != DEPENDENCIES:", "if False:", "CaseTests.test_builder_requires_the_record_source_pins_and_library_versions"),
    ("source_bytes", "cases", "if sha256(data) != pin:", "if False:", "CaseTests.test_source_pin_rejects_changed_bytes_before_decode"),
    ("source_role_pins", "cases", 'if set(sources) != set(SOURCE_PINS) or any(sources[k]["sha256"] != v for k, v in SOURCE_PINS.items()):', "if False:", "CaseTests.test_builder_requires_the_record_source_pins_and_library_versions"),
    ("unicode_whitespace", "cases", 'return " ".join(text.split())', 'return " ".join(text.replace("\\u00a0", "_").split())', "CaseTests.test_unicode_exclusion_and_frozen_lists_fail_closed"),
    ("content_exclusion", "cases", 'final = [r for r in training if canonical(r.text) not in scored_text]', 'final = list(training)', "CaseTests.test_unicode_exclusion_and_frozen_lists_fail_closed"),
    ("frozen_lists", "cases", 'if set(pins) != {"training", "final_training", "scored"} or any(actual[k] != v for k, v in pins.items()):', "if False:", "CaseTests.test_unicode_exclusion_and_frozen_lists_fail_closed"),
    ("option_seed", "cases", "SEED = 20261011", "SEED = 20261012", "CaseTests.test_option_order_matches_record_and_duplicates_stay"),
    ("probability_labels", "scoring", 'if not isinstance(probabilities, dict) or set(probabilities) != set(labels):', "if False:", "MetricsTests.test_probability_validation_and_exact_one_percent_boundary"),
    ("probability_domain", "scoring", 'if any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1 for p in values):', "if False:", "MetricsTests.test_probability_validation_and_exact_one_percent_boundary"),
    ("probability_sum", "scoring", "if abs(sum(values) - 1.0) > 1e-6:", "if False:", "MetricsTests.test_probability_validation_and_exact_one_percent_boundary"),
    ("probability_choice", "scoring", 'if choice is not None and (choice not in labels or probabilities[choice] != probabilities[best]):', "if False:", "TransportTests.test_response_shapes_usage_and_safe_error_retention"),
    ("tie_order", "scoring", "best = max(labels, key=probabilities.__getitem__)", "best = max(reversed(labels), key=probabilities.__getitem__)", "MetricsTests.test_probability_validation_and_exact_one_percent_boundary"),
    ("brier_scaling", "scoring", "scale_by_half=False", "scale_by_half=True", "MetricsTests.test_record_worked_example_and_failure_inclusive_population"),
    ("ece_not_confidence", "scoring", 'expected_calibration_error(proba.max(axis=1), np.array(labels)[proba.argmax(axis=1)] == np.asarray(truth))', 'expected_calibration_error((3 * proba.max(axis=1) - 1) / 2, np.array(labels)[proba.argmax(axis=1)] == np.asarray(truth))', "MetricsTests.test_record_worked_example_and_failure_inclusive_population"),
    ("sentinel_miss", "scoring", 'else "__MISSING__" for r in pack.scored]', 'else r.label for r in pack.scored]', "MetricsTests.test_record_worked_example_and_failure_inclusive_population"),
    ("incomplete_boundary", "scoring", '"incomplete": failures / n > 0.01', '"incomplete": failures / n >= 0.01', "MetricsTests.test_probability_validation_and_exact_one_percent_boundary"),
    ("bootstrap_clusters", "scoring", 'groups = [g for g in groups if g]', 'groups = [[i] for i in range(len(shared))]', "MetricsTests.test_cluster_intervals_match_independent_sklearn_resampling"),
    ("original_representatives", "scoring", 'representatives = [g[0] for g in original_groups if g[0] in shared_ids]', 'representatives = [g[0] for g in clusters(shared)]', "MetricsTests.test_cluster_bootstrap_call_and_representative_no_substitution"),
    ("bootstrap_paired", "scoring", 'statistic, paired=True,', 'statistic, paired=False,', "MetricsTests.test_cluster_bootstrap_call_and_representative_no_substitution"),
    ("bootstrap_method", "scoring", 'method="percentile", n_resamples=10000', 'method="basic", n_resamples=10000', "MetricsTests.test_cluster_bootstrap_call_and_representative_no_substitution"),
    ("bootstrap_draws", "scoring", 'n_resamples=10000,', 'n_resamples=9999,', "MetricsTests.test_cluster_bootstrap_call_and_representative_no_substitution"),
    ("bootstrap_seed", "scoring", 'rng=np.random.default_rng(SEED)', 'rng=np.random.default_rng(SEED + 1)', "MetricsTests.test_cluster_bootstrap_call_and_representative_no_substitution"),
    ("beats_model", "scoring", 'if model not in MODELS or name not in BASELINES:', 'if False:', "BeatsTests.test_all_pairs_subset_not_run_and_interval_boundaries"),
    ("beats_pair_coverage", "scoring", 'if set(pairs) != set(BASELINES[name]):', 'if False:', "BeatsTests.test_all_pairs_subset_not_run_and_interval_boundaries"),
    ("beats_incomplete", "scoring", 'if incomplete:', 'if False:', "BeatsTests.test_all_pairs_subset_not_run_and_interval_boundaries"),
    ("beats_no_pairs", "scoring", 'if not ran:', 'if False:', "BeatsTests.test_all_pairs_subset_not_run_and_interval_boundaries"),
    ("beats_strict_f1", "scoring", 'return low > 0 if f1 else high <= 0', 'return low >= 0 if f1 else high <= 0', "BeatsTests.test_all_pairs_subset_not_run_and_interval_boundaries"),
    ("beats_brier_upper", "scoring", 'return low > 0 if f1 else high <= 0', 'return low > 0 if f1 else high <= 0.01', "BeatsTests.test_all_pairs_subset_not_run_and_interval_boundaries"),
    ("beats_canary", "scoring", 'if status not in {"PASS", "COUNTS_ONLY", "NOT_RUN", "NOT_APPLIED"}:', 'if status not in {"PASS", "COUNTS_ONLY", "NOT_RUN", "NOT_APPLIED", "FAIL"}:', "BeatsTests.test_canary_failure_missing_report_and_harness_not_pooled"),
    ("harness_conjunction", "scoring", 'and all(sets[name]["beats"] for name in applicable)', 'and any(sets[name]["beats"] for name in applicable)', "BeatsTests.test_canary_failure_missing_report_and_harness_not_pooled"),
    ("date_casefold", "canaries", 'DATE_REGEX = re.compile(DATE_PATTERN)', 'DATE_REGEX = re.compile(DATE_PATTERN, re.IGNORECASE)', "CanaryTests.test_date_shift_worked_examples_preserve_form_and_guard_years"),
    ("date_offset", "canaries", 'first = date(year, month, day) + timedelta(days=728)', 'first = date(year, month, day) + timedelta(days=729)', "CanaryTests.test_date_shift_worked_examples_preserve_form_and_guard_years"),
    ("date_mixed_separators", "canaries", 'if sep != other:', 'if False:', "CanaryTests.test_date_shift_worked_examples_preserve_form_and_guard_years"),
    ("date_option_contract", "canaries", 'if re.search(r"\\$[A-Za-z][A-Za-z.]{0,9}\\s+$", text[:match.start()]) and re.match(r"\\s+[PC]\\b", text[match.end():]):', 'if False:', "CanaryTests.test_date_shift_worked_examples_preserve_form_and_guard_years"),
    ("date_year_guard", "canaries", 'if re.match(r"\\W{0,4}(?:19|20)\\d{2}\\b", text[end:]):', 'if False:', "CanaryTests.test_date_shift_worked_examples_preserve_form_and_guard_years"),
    ("date_subset_pin", "canaries", 'if frozen and pack.name in DATE_ID_PINS and digest != DATE_ID_PINS[pack.name]:', 'if False:', "CanaryTests.test_date_subset_pins_and_measured_leftover_year_invariant"),
    ("date_fomc_empty", "canaries", 'if frozen and pack.name == "FOMC" and selected:', 'if False:', "CanaryTests.test_date_subset_pins_and_measured_leftover_year_invariant"),
    ("date_freeze_guard", "canaries", 'if any(row["leftover_years"] for row in selected.values()):', 'if False:', "CanaryTests.test_date_subset_pins_and_measured_leftover_year_invariant"),
    ("audit_fixed_n", "canaries", 'if n != 281:', 'if n < 281:', "CanaryTests.test_audit_exact_fixed_n_invalid_is_recovery"),
    ("audit_invalid_recovery", "canaries", 'count = sum(value is not False for value in recovered)', 'count = sum(value is True for value in recovered)', "CanaryTests.test_audit_exact_fixed_n_invalid_is_recovery"),
    ("audit_margin", "canaries", '"PASS" if upper < 0.15 else "FAIL"', '"PASS" if upper < 0.20 else "FAIL"', "CanaryTests.test_audit_exact_fixed_n_invalid_is_recovery"),
    ("finbert_fomc", "baselines", 'if name not in ("FPB-50", "TFN"):', 'if False:', "BaselineTests.test_finbert_mapping_and_fomc_refusal"),
    ("finbert_mapping", "baselines", 'positive, negative, neutral = map(float, probabilities)', 'negative, positive, neutral = map(float, probabilities)', "BaselineTests.test_finbert_mapping_and_fomc_refusal"),
    ("finbert_offline", "baselines", 'kwargs = {"revision": PINS["finbert"], "local_files_only": True}', 'kwargs = {"revision": PINS["finbert"], "local_files_only": False}', "BaselineTests.test_native_factories_use_pinned_local_only_upstream_loaders"),
    ("nemotron_dimensions", "baselines", 'if values.shape != (len(texts), 2048) or not np.isfinite(values).all():', 'if False:', "BaselineTests.test_head_fits_raw_excluded_training_once_and_freezes_bytes"),
    ("head_raw_training", "baselines", 'values = _embeddings(embed, [r.text for r in pack.training])', 'values = _embeddings(embed, [r.text for r in pack.original_training])', "BaselineTests.test_head_fits_raw_excluded_training_once_and_freezes_bytes"),
    ("head_parameters", "baselines", 'LogisticRegression(max_iter=1000, random_state=SEED)', 'LogisticRegression(max_iter=100, random_state=SEED)', "BaselineTests.test_head_fits_raw_excluded_training_once_and_freezes_bytes"),
    ("haiku_parameters", "baselines", 'if "temperature" not in params or params.get("max_tokens") != 200 or "inference_geo" in params:', 'if False:', "BaselineTests.test_haiku_rejects_unfrozen_parameters_prices_and_invalid_usage"),
    ("haiku_cap", "baselines", 'if actual > reserved or self.spent + self.reserved > self.cap:', 'if False:', "BaselineTests.test_haiku_rejects_unfrozen_parameters_prices_and_invalid_usage"),
    ("haiku_reservation", "baselines", 'self.spent + self.reserved + cost > self.cap', 'False', "BaselineTests.test_haiku_gate_cap_and_clm_gpu_boundary"),
    ("model_request", "run", 'if model not in MODELS:', 'if False:', "TransportTests.test_request_version_options_and_response_mismatch_fail_closed"),
    ("model_response", "run", 'if response.get("model") != model:', 'if False:', "TransportTests.test_request_version_options_and_response_mismatch_fail_closed"),
    ("wire_option_order", "run", 'json.dumps(value, separators=(",", ":"), ensure_ascii=False, allow_nan=False)', 'json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)', "TransportTests.test_request_version_options_and_response_mismatch_fail_closed"),
    ("sdk_native_seam", "run", 'retries = _native_sdk_call(request)', 'retries = _native_sdk_call({**request, "model": "jev-latest"})', "TransportTests.test_sdk_adapter_delegates_to_the_pinned_native_transport"),
    ("syn_fake_only", "run", 'if (evidence_class == "SYN") != (getattr(transport, "is_fake", None) is True):', 'if False:', "TransportTests.test_scored_preregistration_guards_without_invoking_any_transport"),
    ("scored_source_authority", "custody", 'if document.get("source_sha256") != SOURCE_PINS:', 'if False:', "TransportTests.test_scored_preregistration_guards_without_invoking_any_transport"),
    ("scored_two_family_reads", "custody", 'if not isinstance(reviews, dict) or set(reviews) != {"codex", "claude"}:', 'if False:', "TransportTests.test_scored_preregistration_guards_without_invoking_any_transport"),
    ("scored_sdk_amendment", "custody", 'amendment = _verified_record(sdk.get("amendment"))', 'amendment = {}', "TransportTests.test_private_proof_requires_sdk_amendment_and_models_capture"),
    ("scored_models_capture", "custody", 'models = _verified_record(document.get("models_page"))', 'models = {}', "TransportTests.test_scored_preregistration_guards_without_invoking_any_transport"),
    ("baseline_pin", "run", 'if row.get("pin") != PINS[arm]:', 'if False:', "TransportTests.test_scored_preregistration_guards_without_invoking_any_transport"),
    ("head_freeze", "run", 'if evidence_class == "SCORED" and arm == "nemotron" and not _digest(row.get("head_sha256")):', 'if False:', "TransportTests.test_scored_preregistration_guards_without_invoking_any_transport"),
    ("baseline_preflight", "run", 'raise ValueError("baseline adapter missing before first call")', 'pass', "TransportTests.test_missing_baseline_adapter_is_rejected_before_calls"),
    ("preregistration_integrity", "run", 'raise ValueError("preregistration changed after freeze")', 'pass', "TransportTests.test_changed_preregistration_stops_before_the_next_call"),
    ("no_reuse_directory", "run", 'output_dir.mkdir(parents=True, exist_ok=False)', 'output_dir.mkdir(parents=True, exist_ok=True)', "TransportTests.test_partial_receipt_preserves_collision_and_existing_empty_directory"),
    ("exclusive_artifacts", "run", 'with path.open("xb") as stream:', 'with path.open("wb") as stream:', "TransportTests.test_partial_receipt_preserves_collision_and_existing_empty_directory"),
    ("receipt_hash_schema", "run", 'if not isinstance(receipt[key], dict) or not all(_digest(v) for v in receipt[key].values()):', 'if False:', "TransportTests.test_invalid_registration_no_calls_and_partial_run_retained"),
    ("case_row_validation", "cases", 'raise ValueError("invalid case rows")', 'pass', "CaseTests.test_duplicate_ids_unknown_labels_and_empty_text_rejected"),
    ("finbert_config", "baselines", 'if {int(k): v for k, v in model.config.id2label.items()} != {0: "positive", 1: "negative", 2: "neutral"}:', 'if False:', "BaselineTests.test_native_factories_use_pinned_local_only_upstream_loaders"),
    ("head_all_labels", "baselines", 'if set(r.label for r in pack.training) != set(LABELS[pack.name]):', 'if False:', "BaselineTests.test_head_requires_all_classes_before_fit"),
    ("haiku_required_gate", "baselines", 'if not required <= config.keys() or config["model"] != PINS["haiku"] or config["credential_runner"] is not True:', 'if False:', "BaselineTests.test_haiku_rejects_unfrozen_parameters_prices_and_invalid_usage"),
    ("haiku_workload_pricing", "baselines", 'if not config["workload"] or not config["run_order"] or not re.fullmatch(r"[0-9a-f]{64}", config["pricing_sha256"]):', 'if False:', "BaselineTests.test_haiku_rejects_unfrozen_parameters_prices_and_invalid_usage"),
    ("haiku_estimate_cap", "baselines", 'if not all(x.is_finite() and x > 0 for x in (self.cap, estimate, self.input_rate, self.output_rate)) or self.cap != 2 * estimate:', 'if False:', "BaselineTests.test_haiku_rejects_unfrozen_parameters_prices_and_invalid_usage"),
    ("haiku_bound_nonnegative", "baselines", 'if type(input_token_upper_bound) is not int or input_token_upper_bound < 0:', 'if False:', "BaselineTests.test_haiku_rejects_unfrozen_parameters_prices_and_invalid_usage"),
    ("haiku_usage_nonnegative", "baselines", 'if any(type(x) is not int or x < 0 for x in (input_tokens, output_tokens)):', 'if False:', "BaselineTests.test_haiku_rejects_unfrozen_parameters_prices_and_invalid_usage"),
    ("empty_metric_population", "scoring", 'if not n:', 'if False:', "MetricsTests.test_empty_scored_population_rejected"),
    ("harness_all_sets", "scoring", 'if set(sets) != set(LABELS):', 'if False:', "BeatsTests.test_canary_failure_missing_report_and_harness_not_pooled"),
    ("latency_minimum", "run", 'if len(ids) < size:', 'if False:', "TransportTests.test_latency_nearest_rank_sample_and_cost_oracle"),
    ("latency_valid_values", "run", 'if not np.isfinite(values).all() or (values < 0).any():', 'if False:', "TransportTests.test_latency_nearest_rank_sample_and_cost_oracle"),
    ("preregistration_shape", "run", 'if set(packs) != set(LABELS) or evidence_class not in {"SYN", "SCORED"}:', 'if False:', "TransportTests.test_scored_preregistration_guards_without_invoking_any_transport"),
    ("receipt_required", "run", 'if not required <= receipt.keys() or receipt["schema_version"] != 1 or receipt["kind"] != "run":', 'if False:', "TransportTests.test_receipt_schema_rejects_missing_fields_states_and_commands"),
    ("receipt_state", "run", 'if receipt["evidence_class"] not in {"SYN", "SCORED"} or receipt["status"] not in {"COMPLETE", "COMPLETE_WITH_FAILURES", "FAILED", "PARTIAL"}:', 'if False:', "TransportTests.test_receipt_schema_rejects_missing_fields_states_and_commands"),
    ("receipt_command_exit", "run", 'if type(receipt["exit_code"]) is not int or not isinstance(receipt["command"], list) or not receipt["command"]:', 'if False:', "TransportTests.test_receipt_schema_rejects_missing_fields_states_and_commands"),
    ("http_model_guard", "run", 'if request.get("model") not in MODELS:', 'if False:', "TransportTests.test_http_invalid_model_stops_before_any_key_read_or_socket"),
    ("haiku_shared_workload", "run", 'if haiku_configs and any(config != haiku_configs[0] for config in haiku_configs):', 'if False:', "TransportTests.test_haiku_workload_config_cannot_change_between_sets"),
    ("clm_gpu_window", "run", 'if arm == "clm-8b" and clm_status(row.get("gpu_window_sha256"))["status"] != "READY":', 'if False:', "TransportTests.test_scored_preregistration_guards_without_invoking_any_transport"),
    ("baseline_not_run_reason", "run", 'elif row["status"] != "NOT_RUN" or not row.get("reason"):', 'elif False:', "TransportTests.test_scored_preregistration_guards_without_invoking_any_transport"),
    ("haiku_estimate_arithmetic", "baselines", 'if estimate != 8304 * (1000 * self.input_rate + 200 * self.output_rate):', 'if False:', "BaselineTests.test_haiku_rejects_unfrozen_parameters_prices_and_invalid_usage"),
    ("haiku_frozen_run_order", "run", 'if haiku_configs and haiku_configs[0]["run_order"] != haiku_order:', 'if False:', "TransportTests.test_haiku_declared_order_must_equal_actual_order_before_calls"),
    ("ordered_arm_diagnostic", "scoring", 'if ordered_options else {"status": "NOT_APPLICABLE"}', 'if True else {"status": "NOT_APPLICABLE"}', "MetricsTests.test_unordered_baseline_has_no_first_position_diagnostic"),
    ("haiku_usage_mask", "run", 'usage = _masked_response({"usage": answer}, name)["usage"]', 'usage = {key: answer[key] for key in ("input_tokens", "output_tokens")}', "TransportTests.test_fake_haiku_gate_order_and_malformed_usage_are_retained_safely"),
    ("ece_tied_label_point", "scoring", 'np.array(labels)[proba.argmax(axis=1)] == np.asarray(truth)', 'np.asarray(predicted) == np.asarray(truth)', "MetricsTests.test_ece_uses_frozen_sorted_argmax_on_a_tie"),
    ("ece_tied_label_bootstrap", "scoring", '(p.argmax(axis=1) == y)[:, None]', '(chosen == y)[:, None]', "MetricsTests.test_paired_ece_interval_uses_frozen_sorted_argmax"),
    ("model_minus_baseline", "run", 'paired_metrics(pack, all_raw[model][name], baseline_outputs[b])', 'paired_metrics(pack, baseline_outputs[b], all_raw[model][name])', "TransportTests.test_model_minus_baseline_direction_is_preserved_by_run"),
    ("finbert_current_prefix", "baselines", '"finbert": "0bc2ac10dda6"', '"finbert": "4556d13015211d73dccd3fdd39d39232506f3e43"', "BaselineTests.test_native_factories_use_pinned_local_only_upstream_loaders"),
    ("haiku_reserve_before_dispatch", "baselines", 'self.reserved += cost', 'self.reserved += 0', "TransportTests.test_unknown_haiku_usage_keeps_its_budget_reservation"),
    ("haiku_unknown_not_refunded", "baselines", 'self.uncertain_calls += 1', 'self.reserved -= self.active_reservation\n            self.uncertain_calls += 1', "TransportTests.test_unknown_haiku_usage_keeps_its_budget_reservation"),
    ("haiku_sticky_stop", "baselines", 'if self.stopped or self.spent + self.reserved + cost > self.cap:', 'if self.spent + self.reserved + cost > self.cap:', "TransportTests.test_haiku_first_cap_stop_latches_across_conditions_and_sets"),
    ("jev_planning_bound", "budget", 'estimates = {model: n * ASSUMED_INPUT_TOKENS for model, n in planned_calls.items()}', 'estimates = {model: 0 for model in planned_calls}', "JevBudgetTests.test_preflight_checks_per_model_and_combined_bound"),
    ("jev_reserve_before_dispatch", "budget", 'self.held[model] += amount', 'self.held[model] += 0', "JevBudgetTests.test_unknown_sdk_attempts_remain_reserved_until_cap_stop"),
    ("jev_retry_reservation", "budget", 'self.held[model] += retries * CONTEXT_TOKEN_CEILING', 'self.held[model] += 0', "JevBudgetTests.test_usage_and_retry_reconciliation_preserve_reservations"),
    ("jev_token_stop", "budget", 'if input_tokens > ASSUMED_INPUT_TOKENS:', 'if False:', "TransportTests.test_jev_token_bound_stops_later_calls_without_successful_scores"),
    ("jev_ceiling_stop", "budget", 'if type(input_tokens) is int and input_tokens > CONTEXT_TOKEN_CEILING:', 'if False:', "TransportTests.test_jev_usage_above_context_ceiling_stops_and_is_not_known_spend"),
    ("private_record_bytes", "custody", 'if hashlib.sha256(data).hexdigest() != record["sha256"]:', 'if False:', "TransportTests.test_private_attestation_is_verified_without_exporting_private_digests"),
    ("private_record_projection", "custody", 'return {"path": reference, "verified": True}', 'return {"path": reference, "verified": True, "sha256": record["sha256"]}', "TransportTests.test_private_attestation_is_verified_without_exporting_private_digests"),
    ("native_runner_entry", "custody", 'if request and request[0] == "typesafe" and not request[2] and request[3]:', 'if request:', "TransportTests.test_native_runner_parent_scope_is_checked_without_reading_any_store"),
    ("native_start_before_receipt", "run", 'require_credential_run()\n        transport.prepare()', 'transport.prepare()', "TransportTests.test_scored_start_outside_credential_runner_has_no_scored_receipt"),
    ("pending_sec_rules", "baselines", 'return {"status": "NOT_RUN", "reason": "8-K predicates, Item 6.06 tests, code hash and acquisition clock are not frozen"}', 'return {"status": "RAN", "reason": "acquisition clock"}', "TransportTests.test_pending_sets_have_no_acquisition_or_admission"),
    ("jev_arm_retry_accounting", "run", 'unresolved_retries += retries', 'unresolved_retries += 0', "TransportTests.test_jev_retry_uncertainty_is_visible_in_each_arm_cost"),
    ("scored_content_before_dispatch", "run", '            verify_content(pack)', '            pass', "TransportTests.test_scored_rejects_changed_content_with_unchanged_ids"),
    ("frozen_training_content", "cases", 'pack.manifest()["content_sha256"] != CONTENT_PINS[pack.name]', 'pack.manifest()["content_sha256"]["scored"] != CONTENT_PINS[pack.name]["scored"]', "TransportTests.test_scored_rejects_changed_content_with_unchanged_ids"),
    ("partial_haiku_receipt", "run", '"haiku_spend": haiku_budget.snapshot() if haiku_budget else {"status": "NOT_RUN"}', '"haiku_spend": {"status": "NOT_RUN"}', "TransportTests.test_partial_receipt_keeps_haiku_exposure_after_two_completed_calls"),
    ("partial_haiku_reserved", "baselines", '"reserved_usd": str(self.reserved)', '"reserved_usd": "0"', "TransportTests.test_partial_receipt_keeps_haiku_exposure_after_two_completed_calls"),
    ("partial_haiku_uncertain", "baselines", 'self.uncertain_calls + int(active)', 'self.uncertain_calls', "TransportTests.test_partial_receipt_keeps_haiku_exposure_after_two_completed_calls"),
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run_one(mutant):
    name, module, old, new, test = mutant
    source = P1 / f"jev_trading_{module}.py"
    before = source.read_bytes()
    text = before.decode()
    count = text.count(old)
    # The integrity guard is deliberately applied to both Jev and baseline calls.
    expected_count = 2 if name == "preregistration_integrity" else 1
    if count != expected_count:
        return {"id": name, "status": "INVALID", "occurrences": count, "test": test}
    variant = text.replace(old, new)
    with tempfile.TemporaryDirectory(dir="/var/tmp", prefix="jev-mutant-") as scratch:
        path = Path(scratch) / source.name
        path.write_text(variant)
        command = ["bwrap", "--ro-bind", "/", "/", "--ro-bind", str(path), str(source),
                   "--bind", scratch, "/var/tmp", "--dev", "/dev", "--proc", "/proc", "--unshare-net",
                   "--die-with-parent", "--setenv", "TMPDIR", "/var/tmp", sys.executable, "-B", "-m", "unittest",
                   "tests.test_jev_trading." + test]
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
        output = (process.stdout + process.stderr).replace(str(ROOT), "<REPO>").replace(str(Path.home()), "<HOME>")
    preserved = source.read_bytes() == before
    invalid = any(error in output for error in ("SyntaxError", "ImportError", "ModuleNotFoundError", "_FailedTest"))
    killed = process.returncode != 0 and "FAILED (" in output and not invalid and preserved
    return {"id": name, "module": source.name, "test": "tests.test_jev_trading." + test,
            "status": "KILLED" if killed else "INVALID" if invalid else "SURVIVED", "exit_code": process.returncode,
            "source_sha256": digest(before), "mutant_sha256": digest(variant.encode()),
            "live_source_unchanged": preserved,
            "failure_tail": output[-1800:] if not killed else None}


def main():
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run_one, MUTANTS))
    document = {"schema_version": 1, "evidence_class": "SYN", "kind": "guard_mutations",
                "isolation": "bwrap: live root read-only; network namespace; private /var/tmp removed per mutant",
                "count": len(results), "killed": sum(r["status"] == "KILLED" for r in results), "mutants": results}
    print(json.dumps(document, indent=2))
    return 0 if document["killed"] == document["count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
