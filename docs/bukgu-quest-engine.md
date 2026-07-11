# Buk-gu Quest Engine Phase 1

This PR introduces the first quest-engine path for one scenario only:
`housing_department_lookup` ("공동주택 담당부서 찾기").

## Scope

- Implements one registry-backed quest in `data/quests/bukgu_gwangju_quests.json`.
- Matches housing/apartment department questions locally.
- Converts the matched quest to a validated local action plan.
- Reuses the existing MVP action/choreography contract with
  `action="housing_department"`.
- Stops after displaying the result with `STOP_AFTER_RESULT`.

This PR does not implement the full 30-quest plan, five golden scenarios, live
provider rollout, authentication, form submission, personal data entry, or
site-affecting actions.

## Flow

1. User asks a housing department question in `/mvp/`.
2. `/api/mvp/ask` checks the quest registry before resolving an LLM provider.
3. The housing quest matches `housing_department_lookup`.
4. `quest_to_action_plan` validates browser actions and returns:
   - official path: `홈 > 북구소개 > 구청안내 > 행정조직 > 공동주택과 > 조직 및 업무안내`
   - client action: `housing_department`
   - stop condition: `STOP_FOR_USER_CONFIRMATION`
5. The existing first-use shell starts the existing `housing_department`
   choreography.
6. The left pane renders the committed canonical `apartment-dept` snapshot:
   the complete official 19-row organization/work table in source order.
7. The right AI panel shows quest name, official path, result, progress, and
   `STOP_FOR_USER_CONFIRMATION`.

## Runtime Mode

The housing quest path is `local_static` with `official_snapshot` provenance.

The left canvas, deterministic Python answer, model prompt evidence, and
Cloudflare Function all consume `data/official_snapshots/bukgu_gwangju/apartment-dept.json`.
Normal execution does not call the live Buk-gu site, Firecrawl, or crawler
adapters for this route. Non-matching MVP questions keep the existing provider-backed
fallback path.
