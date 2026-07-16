# #1199 Clone Visual Policy — Document Inventory

## Searched paths

- `README.md`
- `docs/**/*.md` (excluding `.claude/`, `.kilo/`, `node_modules/`, `.venv/`, `.pytest_cache/`)
- `tests/**/*.py`, `tests/**/*.json` (document-contract-referencing files)
- `.github/**/*.md` (no `.github/**/*.md` files exist — only `.github/workflows/mvp-contracts.yml` YAML)

## Search queries executed

```bash
rg -n -i \
  --glob '!*.mjs' --glob '!.claude/**' --glob '!.kilo/**' \
  --glob '!node_modules/**' --glob '!.venv/**' --glob '!.pytest_cache/**' \
  '(exact[ -]clone|exact parity|fixture ready|renderer ready|capture_required|visual baseline|screenshot|golden reference|default renderer|resident-facing|resident default|stage 5|visual review|visual approval|structural parity|asset readiness|\bclone\b)' \
  README.md docs tests
```

Additional targeted queries for classification:

```bash
rg -n -i '(capture_required|resident.default.approved|visual.review.pending|project.owner|side.by.side|rollback|erratum)' README.md docs .github
```

## Discovered relevant documents

### Requires correction

| # | Document | Reason | Will correct? |
|---|----------|--------|---------------|
| 1 | `docs/product/exact-official-site-clone-invariant.md` | Missing separation between fixture completeness and visual approval; no mention of project-owner approval authority; no mention of preview/debug vs resident-default route separation; screenshots-without-comparison section incomplete; no linkage to new governing policy | Yes — Section D |
| 2 | `README.md` | No mention of visual approval gate; no mention of structurally-complete-fixture ≠ resident-default; no link to new governing policy | Yes — Section E |

### Requires cross-reference

| # | Document | Reason | Will correct? |
|===|==========|========|===============|
| 3 | `docs/architecture/clone-first-platform-adr.md` | Already correctly separates fixture completeness from exact clone; does not yet reference the new visual-fidelity policy. ADR records a docs-only planning decision; cross-reference addition sufficient | Yes |
| 4 | `docs/bukgu-golden-compatibility-manifest.md` | Already contains correct non-claims language and `capture_required` assertions; does not yet reference new governing policy. (Core content is already compliant; cross-reference addition only) | Yes |
| 5 | `docs/product/1078-corrective-note.md` | Already aligns with exact-clone invariant; does not yet reference new policy chain | Yes |
| 6 | `docs/mvp-demo-operator-runbook.md` | References exact-clone invariant correctly; does not reference promotion gate | Yes |
| 7 | `docs/mvp-demo-milestone-snapshot.md` | References exact-clone invariant correctly; does not reference promotion gate | Yes |

### Already compliant

| # | Document | Reason | Will correct? |
|---|----------|--------|---------------|
| 8 | `docs/artifacts/1172-home-asset-identity-audit.md` | Explicitly says "Exact visual parity is not claimed"; does not assert resident-default eligibility; does not assert visual approval | No |
| 9 | `docs/artifacts/1166-home-renderer-readiness.md` | States "does not claim exact visual parity"; "does not claim that the home route is finished as an exact official clone"; clearly separates structural readiness from visual approval | No |
| 10 | `docs/page-agent-stage3-comparison-report.md` | Correctly describes Stage 5 as blocked; does not claim visual approval | No |
| 11 | `docs/design/bukgu-ai-agent-product-directive.md` | Product direction; does not assert visual approval for current state | No |
| 12 | `docs/design/863-local-execution-contract.md` | Historical design doc; does not claim resident-default status | No |
| 13 | `docs/product/dynamic-retrieval-query-learning-strategy.md` | Retrieval strategy; clone invariant disclaimer present; no visual claims | No |
### Historical artifact requiring erratum

| # | Document | Reason | Will correct? |
|---|----------|--------|---------------|
| 15 | `docs/artifacts/1170-home-fixture-renderer-readiness.md` | Accurately documents its time's achievement (structural fixture renderer readiness) but was subsequently used as grounds for resident-default promotion by project-owner review which was later deemed inappropriate. The document itself did not claim visual approval or resident-default eligibility, but its practical effect requires a visible erratum to clarify scope | Yes — Section A |

### Exact approved clone falsely claimed?

None of the discovered documents falsely claim the current product is an exact approved resident-facing clone. All artifacts correctly assert `capture_required` status. However, README, exact-clone-invariant, and the governing documents lack the visual approval gate distinction, which this PR corrects.

## Erratum justification

`docs/artifacts/1170-home-fixture-renderer-readiness.md` is the only historical artifact requiring erratum because:
1. The document itself was technically accurate at its time (structural fixture renderer readiness, not visual approval)
2. However, the renderer it established was subsequently promoted to resident-facing default without visual approval
3. That promotion was later judged inappropriate by project-owner direct review
4. The erratum clarifies the document's actual scope without rewriting its historical record
5. The erratum connects #1197 (which restored the approved composition) and #1199 (which codifies the gate that was missing)
