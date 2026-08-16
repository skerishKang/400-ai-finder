# Buk-gu AI MVP Reference Specification (#1329 Stage A)

- status: reference-spec (audit artifact)
- audited base: `origin/main` = `007fa1e5c9a00ef03a72075c96773440c47b50da`
- scope: reverse-engineer the CURRENT Buk-gu MVP implementation (code / config / fixtures / SiteSpec / renderer / quests / routing / tests / browser E2E / CI / evidence / lifecycle docs) so that "what Seo-gu must reproduce to reach Buk-gu-level AI Finder MVP" can be judged from this single document.
- method: direct inspection of committed repository evidence only. No live site, provider, or network access. Historical docs never outrank actual code/tests; code and tests on current main are the source of truth.
- audience: #1328 (Seo-gu AI-on-clone) Phase 0 input; Stage B municipality onboarding playbook extraction.

Status vocabulary used below follows `docs/product/PRODUCT_TRACKS_AND_BOUNDARIES.md` and `docs/implementation/RELEASE_GATES.md`. Where a capability does not exist as claimed, it is recorded as `NOT_FOUND`, `PARTIAL`, `HISTORICAL_ONLY`, or `NOT_RUNTIME_WIRED` — never invented.

---

## 1. Product surface anatomy (what a resident actually opens)

The Buk-gu MVP is a local web app with two servers and one resident page:

- Citizen (mobile-first) server — `src/web/mobile_demo.py`
  - `GET /` serves `mobile_demo.html`; `GET /mvp` → 302 to `/mvp?mvp=1` then serves `src/web/static/citizen-action-demo.html` (`mobile_demo.py:69-113`)
  - `POST /api/ask` — full retrieval pipeline via `SiteDemoRunner` (`mobile_demo.py:84-233`)
  - `POST /api/mvp/ask` — quest/LLM action-decision endpoint returning the frozen MVP envelope (`mobile_demo.py:235-339`)
- Admin (desktop) dashboard — `src/web/admin_demo.py` (`/api/info`, `/api/test` with site_id/provider/preset override, runner cache)
- Static assets served by hardened traversal-safe `/static/` handler (`src/web/static_server.py:40-104`)

The resident surface `citizen-action-demo.html` is a split shell: clone canvas (`#demo-canvas`) on one side, AI conversation pane (`#chat-shell`, chips, composer) on the other; layout state machine `data-first-use-state="entry|transitioning|split"` owned by `citizen-first-use-shell.js`; mobile mode via `(max-width:767px)` matchMedia sync of `data-mobile-surface` (no UA sniffing). Journey axis (`entry|answer|confirm|navigate|result`) is independent of layout state.

---

## 2. The 30 dissection items

Each item records: capability, primary paths (path:line on audited main), owning tests, config/fixture, runtime role, failure behavior, safety boundary, generity class, Seo-gu parity requirement, and no-regression obligation. Generity classes: `GENERIC_REUSABLE_AS_IS`, `GENERIC_BUT_BUKGU_ASSUMPTION_EXPOSED`, `BUKGU_DATA_CONFIG_THEME`, `BUKGU_GOLDEN_COMPATIBILITY_ONLY`, `REVIEWED_OVERRIDE`, `UNSUPPORTED_OR_EXCEPTION`.

### A. PRODUCT SURFACE

#### A1. Left-side faithful Buk-gu clone
- PRIMARY_PATHS: `src/web/static/citizen-action-demo.html:281-287` (`#demo-canvas`); `src/web/static/citizen-action-demo-canvas.js` (route rendering `_renderRoute:3489`, `navigateToRoute:3720`, DOM commit `_commitRouteDom:3707`); approved home renderer `_renderApprovedHome:1594`; fixture projection `_renderHomeFixtureProjection:1485`.
- CONFIG/FIXTURE: `data/official_clone_fixtures/bukgu_gwangju/home.json` (24,715 lines; `fixture_id=bukgu_gwangju.home.clone.2026-07-15`, `fixture_sha256=81b27b98…`, `status=fixture_ready_renderer_not_wired`, `clone_status=capture_required`, `exact_clone_claimed=false`); client mirrors `src/web/static/bukgu-home-clone-fixture.js` (`window.__BUKGU_HOME_CLONE_FIXTURE__`, generated, never hand-edited) and `bukgu-official-snapshots.js` (`window.__BUKGU_OFFICIAL_SNAPSHOTS__`, 5 snapshots: apartment-dept, bulky-waste, current-mayor, passport-guidance, unmanned-kiosk).
- RUNTIME_ROLE: client-side only; the browser never fetches Python clone pipeline output. Renderer selection is gated fail-closed by `clone-renderer-approval-gate.js` (query params `renderer`, `approval-state`, `resident-default`, `visual-review-state` are forbidden selection inputs, lines 17-28); registry `clone-renderer-approval-registry.js:28-40` pins approved id `bukgu_gwangju.home.designed.approved` vs candidate `bukgu_gwangju.home.fixture.candidate`.
- FAILURE_BEHAVIOR: explicit unavailable states (`_renderHomeFixtureUnavailable:1373`, `_renderHomeApprovalUnavailable:1574`) — never a fabricated page.
- OWNING_TESTS: `tests/test_bukgu_home_clone_fixture_projection.py`, `tests/test_home_fixture_canvas_parity.py`, `tests/test_bukgu_home_asset_identity_audit.py`, `tests/test_clone_visual_approval_gate.py`.
- SAFETY: inert `aria-disabled` links for non-modeled destinations (renderer contract); no auto-mutation from the live source.
- GENERICITY_CLASS: `BUKGU_GOLDEN_COMPATIBILITY_ONLY` (the canvas route DOM and approved renderer are Buk-gu golden content) — but the approval-gate/registry mechanism is `GENERIC_REUSABLE_AS_IS`.
- SEO_GU_PARITY: Seo-gu must produce its own baseline → fixture → candidate → owner-approved renderer per the G1–G5 ladder; the gate/registry mechanism is reused as-is.
- NO_REGRESSION_OBLIGATION: frozen per `docs/bukgu-golden-compatibility-manifest.md` (17 route ids, 28 target ids, stable DOM ids, window APIs). Any change requires a migration issue + dual-read period.

#### A2. Right-side AI conversation surface
- PRIMARY_PATHS: `citizen-action-demo.html:118-176` (chips with exact Korean questions, composer); `citizen-first-use-shell.js` (state machine, `SUPPORTED_QUESTION_ACTIONS:26-42` question→action map); `citizen-mvp-bridge.js` (`POST /api/mvp/ask` call `:171`, normalization `:185-207`, frozen failure envelope `_stableFailure:118-143`, single in-flight abortable request `:156-161`).
- RUNTIME_ROLE: MVP mode (`?mvp=1`) sends `{question, locale, session_id}` and receives the frozen envelope `{ok, question, answer, action, confidence, provider, model, failure_code, quest?, action_plan?}` plus freshness fields (`mobile_demo.py:275-339`).
- FAILURE_BEHAVIOR: network/abort/parse failure → frozen `{ok:false, action:"none"}` envelope; server never returns 5xx/traceback (outer exception → HTTP 200 with fixed Korean fallback answer, `route_reason:"outer_exception"`, `mobile_demo.py:194-233`).
- OWNING_TESTS: `tests/test_mobile_demo.py`, `tests/test_citizen_action_demo_nonpersistence.py`, `tests/test_mvp_failure_codes.py`.
- GENERICITY_CLASS: `GENERIC_BUT_BUKGU_ASSUMPTION_EXPOSED` — mechanism generic; chip vocabulary and `SUPPORTED_QUESTION_ACTIONS` keys are Buk-gu question strings that must be replaced by Seo-gu data (and today exist in FOUR copies that must stay in sync: HTML chips ↔ shell map ↔ choreography `JOURNEY_MAP` ↔ server quest registry; see §6).
- SEO_GU_PARITY: rebuild chip/question vocabulary from Seo-gu quests; reuse bridge/contract as-is.

#### A3. Desktop/mobile layout & state owner
- PRIMARY_PATHS: `citizen-first-use-shell.js:11-19` (state attrs), `:1278-1390` (mobile matchMedia); examples surface `src/web/examples/page-agent/resident/resident-demo.js:39` (`(max-width:768px)`).
- OWNING_TESTS: browser E2E under `tests/browser` (viewport contracts per the golden manifest), `tests/test_citizen_action_demo_canvas.py`.
- GENERICITY_CLASS: `GENERIC_REUSABLE_AS_IS`.
- SEO_GU_PARITY: reuse; only locale strings change (`citizen-i18n.js` — branding strings currently say "BUKGU AI CIVIC NAVIGATOR" per locale, `citizen-i18n.js:27,170,291,412,533`).

#### A4. Resident entrypoints / route topology
- PRIMARY_PATHS: `GET /`, `GET /mvp` (`mobile_demo.py:69-78`); admin `GET /` (`admin_demo.py`); compare page `src/web/compare/index.html`; Page Agent example `src/web/examples/page-agent/resident/index.html` (NOT_RUNTIME_WIRED — no Python handler for `POST /api/page-agent/plan` exists in `src/`; the client degrades to a `disabled` state).
- GENERICITY_CLASS: `GENERIC_REUSABLE_AS_IS` (servers parameterized by site_id; default `site_id="bukgu_gwangju"` at `mobile_demo.py:47,351`, `admin_demo.py:60,396`).

### B. CLONE / REFERENCE

#### B5. Canonical Buk-gu SiteSpec/profile
- PRIMARY_PATHS: `configs/sites/bukgu_gwangju.sitespec.json` (site_id=`bukgu_gwangju`, legacy_ids=`["bukgu"]`, domain=`bukgu.gwangju.kr`, golden_commit `7217c0f7…`); `configs/sites/bukgu_gwangju.yml:5-9` (base_url, host allowlist); `configs/site-registry.json` (default_site_id `bukgu`, role `reference_adapter`, 7 frozen contract sources); loader `src/site_profiles/site_profile.py:103`; v2 projection `src/site_profiles/sitespec_v2_projection.py:28-29` (DEFAULT source refs hardcode the bukgu files); client mirror `src/web/static/citizen-sitespec-metadata.js:44`.
- GENERICITY_CLASS: data = `BUKGU_DATA_CONFIG_THEME`; projection defaults = `GENERIC_BUT_BUKGU_ASSUMPTION_EXPOSED` (Seo-gu must become the default or the default must be de-pinned — a reviewed decision).
- OWNING_TESTS: `tests/test_site_compatibility_registry.py`.
- SEO_GU_PARITY: author `configs/sites/seogu_gwangju.sitespec.json` + yml + registry entry; reuse loader as-is.

#### B6. Reference fixture/snapshot identities
- PRIMARY_PATHS: home fixture (A1); `bukgu-official-snapshots.js` (5 snapshots); provenance chain documented in `docs/bukgu-golden-compatibility-manifest.md`: authorized capture → canonical fixture JSON → generated projection (never hand-edited) → renderer.
- GENERICITY_CLASS: `BUKGU_GOLDEN_COMPATIBILITY_ONLY` (identities are frozen); the provenance-chain tooling (`src/official_clone/*`) is generic.

#### B7. Route/menu/content/state model
- PRIMARY_PATHS: offline pipeline `src/official_clone/home_region_parser.py` (deterministic segmentation; **hardcoded** `APPROVED_HOST="bukgu.gwangju.kr"`, `BASE_URL`, lines 30-33), `reference_clone_model.py` (G2-A generic model builder, fail-closed checksum/SHA/path validation, no site literals), `reference_clone_renderer.py` (G2-B model-driven renderer, raises unless `reference_baseline_ready`, `aria-disabled` inert links). These are the generic pipeline Seo-gu G1/G2 already uses.
- RUNTIME_ROLE: Python pipeline produces fixtures; the resident runtime consumes the generated JS mirrors (A1). NOTE: for Buk-gu the fixture status is `fixture_ready_renderer_not_wired` — the Python renderer is not wired into the resident page; the resident page uses the designed/approved renderer.
- OWNING_TESTS: `tests/test_official_home_region_segmentation.py`, `test_reference_clone_model.py`, `test_reference_clone_renderer.py`, `test_renderer_route_manifest_fidelity.py`, `test_visual_contract.py`.
- GENERICITY_CLASS: model/renderer/visual-contract = `GENERIC_REUSABLE_AS_IS`; parser host allowlist = `GENERIC_BUT_BUKGU_ASSUMPTION_EXPOSED` (must come from site config).

#### B8. Visual/asset/provenance contracts
- PRIMARY_PATHS: `src/official_clone/visual_contract.py` (every measured CSS value bound to exactly one evidence record; sole presentation source for the renderer); asset root `/static/images/bukgu-current` (`citizen-action-demo-canvas.js:138` and 6 more sites); asset identity audited by `tests/test_bukgu_home_asset_identity_audit.py`.
- GENERICITY_CLASS: contract mechanism `GENERIC_REUSABLE_AS_IS`; assets `BUKGU_DATA_CONFIG_THEME`.

#### B9. Golden/frozen/rollback identities
- PRIMARY_PATHS: `docs/bukgu-golden-compatibility-manifest.md` (freeze at `7217c0f`, #1187): 17 frozen route ids and 28 frozen target ids — the manifest explicitly declares `citizen-action-demo-map.js` as the **read-only source of truth** for the frozen civic route/target vocabulary (`CLOSED_ROUTE_IDS` = 17, `CLOSED_TARGET_IDS` = 28, `citizen-action-demo-map.js:36-85`); frozen DOM ids/state vocabularies, frozen public window APIs (`CitizenActionDemoMap`, `CitizenActionDemoCanvas`, `CitizenFirstUseShell`, `CitizenFirstChoreography`, fixture globals), Page Agent parity scenarios; rollback artifact required for Gate A. The Python `CitizenActionPlan` executable allowlist is a SEPARATE contract (18 targets — see C13), NOT an exact mirror of the 28-target client/golden vocabulary.
- GENERICITY_CLASS: `BUKGU_GOLDEN_COMPATIBILITY_ONLY`; breaking changes require migration issue + dual-read + exact-head CI + stakeholder review.

### C. AI / RUNTIME

#### C10. Resident question/input contract
- PRIMARY_PATHS: `/api/mvp/ask` input `{question, locale, session_id}` (`citizen-mvp-bridge.js:171`); `/api/ask` retrieval envelope with sanitized `fetch_diagnostic` (Stage #801 closed vocabulary, `mobile_demo.py:157-188`); 5 locales (ko/en/vi/th/id) via `citizen-i18n.js`; vocabulary manifest `configs/contracts/runtime-vocabulary.json`.
- GENERICITY_CLASS: `GENERIC_REUSABLE_AS_IS` (contract), locale content `BUKGU_DATA_CONFIG_THEME`.

#### C11. Intent/routing/classification — three-tier, deterministic-first
- Tier 1 (golden, no LLM): quest router `src/agent/quest_router.py` — exact/substring/token scoring (`_phrase_score:47-72`, `_term_score:75-103` requires ≥2 match_terms + domain_term + intent_term, capped 0.88), threshold ≥0.72 else `unsupported` (`:106-142`). Loaded from `data/quests/bukgu_gwangju_quests.json` via `src/agent/quest_registry.py:13-15,73`. Checked BEFORE the LLM in `decide_bukgu_mvp_action` (`src/llm/bukgu_mvp_router.py:180-210,274-276`).
- Tier 2 (model): `bukgu_mvp_router.py` MVP_SYSTEM_PROMPT classification into the 8 `MVP_ACTIONS` (`:42-51`); JSON extraction with failure codes.
- Tier 3 (site search): `src/llm/site_search_router.py` — LLM-first `site_search|direct_answer|clarify`, **positive fallback to site_search** on any provider failure (`:103-117,199-205`); fail-open here is backstopped by answer-side guards (C17).
- OWNING_TESTS: `tests/test_bukgu_quest_schema.py`, `test_mvp_golden_quest_fidelity_matrix.py`, `test_site_search_router.py`, `test_mvp_action_contract.py`.
- GENERICITY_CLASS: router mechanisms `GENERIC_REUSABLE_AS_IS`; quest data `BUKGU_DATA_CONFIG_THEME`; MVP_ACTIONS vocabulary + prompt's "광주광역시 북구청" literals = `BUKGU_GOLDEN_COMPATIBILITY_ONLY` for Buk-gu — for Seo-gu they must move into site-keyed data/config consumed by the SHARED router (no parallel `seogu_mvp_router.py` engine; see §5 row 19).

#### C12. Grounded site knowledge/retrieval
- PRIMARY_PATHS: `src/pipeline/pipeline_runner.py` — 5-stage offline pipeline (homepage_map → document_index → enriched_index → search → answer), fail-per-step; site_id resolution fail-closed on ambiguity (`:268-303`); deterministic candidate merge/dedup by canonical_url (`:414-490`); question-log with `fallback_used` detection (`:199-261`). Retrieval: `src/search/keyword_searcher.py` (Korean particle stripping, tokenized search over enriched JSONL). Query expansion: `src/search/query_rewriter.py` (deterministic regex rules, strategy `deterministic_v1`, site synonym dictionary from site profile by site_id).
- OWNING_TESTS: `tests/test_pipeline_runner.py`, `test_keyword_searcher.py`, `test_query_rewriter.py`, `test_query_rewriter_pipeline_integration.py`, `test_bukgu_crawl_filters_pipeline_regression.py`.
- GENERICITY_CLASS: `GENERIC_REUSABLE_AS_IS` (parameterized by site profile/index), except a few bukgu/Gwangju expansion terms and topic keywords (see §6).

#### C13. Action graph / target resolution
- PRIMARY_PATHS: server contract `src/agent/citizen_action_plan.py` — closed allowlists of action types, route_ids and target_ids (lines 36-83), forbidden `LOGIN/SUBMIT/UPLOAD_FILE/PAY/ENTER_IDENTITY` (`:40-46`), pure `build_citizen_action_plan:428` / `validate_citizen_action_plan:463` (no LLM, no DOM). Client contract `citizen-action-demo-map.js:36-85` — golden-manifest-declared source of truth for the frozen client vocabulary, with validators `isValidRoute/isValidTarget:285-296`. Quest→plan: `src/agent/quest_to_action_plan.py:51-73` (hard-raises on `ai_can_prefill/ai_can_submit` true, unknown action type, or last action ≠ stop_condition).
- VOCABULARY OWNERSHIP — the two contracts are NOT identical mirrors for targets:
  - client/golden map target vocabulary = **28** target ids (`CLOSED_TARGET_IDS`);
  - Python `CitizenActionPlan` executable target allowlist = **18** target ids (`_VALID_TARGET_IDS:56`);
  - route ids currently align 17/17 (`CLOSED_ROUTE_IDS` ≡ `_VALID_ROUTE_IDS`);
  - the 10 client/golden targets absent from the Python executable set: `nav-apartment-dept`, `nav-bulky-waste-disposal`, `nav-passport-guidance`, `nav-complaint-board`, `complaint-write`, `complaint-board-return`, `mayor-office-open`, `mayor-message-write`, `mayor-write-return`, `mayor-receipt-home`;
  - the JS file retains comments claiming an exact mirror of `citizen_action_plan.py`, but the executable constants do not support that claim for targets — the sets, not the comments, are the evidence.
  - Whether the 18-target Python set is an intentional executable subset or accidental drift is `NOT_PROVEN_FROM_COMMITTED_EVIDENCE`. Stage A records the divergence only; no runtime fix is authorized here.
- OWNING_TESTS: `tests/test_citizen_action_plan.py`, `test_citizen_action_acceptance_matrix.py`, `test_bukgu_quest_to_action_plan.py`.
- GENERICITY_CLASS: schema/validators `GENERIC_REUSABLE_AS_IS`; the id vocabularies are `BUKGU_GOLDEN_COMPATIBILITY_ONLY` for Buk-gu and must be re-authored as Seo-gu data. The unresolved 28/18 target alignment between the client vocabulary and the server-executable allowlist is a `GENERIC_CONTRACT_GAP` (see §6/§8) that must be resolved by a defined shared schema/ownership relationship before onboarding site #3 — without claiming the sets are identical.

#### C14. Click/navigation orchestration (NO post-navigation READ)
- PRIMARY_PATHS: `citizen-action-executor.js` — strict plan normalization (exact field sets, 1-12 actions, terminal STOP, ≤1 PREFILL as penultimate, `:72-186`); executes HIGHLIGHT/SCROLL/OPEN_ROUTE/CLICK/PREFILL; CLICK requires the target be a BUTTON and in the current route's `navTargets` (`:313-322`); PREFILL pauses for explicit user confirmation (`:263-268,329-368`); violations → `_handleBlocked` "허용되지 않은 동작으로 안전하게 중단했습니다" (`:370-388`). Canvas: `data-action-target="<targetId>"` selector convention (`getTargetElement:3773-3777`), `navigateToRoute:3720` validates against map. Choreography: `citizen-first-choreography.js` — deterministic journey map keyed by exact Korean questions + MVP action aliases; query-driven replay (`?replay=J-DEPT-01&replay-mode=auto`, canvas `:451,3963-4026`); no fetch/persistence (header 1-15).
- IMPORTANT — there is **no post-navigation READ action**: neither `quest_schema.py` (OPEN_ALLOWLISTED_ROUTE / SEARCH_ALLOWLISTED_QUERY / SHOW_ALLOWLISTED_RESULT / STOP only) nor `citizen_action_plan.py` (highlight/scroll/open/click/prefill/stop) nor the executor contains a DOM-read step, and no evidence-to-answer recomputation happens after navigation. Current orchestration is bounded navigation/show choreography whose answer was already resolved before the plan executes (see C15). **Post-navigation read-to-answer coupling is a current GAP** that #1328 must evaluate explicitly rather than treating visual navigation as read-based Browser Use.
- OWNING_TESTS: `tests/test_citizen_action_demo_canvas.py`, `tests/test_citizen_complaint_journey.py`, browser E2E under `tests/browser` (32 .mjs verify scripts on the audited main).
- GENERICITY_CLASS: executor `GENERIC_REUSABLE_AS_IS`; choreography journeys `BUKGU_GOLDEN_COMPATIBILITY_ONLY` (question strings, cursor selectors like `.bg-illegal-parking-card`, `#btn-board-write`).

#### C15. Deterministic/golden flows (answer pre-resolved, not read-derived)
- PRIMARY_PATHS: `data/quests/bukgu_gwangju_quests.json` — 5 quests (`housing_department_lookup`, `illegal_parking_report_guidance`, `bulky_waste_disposal_guidance`, `passport_guidance`, `unmanned_kiosk_guidance`), each `status:"phase1_golden"`, `source_mode:"local_static"`, browser_actions limited to OPEN_ALLOWLISTED_ROUTE / SEARCH_ALLOWLISTED_QUERY / SHOW_ALLOWLISTED_RESULT / STOP_* (`quest_schema.py:9-52`), answers resolved lazily from `src/bukgu_official_snapshot.py` via `official_snapshot_ref` (`quest_schema.py:117-134`).
- IMPORTANT — the answer is **pre-resolved from the snapshot when the plan is built** (`quest_to_action_plan.py`: `answer=quest.answer`); the left-side navigation/show choreography then runs as a bounded visual demonstration and stops. The current golden flow is: `question → deterministic quest match → pre-resolved snapshot-backed answer + bounded local navigation/show choreography → STOP` — NOT `question → click/navigate → read resulting DOM → derive answer from that read`. The product-level prompt's "content read → grounded answer" step is therefore `PARTIAL` today (read is not an action-graph step; grounding comes from the frozen snapshot, executed before navigation). #1328 must not silently treat Buk-gu's visual navigation as read-based Browser Use.
- OWNING_TESTS: `tests/test_mvp_golden_quest_fidelity_matrix.py`, `test_bukgu_official_apartment_snapshot.py`.
- GENERICITY_CLASS: registry mechanism `GENERIC_REUSABLE_AS_IS` (data-driven; "adding more quests does not add router branches" — `quest_router.py:88-89`); quest content `BUKGU_DATA_CONFIG_THEME` (Seo-gu authors its own quest file + snapshot module).

#### C16. Provider-neutral/model fallback
- PRIMARY_PATHS: `src/llm/base.py` (`LLMProvider`/`ProviderResult`); registry `src/llm/__init__.py:53-102` (9 builtin providers: openai_compatible, mistral, opengateway, kilocode, nvidia, groq, opencode-go, opencode-zen, nous), `:154-216` resolution arg > `AI_FINDER_LLM_PROVIDER` env > **"mock" default** (no egress by default), `:251-307` env resolution chain. Transport `src/llm/openai_compatible_provider.py:121-306` — closed failure vocabulary (`:28-57`), never raises from `complete()`, never leaks exception/URL/key text. Runtime labeling `src/llm/runtime_status.py` (live vs mock/stub/snapshot with explicit "외부 LLM API 미사용").
- IMPORTANT FINDING (product-critical, distinct from provider abstraction) — the **out-of-site model-answer fallback** capability ("site evidence missing → resident receives a clearly labeled model answer that is NOT presented as site-grounded") is **`UNSUPPORTED_OR_EXCEPTION` in the current Buk-gu runtime**:
  - `/api/ask` + `answer_composer.py`: no/weak sources short-circuit to no-source guidance and do **not** call the LLM (`answer_composer.py:148-152,155-169`). The fallback envelope is honest but it is guidance, not a model answer.
  - `/api/mvp/ask` non-quest path can call an injected provider, but `bukgu_mvp_router.py` is an action-decision router over a closed 8-action Buk-gu vocabulary — it is NOT a general site-miss factual-answer fallback contract.
  - Therefore: a general "model answers when the site cannot, with explicit non-site-grounded provenance" contract does not exist on current main. #1328 must NOT inherit the assumption that it does.
- Separately (secondary, non-blocker): there is NO automatic multi-model failover chain. "Fallback" in the current implementation means only: (a) default mock provider when none configured, (b) per-call closed failure codes, (c) deterministic tier-1 quest path replacing the LLM entirely. `runtime_status.py` only labels status. The provider-neutral abstraction itself (this item's mechanism) remains `GENERIC_REUSABLE_AS_IS`.
- ALSO: no SSRF/allowlist guard on the LLM egress path — `openai_compatible_provider.py:166-171` does a raw `requests.post` to the configured base_url; the `PublicEgressPolicy`/`SiteAcquisitionPolicy` (`src/fetch/egress_policy.py`, enforced in `pipeline_runner.py:305-339`) covers only crawl/fetch. For the current offline MVP this is latent, not live.
- OWNING_TESTS: `tests/test_llm_providers.py`, `test_llm_runtime_status.py`, `test_stub_provider.py`.
- GENERICITY_CLASS: `GENERIC_REUSABLE_AS_IS` (bukgu-specific logic lives only in `bukgu_mvp_router.py`).

#### C17. Site-grounded answer vs model fallback distinction
- PRIMARY_PATHS: `src/answer/answer_composer.py` — SYSTEM_PROMPT restricts to source context, forbids fabricated URLs, mandates "관련 정보를 찾지 못했습니다" when no sources (`:22-62`); no-sources short-circuit WITHOUT calling the LLM (`:148-152`); source-match guard converts weak retrieval to no-results guidance (`:155-169`); URL allowlist guard hard-blocks any output URL not exactly matching a retrieved source's canonical URL → `guard_status="blocked_untrusted_output_url"` (`:201-216`). Fallback is structurally distinct: `_build_no_source_guidance` (`:331-370`) sets `provider="none"`, `sources=[]`, `guard_status="no_results"` — a fallback answer can never masquerade as grounded. `src/answer/url_guard.py` canonicalization blocks non-http(s), credentials, dot-segments. `src/answer/answer_status.py:33-56` closed 4-state enum (`answered_with_evidence` / `fallback_no_match` / `fallback_unavailable` / `error`).
- OWNING_TESTS: `tests/test_answer_composer.py`, `test_url_guard.py`, `test_stage803_answer_status_contract.py`, `test_stage806_answer_evidence_envelope.py`.
- GENERICITY_CLASS: `GENERIC_REUSABLE_AS_IS` (guidance hint menus are generic Korean district-office structure).

#### C18. Page Agent vs native AI Finder relationship
- FINDING: the "native AI Finder path" is the Python route `mobile_demo.py:264-316` → `decide_bukgu_mvp_action` → client choreography. "Page Agent" is a separate OFFLINE RESEARCH LAB at `src/web/examples/page-agent/` (upstream aladdin/page-agent fork, mock adapter, `parity-contract.json`, 5 canonical parity scenarios, forbidden "success" routes). The resident plan client (`resident-server-plan-client.js`) targets `POST /api/page-agent/plan`, for which NO Python handler exists — the UI degrades to `disabled`. Recorded: Page Agent = NOT_RUNTIME_WIRED research track (Track F), protected by golden CI parity contracts.
- OWNING_TESTS: `tests/test_page_agent_lab.py`, `test_page_agent_comparison_contract.py`, `test_page_agent_final_route_parity.py`.
- GENERICITY_CLASS: research artifact, `BUKGU_GOLDEN_COMPATIBILITY_ONLY` protection, no Seo-gu MVP obligation.

### D. SAFETY / GOVERNANCE

The four cardinal rules are encoded in FOUR layers, so no single-layer change can remove them:
1. contract JSON — quest browser actions forbid `LOGIN/SUBMIT/UPLOAD_FILE/PAY/ENTER_IDENTITY/PREFILL_APPROVED_DRAFT` (`quest_schema.py:40-52`), so quest-defined browser actions cannot directly request prefill. `CitizenActionPlan` separately forbids `LOGIN/SUBMIT/UPLOAD_FILE/PAY/ENTER_IDENTITY` (`citizen_action_plan.py:28-33`), while allowing only the bounded `PREFILL_APPROVED_DRAFT` case for `target_id=="complaint-body"` with no route/choice ids and `requires_user_confirmation==true` (`citizen_action_plan.py:322-331`), and plan-level validation additionally requires PREFILL to be immediately followed by STOP (`citizen_action_plan.py:385-387`).
2. JS validator — executor `_handleBlocked` on any plan-shape or target violation (`citizen-action-executor.js:72-186,370-388`); PREFILL requires explicit user confirmation
3. Python egress — pipeline `PublicEgressPolicy`/`SiteAcquisitionPolicy` (`src/fetch/egress_policy.py`, `pipeline_runner.py:305-339`) for the crawl/fetch layer (NOT the LLM path — see C16)
4. CI/evidence — `mvp-contracts.yml` (826 lines, 10 domain jobs + gate job) enforces no-network, golden fidelity, and evidence jobs; the golden manifest blocks Stage-5 live LLM in golden CI.

- D19 no-submit: composer demo mayor receipt is local-only (`citizen-complaint-journey*`; golden manifest "no real submission"). Tests: `tests/test_citizen_action_demo_nonpersistence.py`, `test_citizen_complaint_journey.py`.
- D20 no-login / D21 no-payment / D22 no-PII: forbidden action types (layer 1+2); non-persistence tests; evidence PR declarations per promotion policy §16. PII — precise current boundary:
  - TRUE: no dedicated identity-entry action, no login, no submit, no payment anywhere in the guided action contract; the system does not intentionally request identity data.
  - ALSO TRUE: `src/demo/conversation_log.py` persists `question`, `answer`, sources and provider/model metadata to `logs/conversations.jsonl` on the `/api/ask` path (`conversation_log.py:3-4,31,37,149`). Free-text questions can contain resident-supplied PII even without dedicated identity fields, so **incidental free-text PII transit/persistence is possible** unless separately sanitized/disabled. This is a current boundary/gap, not a satisfied guarantee.
  - Scope distinction: `/api/mvp/ask` golden-quest behavior does not use the conversation log (choreography is non-persistent, `citizen-first-choreography.js` header); the logging surface is the `/api/ask` retrieval path.
- D23 external network/provider policy: default mock provider (no egress); CI fully offline; live providers require explicit env config; live smoke requires a controlled approval packet (`docs/product/bukgu-controlled-live-smoke-approval-packet.md`, `bukgu-local-first-controlled-live-smoke-plan.md`).
- D24 same-origin/link safety: URL guard exact-canonical-URL allowlist (C17); origin allow-lists in golden manifest; parser `APPROVED_HOST` gate (B7); clone links to non-modeled destinations are inert/`aria-disabled`.
- D25 high-risk approval boundary: quests carry `final_warning` + `requires_user_confirmation`; executor STOP semantics; `requires_user_confirmation` flag from `quest_to_action_plan.py:70-73`.
- D26 fail-closed behavior: every layer — renderer raises without baseline; visual contract binds every CSS value to evidence; answer guards; provider closed failure codes; servers return sanitized 200 envelopes, never tracebacks.
- D27 clone vs actual-site separation: canonical policy (clone is point-in-time versioned artifact, never a live mirror, never auto-mutated); fixtures carry `exact_clone_claimed=false`; status ladder forbids conflating preview/baseline/candidate/MVP/exact; the live Buk-gu site is a reference source only.

All D items: GENERICITY_CLASS `GENERIC_REUSABLE_AS_IS` (safety architecture is the platform's core reusable asset). SEO_GU_PARITY: reproduce all four encoding layers for Seo-gu quests/action plans verbatim.

### E. VALIDATION

#### E28. Unit/contract/browser-E2E owners
- OWNING_TESTS (reproducible counts on audited main): Python suites — `ls tests/test_*.py | wc -l` → 160 test files (collection via pytest); browser suites — `ls tests/browser/*.mjs | wc -l` → 32 verify scripts under `tests/browser`; plus `functions/` contract tests. Counts are file counts, not collected test cases, and may drift — the owning suites/directories are the stable reference.
#### E29. Evidence
- Journey/comparison/visual evidence: promotion-policy §16 evidence table (base/head SHAs, per-viewport reference+candidate artifacts at 1440x900 full/split, 1440x760 split, 390x844 mobile), difference classification, rollback identity; visual approvals recorded under `docs/artifacts/visual-approvals/<site_id>/<route_id>/<pr>-<head-sha>/approval.md`; owner-only approval authority.
#### E30. CI exact-head / lifecycle / promotion gates
- Single workflow `.github/workflows/mvp-contracts.yml` — 10 domain jobs + gate job; exact-head squash merge with SHA lease; no CI weakening; gate ladder G0–G5 (RELEASE_GATES.md); no stage auto-promotes.

---

## 3. Buk-gu resident MVP end-to-end contract (CURRENT IMPLEMENTATION, not the ideal)

Grounded path (all five golden quests today):
1. Resident types/selects an exact question (chips lower the barrier to exact matching).
2. `POST /api/mvp/ask` → `decide_bukgu_mvp_action`: quest registry matched first (deterministic, no LLM).
3. On match ≥0.72: the answer is **pre-resolved** from the official snapshot module when the plan is built (`quest_to_action_plan.py`: `answer=quest.answer`), together with the action plan (route open → allowlisted result show → STOP for confirmation).
4. Client bridge returns the frozen envelope; choreography navigates the clone (`navigateToRoute`), highlights `data-action-target` elements, optionally types/prefills with explicit confirmation, and hard-stops at the quest's stop condition. **No post-navigation DOM read occurs and no answer is derived from the navigation** — the left-side motion is a bounded visual demonstration of a snapshot-backed answer that was already fixed.
5. Answer displayed with snapshot provenance (`official_path` breadcrumb, `official_snapshot_ref`); nothing is persisted.

So the current chain is precisely: `question → deterministic quest match → pre-resolved snapshot-backed answer + bounded local navigation/show choreography → STOP`. It is NOT yet `question → click/navigate → read resulting DOM/content → derive answer from that read`. Post-navigation read-to-answer coupling is a current gap #1328 must evaluate on its own merits.

Site-evidence-insufficient path (via `/api/ask`, the retrieval pipeline):
1. Question → deterministic query rewrite (site synonyms) → keyword search over the enriched index.
2. No/weak sources → source-match guard → LLM is NOT called; `_build_no_source_guidance` returns a structurally distinct fallback (`provider="none"`, `sources=[]`, `guard_status="no_results"`, Korean guidance to official menus) — fabricated site grounding is impossible by construction (no sources ⇒ no LLM call; any URL not in sources ⇒ blocked).
3. If a live provider is configured (it is NOT by default — mock is default), the composer may answer strictly from retrieved source context, with the URL allowlist guard as the final backstop. This is in-source grounded answering, not a site-miss model answer.
4. **Out-of-site model-answer fallback (`site evidence missing → general model answer, explicitly labeled non-site-grounded`) is UNSUPPORTED_OR_EXCEPTION on current main**: the no-source path returns guidance instead of a model answer, and the `/api/mvp/ask` non-quest provider path is an 8-action Buk-gu action-decision router, not a general factual-answer fallback contract. #1328 must not assume this capability exists.

Explicitly NOT implemented today: free-form Korean questions routing to arbitrary clone navigation outside the quest vocabulary (unsupported → MVP failure answer / clarify); Page Agent-driven navigation (NOT_RUNTIME_WIRED); out-of-site model-answer fallback (site-miss → labeled non-site-grounded model answer; UNSUPPORTED_OR_EXCEPTION); post-navigation read-to-answer coupling; automatic multi-provider failover (secondary); Seo-gu AI-on-clone is not implemented yet; the faithful-clone parent #1303 is CLOSED/COMPLETED and #1328 now owns the AI-on-clone proof.

---

## 4. Generity summary (counts of classified elements above)

- GENERIC_REUSABLE_AS_IS: provider abstraction; answer composer + URL guard + answer_status; pipeline runner; keyword searcher; query rewriter mechanism; strategy router; quest router/registry/schema mechanism; citizen action plan schema/validators; action executor; first-use shell/layout/bridge; clone model/renderer/visual-contract pipeline; approval gate/registry mechanism; site profile loader; web servers; safety architecture (all of D).
- GENERIC_BUT_BUKGU_ASSUMPTION_EXPOSED: sitespec_v2_projection default source refs; home_region_parser APPROVED_HOST; LLM egress path lacking an egress-policy guard; question-vocabulary quadruple duplication (HTML chips / shell map / choreography / server quests); citizen-i18n branding strings.
- BUKGU_DATA_CONFIG_THEME: SiteSpec/yml/registry data; home fixture + snapshots + assets; quest registry JSON; official snapshot answer module; locale strings.
- BUKGU_GOLDEN_COMPATIBILITY_ONLY: frozen route/target/DOM/window-API vocabularies (manifest); approved renderer id; choreography journeys; MVP_ACTIONS + MVP_SYSTEM_PROMPT literals; Page Agent lab.
- REVIEWED_OVERRIDE: none currently recorded (no explicit override registry entries found in runtime code).
- UNSUPPORTED_OR_EXCEPTION: out-of-site model-answer fallback (site-miss → labeled non-site-grounded model answer; see C16/§3 — the primary product gap); post-navigation read-to-answer coupling (C14/C15); automatic multi-provider failover chain (secondary); Page Agent resident plan backend (absent); `configs/contracts/runtime-vocabulary.json` is `inventory_only: true, runtime_wired: false` — a parity manifest asserted by `tests/test_shared_runtime_vocabulary_contract.py`, not a runtime dependency; note its `mayor_message_assist` action is absent from `MVP_ACTIONS` (`bukgu_mvp_router.py:42-51`) — a known vocabulary drift surface.

---

## 5. SEO-GU MUST REPRODUCE matrix

Legend: REUSE_AS_IS / CONFIGURE_FOR_SEOGU / BUILD_SEOGU_DATA_ARTIFACT / GENERALIZE_SHARED_CORE / REVIEWED_OVERRIDE / NOT_REQUIRED_FOR_SCOPED_MVP / UNSUPPORTED.

| # | Buk-gu capability | Proposal | Notes |
|---|---|---|---|
| 1 | Clone renderer approval gate + registry | REUSE_AS_IS | parameterize by site_id |
| 2 | reference_clone_model/renderer/visual_contract pipeline | REUSE_AS_IS | already used by Seo-gu G2 |
| 3 | home_region_parser host allowlist | CONFIGURE_FOR_SEOGU | move APPROVED_HOST to site profile (Stage B; Stage A records only) |
| 4 | Seo-gu SiteSpec/yml/registry entry | BUILD_SEOGU_DATA_ARTIFACT | vNext additive namespace per GENERIC_SITESPEC_VNEXT_VERSIONING_DECISION |
| 5 | Home fixture + snapshots + assets + provenance chain | BUILD_SEOGU_DATA_ARTIFACT | via G1 capture; owner approval required |
| 6 | Quest registry JSON + snapshot answer module | BUILD_SEOGU_DATA_ARTIFACT | evidence-based scope: build the minimum Seo-gu quest/data artifacts to satisfy #1328's accepted journey scope (≥2 materially different resident journeys, incl. ≥1 meaningful navigation/read proof); add quests only where observed Seo-gu capability/product coverage justifies — Buk-gu's count of 5 is NOT a requirement |
| 7 | Quest router/registry/schema mechanism | REUSE_AS_IS | data-driven, no code change |
| 8 | Server-executable `CitizenActionPlan` target allowlist (Buk-gu: 18) | BUILD_SEOGU_DATA_ARTIFACT | define Seo-gu's server-executable safe target subset as its own explicit contract — do NOT assume it equals the client navigable vocabulary (Buk-gu client/golden = 28); see #10 |
| 9 | Action executor + bridge + shell + i18n mechanism | REUSE_AS_IS | swap strings/vocab |
| 10 | De-duplicating the question/action vocabulary (4 copies) + defining client-vs-server target vocabulary ownership (28/18 divergence, intent `NOT_PROVEN_FROM_COMMITTED_EVIDENCE`) | GENERALIZE_SHARED_CORE | highest-value generalization before onboarding site #3: one typed source with explicit subset semantics, or separate contracts with tested invariants |
| 11 | citizen-action-demo-map JS frozen client vocabulary | BUILD_SEOGU_DATA_ARTIFACT | client navigable target vocabulary for Seo-gu; generate from a single source once #10 lands (Buk-gu's map is the golden-manifest source of truth for the client side, not a mirror of the Python allowlist) |
| 12 | Choreography journeys | BUILD_SEOGU_DATA_ARTIFACT | or NOT_REQUIRED_FOR_SCOPED_MVP if Seo-gu MVP uses quest plans only |
| 13 | Answer composer / URL guard / answer_status | REUSE_AS_IS | no site literals |
| 14 | Pipeline/keyword search/query rewriter | REUSE_AS_IS | add Seo-gu synonym dictionary data |
| 15 | Query rewriter/source_match_guard bukgu topic terms | CONFIGURE_FOR_SEOGU | move to site profile vocabulary |
| 16 | Provider abstraction + mock default | REUSE_AS_IS | — |
| 17 | Out-of-site model-answer fallback (site-miss → labeled non-site-grounded model answer) | UNSUPPORTED | does not exist on current main (`/api/ask` returns guidance without calling the LLM; `/api/mvp/ask` non-quest path is an action-decision router, not a factual-answer fallback contract) — #1328 must design/decide it explicitly; automatic multi-provider failover is a separate, also-absent, secondary item |
| 18 | Page Agent resident backend | NOT_REQUIRED_FOR_SCOPED_MVP | research track |
| 19 | MVP router (MVP_ACTIONS + system prompt) | BUILD_SEOGU_DATA_ARTIFACT | ownership boundary: shared router/provider mechanism stays SHARED; Seo-gu action vocabulary + site instructions live in site-keyed data/config (or an explicitly generalized shared contract). Do NOT create a parallel `seogu_mvp_router.py` / duplicated AI engine to mirror Buk-gu (#1328 no-bespoke-engine invariant) |
| 20 | Safety four-layer encoding | REUSE_AS_IS | reproduce verbatim for Seo-gu quests/plans |
| 21 | CI workflow exact-head + gates | REUSE_AS_IS | extend job matrix for seogu site_id |
| 22 | Evidence/visual-approval recording | REUSE_AS_IS | per-site approval directories |
| 23 | admin_demo site switcher | REUSE_AS_IS | profiles already multi-site (seogu_gwangju profile exists) |
| 24 | runtime-vocabulary.json parity manifest | CONFIGURE_FOR_SEOGU | regenerate to include Seo-gu actions; keep inventory-only semantics |

This matrix is the Phase 0 input for #1328. Per instructions, no Seo-gu code is modified in Stage A.

---

## 6. Hard-code / assumption audit (shared runtime)

Classification: LEGITIMATE_GOLDEN_COMPATIBILITY / DATA_SHOULD_MOVE_TO_CONFIG / GENERIC_CONTRACT_GAP / REVIEWED_OVERRIDE_CANDIDATE / NO_RUNTIME_IMPACT.

| Finding | path:line | Class |
|---|---|---|
| default site_id `bukgu_gwangju` | `src/web/mobile_demo.py:47,351`; `admin_demo.py:60,396`; `src/web/__init__.py:9` | DATA_SHOULD_MOVE_TO_CONFIG (env/registry-driven default) |
| `APPROVED_HOST="bukgu.gwangju.kr"` + BASE_URL | `src/official_clone/home_region_parser.py:30-33` | DATA_SHOULD_MOVE_TO_CONFIG (site profile) |
| default sitespec/yml source refs | `src/site_profiles/sitespec_v2_projection.py:28-29` | DATA_SHOULD_MOVE_TO_CONFIG |
| quest registry path pinned to bukgu file; `load_default_bukgu_registry` | `src/agent/quest_registry.py:13-15,73` | DATA_SHOULD_MOVE_TO_CONFIG (site_id-keyed path) |
| snapshot answer module import `src.bukgu_official_snapshot` | `src/agent/quest_schema.py:118,127`; `quest_registry.py`; `src/llm/bukgu_mvp_router.py:32` | GENERIC_CONTRACT_GAP (snapshot resolver should be site-keyed) |
| MVP_ACTIONS closed 8-action set; prompt literals "광주광역시 북구청" etc. | `src/llm/bukgu_mvp_router.py:42-114` | LEGITIMATE_GOLDEN_COMPATIBILITY for Buk-gu; DATA_SHOULD_MOVE_TO_CONFIG for parity |
| route/target vocabularies split across two contracts: routes align 17/17 (`citizen_action_plan.py:36-54` ≡ `citizen-action-demo-map.js` CLOSED_ROUTE_IDS) but targets diverge 28(client/golden)/18(Python executable), with 10 golden targets absent from `_VALID_TARGET_IDS` and a stale "exact mirror" comment in the JS file | `src/agent/citizen_action_plan.py:56-75` ↔ `src/web/static/citizen-action-demo-map.js:56-85` | GENERIC_CONTRACT_GAP (ownership/alignment not proven intentional from committed evidence — `NOT_PROVEN_FROM_COMMITTED_EVIDENCE`) |
| question vocabulary in 4 synchronized copies | HTML chips ↔ `citizen-first-use-shell.js:26-42` ↔ `citizen-first-choreography.js` JOURNEY_MAP ↔ quests JSON | GENERIC_CONTRACT_GAP |
| bukgu/Gwangju expansion + topic terms ("북구청장", "비즈광주북구") | `src/search/query_rewriter.py:38,43`; `src/search/source_match_guard.py:24-25` | DATA_SHOULD_MOVE_TO_CONFIG |
| LLM egress has no allowlist/egress-policy guard | `src/llm/openai_compatible_provider.py:166-171` | GENERIC_CONTRACT_GAP (latent; offline today) |
| asset root `/static/images/bukgu-current`; renderer ids; GNB literals; footer email | `citizen-action-demo-canvas.js` (7 sites); `clone-renderer-approval-registry.js:23-40`; `citizen-first-use-shell.js:1613` | LEGITIMATE_GOLDEN_COMPATIBILITY (Buk-gu golden content) |
| runtime-vocabulary drift (`mayor_message_assist` not in MVP_ACTIONS) | `configs/contracts/runtime-vocabulary.json` vs `bukgu_mvp_router.py:42-51` | REVIEWED_OVERRIDE_CANDIDATE (manifest should reconcile or annotate) |
| docstring/example bukgu mentions | `site_profile.py:103,683-688`; `citizen_action_plan.py:2`; various headers | NO_RUNTIME_IMPACT |
| bukgu brand strings per locale | `citizen-i18n.js:27,170,291,412,533` | DATA_SHOULD_MOVE_TO_CONFIG (per-site branding) |

Stage A performs analysis only; no runtime refactor is undertaken.

---

## 7. Alignment with canonical documents

This spec is consistent with, and subordinate to, the canonical set read for this audit: `docs/CURRENT_STATUS.md` (priority order; Buk-gu frozen demo complete; its Seo-gu execution-status snapshot is stale at this audited main — see drift note below), `clone-first-general-site-platform-strategy.md` (Phase A lifecycle; clone ≠ live mirror; generic engine + site data/config/theme tokens + reviewed overrides), `PRODUCT_TRACKS_AND_BOUNDARIES.md` (Track G onboarding pipeline and promotion vocabulary; Buk-gu → Seo-gu → third-site verification order), `exact-official-site-clone-invariant.md` (exact claims; fixture is sole content source; even Buk-gu home is `capture_required`, not exact), `clone-visual-fidelity-and-promotion-policy.md` (owner-only visual approval; readiness dimensions; viewport evidence), `docs/implementation/RELEASE_GATES.md` (G0–G5 ladder; Gate A frozen demo; HOLD/FAIL conditions), `docs/bukgu-golden-compatibility-manifest.md` (frozen vocabularies and protected golden). Architecture context: `docs/architecture/UNIFIED_RUNTIME_AND_SITESPEC.md`, `GENERIC_SITESPEC_VNEXT_VERSIONING_DECISION.md` (SiteSpec v1 stays the frozen Buk-gu identity contract; multi-site onboarding uses additive vNext). Where any historical snapshot disagrees with current code/tests, the code/tests win, per the audit method.

Known drift at this audited main: `docs/CURRENT_STATUS.md` remains the canonical index by repository policy, but its Seo-gu execution-status snapshot at this audited main is stale relative to current issue state; for this Stage-A audit, current remote/code/test evidence takes precedence for execution status: #1303/#1312 CLOSED/COMPLETED, #1328 OPEN. #1303 completion is faithful-clone completion only and does not imply AI parity. No change to `docs/CURRENT_STATUS.md` is authorized in this Stage-A branch.

Key alignment points a reader must not conflate:
- Buk-gu golden/reference ≠ generic implementation for all municipalities.
- Seo-gu faithful clone complete ≠ Seo-gu AI MVP complete (AI layer is a separate reproduction per §5).
- Buk-gu + Seo-gu ≠ automatic support for arbitrary websites (Gate D wiring is out of scope until Stage B says otherwise).

---

## 8. FOLLOW_UP_REQUIRED (Stage A records; no other files modified)

1. Define the shared schema/ownership relationship for the route/target vocabularies before onboarding site #3: the full client/golden navigable target vocabulary (28 for Buk-gu) and the server-executable safe target subset/contract (18 for Buk-gu) must either be generated from one typed source with explicit subset semantics, or be documented as separate contracts with tested invariants replacing the stale mirror claim. The 28/18 divergence's intent is `NOT_PROVEN_FROM_COMMITTED_EVIDENCE`; #1328 decides the minimum generic contract Seo-gu needs, and a separate runtime issue is created later only if implementation evidence independently requires it.
2. Single-source the question vocabulary (GENERIC_CONTRACT_GAP, 4-copy question vocab) — candidate #1328/Stage B prerequisite.
3. Site-key the quest registry path and official-snapshot resolver (`quest_registry.py`, `quest_schema.py`).
4. Move parser host allowlist and projection default source refs to site config.
5. Add an egress-policy decision for the LLM provider path (currently unguarded; latent offline).
6. Reconcile `runtime-vocabulary.json` `mayor_message_assist` vs `MVP_ACTIONS` drift.
7. Decide default-site de-pinning strategy (registry/env) before onboarding site #3.

---

## 9. Validation

- `git status --short` / `git diff --stat` / `git diff --check` — run post-writing; only `docs/product/bukgu-ai-mvp-reference-spec.md` added.
- Offline tests affected by this doc: none modify behavior (docs-only addition); the canonical docs/invariant scanners do not cover this path. No tests weakened or changed.
