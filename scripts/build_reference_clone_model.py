#!/usr/bin/env python3
"""Write or check the #1303 G2-A reference clone model fixture.

The fixture is derived deterministically from the committed G1 named-site
reference capture ledger and its committed artifact files. The input capture
directory is selected EXPLICITLY via --capture-root (glob discovery is
forbidden by the G2-A work instruction). Run with --check to verify the
committed fixture matches regeneration.

Usage:
  python scripts/build_reference_clone_model.py --capture-root PATH            # write fixture
  python scripts/build_reference_clone_model.py --capture-root PATH --check    # verify committed
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from official_clone.reference_clone_model import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
