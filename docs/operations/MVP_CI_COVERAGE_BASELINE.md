# MVP CI Python Coverage Baseline (#1231-G)

## Official label

`CI-owned Python src line-coverage baseline`

## Scope

- **Source scope:** `src/` only.
- **Metric:** Python **line coverage** only.
- **Not included / not claimed:**
  - repository-wide coverage
  - JavaScript / browser coverage (Playwright harnesses are out of scope)
  - branch coverage (`--branch` is forbidden)
  - coverage thresholds / `--fail-under` (no gate in this first slice)
  - badges

This slice measures the baseline only. No product source changes are made
to raise coverage; no `omit`/`exclude`/`pragma` are added to shrink the
denominator; no tests are deleted/skipped/xfailed.

## Tool

Standalone `coverage.py`, exactly pinned in a CI-only dependency file:

```
requirements-ci-coverage.txt
coverage==7.15.2
```

`coverage` is intentionally **not** mixed into `requirements.txt`, and
`pytest-cov` is not used.

## Workflow architecture

`python-coverage-baseline` is a new parallel job in
`.github/workflows/mvp-contracts.yml` (`ubuntu-latest`, 10 minutes):

1. checkout
2. Python 3.11
3. `requirements.txt` install
4. `requirements-ci-coverage.txt` install
5. deterministic runner:
   `python scripts/run_mvp_python_coverage_baseline.py --output /tmp/mvp-python-coverage-baseline.json`

The existing 9 domain jobs are unchanged; their pytest commands are not
converted into coverage commands. There is no cross-job `.coverage` artifact
fan-in — the first slice simply re-runs the union of the existing Python
pytest surface in the dedicated coverage job (simpler and verifiable).

The final `mvp-contracts` aggregator now requires the 9 existing domains
**plus** `python-coverage-baseline` (needs + shell gate). All 10 must be
`success` for the final aggregator to pass.

## Coverage test surface

`COVERAGE_TEST_FILES` in
`scripts/run_mvp_python_coverage_baseline.py` is the set union of every
`tests/*.py` file that the workflow runs via `python -m pytest` (coverage
job itself excluded). Duplicates across jobs run once. The drift contract
`tests/test_mvp_python_coverage_workflow.py` re-derives that union from the
workflow and asserts it equals `COVERAGE_TEST_FILES`, so any future Python
pytest file added to the workflow must also be added to the coverage
surface.

## Runner behavior

`scripts/run_mvp_python_coverage_baseline.py`:

1. erases prior coverage state
2. `source=["src"]`
3. starts coverage
4. runs `pytest -q` over `COVERAGE_TEST_FILES`
5. propagates a non-zero pytest exit unchanged (no summary written)
6. stops/saves coverage
7. prints a per-module report with missing lines (`show_missing=True`)
8. writes a deterministic JSON summary to `--output`

## JSON contract

Deterministic output (no timestamp / random / run ID):

```json
{
  "schema_version": "1.0.0",
  "label": "CI-owned Python src line-coverage baseline",
  "source": "src",
  "coverage_version": "7.15.2",
  "test_files": [],
  "totals": { "statements": 0, "covered": 0, "missing": 0, "percent": 0.0 },
  "files": []
}
```

- `files` are sorted by path (deterministic order).
- Each module: `path`, `statements`, `covered`, `missing`, `percent`.
- Percentages are rounded to **2 decimal places**.
- Success artifact upload is not needed for this slice; the JSON lives under
  CI `/tmp`.

## Reproduction

```bash
python -m pip install --disable-pip-version-check -r requirements.txt
python -m pip install --disable-pip-version-check -r requirements-ci-coverage.txt
python scripts/run_mvp_python_coverage_baseline.py \
  --output /tmp/mvp-python-coverage-baseline.json
```

## Threshold policy

No threshold is introduced in this first slice. A future threshold will be
decided separately, based on the measured baseline number recorded by the
CTO on #1231 after the final-head CI run.
