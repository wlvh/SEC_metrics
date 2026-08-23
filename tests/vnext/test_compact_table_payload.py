"""Exercise WB-4 compact table transport against every frozen layout source."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from vnext.canonical import sha256_bytes
from vnext.table_grid import build_table_grid
from vnext.table_payload import decode_compact_table_payload
from vnext.table_payload import encode_compact_table_payload
from vnext.table_payload import TablePayloadError


REPO_ROOT = Path(__file__).resolve().parents[2]
LAYOUT_ROOT = REPO_ROOT / "fixtures/vnext/layouts"
MARRIOTT_PROVENANCE = (
    REPO_ROOT / "fixtures/vnext/recorded/marriott_2025_fixture_provenance.json"
)
TABLE_ROUND_TRIP_FIELDS = {
    "table_id",
    "order",
    "caption",
    "caption_raw_text",
    "row_count",
    "column_count",
}
CELL_ROUND_TRIP_FIELDS = {
    "row_index",
    "column_index",
    "origin_row_index",
    "origin_column_index",
    "rowspan",
    "colspan",
    "header",
    "is_origin",
    "raw_text",
    "text",
}


def _json_object(*, path: Path) -> dict:
    """Read one UTF-8 fixture object without silently accepting other shapes.

    Args:
        path: Regular repository fixture path.

    Returns:
        Parsed object with the fixture-declared source metadata.
    """
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise AssertionError("Fixture JSON root is not an object")
    return value


def _round_trip_sources() -> list[tuple[str, Path, str]]:
    """Return Marriott, all Hilton layouts, and all Hyatt holdouts in order.

    Returns:
        Eleven fixture IDs with source paths and their exact SHA-256 values.
    """
    marriott = _json_object(path=MARRIOTT_PROVENANCE)
    sources = [
        (
            str(marriott["fixture_id"]),
            REPO_ROOT / str(marriott["source_repo_relative_path"]),
            str(marriott["source_sha256"]),
        )
    ]
    fixtures = sorted(
        path for path in LAYOUT_ROOT.iterdir() if path.is_dir()
    )
    for root in fixtures:
        manifest = _json_object(path=root / "fixture_manifest.json")
        fixture_id = str(manifest["fixture_id"])
        if not (
            fixture_id.startswith("hilton-")
            or fixture_id.startswith("hyatt-")
        ):
            continue
        sources.append(
            (
                fixture_id,
                REPO_ROOT / str(manifest["source_repo_relative_path"]),
                str(manifest["source_sha256"]),
            )
        )
    if len(sources) != 11:
        raise AssertionError("WB-4 must cover exactly eleven layout sources")
    return sources


class CompactTablePayloadTest(unittest.TestCase):
    """Prove compact transport has no authority or semantic loss."""

    def test_all_eleven_sources_round_trip_every_expanded_field(self) -> None:
        """Recover every table and every cell from compact transport exactly."""
        for fixture_id, source_path, expected_sha256 in _round_trip_sources():
            with self.subTest(fixture_id=fixture_id):
                source_bytes = source_path.read_bytes()
                self.assertEqual(expected_sha256, sha256_bytes(content=source_bytes))
                asset = build_table_grid(
                    html_bytes=source_bytes,
                    parent_raw_asset_ids=["sha256:" + expected_sha256],
                    storage_uri=(
                        "artifacts/vnext/wb4/{}.json".format(fixture_id)
                    ),
                )
                compact = encode_compact_table_payload(derived_asset=asset)
                decoded = decode_compact_table_payload(transport=compact)
                self.assertEqual(asset["tables"], decoded)
                self.assertEqual(
                    asset["derived_asset_id"],
                    compact["expanded_derived_asset_id"],
                )
                for table in decoded:
                    self.assertTrue(TABLE_ROUND_TRIP_FIELDS <= set(table))
                    for row in table["rows"]:
                        for cell in row["cells"]:
                            self.assertTrue(
                                CELL_ROUND_TRIP_FIELDS <= set(cell)
                            )

    def test_mutated_compact_transport_fails_before_any_evidence_use(self) -> None:
        """Reject a compact payload whose canonical byte identity was changed."""
        fixture_id, source_path, expected_sha256 = _round_trip_sources()[0]
        asset = build_table_grid(
            html_bytes=source_path.read_bytes(),
            parent_raw_asset_ids=["sha256:" + expected_sha256],
            storage_uri="artifacts/vnext/wb4/{}.json".format(fixture_id),
        )
        compact = encode_compact_table_payload(derived_asset=asset)
        compact["tables"][0]["i"] = "table_mutated"
        with self.assertRaises(TablePayloadError):
            decode_compact_table_payload(transport=compact)


if __name__ == "__main__":
    unittest.main()
