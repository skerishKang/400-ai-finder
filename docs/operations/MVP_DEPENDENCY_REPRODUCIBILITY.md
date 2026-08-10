# MVP Dependency Reproducibility

Status: #1231-B implementation contract.

## Scope

This slice makes the Python and Node dependency graph used by `MVP Contract Checks` reproducible from the same commit. It does not introduce new libraries, change application behavior, add live network validation, or combine dependency locking with the later security/static-analysis slice.

## Python lock provenance

Before this slice, `requirements.txt` contained only lower bounds (`>=`). A clean Python 3.11 CI run could therefore resolve newer direct or transitive packages without any repository change.

The exact versions now committed in `requirements.txt` are the versions installed by the fully green #1231-A PR run:

- workflow run: `31376184336`
- job: `python-contracts` (`93415828908`)
- Python: `3.11.15`
- captured: `2026-08-10`

Direct requirements:

- requests `2.34.2`
- beautifulsoup4 `4.15.0`
- pytest `9.1.1`
- PyYAML `6.0.3`
- Pillow `12.3.0`

Transitive requirements:

- certifi `2026.7.22`
- charset-normalizer `3.4.9`
- idna `3.18`
- urllib3 `2.7.0`
- soupsieve `2.9.2`
- typing-extensions `4.16.0`
- iniconfig `2.3.0`
- packaging `26.3`
- pluggy `1.6.0`
- Pygments `2.20.0`

The normal CI install command remains `python -m pip install --disable-pip-version-check -r requirements.txt`; the difference is that the committed graph is now exact rather than open-ended.

## Node lock

`package-lock.json` already recorded Playwright `1.61.1` and CI already used `npm ci --ignore-scripts`. `package.json` still declared `^1.61.1`, so this slice aligns the direct declaration and lock root to the exact version `1.61.1`.

Every Node-bearing MVP CI domain continues to use `npm ci --ignore-scripts` rather than `npm install`.

## Fail-closed self-contract

`tests/test_mvp_ci_job_decomposition.py`, already owned by the `build-packaging` job, now additionally verifies:

1. every non-comment Python requirement is exact-pinned;
2. the entire expected 15-package Python graph matches the committed provenance set;
3. `package.json`, the package-lock root, Playwright, and playwright-core all resolve to `1.61.1`;
4. all four Node-bearing MVP jobs use `npm ci --ignore-scripts` and do not use `npm install`.

This prevents a later edit from silently reopening a dependency range while leaving CI green.

## Update procedure

Dependency upgrades must be intentional repository changes:

1. update the direct dependency target;
2. resolve and review the full resulting lock graph;
3. update the self-contract/provenance together;
4. run the full `MVP Contract Checks` matrix;
5. do not mix an unrelated product change into the lock refresh.

## Remaining #1231 work

This slice satisfies dependency reproducibility only. Secret scanning, dependency auditing, Ruff/static analysis, browser failure artifacts, cache policy, branch-protection planning, coverage baseline, and additional quality gates remain separate #1231 slices.
