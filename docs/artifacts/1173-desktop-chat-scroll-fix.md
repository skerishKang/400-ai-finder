# #1173 Desktop chat scroll containment

**Issue:** #1173  
**Branch:** `fix/1173-desktop-chat-scroll-containment`  
**Status:** fixed + permanent regression contract (fail-closed E2E)


## Latest verification snapshot

| Field | Value |
|-------|--------|
| Merged main SHA | `5d085ff408f64b4a94df86e0de5fa8906496bc40` |
| Verifier | `tests/browser/verify_desktop_chat_scroll_containment_e2e.mjs` |
| Fail-closed | per-turn HTTP 200 + body marker + exact user/assistant +1 |
| Home audit `--check` | **PASS** (frozen #1177 manifest; no refresh) |
| `pytest` citizen shell + home audit | **119 passed** |
| `verify_mobile_link_safety.mjs` | **PASS** (local dist on `127.0.0.1`) |

Safety counters from final E2E run: console/page/failed/external/nav/popup/liveApi = **0**.
Network / Firecrawl / official-site access: **0**.

## Before (reproduction)

Desktop split/transitioning `.chat-shell` declared:

```css
height: 100vh;
height: 100%;
```

The trailing `height: 100%` overrode the viewport constraint. As chat history
grew, `.chat-shell` (and often document/body) grew with content instead of
keeping overflow inside `#chat-thread`.

Observed before-fix pattern (1440×1000, multi-turn chat):

| Metric | Before (bug) |
|--------|--------------|
| `.chat-shell` height | content-driven (can exceed viewport) |
| `document` / `body` scrollHeight | grows with full chat history |
| `#chat-thread` clientHeight | unbounded / not a stable scrollport |
| overflow locus | document/page, not chat-thread |
| composer after 15 turns | can leave viewport |

Exact pre-fix CSS locus:

`src/web/static/citizen-first-use-shell.css`  
`body[data-first-use-state="transitioning"] .chat-shell,`  
`body[data-first-use-state="split"] .chat-shell`

## Root cause

Cascading height declarations on desktop transitioning/split `.chat-shell`:

1. `height: 100vh` — intended viewport containment  
2. `height: 100%` — **wins**, ties shell height to parent content height  

Parent layout then expands with chat history → document scroll hijacks the
conversation.

Mobile `@media (max-width: 767px)` rules that also use `height: 100%` are
**unchanged** (out of scope; #1174 multi-step composer collapse is separate).

## Exact CSS change

Remove only the trailing desktop override:

```diff
 body[data-first-use-state="transitioning"] .chat-shell,
 body[data-first-use-state="split"] .chat-shell {
   grid-area: chat;
   align-self: stretch;
   width: var(--first-use-chat-width);
   height: 100vh;
-  height: 100%;
   flex-shrink: 0;
   ...
 }
```

No mobile rule edits. No unrelated CSS reformat/reorder.

## Companion scroll policy (#1173)

`scrollChatToLatest` now auto-scrolls only when the thread was bottom-pinned
before the DOM mutation (`CHAT_PIN_THRESHOLD_PX = 72`). Reading older history
must not be yanked to the latest message; returning near the bottom restores
auto-scroll.

## After metrics (permanent browser contract)

Verifier: `tests/browser/verify_desktop_chat_scroll_containment_e2e.mjs`  
Static build + local server + mocked `/api/mvp/ask` only.

### 1440×1000 after 15 mixed turns (measured)

Baseline (post-warmup split): doc/shell/canvas **1000**. After 15 chat-only turns:

| Metric | After fix |
|--------|-----------|
| document / body scrollHeight | **1000 / 1000** (= baseline; delta 0) |
| `#chat-thread` clientHeight | **742** |
| `#chat-thread` scrollHeight | **11610** (internal overflow) |
| `.chat-shell` height | **1000** |
| left canvas height | **1000** |
| user / assistant delta vs post-warmup | **+15 / +15** |
| composer | inside viewport, operable |
| bottom-pinned last assistant | **PASS** (`distBottom=0`, near-bottom required) |
| reading-history (assistant complete, no yank) | **PASS** (unpinned; `distBottom≈12209`) |
| re-pin auto-scroll | **PASS** (`distBottom=0`, near-bottom required) |

### 1024×768 after 15 mixed turns (measured)

Baseline (post-warmup split): doc/shell/canvas **768**. After 15 turns:

| Metric | After fix |
|--------|-----------|
| document / body scrollHeight | **768 / 768** (delta 0) |
| `#chat-thread` clientHeight | **510** |
| `#chat-thread` scrollHeight | **11610** |
| `.chat-shell` height | **768** |
| left canvas height | **768** |
| user / assistant delta | **+15 / +15** |
| bottom-pinned / re-pin | **PASS** (`distBottom=0` each; near-bottom required) |
| reading-history | **PASS** (unpinned; `distBottom≈12441`) |

### 390×844 regression (measured)

Six chat-only turns (never clicks **예**) plus bottom-pin check:

| Metric | Result |
|--------|--------|
| document scrollHeight | **844** (= baseline 844) |
| `#chat-thread` clientHeight / scrollHeight | **514 / 5027** (`scrollHeight > clientHeight`) |
| user / assistant delta | **+6 / +6** |
| composer box | **364×97**, in viewport, operable |
| bottom-pinned latest assistant | **PASS** (`distBottom=0`, near-bottom required) |

**Does not** enter the #1174 multi-step path after **예**. That composer
0×0 defect remains a separate issue.

## Bottom-pinned policy

When the resident is within `CHAT_PIN_THRESHOLD_PX` of the thread bottom,
new messages / meta / confirm bubbles scroll the thread so the latest content
is visible.

## Reading-history preservation policy

When the resident has scrolled up to read older messages (farther than the pin
threshold from the bottom), subsequent chat DOM updates must **not** force
`scrollTop` to the bottom. Returning near the bottom and sending again resumes
normal auto-scroll.

## Safety counters (verifier)

| Counter | Required |
|---------|----------|
| console errors | 0 |
| page errors | 0 |
| failed resources | 0 |
| external requests | 0 |
| external navigations | 0 |
| popups | 0 |
| live provider / Firecrawl / API | 0 |
| actual 북구청 site access | 0 |
| submission / login / payment / PII | 0 |

## Boundaries

| Topic | This branch |
|-------|-------------|
| #1174 mobile multi-step composer after **예** | **not fixed** (separate) |
| #1170 home fixture canvas renderer | **not included** |
| Temporary diagnostics (`test_scroll_bug.py`, `test_screenshot.py`, screenshots, traces) | **not committed** |

## 15-turn mixed sequence

Warmup (exact product prompt → split once):  
`공동주택 관련 문의는 어느 부서에 해야 하나요?` then dismiss **아니요**.

Then chat-only mixed turns (paraphrases; not exact `SUPPORTED_QUESTION_ACTIONS` keys):

1. KO supported — 공동주택과 담당 연락처를 알려주세요  
2. KO unsupported — 내일 날씨가 어때?  
3. EN supported — Please explain how illegal parking reports work in Buk-gu  
4. EN unsupported — What will the weather be tomorrow?  
5. KO supported — 대형폐기물 수수료 납부 방법을 알려줘  
6. EN supported — How do passport applications work at the district office?  
7. KO unsupported — 비트코인 가격 알려줘  
8. EN unsupported — Tell me a joke please  
9. KO supported — 주정차 단속 기준이 궁금해요  
10. EN supported — Where can residents find unmanned certificate kiosks?  
11. KO supported — 여권 사진 규격이 어떻게 되나요?  
12. EN unsupported — Recommend a restaurant nearby  
13. KO unsupported — 주식 종목 추천해줘  
14. EN supported — What steps are needed for bulky waste pickup?  
15. KO supported — 민원서류 무인발급 가능 시간을 알려주세요  

## Fail-closed E2E contract notes

Removed fail-open patterns from the verifier:

- no `.catch(() => null)` / `.catch(() => {})` on response or message waits
- each turn: `waitForResponse` POST `/api/mvp/ask` must be HTTP **200** with JSON `ok:true` and deterministic **marker** in `answer`
- each chat-only turn: user count **+1**, assistant count **+1**, last AI text contains marker
- after 15 turns: user/assistant deltas exactly **15**; all 15 markers present (no duplicates)
- `assertLatestAssistantVisible` requires last **assistant** + marker + composer in viewport + **`distBottom <= PIN_THRESHOLD+8`** (near-bottom); partial bubble intersection alone fails
- reading-history asserts after **assistant response completes** (marker present, `scrollTop` not yanked)
- document/shell containment uses **baseline delta** (not only absolute `< 4000`)
- mobile requires internal overflow (`scrollHeight > clientHeight`) and per-turn count growth

## How to run

```bash
node tests/browser/verify_desktop_chat_scroll_containment_e2e.mjs
```
