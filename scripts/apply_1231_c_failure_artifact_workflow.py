from pathlib import Path


path = Path(".github/workflows/mvp-contracts.yml")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, got {count}")
    text = text.replace(old, new, 1)


replace_once(
    '''      - name: Run CI job decomposition self-contract (#1231)\n        run: python -m pytest -q tests/test_mvp_ci_job_decomposition.py\n\n      - name: Check whitespace errors\n''',
    '''      - name: Run CI job decomposition self-contract (#1231)\n        run: python -m pytest -q tests/test_mvp_ci_job_decomposition.py\n\n      - name: Run CI failure artifact contracts (#1231)\n        run: |\n          python -m pytest -q \\\n            tests/test_mvp_failure_artifacts.py \\\n            tests/test_mvp_failure_artifact_workflow.py\n\n      - name: Check whitespace errors\n''',
    "build contract",
)

replace_once(
    '''      - name: Run two-stage bilingual draft browser contract\n        run: node tests/browser/verify_two_stage_bilingual_draft_e2e.mjs\n\n  page-agent:\n''',
    '''      - name: Run two-stage bilingual draft browser contract\n        run: node tests/browser/verify_two_stage_bilingual_draft_e2e.mjs\n\n      - name: Prepare privacy-safe failure artifacts\n        if: failure()\n        run: python scripts/collect_mvp_failure_artifacts.py --job citizen-browser --out-dir /tmp/mvp-failure-artifacts-citizen\n\n      - name: Upload bounded failure artifacts\n        if: failure()\n        uses: actions/upload-artifact@v7.0.1\n        with:\n          name: mvp-citizen-browser-failure-${{ github.run_id }}-${{ github.run_attempt }}\n          path: /tmp/mvp-failure-artifacts-citizen\n          if-no-files-found: warn\n          retention-days: 5\n\n  page-agent:\n''',
    "citizen artifacts",
)

replace_once(
    '''      - name: Run Page Agent production-gap browser contract\n        run: node tests/browser/verify_page_agent_production_gaps_e2e.mjs\n\n  comparison-evidence:\n''',
    '''      - name: Run Page Agent production-gap browser contract\n        run: node tests/browser/verify_page_agent_production_gaps_e2e.mjs\n\n      - name: Prepare privacy-safe failure artifacts\n        if: failure()\n        run: python scripts/collect_mvp_failure_artifacts.py --job page-agent --out-dir /tmp/mvp-failure-artifacts-page-agent\n\n      - name: Upload bounded failure artifacts\n        if: failure()\n        uses: actions/upload-artifact@v7.0.1\n        with:\n          name: mvp-page-agent-failure-${{ github.run_id }}-${{ github.run_attempt }}\n          path: /tmp/mvp-failure-artifacts-page-agent\n          if-no-files-found: warn\n          retention-days: 5\n\n  comparison-evidence:\n''',
    "page-agent artifacts",
)

replace_once(
    '''          print(\n              "Evidence schema OK: "\n              f"{len(runs)} runs, 0 external requests, "\n              "all no_submit preserved, "\n              "all pass_criteria populated"\n          )\n          PY\n\n  mvp-contracts:\n''',
    '''          print(\n              "Evidence schema OK: "\n              f"{len(runs)} runs, 0 external requests, "\n              "all no_submit preserved, "\n              "all pass_criteria populated"\n          )\n          PY\n\n      - name: Prepare privacy-safe failure artifacts\n        if: failure()\n        run: python scripts/collect_mvp_failure_artifacts.py --job comparison-evidence --out-dir /tmp/mvp-failure-artifacts-comparison\n\n      - name: Upload bounded failure artifacts\n        if: failure()\n        uses: actions/upload-artifact@v7.0.1\n        with:\n          name: mvp-comparison-evidence-failure-${{ github.run_id }}-${{ github.run_attempt }}\n          path: /tmp/mvp-failure-artifacts-comparison\n          if-no-files-found: warn\n          retention-days: 5\n\n  mvp-contracts:\n''',
    "comparison artifacts",
)

path.write_text(text, encoding="utf-8")
print("#1231-C failure artifact workflow applied")
