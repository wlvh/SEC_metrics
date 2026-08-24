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
from vnext.stage_a_snapshot import (  # noqa: E402
    SOURCE_ONLY_ERRORS,
    StageASnapshotError,
    validate_stage_a_snapshot,
)
from vnext.stage_c_packet import (  # noqa: E402
    StageCAPacketError,
    validate_stage_c_a_packet,
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
        # Stage A changes source authority but deliberately keeps the R2
        # validation sidecar/root artifacts immutable.  Accept that narrow
        # case only when an independently current-source overlay proves both
        # the new clean tree and every historical R2 byte still match.
        if set(result.errors) == SOURCE_ONLY_ERRORS:
            try:
                stage_c = validate_stage_c_a_packet(repo_root=WORKDIR)
            except StageCAPacketError as stage_c_error:
                stage_c_failure = stage_c_error
            else:
                if stage_c["source_commit_equivalent_tree"]:
                    print(
                        "WARNING: Stage-C packet base commit differs but its "
                        "complete source-input tree is equivalent"
                    )
                print(
                    "PASS: historical R2 provenance and current Stage C-A "
                    "decision-evidence overlay verified"
                )
                return 0
            try:
                stage_a = validate_stage_a_snapshot(repo_root=WORKDIR)
            except StageASnapshotError as error:
                print(
                    "FAIL: Stage-C validation overlay: {}".format(
                        stage_c_failure
                    )
                )
                print("FAIL: Stage-A validation overlay: {}".format(error))
            else:
                if stage_a["source_commit_equivalent_tree"]:
                    print(
                        "WARNING: Stage-A artifact commit differs but its "
                        "complete source-input tree is equivalent"
                    )
                print(
                    "PASS: historical R2 provenance and current Stage-A "
                    "source overlay verified"
                )
                return 0
        for error in result.errors:
            print("FAIL: {}".format(error))
        return 1
    print("PASS: validation snapshot provenance and artifact digests verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
