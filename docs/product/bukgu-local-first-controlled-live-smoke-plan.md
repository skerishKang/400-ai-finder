# Bukgu Local-First Controlled Live Smoke Plan

## Stage
Stage 413

---

## 1. Purpose

This document defines the live validation path for `bukgu_gwangju` **after** the no-live readiness audit (Stage 412) confirmed **COMPLETE** status.

**Key framing shift:**
- Previous documentation (Stages 405-412) positioned Firecrawl as a potential default path for live validation
- This plan **replaces the prior default with local-first** as the default controlled live smoke path
- Firecrawl/manual provider becomes an **optional fallback only**, never default, and only with separate explicit approval

---

## 2. Provider Priority

The default provider priority for controlled live smoke validation is:

| Priority | Provider | Condition | Notes |
|----------|----------|-----------|-------|
| **1 (Default)** | `requests` (existing local path) | Always available | Uses `URLCrawler` → `HomepageMapper` → `PipelineRunner` path already validated in no-live tests |
| **2 (Fallback 1)** | `playwright` / browser automation | Only if static fetch cannot discover required links | Requires **separate issue**; not part of default plan |
| **3 (Fallback 2)** | `firecrawl` / manual provider | Only with **explicit separate approval** | Never default; credit/cost constrained; see §3 |

**Parser assumption for default path:** Static HTML parsing with BeautifulSoup-style link extraction (same as no-live `provider="mock"` path and existing `URLCrawler.extract_links` implementation).

---

## 3. Why Not Firecrawl-First

| Reason | Detail |
|--------|--------|
| **Cost / credit constraint** | Firecrawl credits are limited; repeated validation iterations exhaust budget rapidly |
| **Unsuitable for repeated validation** | Live smoke requires multiple iterative runs (tuning caps, adjusting filters); Firecrawl not designed for high-frequency re-runs |
| **Project already has validated local path** | `URLCrawler` + `HomepageMapper` + `PipelineRunner` with `provider="requests"` is already tested in 245+ no-live tests |
| **Local-first is better for debugging / reproduction / cost / control** | Static fetch is deterministic, reproducible, inspectable, and can run in CI without secrets |

**Conclusion:** Firecrawl is relegated to manual/optional fallback (§2 priority 3), never the default path.

---

## 4. Explicit Operator Approval Requirements

**NO live smoke may be executed without ALL of the following documented and approved:**

| Requirement | Specification |
|-------------|---------------|
| **Target profile** | Must be exactly `bukgu_gwangju` (one profile at a time) |
| **Exact command** | Must be pasted in full before execution (see §5 templates) |
| **Max pages cap** | Explicit integer (e.g., `--max-pages=20`) |
| **Max depth cap** | Explicit integer (e.g., `--max-depth=2`) |
| **Timeout cap** | Explicit seconds (e.g., `--timeout=180`) |
| **Provider** | Must be specified (default: `requests`) |
| **Artifact policy** | Must be specified (default: `--no-write-artifacts`) |
| **Rollback / stop condition** | Must be specified (see §6) |
| **No API key / secret** | Must be affirmed — no Firecrawl key, no LLM key, no secrets |
| **No Firecrawl unless separately approved** | Firecrawl requires its own explicit approval document |

Approval must be in writing (GitHub Issue comment, PR approval, or documented message). Blanket or implicit approvals are invalid.

---

## 5. Command Templates Only

**⚠️ These are TEMPLATES with placeholders. They are NOT executable until:**
1. A candidate script is verified to exist and work
2. All §4 approval requirements are met
3. The operator pastes the exact filled-in command

### 5.1 Candidate Live Smoke Command Template

```bash
# TEMPLATE ONLY — candidate/template only; not executable until verified
PYTHONPATH=. .venv/bin/python scripts/<candidate_live_smoke_script>.py \
  --site-id bukgu_gwangju \
  --provider requests \
  --max-pages <SMALL_CAP> \
  --max-depth <SHALLOW_DEPTH> \
  --timeout <SECONDS> \
  --no-write-artifacts
```

**Placeholder definitions:**
- `<candidate_live_smoke_script>` — script name to be determined (e.g., `run_live_smoke.py`, `crawl_validate.py`); **does not exist yet**
- `<SMALL_CAP>` — small page budget (e.g., `20`, `30`, `50`)
- `<SHALLOW_DEPTH>` — shallow depth (e.g., `1`, `2`)
- `<SECONDS>` — timeout in seconds (e.g., `180`, `300`)

### 5.2 Alternative: pytest-based Template (if test file exists)

```bash
# TEMPLATE ONLY — candidate/template only; not executable until verified
PYTHONPATH=. RUN_LIVE_CRAWL_TESTS=1 .venv/bin/python -m pytest \
  tests/test_bukgu_live_smoke.py \
  -k "<SELECTOR>" \
  --max-pages=<SMALL_CAP> \
  --max-depth=<SHALLOW_DEPTH> \
  --timeout=<SECONDS>
```

**⚠️ Critical:** `RUN_LIVE_CRAWL_TESTS=1` is **prohibited** in any execution without explicit approval per §4. The template shows the parameter format only.

### 5.3 Script Verification Requirement

> **The script referenced in these templates does not currently exist.**  
> Before any live execution, a **verified script** must be created, tested in no-live mode, and confirmed executable.  
> This plan documents the **command contract only** — not an executable command.

---

## 6. Stop Conditions

The live run **MUST BE STOPPED IMMEDIATELY** if ANY of the following occur:

| Condition | Detection | Action |
|-----------|-----------|--------|
| **Unexpected domain expansion** | URLs outside `allowed_domains` discovered | Kill process; investigate domain filtering |
| **Page count exceeds cap** | Pages crawled > `--max-pages` × 2 | Kill process; check pagination filtering |
| **Repeated timeout** | Multiple requests exceed `--timeout` | Kill process; site may be blocking or slow |
| **Redirect loop** | Same URL redirected repeatedly | Kill process; check redirect handling |
| **Non-bukgu domain** | Any non-`bukgu.gwangju.kr` domain crawled | Kill process; check allowed_domains |
| **Any artifact write attempt** | File write to `scenario/`, `snapshot/`, `cache/`, `configs/` | Kill process; verify `--no-write-artifacts` honored |
| **Any API key/secret requirement** | Code requests env var with key/secret | Kill process; violates §4 no-secrets rule |
| **Any Firecrawl/API call attempt** | Firecrawl import or HTTP call to Firecrawl API | Kill process; violates provider priority (§2) |

All stop conditions must be documented in the live run log.

---

## 7. Expected Output Policy

| Output | Policy |
|--------|--------|
| **Audit notes only** | Human-readable log/summary of what was discovered |
| **Scenario/snapshot/cache generation** | **FORBIDDEN** — `--no-write-artifacts` required |
| **Promotion to config/test/production** | **FORBIDDEN** — no auto-promotion |
| **Config mutation** | **FORBIDDEN** — `configs/sites/bukgu_gwangju.yml` unchanged |
| **Source grounding mutation** | **FORBIDDEN** — query rewrite, answer composition unchanged |
| **Persisted crawl artifacts** | **FORBIDDEN** unless separately approved in writing |

**The only allowed output is an audit report/notes file written to a temporary location (e.g., `/tmp/live_smoke_audit_<timestamp>.md`).**

---

## 8. Stage 414 Recommendation

| Option | Description | When to Choose |
|--------|-------------|----------------|
| **A: Execute bukgu local-first controlled live smoke** | Run the plan in this document **after explicit operator approval** per §4 | Only if operator explicitly approves; all §4 prerequisites met; script verified |
| **B: Add dry-run/no-live command contract tests** | If script support is unclear, add tests that verify the command interface without live execution | **Default recommendation** — no live approval needed; builds confidence on command contract |
| **C: Defer live and continue no-live hardening** | Add more no-live integration tests for `bukgu_gwangju` (dynamic URLs, deep pagination, edge cases) | Safe default; continues proven no-live track |

**Profile expansion (fourth/fifth municipal) remains DEFERRED** — requires separate explicit approval, not part of default Stage 414.

---

## 9. Files Not Modified in This Stage

| Category | Status |
|----------|--------|
| `configs/sites/` | No changes |
| `src/` production code | No changes |
| `tests/` | No changes (docs-only) |
| `scenario/` `snapshot/` `cache/` | No mutations |
| `README.md` | No changes |
| `validate_matrix()` / `evaluate_response()` | No changes |
| Live/Network/API/Firecrawl | No calls made |

---

## 10. Validation

```bash
git diff --check  # PASS
# No pytest required (docs-only change)
grep -R "local-first" docs/product  # Should include this document
grep -R "bukgu_gwangju" docs/product/bukgu-local-first-controlled-live-smoke-plan.md  # Should match
```

---

## 11. Next Steps

- **Stage 414 Default (Option B/C)**: Command contract tests or continued no-live hardening
- **Stage 414 Live (Option A)**: Only with explicit operator approval and verified script
- **Profile Expansion**: Deferred — separate explicit approval required

---

## 12. Cross-References

- **No-live readiness basis:** `docs/product/bukgu-crawl-filter-no-live-readiness-audit.md` (Stage 412 COMPLETE)
- **Live smoke boundary:** `docs/product/controlled-live-smoke-boundary-for-crawl-filters.md` (updated to reference this plan)
- **Crawl budget policy:** `docs/product/crawl-budget-path-filtering-policy.md` (updated to reference this plan)
- **Dynamic retrieval strategy:** `docs/product/dynamic-retrieval-query-learning-strategy.md` (updated to reference this plan)
- **Onboarding boundary:** `docs/product/new-municipal-profile-onboarding-boundary.md` (updated to reference this plan)
- **Candidate audit:** `docs/product/fourth-municipal-profile-onboarding-candidate-audit.md` (updated to reference this plan)