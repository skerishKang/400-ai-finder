# #1099 Buk-gu guidance and mayor writing WIP handoff

## Purpose

This branch is a work-in-progress implementation for Issue #1099. It preserves the existing litter/garbage complaint writing scenario, refreshes three official Buk-gu guidance pages from captured official content, and adds a separate proposed mayor-message AI writing journey.

The exact-official-site boundary remains governed by [Exact Official Site Clone Invariant](product/exact-official-site-clone-invariant.md):

- `bulky-waste-disposal`, `passport-guidance`, and `unmanned-kiosk-guidance` are official fixture-backed pages.
- `complaint-board`, `complaint-write`, `complaint-review`, `handoff-stop`, `mayor-office`, `mayor-complaint-write`, and `mayor-complaint-receipt` are product-transition proposal pages. They must not be represented as exact official pages.
- The litter/garbage complaint journey and mayor-message journey are independent scenarios. They may share visual components but must not be merged into one route or action.

## Repository state

- Issue: `#1099`
- Branch: `codex/1099-bukgu-mayor-writing`
- Base at branch creation: `origin/main` `df3b4fb`
- Worktree used for this slice: `G:\Ddrive\BatangD\task\workdiary\400-ai-finder-1099`
- Separate `#1062` worktree: `G:\Ddrive\BatangD\task\workdiary\400-ai-finder-1062`

Do not move, reset, clean, stash, or absorb the `#1062` worktree. Do not use the original dirty workspace to continue this branch.

## Completed in this WIP slice

### Official guidance fixtures

Captured and sanitized official Buk-gu content for:

- Bulky waste: `https://bukgu.gwangju.kr/menu.es?mid=a10406070000`
- Passport guidance: `https://bukgu.gwangju.kr/menu.es?mid=a10101060200`
- Unmanned kiosk guidance: `https://bukgu.gwangju.kr/menu.es?mid=a10101020100`

The fixtures are stored in `data/official_snapshots/bukgu_gwangju/`. They use schema version 2 with page provenance, canonical content hashes, table counts, localized assets, and stripped scripts/styles/events.

The snapshot validator now supports both the existing department snapshot schema and the generic official-content-page schema. Browser and Cloudflare generated snapshot bundles were refreshed.

### Left-canvas rendering

- The bulky-waste, passport, and kiosk routes prefer official snapshot content and keep the previous synthetic renderer only as a fallback.
- The existing complaint board and complaint writing views were redesigned as explicit product proposals.
- Existing litter scenario field IDs and action IDs were preserved.
- The home mayor card now exposes an in-canvas `열린구청장실 바로가기` control.
- Added separate `mayor-office`, `mayor-complaint-write`, and `mayor-complaint-receipt` product routes.
- Added a distinct `mayor_message_assist` choreography that types into the mayor form, asks for explicit confirmation, and routes to a demo receipt.
- Chat decision buttons now have dedicated hover, active, focus-visible, disabled, mobile, and reduced-motion states.

### Official mayor references

The current official flow was inspected as reference only:

- Home mayor link: `https://bukgu.gwangju.kr/mayor/`
- Official `구청장에게 바란다`: `https://bukgu.gwangju.kr/menu.es?mid=a10103150100`

The current official flow opens new windows and ultimately links to 국민신문고. The new same-canvas AI writing flow is intentionally a future product proposal, not a claim about current official behavior.

## Files changed

- `data/official_snapshots/bukgu_gwangju/*.json`
- `functions/api/mvp/bukgu-official-snapshots.js`
- `src/bukgu_official_snapshot.py`
- `src/agent/citizen_action_plan.py`
- `src/web/static/bukgu-official-snapshots.js`
- `src/web/static/citizen-action-demo-canvas.js`
- `src/web/static/citizen-action-demo-canvas.css`
- `src/web/static/citizen-action-demo-map.js`
- `src/web/static/citizen-first-choreography.js`
- `src/web/static/citizen-first-use-shell.css`
- `src/web/static/images/bukgu-current/mayor/*`
- `tests/fixtures/official_site_clone_manifest.json`
- `tests/test_capture_required_entry_spec.py`

## Verification completed

Passed:

```text
node --check src/web/static/citizen-action-demo-map.js
node --check src/web/static/citizen-action-demo-canvas.js
node --check src/web/static/citizen-first-choreography.js
node --check src/web/static/bukgu-official-snapshots.js
node --check functions/api/mvp/bukgu-official-snapshots.js
python scripts/generate_bukgu_official_snapshots.py --check
pytest tests/test_renderer_route_manifest_fidelity.py tests/test_capture_required_entry_spec.py -q
# 27 passed
```

The broader targeted run currently reports `416 passed, 1 failed`:

```text
pytest tests/test_citizen_action_demo_canvas.py tests/test_citizen_first_use_shell.py tests/test_citizen_action_plan.py -q
```

Known failure:

```text
TestJDept01SpecificContracts.test_jdept01_css_is_scoped
```

The test treats every selector after an old J-DEPT CSS marker as part of the J-DEPT block, so it incorrectly captures the newly appended selector `.bg-page--home .bg-home-lead__mayor`. Do not broadly weaken the scoped-selector test. Prefer either delimiting the J-DEPT block precisely in the test or moving the new #1099 CSS outside the region parsed as J-DEPT-only CSS.

Browser visual verification, responsive verification, and full CI have not been completed. Do not report this Draft PR as feature-complete.

## Next work order

1. Resolve the single J-DEPT scoped-CSS test without weakening its contract.
2. Add focused tests for generic schema-v2 official snapshots, local asset hashes, generated browser/Function parity, the mayor routes, and the separate mayor choreography.
3. Add or update runtime browser coverage for the official three routes, home mayor hotspot, mayor office, AI typing, confirmation, receipt, and the unchanged independent litter journey.
4. Run the local app and visually compare the three official guidance pages against the current official references.
5. Verify chat decision-button hover, pressed, keyboard focus, disabled, reduced-motion, desktop, and mobile behavior.
6. Verify that same-canvas navigation never opens a new tab in the proposed mayor flow.
7. Decide whether the litter flow should keep the existing `complaint-review` safety-stop or receive a separate polished demo receipt. Do not reuse the mayor receipt without an explicit product decision.
8. Record the official mayor asset provenance and hashes in a committed reference record.
9. Turn the ad-hoc browser capture procedure into a reproducible capture tool or documented operator workflow.
10. Run the full Python, runtime harness, responsive browser, Cloudflare Function, generated-artifact, and whitespace checks before marking the PR ready.

## Continuation commands

Use a clean worktree for the existing branch:

```powershell
git fetch origin
git worktree add G:\Ddrive\BatangD\task\workdiary\400-ai-finder-1099-next codex/1099-bukgu-mayor-writing
Set-Location G:\Ddrive\BatangD\task\workdiary\400-ai-finder-1099-next
git status -sb
```

If the branch is already checked out by another worktree, continue in that worktree or coordinate ownership instead of forcing checkout.

## Copy/paste prompt for the next model

```text
Continue GitHub Issue #1099 from branch codex/1099-bukgu-mayor-writing and its Draft PR. Read docs/1099-bukgu-guidance-mayor-writing-handoff.md and docs/product/exact-official-site-clone-invariant.md before editing.

Important boundaries:
- Do not touch, reset, stash, clean, or merge the separate #1062 worktree/branch.
- Preserve the existing litter/garbage complaint AI-writing scenario as one independent product journey.
- Preserve the new mayor-message AI-writing scenario as a separate journey. Shared components/styles are fine; route/action integration is not.
- Bulky waste, passport, and unmanned kiosk are official fixture-backed pages.
- Complaint board/write/review and mayor office/write/receipt are product-transition proposals, not exact official pages.
- Do not open new windows in the proposed mayor journey.
- Do not expose or commit API keys or secrets.

Start by reproducing and fixing the one known failure:
pytest tests/test_citizen_action_demo_canvas.py tests/test_citizen_first_use_shell.py tests/test_citizen_action_plan.py -q

The failure is TestJDept01SpecificContracts.test_jdept01_css_is_scoped because an old test parses all CSS after the J-DEPT marker and sees .bg-page--home .bg-home-lead__mayor. Fix the block boundary or CSS placement without weakening the J-DEPT scoping guarantee.

Then add focused snapshot/route/choreography tests, run the local site, visually verify desktop/mobile interactions and same-canvas mayor navigation, run full CI-equivalent checks, and update the Draft PR with exact evidence. Do not claim visual or browser success until it has actually been run. Keep all changes on codex/1099-bukgu-mayor-writing.
```
