from __future__ import annotations

import argparse
import json
import re
import shutil
import stat
from pathlib import Path


SCHEMA_VERSION = "1.1.0"
MAX_LOG_BYTES = 128 * 1024
MAX_PNG_BYTES = 4 * 1024 * 1024
MAX_TRACE_BYTES = 32 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
ZIP_MAGIC = b"PK\x03\x04"
EVIDENCE_ROOT_NAME = "400-ai-finder-1116"
TRACE_FILENAME = "responsive-trace.zip"

# Literal exact allowlist — no globs, no recursive /tmp walks. The responsive
# harness (tests/browser/verify_first_use_responsive.mjs) produces exactly
# these 18 deterministic PNGs plus one bounded Stage-B trace.
VISUAL_FILENAMES = (
    "320-entry.png",
    "320-confirm.png",
    "320-first-action.png",
    "320-search-typing.png",
    "320-result.png",
    "320-view-switch.png",
    "320-reset.png",
    "390-entry.png",
    "390-confirm.png",
    "390-first-action.png",
    "390-search-typing.png",
    "390-result.png",
    "390-view-switch.png",
    "390-reset.png",
    "390-writing-route.png",
    "390-writing-typing.png",
    "390-writing-cancelled.png",
    "1440-desktop.png",
    TRACE_FILENAME,
)
VISUAL_JOBS = frozenset({"citizen-browser"})

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


def _redact_secret_assign(match: re.Match[str]) -> str:
    # "Authorization: Bearer <token>" is owned by _BEARER_RE, which already
    # redacts the token to "Bearer [redacted]"; the literal word "Bearer" is
    # not itself a secret. Skipping it here preserves that canonical form.
    if match.group(2).lower() == "bearer":
        return match.group(0)
    return f"{match.group(1)}=[redacted]"
_QUERY_RE = re.compile(r"(https?://[^\s?#]+|\s/[^\s?#]*)\?[^\s\"]+")
_JSON_SENSITIVE_RE = re.compile(
    r'(?i)("(?:question|prompt|resident_question|raw_error|provider_error)"\s*:\s*)"(?:[^"\\]|\\.)*"'
)
_TEXT_SENSITIVE_RE = re.compile(
    r"(?i)\b(question|prompt|resident_question|raw_error|provider_error)\s*[:=].*$"
)


def sanitize_log_text(text: str) -> str:
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _PHONE_RE.sub("[redacted-phone]", text)
    text = _BEARER_RE.sub("Bearer [redacted]", text)
    text = _SECRET_ASSIGN_RE.sub(_redact_secret_assign, text)
    text = _JSON_SENSITIVE_RE.sub(lambda m: f'{m.group(1)}"[redacted]"', text)
    text = _TEXT_SENSITIVE_RE.sub(lambda m: f"{m.group(1)}=[redacted]", text)
    text = _QUERY_RE.sub(lambda m: f"{m.group(1)}?[redacted]", text)

    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_LOG_BYTES:
        return text

    tail = encoded[-MAX_LOG_BYTES:]
    # The byte cap can land mid-code-point. Drop the partial leading UTF-8
    # sequence (the source was read with errors="replace", so the payload is
    # valid UTF-8 and only the cut boundary can be incomplete), then decode
    # back to valid UTF-8 text.
    return tail.decode("utf-8", errors="ignore")


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


def _require_regular_file(path: Path, label: str) -> None:
    """lstat-based guard: reject symlinks and non-regular files.

    Raises:
        FileNotFoundError: if *path* does not exist.
        ValueError: if *path* is a symlink or not a regular file.
    """
    st = path.lstat()
    if stat.S_ISLNK(st.st_mode):
        raise ValueError(f"{label} must not be a symlink: {path}")
    if not stat.S_ISREG(st.st_mode):
        raise ValueError(f"{label} must be a regular file: {path}")


def _visual_root(source_root: Path) -> Path:
    """Return the guarded visual evidence root under *source_root*.

    The root must be a real directory (never a symlink) whose resolved parent
    is the resolved source root — in CI the resolved OS temp directory.
    """
    root = source_root / EVIDENCE_ROOT_NAME
    st = root.lstat()
    if stat.S_ISLNK(st.st_mode):
        raise ValueError(f"visual evidence root must not be a symlink: {root}")
    if not stat.S_ISDIR(st.st_mode):
        raise ValueError(f"visual evidence root must be a directory: {root}")
    if root.resolve().parent != source_root.resolve():
        raise ValueError(
            f"visual evidence root parent mismatch: {root} "
            f"(parent={root.resolve().parent}, source_root={source_root.resolve()})"
        )
    return root


def _validate_visual_source(source: Path, name: str) -> None:
    """Validate one allowlisted visual evidence file (PNG or trace).

    Guards: lstat (no symlink, regular file), resolved parent == resolved
    evidence root, bounded size, and binary signature.
    """
    _require_regular_file(source, f"visual evidence {name}")
    if source.resolve().parent != _visual_root(source.parents[1]).resolve():
        raise ValueError(f"visual evidence escapes evidence root: {source}")
    if name == TRACE_FILENAME:
        if source.lstat().st_size > MAX_TRACE_BYTES:
            raise ValueError(f"trace exceeds {MAX_TRACE_BYTES} bytes: {source}")
        with source.open("rb") as fh:
            head = fh.read(4)
        if head != ZIP_MAGIC:
            raise ValueError(f"trace missing ZIP signature: {source}")
    else:
        if source.lstat().st_size > MAX_PNG_BYTES:
            raise ValueError(f"png exceeds {MAX_PNG_BYTES} bytes: {source}")
        with source.open("rb") as fh:
            head = fh.read(8)
        if head != PNG_MAGIC:
            raise ValueError(f"png missing PNG magic: {source}")


def _copy_binary(source: Path, target: Path) -> None:
    """Byte-for-byte copy; binary evidence is never decoded or sanitized."""
    with source.open("rb") as src, target.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)


def collect(job: str, source_root: Path, out_dir: Path) -> dict[str, object]:
    if job not in JOB_SOURCES:
        raise ValueError(f"unsupported job: {job}")

    out_dir.mkdir(parents=True, exist_ok=True)
    collected: list[str] = []
    missing: list[str] = []
    missing_visual: list[str] = []
    visual_manifest: dict[str, object] | None = None

    for filename in JOB_SOURCES[job]:
        source = source_root / filename
        try:
            _require_regular_file(source, filename)
        except FileNotFoundError:
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

    if job in VISUAL_JOBS:
        try:
            root = _visual_root(source_root)
        except FileNotFoundError:
            # No evidence produced this run: report every allowlisted name as
            # missing and never search an arbitrary fallback directory.
            missing_visual = list(VISUAL_FILENAMES)
            visual_manifest = {
                "evidence_root": str(source_root / EVIDENCE_ROOT_NAME),
                "png_max_bytes": MAX_PNG_BYTES,
                "trace_max_bytes": MAX_TRACE_BYTES,
                "png_magic_hex": PNG_MAGIC.hex(),
                "zip_signature_hex": ZIP_MAGIC.hex(),
            }
        else:
            visual_manifest = {
                "evidence_root": str(root),
                "png_max_bytes": MAX_PNG_BYTES,
                "trace_max_bytes": MAX_TRACE_BYTES,
                "png_magic_hex": PNG_MAGIC.hex(),
                "zip_signature_hex": ZIP_MAGIC.hex(),
            }
            for name in VISUAL_FILENAMES:
                source = root / name
                try:
                    _validate_visual_source(source, name)
                except FileNotFoundError:
                    missing_visual.append(name)
                    continue
                target = out_dir / name
                _copy_binary(source, target)
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
        "missing_visual_sources": sorted(missing_visual),
        "visual": visual_manifest,
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
        f"missing={len(manifest['missing_optional_sources'])} "
        f"missing_visual={len(manifest['missing_visual_sources'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
