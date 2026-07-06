# Stage #863-B — Buk-gu Semantic HTML/CSS Reconstruction Report

## 1. Overview
* **Goal**: Reconstruct Buk-gu Office portal pages as semantic HTML/CSS using actual screenshots as reference.
* **Status**: All 6 routes implemented — `home`, `civil-service`, `complaint-category`, `complaint-intake`, `complaint-review`, `handoff-stop`.

## 2. Architecture

```
실제 북구청 캡처 이미지 (src/web/static/images/bukgu_*.png)
→ 레퍼런스 분석 → text content + layout extracted
→ HTML/CSS로 실제 북구청 화면 구조 재현 (citizen-action-demo-canvas.js)
→ GNB·LNB·카드·표를 실제 DOM으로 구현
→ 각 click 대상에 data-action-target 부착
→ route navigation + AI narration (우측 chat-shell)
```

## 3. Route Structure

| Route | Renderer | Content | Key data-action-target |
|-------|----------|---------|----------------------|
| home | _renderHome() | Header+GNB+Search+Visual+Quick+Notice+FieldInfo+Footer | nav-civil-service (종합민원 GNB) |
| civil-service | _renderCivilService() | Sub-header+Breadcrumb+PocBanner+NavTargets | nav-complaint-category |
| complaint-category | _renderComplaintCategory() | LNB (real site menu)+Category cards | complaint-category-* |
| complaint-intake | _renderComplaintIntake() | LNB+TableFilter+FormTable (5 forms) | complaint-draft-review |
| complaint-review | _renderComplaintReview() | ReviewSummary+DisabledSubmit+SafetyStop | handoff-notice |
| handoff-stop | _renderHandoffStop() | Demo end message | handoff-notice |

## 4. Visual Reference Sources

| File | URL | Viewport | Browser Chrome |
|------|-----|----------|---------------|
| bukgu_home.png | bukgu.gwangju.kr (홈페이지) | 1497×2608 | 없음 |
| bukgu_menu.png | bukgu.gwangju.kr (청원24) | 1497×2593 | 없음 |
| bukgu_intake.png | bukgu.gwangju.kr (민원서식) | 1497×1600 | 없음 |

All screenshots are content-only captures (no browser chrome). Kept as reference artifacts only.

## 5. Right-side Chat-first Shell

- **Chat-shell** replaces legacy copilot-rail
- Conversation thread: user question + 2 AI responses
- Compact progress indicator: 홈→신청→확인→종료
- 한국어 보내기 composer (disabled for demo)
- Legacy copilot-rail kept hidden for compatibility

## 6. Safety Stop

Implemented on `complaint-review` route as `position:fixed` modal:
- Semi-transparent backdrop (rgba(0,0,0,0.5))
- White dialog with red border + title "⚠️ 제출 전 안전 중지 (Safety Stop)"
- Explanatory text + "확인 및 데모 종료" button
- Disabled submit button in background visually confirms no submission occurs

## 7. Verification Screenshots

Screenshots generated from local server at http://127.0.0.1:8401/static/citizen-action-demo.html:

1. **home.png** — Main portal with GNB highlighted, search, quick services, field info, footer
2. **complaint-category.png** — LNB sidebar + category cards
3. **complaint-intake.png** — Form table with search filter
4. **safety-stop.png** — Pre-submit review with Safety Stop modal

## 8. Test Results

### pytest
```
$ python3 -m pytest tests/test_citizen_action_demo_canvas.py -v
============================== 91 passed in 0.91s ==============================
```

All 91 tests pass, including 7 new focused tests for semantic reconstruction:

| Test | Status |
|------|--------|
| `test_no_image_routes_in_canvas` | ✅ IMAGE_ROUTES removed |
| `test_safety_stop_in_complaint_review` | ✅ Safety Stop rendered |
| `test_chat_shell_in_html` | ✅ Chat-shell + 보내기 |
| `test_home_has_gnb_with_data_action_target` | ✅ GNB data-action-target |
| `test_complaint_review_has_disabled_submit` | ✅ Disabled submit |
| `test_route_metadata_titles_updated` | ✅ Correct naming |

### git diff --check
```
$ git diff --check
(no output) — clean, no trailing whitespace or merge conflicts
```

### Visual Verification Screenshots

Located in `docs/artifacts/863-semantic/`:

| View | Reconstruction | Reference Comparison |
|------|---------------|---------------------|
| Home | `semantic-home.png` | `compare-home---홈.png` |
| Complaint Category (LNB + cards) | `semantic-complaint-category.png` | `compare-complaint-category---민원-메뉴.png` |
| Intake (Form Table) | `semantic-intake.png` | N/A (reference is 전체 페이지) |
| Safety Stop | `semantic-safety-stop.png` | N/A (modal is demo-only) |

## 9. Non-functional Requirements

- No fetch, no persistence, no external URLs
- No actual form submission, login, or data storage
- All icons use text/emoji fallbacks (no external icon dependencies)
- Copyright and legal notice included in footer
