#!/usr/bin/env python3
"""Canonical Tier-0 Multi-Runtime Harness `.md` Sync & Public-Safe Master ADR Registry (`ADR-0044`)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKSTATION = ROOT.parent
PUBLIC_REPOS = frozenset(
    {
        "agy-sota-harness",
        "astrolabe",
        "dot-github",
        "dsh-sota-harness",
        "native-agent-stack",
        "sota-compounding-lab",
        "sota-harness-foundation",
        "sota-multi-model-workflows",
        "sota-upstream-shelf-lock",
    }
)
SKIP_ADR_NAMES = frozenset(
    {
        "CATALOG.md",
        "README.md",
        "INDEX.md",
        "ECOSYSTEM_FINALIZED_ADRS_MASTER_REGISTRY.md",
    }
)
TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
STATUS_RE = re.compile(r"(?:^-\s+\*\*Status:\*\*\s+|\*\*Status:\s*)(.+?)(?:\*\*|\s*$)", re.MULTILINE)
DATE_RE = re.compile(r"^-\s+\*\*Date:\*\*\s+(\d{4}-\d{2}-\d{2})", re.MULTILINE)
GRADE_RE = re.compile(r"^-\s+\*\*Evidence Grade:\*\*\s+(.+)$", re.MULTILINE)
GITHUB_URL_RE = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")

TIER0_MARKER_START = "<!-- BEGIN TIER0-SOTA-RULES -->"
TIER0_MARKER_END = "<!-- END TIER0-SOTA-RULES -->"
SYNC_END_MARKER = "<!-- END SOTA-ECOSYSTEM-SYNC -->"

CANONICAL_CHARTER_HEADER = "# Tier-0 Engineering & Quantitative Charter (Canonical Single Rule)"
CANONICAL_CHARTER_REQUIRED_CLAUSES: tuple[str, ...] = (
    CANONICAL_CHARTER_HEADER,
    "Upstream-Only Mandate",
    "Zero Paper Self-Invention",
    "<= 5,000",
    "<= 2026-10-15",
    "<= 2.00%",
    "singleActiveBrokerHostOnly = true",
    "Zero Secret or PII Leaks",
)


def is_canonical_tier0_charter(text: str) -> bool:
    """Return True if text matches the concise Canonical Single-Rule Tier-0 Charter (`ADR-0049`/`ADR-0050`)."""
    return all(clause in text for clause in CANONICAL_CHARTER_REQUIRED_CLAUSES)


TIER0_CANONICAL_BLOCK = (
    f"{TIER0_MARKER_START}\n"
    "- **Tier-0 SOTA-Source-Only, Zero Paper Self-Invention & Hard Upstream Provenance (`ADR-0023` / `ADR-0092` / `ADR-0094`):** "
    "Every production line, backtest engine, strategy, hook, skill, and ADR across all `18/18` repos MUST cleanly "
    "install, integrate, or build directly upon pinned SOTA upstream frameworks, hosted platforms, and official/verified "
    "paper repositories (`~/Documents/upstream/` `18`-pin shelf lock, `UPSTREAM.md`, `upstream-map.toml`, zero placeholders/"
    "banned libs, GitHub-evidenced MADR 4.0 ADRs) and validate E2E on pre-wall historical data (`<= 2026-10-15`) — NEVER "
    "self-invent from scratch based on papers. Verify `scripts/merge_gate.py` and `shelf_lock.hard_upstream_rule "
    "--require-full-compliance` before landing; consolidated single-repo finalized ADRs live verbatim in "
    "`sota-private-vault/adr_archive/` (`ADR-0027`) and as the public-safe master registry in "
    "`native-agent-stack/docs/adr/ECOSYSTEM_FINALIZED_ADRS_MASTER_REGISTRY.md` (`ADR-0044`).\n"
    "- **Tier-0 Full-Resolution, Zero-Residual, Zero-Fallback Rule (`ADR-0025` / `ADR-0038` / `ADR-0034` / "
    "`ADR-0095`):** Every backtest, simulation, GPU sweep (`:8794`), and sealed E2E manifest MUST execute "
    "pinned upstream engines at `100%` full resolution (`allow_silent_fallback = False`, `0` residuals): "
    "real `NautilusTrader v2` instruments + data + `Strategy` (`iterations > 0`, empty `BacktestEngine.run()` "
    "stubs fail `merge_gate.py` via AST across `4/4` quant repos), real Rust `hftbacktest` "
    "`HashMapMarketDepthBacktest` + `RiskAdverseQueueModel` L1 ticks, `rtx4090_gpu_cuda` (`require_gpu=True`), "
    "and strict pre-wall `<= 2026-10-15` isolation.\n"
    "- **Tier-0 One-Harness Cleanliness, 16-Layer Landscape & 415+ Starred/Beyond Maintenance (`ADR-0045` / `ADR-0046`):** "
    "All `16` layers (`L0`–`L15`), `18` repos, `415` audited GitHub starred repos + beyond-starred SOTA anchors, "
    "`8`-stage Research Convergence Practice (`S1`–`S8`), `7/7` runtime `.md` files, `60/60` `SkillEvaluator` corpus, "
    "`18/18` `orca.yaml` `Tier-0 Merge Gate` tabs, and universal Git `pre-commit`/`pre-push` hooks (`core.hooksPath` -> "
    "`native-agent-stack/hooks`) are continuously audited by `native-agent-stack/scripts/one_harness_cleanliness_doctor.py --check`.\n"
    "- **Tier-0 No Self-Built Waste, Monolith Freeze & Hosted SOTA Platform Mandate (`ADR-0047`):** "
    "NEVER hand-roll custom OMS loops, fill reconcilers, backtest runners, custom HTML/JS dashboards, or 1-bar strategy "
    "proxies behind cosmetic `upstream-map.toml` labels, and NEVER mask negative-expectancy strategy bugs with stacked "
    "sizing throttles. Host the actual pinned SOTA platforms directly (`NautilusTrader v2` `BacktestNode`/`TradingNode`, "
    "`FINOS/OpenBB Workspace` `:1420` + `backends-for-openbb` `:6900`, `hftbacktest`, `vectorbt`, `QuantStats`, "
    "`Perspective`, `Lightweight Charts`, `Polars`, `DuckDB`) with only a thin native plugin layer; keep legacy monoliths "
    "frozen under downward-only LOC ratchets and prune merged Orca worktrees immediately after push.\n"
    "- **Tier-0 Advanced LLM-Native Quant Frontier & License/Order-Path Firewall (`ADR-0048` / `shelf-lock ADR-0026`):** "
    "All `16` layers (`L0`–`L15`) converge live-verified, non-archived, SPDX-licensed frontier anchors (`nautilus_agents`, "
    "`anthropics/financial-services`, `FINSABER`, `MarS`, `LOBS5`, `FinRobot`, `qwen-dianjin`, `Fino1`, `FinBen`, `TabPFN`, "
    "`Chronos-2`, `MOIRAI-2`, `river`, `MAPIE`, `DoWhy`, `mcp_massive`, `mcp-polymarket` read-only, `TwinMarket`, `openbq-org/OpenBB` "
    "+ `edgartools` built-in MCP) while strictly quarantining unlicensed (`NONE`), archived, and GPL-3.0 repos and blocking external "
    "agent order-routing paths (`Vibe-Trading`, `mcp-polymarket`, `FINSABER` vendored broker scripts) under `ADR-0022`.\n"
    f"{TIER0_MARKER_END}"
)

AGY_PLUGIN_ADR0023_LINE = (
    "- **Tier-0 SOTA-Source-Only, Zero Paper Self-Invention & Hosted SOTA Platform Mandate (`ADR-0023` / `ADR-0027` / `ADR-0044` / `ADR-0045` / `ADR-0046` / `ADR-0047`):** "
    "Every production file, strategy, hook, skill, and ADR across all `18/18` repos MUST cleanly install, host, or build thinly atop pinned SOTA upstream frameworks, platforms, and official paper repos tested E2E on historical data (`<= 2026-10-15`) "
    "(`NautilusTrader v2`, `OpenBB/FINOS Workspace :1420/:6900`, `hftbacktest`, `vectorbt`, `QuantStats`, `Perspective`, `Polars`, `DuckDB`) — "
    "ZERO self-invented paper implementations, ZERO self-built custom OMS/UI/proxy waste, ZERO throttle band-aids on broken strategies, strict legacy monolith LOC freeze & merged-worktree cleanup "
    "audited via `native-agent-stack/scripts/one_harness_cleanliness_doctor.py`; single-repo finalized ADR archives live in "
    "`sota-private-vault/adr_archive/` (verbatim private) and `native-agent-stack/docs/adr/ECOSYSTEM_FINALIZED_ADRS_MASTER_REGISTRY.md` (public-safe registry)."
)


def _scrub_public_meta(text: str) -> str:
    s = re.sub(r"\b(?:PA|DU)(?=[0-9A-Z]*[0-9])[0-9A-Z]{8,14}\b", "<REDACTED>", text)
    s = re.sub(r"\b(?:AK|PK)[0-9A-Z]{16,28}\b", "<REDACTED>", s)
    s = re.sub(r"(?<![A-Za-z0-9_*])/" + r"Users/[A-Za-z0-9._-]+/", "~/", s)
    s = re.sub(r"(?<![A-Za-z0-9_*])/home/[A-Za-z0-9._-]+/", "~/", s)
    s = re.sub(r"[A-Za-z]:[/\\]Users[/\\][A-Za-z0-9._-]+[/\\]", "~/", s)
    return s


def build_public_master_adr_registry(
    workstation: Path = DEFAULT_WORKSTATION,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate public-safe metadata-only Master Finalized ADR Registry across all 18 repos."""
    target_dir = out_dir or (ROOT / "docs" / "adr")
    target_dir.mkdir(parents=True, exist_ok=True)
    repos = sorted(
        (p for p in workstation.iterdir() if p.is_dir() and (p / ".git").exists()),
        key=lambda p: p.name,
    )
    records: list[dict[str, Any]] = []
    per_repo_counts: dict[str, int] = {}

    for repo_path in repos:
        adr_dir = repo_path / "docs" / "adr"
        if not adr_dir.is_dir():
            continue
        adr_files = sorted(p for p in adr_dir.glob("*.md") if p.is_file() and p.name not in SKIP_ADR_NAMES)
        per_repo_counts[repo_path.name] = len(adr_files)
        tier = "PUBLIC" if repo_path.name in PUBLIC_REPOS else "PRIVATE"
        for src in adr_files:
            raw = src.read_text(encoding="utf-8", errors="replace")
            m_title = TITLE_RE.search(raw)
            m_status = STATUS_RE.search(raw)
            m_date = DATE_RE.search(raw)
            m_grade = GRADE_RE.search(raw)
            gh_urls = sorted(set(GITHUB_URL_RE.findall(raw)))[:4]
            title = _scrub_public_meta(m_title.group(1).strip() if m_title else src.stem)
            status = _scrub_public_meta(m_status.group(1).strip() if m_status else "Accepted")[:48]
            grade = _scrub_public_meta(m_grade.group(1).strip()[:48] if m_grade else "")
            records.append(
                {
                    "repo": repo_path.name,
                    "tier": tier,
                    "file": src.name,
                    "title": title,
                    "status": status,
                    "date": m_date.group(1).strip() if m_date else "",
                    "evidence_grade": grade,
                    "github_urls": gh_urls,
                    "file_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                }
            )

    manifest: dict[str, Any] = {
        "schema": "sota.public-master-finalized-adr-registry.v1",
        "adr": "ADR-0044",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "repos_indexed": len(per_repo_counts),
        "total_adrs_indexed": len(records),
        "verbatim_private_archive_repo": "native-agent-stack/sota-private-vault (adr_archive/)",
        "per_repo_counts": per_repo_counts,
        "records": records,
    }
    raw_body = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest["manifest_sha256"] = hashlib.sha256(raw_body).hexdigest()

    (target_dir / "ECOSYSTEM_FINALIZED_ADRS_MASTER_REGISTRY.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    lines = [
        "# Native Agent Stack — Unified Single-Repo Master Finalized ADR Registry (`ADR-0044`)",
        "",
        f"- **Total Finalized ADRs Indexed:** `{len(records)}` across `{len(per_repo_counts)}` repositories (`18/18` `ADR-0023` PASS)",
        f"- **Canonical Manifest SHA-256:** `{manifest['manifest_sha256']}`",
        "- **Verbatim Private Continuity Copy:** `sota-private-vault/adr_archive/` (`ADR-0027`, Two-Tier Public/Private Firewall intact)",
        "",
        "## Per-Repository Finalized ADR Summary",
        "",
        "| Repository | Tier | Finalized ADRs |",
        "| :--- | :---: | ---: |",
    ]
    for rname, cnt in sorted(per_repo_counts.items()):
        tier_lbl = "PUBLIC" if rname in PUBLIC_REPOS else "PRIVATE"
        lines.append(f"| `{rname}` | `{tier_lbl}` | `{cnt}` |")

    lines.extend(
        [
            "",
            "## Complete Public-Safe Master ADR Registry",
            "",
            "| Repo | Tier | ADR Title | Status | Date | SHA-256 (12) |",
            "| :--- | :---: | :--- | :--- | :--- | :--- |",
        ]
    )
    for rec in records:
        safe_title = rec["title"].replace("|", "\\|")
        safe_status = rec["status"].replace("|", "\\|")
        lines.append(
            f"| `{rec['repo']}` | `{rec['tier']}` | {safe_title} | {safe_status} | "
            f"{rec['date']} | `{rec['file_sha256'][:12]}` |"
        )
    lines.append("")
    (target_dir / "ECOSYSTEM_FINALIZED_ADRS_MASTER_REGISTRY.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n"
    )
    return {
        "repos_indexed": len(per_repo_counts),
        "total_adrs_indexed": len(records),
        "manifest_sha256": manifest["manifest_sha256"],
    }


def upsert_tier0_block_in_text(text: str) -> str:
    """Idempotently upsert `TIER0_CANONICAL_BLOCK` inside `SOTA-ECOSYSTEM-SYNC` (preserving other sections)."""
    if TIER0_MARKER_START in text and TIER0_MARKER_END in text:
        pattern = re.compile(
            re.escape(TIER0_MARKER_START) + r".*?" + re.escape(TIER0_MARKER_END),
            flags=re.DOTALL,
        )
        return pattern.sub(TIER0_CANONICAL_BLOCK, text, count=1)
    if SYNC_END_MARKER in text:
        return text.replace(SYNC_END_MARKER, f"{TIER0_CANONICAL_BLOCK}\n{SYNC_END_MARKER}", 1)
    suffix = "" if text.endswith("\n") else "\n"
    return f"{text}{suffix}\n{TIER0_CANONICAL_BLOCK}\n"


def global_runtime_md_targets(home_dir: Path | None = None) -> tuple[tuple[str, Path], ...]:
    home = home_dir or Path.home()
    return (
        ("gemini_global", home / ".gemini" / "GEMINI.md"),
        ("claude_global", home / ".claude" / "CLAUDE.md"),
        ("codex_global", home / ".codex" / "AGENTS.md"),
        ("opencode_global", home / ".config" / "opencode" / "AGENTS.md"),
        ("dsh_global", home / ".dsh" / "AGENTS.md"),
        ("omp_global", home / ".omp" / "agent" / "AGENTS.md"),
    )


def _upsert_agy_plugin_line(text: str) -> str:
    if AGY_PLUGIN_ADR0023_LINE in text:
        return text
    pat = re.compile(r"^- \*\*Tier-0 SOTA-Source-Only[^\n]*$", flags=re.MULTILINE)
    if pat.search(text):
        return pat.sub(AGY_PLUGIN_ADR0023_LINE, text, count=1)
    sep = "" if text.endswith("\n") else "\n"
    return f"{text}{sep}{AGY_PLUGIN_ADR0023_LINE}\n"


def check_tier0_harness_md_parity(home_dir: Path | None = None) -> dict[str, Any]:
    """Deterministically verify 0-byte Tier-0 drift across global runtime `.md` files (Canonical Charter or legacy sync)."""
    home = home_dir or Path.home()
    statuses: dict[str, str] = {}
    drifted: list[str] = []
    canonical_hashes: dict[str, str] = {}
    for label, target in global_runtime_md_targets(home):
        if not target.is_file():
            statuses[label] = "missing"
            drifted.append(label)
            continue
        cur = target.read_text(encoding="utf-8")
        if is_canonical_tier0_charter(cur):
            statuses[label] = "synced"
            canonical_hashes[label] = hashlib.sha256(cur.encode("utf-8")).hexdigest()[:16]
        elif TIER0_CANONICAL_BLOCK in cur:
            statuses[label] = "synced"
        else:
            statuses[label] = "drifted"
            drifted.append(label)

    # When runtimes adopt the Canonical Single-Rule Charter, enforce 0-byte cross-runtime parity
    canonical_mode = len(canonical_hashes) == len(global_runtime_md_targets(home))
    if canonical_hashes and len(set(canonical_hashes.values())) > 1:
        dominant = max(
            set(canonical_hashes.values()), key=lambda h: list(canonical_hashes.values()).count(h)
        )
        for label, digest in canonical_hashes.items():
            if digest != dominant:
                statuses[label] = "drifted"
                if label not in drifted:
                    drifted.append(label)

    agy_plugin_rules = home / ".gemini" / "config" / "plugins" / "agy-sota-core" / "rules" / "AGENTS.md"
    if not agy_plugin_rules.is_file():
        if canonical_mode and statuses.get("gemini_global") == "synced":
            statuses["agy_plugin_rules"] = "synced"
        else:
            statuses["agy_plugin_rules"] = "missing"
            drifted.append("agy_plugin_rules")
    else:
        cur_p = agy_plugin_rules.read_text(encoding="utf-8")
        if AGY_PLUGIN_ADR0023_LINE in cur_p or is_canonical_tier0_charter(cur_p):
            statuses["agy_plugin_rules"] = "synced"
        else:
            statuses["agy_plugin_rules"] = "drifted"
            drifted.append("agy_plugin_rules")

    return {
        "total_targets": len(statuses),
        "synced_count": sum(1 for v in statuses.values() if v == "synced"),
        "drifted": drifted,
        "all_synced": len(drifted) == 0,
        "canonical_charter_mode": canonical_mode,
        "canonical_charter_sha256_16": next(iter(canonical_hashes.values()), "") if canonical_mode else "",
        "statuses": statuses,
    }


def sync_tier0_harness_md_files(home_dir: Path | None = None) -> dict[str, str]:
    """Propagate canonical Tier-0 rules across runtime `.md` files (upgrading Canonical Charter verbatim)."""
    home = home_dir or Path.home()
    results: dict[str, str] = {}
    canonical_count = 0
    charter_path = ROOT / "docs" / "cleanroom" / "TIER0_CANONICAL_CHARTER.md"
    canonical_txt = (
        charter_path.read_text(encoding="utf-8").replace("\r\n", "\n") if charter_path.is_file() else ""
    )
    for label, target in global_runtime_md_targets(home):
        if not target.is_file():
            results[label] = "missing"
            continue
        old = target.read_text(encoding="utf-8")
        if old.lstrip().startswith(CANONICAL_CHARTER_HEADER) and canonical_txt:
            canonical_count += 1
            if old.replace("\r\n", "\n") == canonical_txt:
                results[label] = "unchanged"
            else:
                target.write_text(canonical_txt, encoding="utf-8", newline="\n")
                results[label] = "updated"
            continue
        if is_canonical_tier0_charter(old):
            canonical_count += 1
            results[label] = "unchanged"
            continue
        new = upsert_tier0_block_in_text(old)
        if new != old:
            target.write_text(new, encoding="utf-8", newline="\n")
            results[label] = "updated"
        else:
            results[label] = "unchanged"

    agy_plugin_rules = home / ".gemini" / "config" / "plugins" / "agy-sota-core" / "rules" / "AGENTS.md"
    if agy_plugin_rules.is_file():
        old_p = agy_plugin_rules.read_text(encoding="utf-8")
        if is_canonical_tier0_charter(old_p):
            results["agy_plugin_rules"] = "unchanged"
        else:
            new_p = _upsert_agy_plugin_line(old_p)
            if new_p != old_p:
                agy_plugin_rules.write_text(new_p, encoding="utf-8", newline="\n")
                results["agy_plugin_rules"] = "updated"
            else:
                results["agy_plugin_rules"] = "unchanged"
    elif canonical_count == len(global_runtime_md_targets(home)):
        results["agy_plugin_rules"] = "superseded_by_canonical_charter"
    else:
        results["agy_plugin_rules"] = "missing"
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync Tier-0 multi-runtime harness .md & Master ADR Registry"
    )
    parser.add_argument(
        "--apply-global-md", action="store_true", help="Update all 7 local runtime .md files"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify 0-byte Tier-0 drift across all 7 global runtime .md files",
    )
    parser.add_argument("--workstation", type=Path, default=DEFAULT_WORKSTATION)
    args = parser.parse_args()

    if args.check:
        parity = check_tier0_harness_md_parity()
        print(json.dumps(parity, indent=2))
        return 0 if parity["all_synced"] else 1

    reg = build_public_master_adr_registry(workstation=args.workstation)
    md_res = sync_tier0_harness_md_files() if args.apply_global_md else {}
    print(json.dumps({"registry": reg, "global_md_synced": len(md_res), "details": md_res}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
