"""Verify that a committed validation snapshot still matches this checkout."""

from __future__ import annotations

import sys
from pathlib import Path


WORKDIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = WORKDIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from validation_provenance import (  # noqa: E402
    ValidationProvenanceError,
    pin_validation_publication_transaction,
    verify_validation_snapshot,
)


def main() -> int:
    """Return zero only for a byte-bound source/artifact snapshot."""
    try:
        transaction = pin_validation_publication_transaction(
            workdir=WORKDIR,
        )
    except ValidationProvenanceError as error:
        print("FAIL: {}".format(error))
        return 1
    result = verify_validation_snapshot(
        workdir=WORKDIR,
        allow_equivalent_source_tree=True,
        publication_transaction=transaction,
    )
    for warning in result.warnings:
        print("WARNING: {}".format(warning))
    if result.errors:
        for error in result.errors:
            print("FAIL: {}".format(error))
        return 1
    print("PASS: validation snapshot provenance and artifact digests verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
