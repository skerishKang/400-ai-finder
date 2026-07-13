"""Provider-neutral Page Agent plan schema constants (Stage 4).

Mirrors ``functions/api/page-agent/_schema.js`` for documentation and
future Python contract tests. Does not perform network I/O.
"""

from __future__ import annotations

from typing import Final

ENABLE_FLAG: Final[str] = "PAGE_AGENT_MODEL_ENABLED"
PROVIDER_ENV: Final[str] = "PAGE_AGENT_MODEL_PROVIDER"

ALLOWED_ACTIONS: Final[tuple[str, ...]] = (
    "click",
    "input",
    "select",
    "scroll",
    "read",
    "navigate",
)

ALLOWED_REQUEST_KEYS: Final[tuple[str, ...]] = (
    "request_id",
    "question",
    "current_route",
    "available_actions",
    "max_steps",
)

RESULT_BOUNDARY: Final[str] = "STOP_FOR_USER_CONFIRMATION"
DEFAULT_MAX_STEPS: Final[int] = 10
ABS_MAX_STEPS: Final[int] = 10
DISABLED_ERROR: Final[str] = "page_agent_model_disabled"
