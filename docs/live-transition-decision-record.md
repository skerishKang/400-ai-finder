# Live Transition Decision Record

> **2026-07-10 업데이트:** 현재 Cloudflare MVP Function(`functions/api/mvp/ask.js`)은
> 실제로 **Gemini**(`gemini-3.1-flash-lite`)를 사용합니다. 아래 hy3/kilocode 참조는
> 이전 결정 기록으로, Gemini 적용 시 이 결정 레코드의 조건(have-firecrawl, hy3 의존성)은
> 더 이상 해당하지 않습니다.

Decision gate between the **local/static MVP demo** and the **intended live /
provider-assisted product** — official-site action navigator + live
integration (epic #862).

> **Live integration is the intended product direction, not a prohibition.**
> The MVP demo surface defaults to local/static for safe stakeholder review, but
> the product goal is an AI that answers resident questions and **actually
> navigates the real Buk-gu site** (click, fetch, return the answer). Live
> provider calls are gated by this record for *operational safety*, not forbidden.
> The earlier "no live" framing in this doc was over-built by an assistant model
> and has been corrected to match the actual product intent.

---

## 1. Current state

| Item | Status |
|------|--------|
| Local/static MVP demo | **Complete** (stakeholder-review surface) |
| Golden quests | Remain **local/static** and **locked** (five quests) for the demo surface |
| LLM intent router + fallback | **Intended product path — now being enabled** |
| Approved live provider | **`tencent/hy3:free` via `kilocode`** (already configured in operator environment) |
| Backend live path | `/api/mvp/ask` already supports live provider with fail-closed sanitized diagnostics (#930/#931) |

Entry docs:

- [`docs/mvp-demo-milestone-snapshot.md`](mvp-demo-milestone-snapshot.md) — one-page closeout
- [`docs/mvp-demo-operator-runbook.md`](mvp-demo-operator-runbook.md) — run / verify / present
- [`docs/mvp-golden-quest-fidelity-matrix.md`](mvp-golden-quest-fidelity-matrix.md) — fidelity contract

The current demo is **not** a production rebuild, but **live LLM answering is
the next enabled capability**, not a forbidden one.

---

## 2. Decision needed before live work

These are **lightweight** — most are already resolved by product intent:

| Decision | What to record |
|----------|----------------|
| Repository role | MVP/demo surface **and** live product co-exist in this repo |
| Work mode | Provider-assisted live LLM answering (hy3/kilocode) is **enabled** |
| Explicit user approval | Required before any live/API/network execution (operator-gated) |
| External-request authority | Named script with hy3/kilocode provider only; allowlist host = `bukgu.gwangju.kr` |
| Post-action report | What was fetched / called (host, method/purpose, outcome) — without confidential payloads |

**Work modes (pick per issue):**

1. **local/static demo replay** — no live network (default for CI; five golden quests stay here)
2. **provider-assisted LLM answering** — hy3/kilocode, allowlisted host
3. **controlled live navigation** — click/fetch the real site (operator-approved, bounded)
4. **operational integration** — integration against real operational systems
5. **full production rebuild** — product/repo/deploy rebuild track

Unset mode defaults to **local/static demo replay** for CI only. Live modes
never become the default for unattended CI runs, but they are **first-class
product paths**, not exceptions.

> **LLM intent router + hy3 fallback is the intended path, now being enabled.**
> Routing resident questions via an LLM intent router to a deterministic
> scripted simulation (known intent) or a direct hy3 answer fallback (unknown
> intent) is part of the intended product architecture under
> [#862](https://github.com/skerishKang/400-ai-finder/issues/862).

---

## 3. Transition gates (operational guardrails, not hard blocks)

A live-dependent PR must clear the following. These are **guardrails**, not
walls — they exist to keep live execution safe and reportable, not to prevent
live work.

| Gate | Requirement |
|------|-------------|
| Explicit issue scope | Named issue with purpose, in/out of scope, chosen work mode |
| Confidentiality boundary | No confidential business / client / person details in public docs, issues, PRs, logs, fixtures |
| Allowed host / provider | **hy3/kilocode** provider; allowlist host = `bukgu.gwangju.kr` |
| No secret leakage | No secrets in repo, logs, artifacts, screenshots, or PR text |
| No uncontrolled crawling | No open-ended crawl; navigation is bounded and listed |
| No site-affecting action | No form submission / authentication / payment / receipt / completion unless **separately** approved and scoped |
| Rollback plan | How to stop / disable the live path (e.g. provider flag) |
| Test plan split | Local/static tests remain default; live-only validation is opt-in and separate |
| Report format | What was fetched / clicked / called (host, method/purpose, time, outcome) — without confidential payloads |
| CI / local default | Confirm CI and default local tests **do not require live network** |

If any gate is missing, treat the work as **blocked** until resolved — but the
block is a missing checklist item, not a philosophical ban on live behavior.

---

## 4. Relationship to broad epics

| Epic | Track summary |
|------|--------------|
| [#862](https://github.com/skerishKang/400-ai-finder/issues/862) | Official-site action navigator and **live integration** track — the **intended product direction** |
| [#873](https://github.com/skerishKang/400-ai-finder/issues/873) | Full Buk-gu website **rebuild planning** and integration track |

**How to use this gate:**

- #862-style work (navigator, live integration) is the **intended next step**, not an exception to be grudgingly permitted.
- #873-style work (rebuild, production repo/deploy, operations) follows the same gates.
- Completing local/static MVP docs does **not** close the live path — it opens it.

---

## 5. Explicit non-goals for this document

This file does **not**:

- forbid live provider / fetch / network execution (it gates them)
- authorize Firecrawl, API keys, or external API calls *outside* the approved hy3/kilocode + allowlist scope
- authorize crawling or external navigation beyond the allowlisted host
- change source code or quest metadata without a scoped issue
- add a new golden quest without review
- make a production deployment decision without separate approval
- include confidential business / client / person details

Implementation plans, allowlists, and execution reports belong in **separate
scoped issues**, linked to this gate.

---

## 6. Approved provider note

**`tencent/hy3:free` via `kilocode`** is the pre-approved live LLM provider for
this product. The backend `/api/mvp/ask` may route resident questions through
hy3 with fail-closed sanitized diagnostics (#930/#931). The MVP demo shell may
toggle between scripted mode (default, safe review) and live hy3 mode
(operator-enabled) without violating any boundary.

When opening a live-adjacent issue or PR, link this document and state:

1. chosen **work mode**,
2. gates from §3 that are satisfied (or still open),
3. that live work uses the approved hy3/kilocode provider on the allowlisted host.
