#!/usr/bin/env python3
"""Print the zero-AI producer/public-renderer independence receipt."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from vnext.projection_independence import (  # noqa: E402
    build_projection_independence_receipt,
)


def main() -> int:
    """Emit one deterministic JSON proof and return zero on success."""
    receipt = build_projection_independence_receipt(repo_root=REPO_ROOT)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
