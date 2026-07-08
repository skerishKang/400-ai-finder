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
   - official path: `북구소개 > 구청안내 > 업무 및 전화번호 안내 > 공동주택과`
   - client action: `housing_department`
   - stop condition: `STOP_AFTER_RESULT`
5. The existing first-use shell starts the existing `housing_department`
   choreography.
6. The left pane renders the local `J-DEPT-01` department directory result:
   `공동주택과 / 062-410-6033 / 공동주택과 업무전반`.
7. The right AI panel shows quest name, official path, result, progress, and
   `STOP_AFTER_RESULT`.

## Runtime Mode

The housing quest path is `local_static`.

It does not call the live Buk-gu site, Firecrawl, crawler adapters, or an LLM
provider. Non-matching MVP questions keep the existing provider-backed fallback
path.
