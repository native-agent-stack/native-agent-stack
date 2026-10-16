"""Fixed-date policy fixtures; no model, credential or network operation."""

import copy
import hashlib
import json
import os
from datetime import date
from pathlib import Path
import subprocess
import sys
import unittest

from scripts.validate import model_currency_problems

if __package__:
    from . import test_validate as publication_fixtures
else:
    import test_validate as publication_fixtures


TODAY = date(2026, 10, 7)


def inventory():
    return {
        "schema_version": 1, "inventory_status": "complete",
        "policy": {"max_release_age_days": 42, "max_landscape_age_days": 7, "refresh_lead_days": 2},
        "packages": [],
        "models": [{"id": "reader", "role": "document reading", "consumer": "native fixture",
                    "model_id": "vendor/model", "revision": "a" * 40,
                    "release_date": "2026-10-01", "release_source": "https://huggingface.co/vendor/model/commit/" + "a" * 40,
                    "checked_at": "2026-10-07", "status": "in_use",
                    "release_line": {"kind": "huggingface", "repository": "vendor/model", "ref": "main"}}],
    }


def landscape():
    return {"date": "2026-10-01", "sources": ["https://example.org/vendor/release"],
            "newer_candidates": [{"model_id": "vendor/new", "revision": "b" * 40,
                                  "source": "https://example.org/vendor/new", "reason": "Incompatible upstream package contract."}],
            "reason": "The supported upstream consumer does not yet qualify this replacement."}


def package_bound_inventory():
    data = inventory()
    data["packages"] = [{"id": "reader-tool", "latest_version": "4.0.10", "release_date": "2026-10-01",
                         "release_source": "https://pypi.org/project/reader-tool/4.0.10/", "checked_at": "2026-10-07",
                         "release_line": {"kind": "pypi", "package": "reader-tool"}}]
    data["models"][0].update(status="package_bound", release_date="2025-01-01",
                             package={"id": "reader-tool", "version": "4.0.10"})
    return data


class ModelCurrencyTests(unittest.TestCase):
    def test_user_guide_matches_report_only_age_policy(self):
        root = Path(__file__).resolve().parents[1]
        guide = (root / "docs/model-currency.md").read_text()
        self.assertTrue("model_currency_notices" in guide, "Document the publication maintenance report.")
        self.assertTrue("models_past_window" in guide, "Document the persisted daily age count.")
        self.assertTrue("2026-10-16-model-route-currency-consistency.md" in guide, "Link the reporting supersession.")
        self.assertFalse("A release more than 42 days old fails" in guide, "Remove the superseded age-failure claim.")
        self.assertFalse("an older release fails\non day eight" in guide, "Day eight is maintenance, not a publication failure.")

    def test_background_haiku_is_a_current_normal_refresh_proposal(self):
        path = Path(__file__).resolve().parents[1] / "catalogs/foundation/model-currency.json"
        row = next(model for model in json.loads(path.read_text())["models"] if model["id"] == "background-haiku")
        self.assertEqual(row["model_id"], "claude-haiku-5-5")
        self.assertEqual(row["revision"], "claude-haiku-5-5")
        self.assertEqual(row["status"], "held")
        self.assertIn("normal refresh", row["consumer"])
        self.assertIn("No runtime configuration", row["consumer"])

    def test_background_refresh_retains_primary_source_and_measured_boundary(self):
        path = Path(__file__).resolve().parents[1] / "catalogs/foundation/model-currency.json"
        row = next(model for model in json.loads(path.read_text())["models"] if model["id"] == "background-haiku")
        self.assertEqual(row["release_date"], "2026-10-07")
        self.assertEqual(row["release_source"],
                         "https://platform.claude.com/docs/en/release-notes/overview#october-7-2026")
        self.assertIn("not a measured reason", row["landscape_check"]["reason"])
        self.assertIn("normal refresh", row["landscape_check"]["reason"])
        self.assertEqual(row["landscape_check"]["newer_candidates"], [])

    def assert_valid(self, document):
        self.assertEqual(model_currency_problems(document, TODAY), [])

    def assert_invalid(self, document, needle):
        self.assertTrue(any(needle in e for e in model_currency_problems(document, TODAY)))

    def test_fresh_and_exact_42_day_boundary_pass(self):
        data = inventory()
        self.assert_valid(data)
        data["models"][0]["release_date"] = "2026-08-26"
        self.assert_valid(data)

    def test_stale_without_landscape_fails(self):
        data = inventory()
        data["models"][0]["release_date"] = "2026-08-25"
        self.assert_invalid(data, "older than 42")

    def test_fresh_sourced_exception_and_seven_day_boundary_pass(self):
        data = inventory()
        row = data["models"][0]
        row.update(release_date="2026-08-01", landscape_check=landscape(), overturn="Consumer qualifies a current candidate.")
        self.assert_valid(data)
        row["landscape_check"]["date"] = "2026-09-30"
        self.assert_valid(data)

    def test_expired_exception_fails(self):
        data = inventory()
        row = data["models"][0]
        row.update(release_date="2026-08-01", landscape_check=landscape(), overturn="Upstream qualifies replacement.")
        row["landscape_check"]["date"] = "2026-09-29"
        self.assert_invalid(data, "within 7 days")

    def test_exception_needs_sources_reason_candidates_and_overturn(self):
        for field in ("sources", "reason", "newer_candidates"):
            with self.subTest(field=field):
                data = inventory()
                data["models"][0].update(release_date="2026-08-01", landscape_check=landscape(), overturn="A qualified replacement.")
                del data["models"][0]["landscape_check"][field]
                self.assertTrue(model_currency_problems(data, TODAY))
        data["models"][0]["landscape_check"] = landscape()
        del data["models"][0]["overturn"]
        self.assert_invalid(data, "overturn")

    def test_package_bound_joins_latest_package_and_uses_package_release(self):
        data = package_bound_inventory()
        row = data["models"][0]
        self.assert_valid(data)
        row["package"]["version"] = "4.0.9"
        self.assert_invalid(data, "recorded latest")
        row["package"] = {"id": "absent", "version": "4.0.10"}
        self.assert_invalid(data, "join a package")

    def test_package_bound_hub_model_keeps_exact_origin_revision(self):
        data = package_bound_inventory()
        self.assert_valid(data)
        data["models"][0]["revision"] = "main"
        self.assert_invalid(data, "exact Hugging Face commit SHA")

    def test_package_bound_model_requires_its_origin_release_line(self):
        data = package_bound_inventory()
        self.assert_valid(data)
        del data["models"][0]["release_line"]
        self.assert_invalid(data, "release_line")

    def test_old_shipping_package_also_requires_exception(self):
        data = inventory()
        data["packages"] = [{"id": "tool", "latest_version": "1", "release_date": "2026-08-01",
                             "release_source": "https://example.org/release", "checked_at": "2026-10-07",
                             "release_line": {"kind": "github_release", "repository": "vendor/tool"}}]
        data["models"][0].update(status="package_bound", package={"id": "tool", "version": "1"})
        self.assert_invalid(data, "older than 42")

    def test_malformed_dates_and_missing_source_fail(self):
        for field, value in (("release_date", "2026-02-30"), ("checked_at", "today"), ("release_date", "20261001"),
                             ("release_source", None), ("release_source", "not-a-url")):
            with self.subTest(field=field, value=value):
                data = inventory()
                data["models"][0][field] = value
                self.assertTrue(model_currency_problems(data, TODAY))

    def test_future_dates_unknown_status_and_nonexact_hf_revision_fail(self):
        for field, value in (("release_date", "2026-10-08"), ("status", "pending"), ("status", {}), ("revision", "main")):
            data = inventory()
            data["models"][0][field] = value
            self.assertTrue(model_currency_problems(data, TODAY))

    def test_pending_empty_scaffold_is_not_a_complete_inventory(self):
        data = inventory()
        data.update(models=[], inventory_status="pending")
        self.assert_valid(data)
        data["inventory_status"] = "complete"
        self.assert_invalid(data, "complete inventory")

    def test_latest_hub_line_cannot_be_an_immutable_pin_or_tag(self):
        for ref in ("a" * 40, "v1.0.0"):
            with self.subTest(ref=ref):
                data = inventory()
                data["models"][0]["release_line"]["ref"] = ref
                self.assert_invalid(data, "default main branch")

    def test_policy_cannot_relax_limits_and_duplicate_ids_fail(self):
        data = inventory()
        data["policy"]["max_release_age_days"] = 180
        self.assert_invalid(data, "policy")
        data = inventory()
        data["models"].append(copy.deepcopy(data["models"][0]))
        self.assert_invalid(data, "duplicate id")

    def test_misspelled_extra_fields_fail_at_every_inventory_object_level(self):
        cases = (
            ((), "schema_verion"),
            (("policy",), "refresh_leed_days"),
            (("packages", 0), "latest_verion"),
            (("models", 0), "landscape_chek"),
            (("models", 0, "package"), "verion"),
            (("models", 0, "landscape_check"), "newer_canddates"),
            (("models", 0, "landscape_check", "newer_candidates", 0), "reasion"),
        )
        for path, typo in cases:
            with self.subTest(path=path, typo=typo):
                data = package_bound_inventory()
                data["models"][0].update(landscape_check=landscape(), overturn="Upstream qualifies a replacement.")
                self.assert_valid(data)
                target = data
                for key in path:
                    target = target[key]
                target[typo] = "unrecognized"
                self.assert_invalid(data, typo)

    def test_release_line_kinds_accept_known_fields_and_reject_extra_fields(self):
        lines = (
            {"kind": "huggingface", "repository": "vendor/model", "ref": "main"},
            {"kind": "github_release", "repository": "vendor/tool"},
            {"kind": "pypi", "package": "reader-tool"},
            {"kind": "vendor_page", "url": "https://example.org/releases"},
        )
        for line in lines:
            for parent_path in (("packages", 0), ("models", 0)):
                with self.subTest(kind=line["kind"], parent_path=parent_path):
                    data = package_bound_inventory()
                    target = data[parent_path[0]][parent_path[1]]
                    target["release_line"] = copy.deepcopy(line)
                    self.assert_valid(data)
                    target["release_line"]["unrecognized_line_field"] = "typo"
                    self.assert_invalid(data, "unrecognized_line_field")

    def test_valid_https_sources_include_ipv6_ports_and_encoded_space(self):
        urls = (
            "https://example.org/release",
            "https://example.org:443/release",
            "https://example.org:8443/release?version=1.2#notes",
            "https://[2001:db8::1]/release",
            "https://[::1]:8443/release",
            "https://example.org/release?name=encoded%20space",
        )
        for url in urls:
            with self.subTest(url=url):
                data = package_bound_inventory()
                row = data["models"][0]
                row.update(landscape_check=landscape(), overturn="Upstream qualifies a replacement.")
                row["release_source"] = url
                data["packages"][0]["release_source"] = url
                row["landscape_check"]["sources"] = [url]
                row["landscape_check"]["newer_candidates"][0]["source"] = url
                row["release_line"] = {"kind": "vendor_page", "url": url}
                self.assert_valid(data)

    def test_malformed_https_authorities_whitespace_and_controls_fail_for_each_source(self):
        urls = (
            "https://example.org:not-a-port/release",
            "https://example.org:65536/release",
            "https://example.org:-1/release",
            "https://exa mple.org/release",
            "https://example.org/re lease",
            "https://example.org/\trelease",
            "https://example.org/\nrelease",
            "https://example.org/\x00release",
            "https://example.org/\x1frelease",
            "https://example.org/\x7frelease",
            "https://example.org/\x80release",
            "https://example.org/\u00a0release",
            "https://[::1]:not-a-port/release",
        )
        paths = (
            ("models", 0, "release_source"),
            ("packages", 0, "release_source"),
            ("models", 0, "landscape_check", "sources", 0),
            ("models", 0, "landscape_check", "newer_candidates", 0, "source"),
            ("models", 0, "release_line", "url"),
        )
        for url in urls:
            for path in paths:
                with self.subTest(url=url, path=path):
                    data = package_bound_inventory()
                    data["models"][0].update(landscape_check=landscape(), overturn="Upstream qualifies a replacement.")
                    data["models"][0]["release_line"] = {"kind": "vendor_page", "url": "https://example.org/releases"}
                    self.assert_valid(data)
                    target = data
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = url
                    self.assert_invalid(data, "HTTPS source URL")

    def test_stale_exception_cannot_be_qualified_by_a_malformed_landscape_source(self):
        for url in ("https://example.org:not-a-port/release", "https://exa mple.org/release"):
            with self.subTest(url=url):
                data = inventory()
                data["models"][0].update(release_date="2026-08-01", landscape_check=landscape(),
                                         overturn="Consumer qualifies a current candidate.")
                self.assert_valid(data)
                data["models"][0]["landscape_check"]["sources"] = [url]
                self.assert_invalid(data, "HTTPS source URL")

    def test_schema_closes_complete_objects_and_retains_model_origin_requirement(self):
        path = Path(__file__).resolve().parents[1] / "catalogs/foundation/model-currency.schema.json"
        schema = json.loads(path.read_text())
        model_schema = schema["properties"]["models"]["items"]
        objects = (
            (schema, {"schema_version", "inventory_status", "policy", "packages", "models"}),
            (schema["properties"]["policy"], {"max_release_age_days", "max_landscape_age_days", "refresh_lead_days"}),
            (schema["properties"]["packages"]["items"],
             {"id", "latest_version", "release_date", "release_source", "checked_at", "release_line"}),
            (model_schema, {"id", "role", "consumer", "model_id", "revision", "release_date", "release_source",
                            "checked_at", "status", "release_line", "package", "landscape_check", "overturn"}),
            (model_schema["properties"]["package"], {"id", "version"}),
            (model_schema["properties"]["landscape_check"], {"date", "sources", "newer_candidates", "reason"}),
            (model_schema["properties"]["landscape_check"]["properties"]["newer_candidates"]["items"],
             {"model_id", "revision", "source", "reason"}),
        )
        for object_schema, keys in objects:
            with self.subTest(keys=keys):
                self.assertEqual(object_schema["type"], "object")
                self.assertIs(object_schema.get("additionalProperties"), False)
                self.assertEqual(set(object_schema["properties"]), keys)
        line_keys = {
            "huggingface": {"kind", "repository", "ref"},
            "github_release": {"kind", "repository"},
            "pypi": {"kind", "package"},
            "vendor_page": {"kind", "url"},
        }
        for object_schema in schema["$defs"]["release_line"]["oneOf"]:
            kind = object_schema["properties"]["kind"]["const"]
            with self.subTest(kind=kind):
                self.assertIs(object_schema.get("additionalProperties"), False)
                self.assertEqual(set(object_schema["properties"]), line_keys[kind])
        self.assertIn("release_line", model_schema["required"])

    def test_daily_shape_check_can_report_stale_rows_without_hiding_invalid_source(self):
        data = inventory()
        data["models"][0]["release_date"] = "2026-08-01"
        self.assertEqual(model_currency_problems(data, TODAY, enforce_age=False), [])
        data["models"][0]["release_source"] = None
        self.assertTrue(model_currency_problems(data, TODAY, enforce_age=False))

    def test_publication_reports_inventory_age_but_rejects_invalid_dates(self):
        fixture = publication_fixtures.PublicationValidationTests(methodName="runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        data = inventory()
        data["models"][0]["release_date"] = "2026-08-25"
        path = "catalogs/foundation/model-currency.json"
        fixture.write_json(path, data)
        content = (fixture.root / path).read_bytes()
        fixture.evidence["files"].append({"path": path, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
        fixture.save()
        script = Path(__file__).resolve().parents[1] / "scripts/validate.py"
        step_summary = fixture.root / "step-summary.md"
        step_summary.write_text("Existing summary\n")
        result = subprocess.run([sys.executable, str(script), "--root", str(fixture.root), "--today", "2026-10-07"],
                                capture_output=True, text=True,
                                env={**os.environ, "GITHUB_STEP_SUMMARY": str(step_summary)})
        self.assertEqual(result.returncode, 0, result.stdout)
        summary = json.loads(result.stdout.splitlines()[0])
        self.assertTrue(any("older than 42" in notice for notice in summary["model_currency_notices"]))
        self.assertTrue(step_summary.is_file(), "Stale findings must remain visible in the CI step summary.")
        self.assertIn("model currency model reader", step_summary.read_text())
        self.assertIn("older than 42", step_summary.read_text())
        self.assertTrue(step_summary.read_text().startswith("Existing summary\n"))
        result = subprocess.run([sys.executable, str(script), "--root", str(fixture.root), "--today", "2026-09-01"],
                                capture_output=True, text=True)
        # A past clock cannot silently accept future checked_at or release evidence.
        self.assertEqual(result.returncode, 1)
        self.assertIn("future date", result.stdout)


class ModelRouteCurrencyTests(unittest.TestCase):
    """Exercise the publication CLI: broken joins fail, freshness is a notice."""

    def setUp(self):
        self.fixture = publication_fixtures.PublicationValidationTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.write_registered("catalogs/foundation/model-currency.json", inventory())
        self.write_registered("catalogs/landscape/angles/foundation-model-routes.json", {
            "schema_version": 1, "candidates": [{"id": "test-route", "pin": "vendor/model"}],
        })

    def write_registered(self, path, value):
        self.fixture.write_json(path, value)
        raw = (self.fixture.root / path).read_bytes()
        self.fixture.evidence["files"] = [row for row in self.fixture.evidence["files"] if row["path"] != path]
        self.fixture.evidence["files"].append({
            "path": path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
        })
        self.fixture.save()

    def run_validator(self):
        script = Path(__file__).resolve().parents[1] / "scripts/validate.py"
        return subprocess.run([sys.executable, str(script), "--root", str(self.fixture.root),
                               "--today", "2026-10-07"], capture_output=True, text=True)

    def bind_routes(self, rows):
        self.write_registered("catalogs/foundation/model-route-bindings.json", {"schema_version": 1, "routes": rows})

    def write_c2(self, proposed, routes):
        root = "evidence/artifacts/model-routes-sweep-merge-20261015/"
        self.write_registered(root + "returns.json", {"discovery": {"model-routes": {"proposed": proposed}}})
        self.write_registered(root + "route-currency.json", {"schema_version": 1, "routes": routes})

    def test_duplicate_route_binding_is_rejected(self):
        row = {"route_id": "test-route", "model_currency_id": "reader"}
        self.bind_routes([row, row])
        result = self.run_validator()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("duplicate route binding", result.stdout)

    def test_duplicate_source_route_is_rejected(self):
        self.bind_routes([{"route_id": "test-route", "model_currency_id": "reader"}])
        row = {"id": "test-route", "pin": "vendor/model"}
        self.write_registered("catalogs/landscape/angles/foundation-model-routes.json", {
            "schema_version": 1, "candidates": [row, row],
        })
        result = self.run_validator()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("duplicate route test-route", result.stdout)

    def test_duplicate_c2_repository_is_rejected(self):
        self.bind_routes([{"route_id": identifier, "model_currency_id": "reader"}
                          for identifier in ("test-route", "merged-one", "merged-two")])
        repository = "https://example.org/model#route"
        self.write_c2([repository], [{"repository": repository, "route_id": identifier,
                                     "model_id": "vendor/model", "model_currency_id": "reader"}
                                    for identifier in ("merged-one", "merged-two")])
        result = self.run_validator()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("C2 repositories must be nonempty and unique", result.stdout)

    def test_gpt_manifest_requires_exactly_one_target_layer(self):
        self.bind_routes([{"route_id": "test-route", "model_currency_id": "reader"}])
        source = "evidence/artifacts/model-routes-sweep-20261015/sweep-manifest.json"
        layer = {"catalog": "foundation", "layer_id": "model-routes", "candidates": [
            {"candidate_id": "test-route", "model": "vendor/model"},
        ]}
        for layers in ([], [layer, layer]):
            with self.subTest(layer_count=len(layers)):
                self.write_registered(source, {"schema_version": 1, "layers": layers})
                result = self.run_validator()
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("exactly one foundation/model-routes layer", result.stdout)

    def test_malformed_binding_rows_fail_without_a_traceback(self):
        for row in (None, [], "not-an-object"):
            with self.subTest(row_type=type(row).__name__):
                self.bind_routes([row])
                result = self.run_validator()
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("expected route objects", result.stdout)
                self.assertNotIn("Traceback", result.stderr)

    def test_malformed_source_rows_fail_without_a_traceback(self):
        self.bind_routes([{"route_id": "test-route", "model_currency_id": "reader"}])
        for row in (None, [], "not-an-object"):
            with self.subTest(row_type=type(row).__name__):
                self.write_registered("catalogs/landscape/angles/foundation-model-routes.json", {
                    "schema_version": 1, "candidates": [row],
                })
                result = self.run_validator()
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("expected route objects", result.stdout)
                self.assertNotIn("Traceback", result.stderr)

    def test_c2_row_must_agree_with_its_registered_binding(self):
        data = inventory()
        other = copy.deepcopy(data["models"][0])
        other["id"] = "other-reader"
        data["models"].append(other)
        self.write_registered("catalogs/foundation/model-currency.json", data)
        self.bind_routes([{"route_id": "test-route", "model_currency_id": "reader"}])
        self.write_c2(["https://example.org/model#route"], [{
            "repository": "https://example.org/model#route", "route_id": "test-route",
            "model_id": "vendor/model", "model_currency_id": "other-reader",
        }])
        result = self.run_validator()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("does not match the registered route binding", result.stdout)

    def test_missing_inventory_row_fails_publication(self):
        self.write_registered("catalogs/foundation/model-route-bindings.json", {
            "schema_version": 1,
            "routes": [{"route_id": "test-route", "model_currency_id": "missing"}],
        })
        result = self.run_validator()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("unknown model-currency row", result.stdout)

    def test_structure_date_format_and_source_errors_still_fail(self):
        self.write_registered("catalogs/foundation/model-route-bindings.json", {
            "schema_version": 1,
            "routes": [{"route_id": "test-route", "model_currency_id": "reader"}],
        })
        for field, value, expected in [
                ("model_id", None, "expected nonempty string"),
                ("release_date", "2026/10/01", "release_date"),
                ("release_source", "http://example.org/release", "expected primary HTTPS source URL")]:
            with self.subTest(field=field):
                data = inventory()
                data["models"][0][field] = value
                self.write_registered("catalogs/foundation/model-currency.json", data)
                result = self.run_validator()
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(expected, result.stdout)
        path = "catalogs/foundation/model-currency.json"
        raw = b'{"schema_version":'
        (self.fixture.root / path).write_bytes(raw)
        entry = next(row for row in self.fixture.evidence["files"] if row["path"] == path)
        entry.update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
        self.fixture.save()
        result = self.run_validator()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("invalid JSON", result.stdout)

    def test_older_generation_is_reported_without_failing_publication(self):
        data = inventory()
        data["models"][0]["model_id"] = "gpt-6.1-sol"
        self.write_registered("catalogs/foundation/model-currency.json", data)
        self.write_registered("catalogs/landscape/angles/foundation-model-routes.json", {
            "schema_version": 1, "candidates": [{"id": "test-route", "pin": "gpt-5.6-sol"}],
        })
        self.write_registered("catalogs/foundation/model-route-bindings.json", {
            "schema_version": 1,
            "routes": [{"route_id": "test-route", "model_currency_id": "reader"}],
        })
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stdout)
        report = json.loads(result.stdout.splitlines()[0])["model_route_currency"]
        self.assertEqual(report["checked_routes"], 1)
        self.assertEqual(len(report["notices"]), 1)
        self.assertEqual(report["notices"][0]["selected_model"], "gpt-5.6-sol")
        self.assertEqual(report["notices"][0]["inventory_model"], "gpt-6.1-sol")

    def test_gpt_sweep_model_is_checked_against_its_named_row(self):
        self.write_registered("catalogs/foundation/model-route-bindings.json", {
            "schema_version": 1,
            "routes": [{"route_id": "test-route", "model_currency_id": "reader"}],
        })
        source = "evidence/artifacts/model-routes-sweep-20261015/sweep-manifest.json"
        self.write_registered(source, {"schema_version": 1, "layers": [{"catalog": "foundation", "layer_id": "model-routes", "candidates": [
            {"candidate_id": "test-route", "model": "vendor/older-model"},
        ]}]})
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stdout)
        report = json.loads(result.stdout.splitlines()[0])["model_route_currency"]
        self.assertEqual(report["checked_routes"], 2)
        self.assertEqual(report["notices"][0]["source"], source)

    def test_c2_requires_explicit_currency_rows_before_publication(self):
        self.write_registered("catalogs/foundation/model-route-bindings.json", {
            "schema_version": 1,
            "routes": [{"route_id": "test-route", "model_currency_id": "reader"}],
        })
        self.write_registered("evidence/artifacts/model-routes-sweep-merge-20261015/returns.json", {})
        result = self.run_validator()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("C2 route-currency.json is required", result.stdout)

    def test_c2_cannot_omit_a_proposed_route_from_the_join(self):
        self.write_registered("catalogs/foundation/model-route-bindings.json", {
            "schema_version": 1,
            "routes": [{"route_id": "test-route", "model_currency_id": "reader"}],
        })
        root = "evidence/artifacts/model-routes-sweep-merge-20261015/"
        self.write_registered(root + "returns.json", {
            "discovery": {"model-routes": {"proposed": ["https://example.org/model#route"]}},
        })
        self.write_registered(root + "route-currency.json", {"schema_version": 1, "routes": []})
        result = self.run_validator()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("C2 inventory coverage differs", result.stdout)

    def test_removing_the_binding_file_cannot_disable_the_check(self):
        result = self.run_validator()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("route bindings are required", result.stdout)

    def test_an_observed_route_needs_its_own_binding(self):
        self.write_registered("catalogs/foundation/model-route-bindings.json", {
            "schema_version": 1,
            "routes": [{"route_id": "different-route", "model_currency_id": "reader"}],
        })
        result = self.run_validator()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("test-route: missing or unknown model-currency row", result.stdout)

    def test_c2_stale_model_and_current_component_pass_with_a_notice(self):
        data = inventory()
        data["packages"] = [{"id": "gateway", "latest_version": "1.0", "release_date": "2026-10-01",
                             "release_source": "https://example.org/release", "checked_at": "2026-10-07",
                             "release_line": {"kind": "github_release", "repository": "example/gateway"}}]
        self.write_registered("catalogs/foundation/model-currency.json", data)
        self.write_registered("catalogs/foundation/model-route-bindings.json", {
            "schema_version": 1,
            "routes": [{"route_id": "test-route", "model_currency_id": "reader"},
                       {"route_id": "merged-route", "model_currency_id": "reader"}],
        })
        root = "evidence/artifacts/model-routes-sweep-merge-20261015/"
        self.write_registered(root + "returns.json", {"discovery": {"model-routes": {
            "proposed": ["https://example.org/model#route", "https://github.com/example/gateway"],
        }}})
        self.write_registered(root + "route-currency.json", {"schema_version": 1, "routes": [{
            "repository": "https://example.org/model#route", "route_id": "merged-route",
            "model_id": "vendor/older-model", "model_currency_id": "reader",
        }], "components": [{"repository": "https://github.com/example/gateway", "package_currency_id": "gateway"}]})
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stdout)
        report = json.loads(result.stdout.splitlines()[0])["model_route_currency"]
        self.assertEqual(report["checked_routes"], 2)
        self.assertEqual(len(report["notices"]), 1)
        self.assertIs(report["notices"][0]["blocking"], False)

    def test_c2_cannot_disguise_a_model_route_as_a_package(self):
        data = inventory()
        data["packages"] = [{"id": "gateway", "latest_version": "1.0", "release_date": "2026-10-01",
                             "release_source": "https://github.com/example/gateway/releases/tag/v1.0",
                             "checked_at": "2026-10-07",
                             "release_line": {"kind": "github_release", "repository": "example/gateway"}}]
        self.write_registered("catalogs/foundation/model-currency.json", data)
        self.write_registered("catalogs/foundation/model-route-bindings.json", {
            "schema_version": 1,
            "routes": [{"route_id": "test-route", "model_currency_id": "reader"}],
        })
        root = "evidence/artifacts/model-routes-sweep-merge-20261015/"
        self.write_registered(root + "returns.json", {"discovery": {"model-routes": {
            "proposed": ["https://example.org/model#route"],
        }}})
        self.write_registered(root + "route-currency.json", {"schema_version": 1, "routes": [], "components": [{
            "repository": "https://example.org/model#route", "package_currency_id": "gateway",
        }]})
        result = self.run_validator()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("component identity does not match", result.stdout)

    def test_c2_component_case_matches_without_rewriting_retained_identity(self):
        data = inventory()
        data["packages"] = [{"id": "gateway", "latest_version": "1.0", "release_date": "2026-10-01",
                             "release_source": "https://github.com/Example/GateWay/releases/tag/v1.0",
                             "checked_at": "2026-10-07",
                             "release_line": {"kind": "github_release", "repository": "Example/GateWay"}}]
        self.write_registered("catalogs/foundation/model-currency.json", data)
        self.write_registered("catalogs/foundation/model-route-bindings.json", {
            "schema_version": 1,
            "routes": [{"route_id": "test-route", "model_currency_id": "reader"}],
        })
        root = "evidence/artifacts/model-routes-sweep-merge-20261015/"
        for repository in ("https://github.com/example/gateway",
                           "https://WWW.GitHub.com/eXample/gATEway.git/tree/main"):
            with self.subTest(repository=repository):
                self.write_registered(root + "returns.json", {"discovery": {"model-routes": {
                    "proposed": [repository],
                }}})
                self.write_registered(root + "route-currency.json", {"schema_version": 1, "routes": [],
                    "components": [{"repository": repository, "package_currency_id": "gateway"}]})
                result = self.run_validator()
                self.assertEqual(result.returncode, 0, result.stdout)
                from scripts.validate import validate
                self.assertEqual(validate(self.fixture.root, today=TODAY)["model_route_currency"]["checked_routes"], 1)

    def test_c2_inline_row_cannot_bypass_the_route_binding_registry(self):
        self.write_registered("catalogs/foundation/model-route-bindings.json", {
            "schema_version": 1,
            "routes": [{"route_id": "test-route", "model_currency_id": "reader"}],
        })
        root = "evidence/artifacts/model-routes-sweep-merge-20261015/"
        self.write_registered(root + "returns.json", {"discovery": {"model-routes": {
            "proposed": ["https://example.org/model#route"],
        }}})
        self.write_registered(root + "route-currency.json", {"schema_version": 1, "routes": [{
            "repository": "https://example.org/model#route", "route_id": "merged-route",
            "model_id": "vendor/model", "model_currency_id": "reader",
        }]})
        result = self.run_validator()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("registered route binding required", result.stdout)

    def test_c2_component_only_proposal_uses_its_package_row(self):
        data = inventory()
        data["packages"] = [{"id": "gateway", "latest_version": "1.0", "release_date": "2026-10-01",
                             "release_source": "https://github.com/Example/Gateway/releases/tag/v1.0",
                             "checked_at": "2026-10-07",
                             "release_line": {"kind": "github_release", "repository": "Example/Gateway"}}]
        self.write_registered("catalogs/foundation/model-currency.json", data)
        self.write_registered("catalogs/foundation/model-route-bindings.json", {
            "schema_version": 1,
            "routes": [{"route_id": "test-route", "model_currency_id": "reader"}],
        })
        root = "evidence/artifacts/model-routes-sweep-merge-20261015/"
        self.write_registered(root + "returns.json", {"discovery": {"model-routes": {
            "proposed": ["https://github.com/example/gateway"],
        }}})
        self.write_registered(root + "route-currency.json", {"schema_version": 1, "components": [{
            "repository": "https://github.com/example/gateway", "package_currency_id": "gateway",
        }]})
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
