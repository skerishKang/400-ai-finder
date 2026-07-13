"""Page Agent server-side adapter boundary (Stage 4).

Python package marker for the provider-neutral plan schema documentation
and future pure-Python contract helpers.

The live Cloudflare Pages Function owner lives at:

    functions/api/page-agent/plan.js
    functions/api/page-agent/_adapter.js
    functions/api/page-agent/_schema.js

Stage 4 ships disabled-by-default. Real provider calls are not implemented.
"""

__all__ = [
    "ENABLE_FLAG",
    "ALLOWED_ACTIONS",
    "RESULT_BOUNDARY",
    "ABS_MAX_STEPS",
]

# Keep in sync with functions/api/page-agent/_schema.js
ENABLE_FLAG = "PAGE_AGENT_MODEL_ENABLED"
ALLOWED_ACTIONS = (
    "click",
    "input",
    "select",
    "scroll",
    "read",
    "navigate",
)
RESULT_BOUNDARY = "STOP_FOR_USER_CONFIRMATION"
ABS_MAX_STEPS = 10
