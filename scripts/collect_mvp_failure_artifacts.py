from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SCHEMA_VERSION = "1.0.0"
MAX_LOG_BYTES = 128 * 1024

JOB_SOURCES = {
    "citizen-browser": (
        "mobile-link-safety-server.log",
        "housing-e2e-server.log",
    ),
    "page-agent": (
        "page-agent-e2e-server.log",
        "resident-e2e-server.log",
    ),
    "comparison-evidence": (
        "comparison-harness-server.log",
        "comparison-evidence-ci.json",
    ),
}

_EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:01[016789]|0\d{1,2})[- .]?\d{3,4}[- .]?\d{4}(?!\d)")
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/-]{8,}")
_SECRET_ASSIGN_RE = re.compile(
    r"(?i)\b(api[_ -]?key|token|secret|authorization)\b\s*[:=]\s*([^\s,;]+)"
)
_QUERY_RE = re.compile(r"(https?://[^\s?#]+|\s/[^\s?#]*)\?[^\s\"]+")
_JSON_SENSITIVE_RE = re.compile(
    r'(?i)("(?:question|prompt|resident_question|raw_error|provider_error)"\s*:\s*)"(?:[^"\\]|\\.)*"'
)
_TEXT_SENSITIVE_RE = re.compile(
    r"(?i)\b(question|prompt|resident_question|raw_error|provider_error)\s*[:=].*$"
)


def sanitize_log_text(text: str) -> str:
    text = text[-MAX_LOG_BYTES:]
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _PHONE_RE.sub("[redacted-phone]", text)
    text = _BEARER_RE.sub("Bearer [redacted]", text)
    text = _SECRET_ASSIGN_RE.sub(lambda m: f"{m.group(1)}=[redacted]", text)
    text = _JSON_SENSITIVE_RE.sub(lambda m: f'{m.group(1)}"[redacted]"', text)
    text = _TEXT_SENSITIVE_RE.sub(lambda m: f"{m.group(1)}=[redacted]", text)
    text = _QUERY_RE.sub(lambda m: f"{m.group(1)}?[redacted]", text)
    return text


def summarize_comparison_evidence(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError("comparison evidence must be an object")

    safe_runs: list[dict[str, object]] = []
    for raw in payload.get("primary_runs", []):
        if not isinstance(raw, dict):
            continue
        safe_runs.append(
            {
                "mode": raw.get("mode"),
                "scenario_id": raw.get("scenario_id"),
                "attempt": raw.get("attempt"),
                "external_request_count": raw.get("external_request_count"),
                "no_submit_preserved": raw.get("no_submit_preserved"),
                "action_step_count": raw.get("action_step_count"),
            }
        )

    return {
        "schema_version": payload.get("schema_version"),
        "primary_run_count": len(safe_runs),
        "primary_runs": safe_runs,
    }


def collect(job: str, source_root: Path, out_dir: Path) -> dict[str, object]:
    if job not in JOB_SOURCES:
        raise ValueError(f"unsupported job: {job}")

    out_dir.mkdir(parents=True, exist_ok=True)
    collected: list[str] = []
    missing: list[str] = []

    for filename in JOB_SOURCES[job]:
        source = source_root / filename
        if not source.is_file():
            missing.append(filename)
            continue

        if filename == "comparison-evidence-ci.json":
            payload = json.loads(source.read_text(encoding="utf-8"))
            safe = summarize_comparison_evidence(payload)
            target = out_dir / "comparison-evidence-summary.json"
            target.write_text(
                json.dumps(safe, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        else:
            raw = source.read_text(encoding="utf-8", errors="replace")
            target = out_dir / filename
            target.write_text(sanitize_log_text(raw), encoding="utf-8")
        collected.append(target.name)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "job": job,
        "privacy": {
            "environment_dump_included": False,
            "raw_question_included": False,
            "raw_provider_error_included": False,
            "source_allowlist_only": True,
            "max_log_bytes": MAX_LOG_BYTES,
        },
        "collected": sorted(collected),
        "missing_optional_sources": sorted(missing),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True, choices=sorted(JOB_SOURCES))
    parser.add_argument("--source-root", default="/tmp")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    manifest = collect(args.job, Path(args.source_root), Path(args.out_dir))
    print(
        f"failure artifacts prepared: job={args.job} "
        f"collected={len(manifest['collected'])} "
        f"missing={len(manifest['missing_optional_sources'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
