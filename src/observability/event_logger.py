import json
import logging
import uuid
from typing import Any


_ALLOWED_KEYS = (
    "correlation_id",
    "duration_ms",
    "event",
    "failure_code",
    "ok",
    "site_id",
    "stage",
)


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def get_event_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_pipeline_event(
    logger: logging.Logger,
    *,
    event: str,
    correlation_id: str,
    stage: str | None = None,
    ok: bool | None = None,
    duration_ms: int | None = None,
    site_id: str | None = None,
    failure_code: str | None = None,
) -> None:
    record: dict[str, Any] = {
        "event": event,
        "correlation_id": correlation_id,
    }
    if stage is not None:
        record["stage"] = stage
    if ok is not None:
        record["ok"] = ok
    if duration_ms is not None:
        record["duration_ms"] = duration_ms
    if site_id:
        record["site_id"] = site_id
    if failure_code is not None:
        record["failure_code"] = failure_code

    filtered = {key: record[key] for key in _ALLOWED_KEYS if key in record}
    logger.info(
        "pipeline_event=%s",
        json.dumps(filtered, ensure_ascii=False, sort_keys=True),
    )
