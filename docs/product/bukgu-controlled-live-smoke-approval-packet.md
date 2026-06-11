# Bukgu Controlled Live Smoke Approval Packet

## Stage
Stage 417

---

## 1. Purpose and Scope

This document is an **approval/preflight packet** for a future controlled live smoke validation of `bukgu_gwangju`.

**This packet does NOT approve or execute live validation.**

- It documents the exact fields a human operator must fill and explicitly approve before ANY live smoke can run.
- Future live execution remains **blocked** until this packet is fully completed, reviewed, and approved by an authorized operator.
- This is a **pre-approval contract**, not an execution trigger.

### Key Declarations

- This is **Stage 417** — approval/preflight packet only.
- **Live validation is NOT approved** by this document.
- **Live execution remains blocked** until a human explicitly fills and approves this packet.
- All fields below are **mandatory** and must be completed before approval consideration.

### Completeness Gate (Stage 418)

**An incomplete packet is NOT an approval and MUST NOT be interpreted as authorization for live execution.**

- **Incomplete packet = not approved = no execution.** Any missing mandatory field (§4) blocks approval.
- **Placeholders are not approval.** Template placeholders (e.g., `<MAX_PAGES>`, `<CANDIDATE_LIVE_SMOKE_SCRIPT>`) do not constitute filled values.
- **A command template is not an executable script.** The template in §5 is a non-executable placeholder; it does not reference a verified runnable script.
- **Approval requires ALL mandatory fields (§4) plus separate explicit human approval.** No field may be left blank, defaulted, or placeholdered.
- **Missing ANY mandatory field blocks approval.** The gate is all-or-nothing.
- **Unsafe requests cannot receive default approval** (see §6 Forbidden Defaults). Any request involving Firecrawl/provider switch, API keys/secrets, profile expansion, batch runs, `RUN_LIVE_*_TESTS=1`, or persistence of scenario/snapshot/cache/config/source-grounding is explicitly blocked from default approval and requires separate, explicit approval per the cross-referenced boundaries.

### Post-Run Evidence Review Gate (Stage 419)

**Even if a live smoke is executed after full approval, its results are EVIDENCE ONLY and do not constitute approval for any persistence or promotion.**

- **Live result is evidence only.** A successful live smoke produces audit data — it does not authorize scenario/snapshot/cache/config/source-grounding changes.
- **Live success is NOT approval for persistence.** No automatic merge, promotion, or config mutation occurs based on live results alone.
- **Post-run report is mandatory before any follow-up.** The operator MUST produce the full report (§8) before any further action.
- **Evidence review issue/PR is MANDATORY for EVERY approved live run.** Regardless of success or failure, every approved live run MUST have a corresponding human-reviewed GitHub issue or PR link documenting the evidence review. This is not optional and is not conditional on outcome.
- **Evidence review must be a separate human-reviewed GitHub issue or PR.** No automatic process may consume live results.
- **No automatic merge/promotion based only on live success.** Any promotion requires explicit human review and a separate decision.
- **Scenario/snapshot/cache/config/source-grounding changes remain PROHIBITED by default.** The default no-persist policy (§4 field #12, §6) continues to apply after live execution.
- **Any promotion requires a separate follow-up issue after human review.** The post-run report's "Recommended follow-up issue" field (§8) is for gaps/anomalies only; it is distinct from the mandatory evidence review link and is not auto-triggered.
- **`bukgu_gwangju` remains the only first-live target.** No profile expansion or batch live runs are authorized by this gate.

#### Failure Reporting Rules — Automatic Promotion Blockers

The following conditions, if observed in a live run, **automatically block any promotion** regardless of other results:

| Blocker | Description |
|---------|-------------|
| **Failures** | Any fetch error, non-2xx response, or crawl failure |
| **Timeouts** | Any request exceeding approved `--timeout` |
| **Unexpected domain expansion** | Any URL outside `bukgu.gwangju.kr` (and allowed subdomains) |
| **Provider switch** | Any attempt to switch provider away from approved `requests` |
| **Artifact write attempt** | Any attempt to write scenario/snapshot/cache/config |
| **Firecrawl/API key/secret requirement** | Any code path requiring Firecrawl or API key/secret (unless separately approved per §6) |
| **Disallowed persistence attempt** | Any attempt to persist scenario/snapshot/cache/config/source-grounding changes |

---

## 2. Exact Target Policy

| Field | Value | Notes |
|-------|-------|-------|
| **Target Profile** | `bukgu_gwangju` | Only profile allowed for first live smoke |
| **Batch Profile Run** | Prohibited | One profile at a time |
| **Profile Expansion** | Not permitted in this approval | Requires separate onboarding approval per `new-municipal-profile-onboarding-boundary.md` |

---

## 3. Provider Policy

| Provider | Status | Notes |
|----------|--------|-------|
| **`requests` (local-first)** | **Default** | Existing path: `URLCrawler` → `HomepageMapper` → `PipelineRunner` |
| `playwright` | Fallback 1 | Only if static fetch cannot discover required links; requires separate issue |
| `firecrawl` / manual | Fallback 2 | **Separately unapproved**; never default; credit/cost constrained; requires explicit separate approval |
| Any other / API key / secret | **Prohibited** | No API keys/secrets allowed in this packet |

---

## 4. Required Approval Fields

**All fields below are mandatory.** The approver must fill each field explicitly. Placeholders are not acceptable for approval.

| # | Field | Description | Required |
|---|-------|-------------|:--------:|
| 1 | **Approver** | Full name / GitHub handle of person granting approval | ✅ |
| 2 | **Approval Timestamp** | ISO 8601 date-time of approval (e.g., `2026-01-15T14:30:00Z`) | ✅ |
| 3 | **Target Profile** | Must be exactly `bukgu_gwangju` | ✅ |
| 4 | **Exact Command** | Full command line to execute (see §5 for template) | ✅ |
| 5 | **Max Pages** | Integer cap on total pages fetched (e.g., `50`) | ✅ |
| 6 | **Max Depth** | Integer cap on crawl depth from seed (e.g., `2`) | ✅ |
| 7 | **Timeout** | Per-request timeout in seconds (e.g., `30`) | ✅ |
| 8 | **Retry Policy** | Max retries, backoff strategy, retryable status codes | ✅ |
| 9 | **Output Location** | Where audit notes / logs will be written (path or `stdout`) | ✅ |
| 10 | **Expected Diff Policy** | What changes are expected/allowed (default: NO persisted artifacts) | ✅ |
| 11 | **Stop/Rollback Conditions** | Explicit conditions that trigger immediate stop (see §5 defaults) | ✅ |
| 12 | **No-Persist Confirmation** | Written confirmation that no scenario/snapshot/cache/config/source-grounding changes will be persisted by default | ✅ |

---

## 5. Command Template

**⚠️ NON-EXECUTABLE PLACEHOLDER — NOT A RUNNABLE COMMAND**

The following template must be filled with actual approved values from §4 before execution. It does not reference an existing verified script and must not be executed as-is.

```bash
# PLACEHOLDER ONLY — DO NOT EXECUTE
# Requires: approved values for all placeholders below
# Requires: explicit operator approval per this packet
# Requires: no RUN_LIVE_*_TESTS=1, no API keys/secrets, no Firecrawl unless separately approved

PYTHONPATH=. .venv/bin/python scripts/<CANDIDATE_LIVE_SMOKE_SCRIPT>.py \
  --site-id bukgu_gwangju \
  --provider requests \
  --max-pages <MAX_PAGES> \
  --max-depth <MAX_DEPTH> \
  --timeout <TIMEOUT_SECONDS> \
  --retry-max <RETRY_MAX> \
  --retry-backoff <BACKOFF_SECONDS> \
  --output <OUTPUT_PATH> \
  --no-write-artifacts \
  --dry-run-verify-only
```

### Template Constraints

| Constraint | Value |
|------------|-------|
| **Script existence** | `<CANDIDATE_LIVE_SMOKE_SCRIPT>` is a placeholder — no verified executable script exists yet |
| **`RUN_LIVE_*_TESTS=1`** | **MUST NOT** be set in this template or approval |
| **Provider** | Fixed to `requests` (local-first default) |
| **Caps** | All numeric caps (`--max-pages`, `--max-depth`, `--timeout`, `--retry-max`, `--retry-backoff`) are placeholders — must be filled with approved integers |
| **Artifacts** | `--no-write-artifacts` flag mandatory (default no-persist policy) |
| **Dry-run marker** | `--dry-run-verify-only` placeholder — actual live run flag only with explicit approval |

**If no verified executable script exists at approval time, the approval is conditional on script verification first.**

---

## 6. Forbidden Defaults

The following are **explicitly prohibited** as defaults in this packet and any live execution:

| Forbidden Default | Status |
|-------------------|:------:|
| `RUN_LIVE_*_TESTS=1` enabled | ❌ Prohibited |
| API keys / secrets in command or environment | ❌ Prohibited |
| Firecrawl / provider switch away from `requests` | ❌ Prohibited (requires separate approval) |
| Scenario / snapshot / cache / config / source-grounding mutation | ❌ Prohibited by default |
| Profile expansion / batch multi-profile run | ❌ Prohibited |
| Executable live smoke script creation as part of this packet | ❌ Prohibited (separate work) |
| Any live/network/API/Firecrawl call in docs/tests | ❌ Prohibited |

---

## 7. Default Stop / Rollback Conditions

The following stop conditions apply by default and must be acknowledged in §4 field #11. Additional conditions may be added by the approver.

| Condition | Description |
|-----------|-------------|
| **Unexpected domain expansion** | Any URL outside `bukgu.gwangju.kr` (and allowed subdomains) |
| **Page cap exceeded** | Total fetched pages > approved `--max-pages` |
| **Depth cap exceeded** | Crawl depth > approved `--max-depth` |
| **Repeated timeout** | > 3 consecutive request timeouts |
| **Redirect loop** | > 5 redirects for same URL |
| **Non-bukgu domain** | Any response from non-bukgu domain |
| **Artifact write attempt** | Any attempt to write scenario/snapshot/cache/config |
| **API key/secret requirement** | Any code path requiring API key/secret |
| **Firecrawl/API call attempt** | Any Firecrawl provider construction, `fetch()` call, or network API call |
| **Provider switch** | Any attempt to switch provider away from `requests` |

---

## 8. Future Post-Run Report Checklist

If and when live smoke is executed after approval, the operator MUST produce a post-run report containing:

| Item | Description | Required |
|------|-------------|:--------:|
| **Exact command used** | Full command line as executed | ✅ |
| **Target profile** | Confirmed `bukgu_gwangju` | ✅ |
| **Provider used** | Confirmed `requests` (or separately approved fallback) | ✅ |
| **Caps used** | Actual `--max-pages`, `--max-depth`, `--timeout`, retry values | ✅ |
| **Pages attempted / fetched** | Count of URLs discovered vs. successfully fetched | ✅ |
| **Errors / timeouts** | List of errors, timeout counts, affected URLs | ✅ |
| **Output artifacts** | Location and summary of any artifacts produced | ✅ |
| **No-disallowed-persistence confirmation** | Explicit statement that no scenario/snapshot/cache/config/source-grounding changes were persisted | ✅ |
| **Evidence review issue/PR** | Link to human-reviewed GitHub issue or PR for evidence review — **MANDATORY for every approved live run, regardless of outcome** | ✅ |
| **Recommended follow-up issue** | If any gaps, anomalies, or new findings — link to new GitHub issue (distinct from evidence review) | — |

---

### Evidence Review Link Requirement

The **Evidence review issue/PR** field is **unconditionally mandatory** for every approved live run:

- Required regardless of live success, failure, partial results, or no results
- Must be a link to a GitHub issue or PR where human evidence review is documented
- Separate from "Recommended follow-up issue" which is only for gaps/anomalies
- Without this link, the post-run report is incomplete and no further action may proceed

---

## 9. Cross-References

- **Stage 413 — Local-First Controlled Live Smoke Plan:** `docs/product/bukgu-local-first-controlled-live-smoke-plan.md`
- **Stage 416 — No-Live Track Closure Audit:** `docs/product/bukgu-no-live-crawl-filter-track-closure-audit.md`
- **Controlled Live Smoke Boundary:** `docs/product/controlled-live-smoke-boundary-for-crawl-filters.md`
- **New Municipal Profile Onboarding Boundary:** `docs/product/new-municipal-profile-onboarding-boundary.md` (profile expansion deferred)

---

## 10. Validation

```bash
git diff --check  # PASS
# Contract test (if added):
PYTHONPATH=. python3 -m pytest tests/test_bukgu_controlled_live_smoke_approval_packet.py  # PASS
# Related contract tests:
PYTHONPATH=. python3 -m pytest tests/test_bukgu_local_first_live_smoke_plan_contract_no_live.py tests/test_bukgu_no_live_track_closure_audit.py  # PASS
# Full pytest: not run unless shared helpers or broad infrastructure changed
```

**No live/network/API/Firecrawl calls executed. No API keys/secrets. No `RUN_LIVE_*_TESTS=1`. No config/src/scenario/snapshot/cache changes. No executable live smoke script. No profile expansion.**