# Official-Site Route Inventory First Local-Static Seed Records

> **Clone invariant:** 좌측 시민 사이트의 공식 페이지 clone은 [canonical invariant](product/exact-official-site-clone-invariant.md)를 따른다. 이 historical/planning 문서의 내용은 exact-clone 계약을 약화하지 않는다. Live retrieval이나 분석은 canonical fixture 기반 왼쪽 화면을 대체하지 않는다.

Planning-only **seed records** for the first local/static route inventory scope
under the [#862](https://github.com/skerishKang/400-ai-finder/issues/862)
official-site action navigator track.

> **Local/static only — NOT live/provider/API/network authorization.**
> This document is **local/static only** and uses **repository-local/static
> inputs only**. It performs **no** live browsing, crawling, fetch, provider/API,
> Firecrawl, or network execution, collects **no** route URLs, adds **no**
> selectors or screenshots, and adds **no** newly discovered official-site facts.
> The `route_url` field is deliberately **not collected** for these local/static
> records. This document does **not** authorize live/provider work; any future
> collection still requires a separately scoped, explicitly approved issue plus
> the gates in
> [`docs/live-transition-decision-record.md`](live-transition-decision-record.md).

---

## Planning / source boundary

- **local/static only** — no live network, no provider, no API.
- **repo-local/static inputs only** — see Inputs used.
- **no** live/provider/API/fetch/network execution in this PR.
- **no** route URL collection — `route_url` is `not_collected_local_static` / `N/A`.
- **no** selectors or screenshots.
- **no** newly discovered official-site facts added in this PR.
- **no** confidential business / client / person details.
- this document **does not authorize live/provider work** by itself.

---

## Inputs used

| Input | Role |
|-------|------|
| [`docs/official-site-route-inventory-plan.md`](official-site-route-inventory-plan.md) | Inventory record schema and field rules |
| [`docs/official-site-route-inventory-first-scope-selection.md`](official-site-route-inventory-first-scope-selection.md) | First-scope candidate selection (repo-local/static) |
| [`docs/official-site-route-inventory-first-scope-issue-draft.md`](official-site-route-inventory-first-scope-issue-draft.md) | Draft issue package for the local/static scope |
| [`docs/mvp-golden-quest-fidelity-matrix.md`](mvp-golden-quest-fidelity-matrix.md) | Existing local/static golden-quest references (read-only) |
| [`docs/official-site-route-inventory-post-action-report-template.md`](official-site-route-inventory-post-action-report-template.md) | Post-action report format (used in PR body) |
| [`docs/live-transition-decision-record.md`](live-transition-decision-record.md) | Work modes and live-transition gates |

No external source was consulted. Existing golden-quest references are used
strictly as read-only inputs and were not changed.

---

## Inventory seed record table

Three local/static candidates from the first-scope selection plan. Field values
are derived from the committed repo docs/sections only. `route_url` is not
collected; `last_verified_at` does not claim live verification.

### R1 — housing_department_lookup

| Field | Value |
|-------|-------|
| `inventory_id` | `inv_housing_department_lookup` |
| `source_site` | Buk-gu official site profile (local/static reference only) |
| `route_url` | `not_collected_local_static` (N/A) |
| `route_title` | 아파트 정보 안내 |
| `breadcrumb` | `북구청 홈 > 분야별정보 > 건축 > 아파트정보 > 아파트현황` (from fidelity matrix, read-only) |
| `primary_menu` | 분야별정보 |
| `secondary_menu` | 건축 |
| `resident_task` | 아파트 정보 안내 (주거 현황/동수/층수/세대수 안내) |
| `content_summary` | Local/static guidance for apartment-status lookup; no operational submit. |
| `required_user_inputs` | none (guidance only) |
| `external_handoff_target` | none (local_static) |
| `site_affecting_actions` | none |
| `auth_required` | no |
| `payment_required` | no |
| `personal_data_required` | no |
| `safe_demo_mode` | `local_static` |
| `allowed_future_work_mode` | `local/static demo replay` |
| `evidence_reference` | `docs/mvp-golden-quest-fidelity-matrix.md` §1 |
| `last_verified_at` | `not_live_verified` |
| `notes` | Existing local/static golden quest; no route URL collected. |

### R2 — bulky_waste_disposal_guidance

| Field | Value |
|-------|-------|
| `inventory_id` | `inv_bulky_waste_disposal_guidance` |
| `source_site` | Buk-gu official site profile (local/static reference only) |
| `route_url` | `not_collected_local_static` (N/A) |
| `route_title` | 대형폐기물 배출 안내 |
| `breadcrumb` | `북구청 홈 > 분야별정보 > 환경재활용 > 대형폐기물 배출방법` (from fidelity matrix, read-only) |
| `primary_menu` | 분야별정보 |
| `secondary_menu` | 환경재활용 |
| `resident_task` | 대형폐기물 배출 안내 |
| `content_summary` | Local/static guidance for bulky-waste disposal method; possible external handoff noted. |
| `required_user_inputs` | none (guidance only) |
| `external_handoff_target` | none for local/static demo (external disposal-service handoff noted as guidance) |
| `site_affecting_actions` | none |
| `auth_required` | no |
| `payment_required` | no |
| `personal_data_required` | no |
| `safe_demo_mode` | `local_static` |
| `allowed_future_work_mode` | `local/static demo replay` |
| `evidence_reference` | `docs/mvp-golden-quest-fidelity-matrix.md` §3 |
| `last_verified_at` | `not_live_verified` |
| `notes` | Existing local/static golden quest; no route URL collected. |

### R3 — public_health_center_guidance

| Field | Value |
|-------|-------|
| `inventory_id` | `inv_public_health_center_guidance` |
| `source_site` | Buk-gu official site profile (local/static reference only) |
| `route_url` | `not_collected_local_static` (N/A) |
| `route_title` | 보건소 위치·진료 안내 |
| `breadcrumb` | `북구청 홈 > 보건소 > 보건소소개 > 찾아오시는 길` (from fidelity matrix, read-only) |
| `primary_menu` | 보건소 |
| `secondary_menu` | 보건소소개 |
| `resident_task` | 보건소 위치·진료 안내 |
| `content_summary` | Local/static guidance for health-center location/hours/departments; no appointment submission. |
| `required_user_inputs` | none (no 본인인증 / 건강정보 input) |
| `external_handoff_target` | none (local_static) |
| `site_affecting_actions` | none |
| `auth_required` | no |
| `payment_required` | no |
| `personal_data_required` | no |
| `safe_demo_mode` | `local_static` |
| `allowed_future_work_mode` | `local/static demo replay` |
| `evidence_reference` | `docs/mvp-golden-quest-fidelity-matrix.md` §5 |
| `last_verified_at` | `not_live_verified` |
| `notes` | Existing local/static golden quest; no route URL collected. |

---

## Out-of-scope block

Explicitly excluded from this local/static seed record set:

- `illegal_parking_report_guidance` — report-channel handoff with identity/photo/location inputs; stays do-not-demo until separately scoped.
- `move_in_report_guidance` — Government24 handoff with auth; stays do-not-demo until separately scoped.
- **auth / payment / personal-data / site-affecting actions** — excluded.
- **external handoff execution** — guidance only; no execution.
- **live validation** — not performed.
- **provider/API/Firecrawl/fetch/network execution** — excluded.
- **whole-site cataloging** — resident-task-relevant routes only.
- **production / full-site rebuild decisions** — deferred to [#873](https://github.com/skerishKang/400-ai-finder/issues/873) if ever required.

---

## Relationship to #862 and #873

- [#862](https://github.com/skerishKang/400-ai-finder/issues/862) remains the **parent** for official-site action navigator / route inventory planning.
- [#873](https://github.com/skerishKang/400-ai-finder/issues/873) is only for production / full-site rebuild escalation.

This local/static seed record set does not authorize live work by itself; any
future step still requires the linked gates and a separately scoped, explicitly
approved issue.
