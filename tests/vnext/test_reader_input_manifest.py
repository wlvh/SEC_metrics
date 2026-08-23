"""Reader complete-table input manifest and strict output contract tests."""

from __future__ import annotations

import copy
import inspect
import json
import unittest

from tests.vnext.common import compiled_specs, reader_response, sample_asset
from vnext.reader import ReaderError, validate_reader_output
from vnext.reader_input import ReaderInputError, build_reader_input_manifest
from vnext.reader_input import build_reader_payload, verify_reader_table_set


class ReaderInputManifestTest(unittest.TestCase):
    """Prove exact table-set transport and strict three-role output."""

    def setUp(self) -> None:
        """Build one deterministic complete two-table asset and manifest."""
        self.asset = sample_asset()
        self.source_ids = ["sha256:" + "c" * 64]
        self.manifest = build_reader_input_manifest(
            derived_asset=self.asset, source_reference_ids=self.source_ids,
        )

    def test_metric_words_cannot_change_reader_table_set(self) -> None:
        """Keep exact input bytes stable across unrelated task wording."""
        first = build_reader_payload(
            manifest=self.manifest,
            derived_asset=self.asset,
            task_contract={"metric_words": ["occupancy", "RevPAR"]},
        )
        second = build_reader_payload(
            manifest=self.manifest,
            derived_asset=self.asset,
            task_contract={"metric_words": ["bananas", "instructions"]},
        )
        self.assertEqual(
            first["body"]["untrusted_table_data"],
            second["body"]["untrusted_table_data"],
        )
        parameters = inspect.signature(build_reader_payload).parameters
        self.assertNotIn("query", parameters)
        self.assertNotIn("filter", parameters)
        self.assertNotIn("callback", parameters)

    def test_removed_or_reordered_table_is_rejected(self) -> None:
        """Reject an input manifest that no longer exact-lists the grid."""
        changed = copy.deepcopy(self.manifest)
        changed["tables"].reverse()
        with self.assertRaises(ReaderInputError):
            verify_reader_table_set(
                manifest=changed, derived_asset=self.asset,
            )

    def test_reader_requires_one_ordered_complete_role_group(self) -> None:
        """Accept three exact roles and reject duplicate or unknown fields."""
        response = reader_response(asset=self.asset).decode("utf-8")
        candidate = validate_reader_output(
            response_text=response,
            attempt_id="attempt:reader:fixture",
            required_roles=["occupancy", "revpar", "adr"],
            scope_contract=compiled_specs()["DISCLOSURE"]["compiled"][
                "scope_contract"
            ],
            source_reference_ids=self.source_ids,
            derived_asset_ids=[self.asset["derived_asset_id"]],
        )
        self.assertEqual(
            ["occupancy", "revpar", "adr"], list(candidate["selected"]),
        )
        parsed = json.loads(response)
        parsed["candidates"][1]["role"] = "occupancy"
        with self.assertRaisesRegex(ReaderError, "roles"):
            validate_reader_output(
                response_text=json.dumps(parsed),
                attempt_id="attempt:reader:fixture",
                required_roles=["occupancy", "revpar", "adr"],
                scope_contract=compiled_specs()["DISCLOSURE"]["compiled"][
                    "scope_contract"
                ],
                source_reference_ids=self.source_ids,
                derived_asset_ids=[self.asset["derived_asset_id"]],
            )
        parsed = json.loads(response)
        parsed["unexpected"] = True
        with self.assertRaises(ReaderError):
            validate_reader_output(
                response_text=json.dumps(parsed),
                attempt_id="attempt:reader:fixture",
                required_roles=["occupancy", "revpar", "adr"],
                scope_contract=compiled_specs()["DISCLOSURE"]["compiled"][
                    "scope_contract"
                ],
                source_reference_ids=self.source_ids,
                derived_asset_ids=[self.asset["derived_asset_id"]],
            )

    def test_reader_locator_must_stay_inside_target_table(self) -> None:
        """Reject a selected claim that crosses to another supplied table."""
        parsed = json.loads(reader_response(asset=self.asset))
        locator = parsed["candidates"][0]["locator"]
        locator.update(
            {
                "table_id": "table_000001",
                "row_index": 0,
                "column_index": 0,
                "origin_row_index": 0,
                "origin_column_index": 0,
                "rowspan": 1,
                "colspan": 1,
            }
        )
        with self.assertRaisesRegex(ReaderError, "target table"):
            validate_reader_output(
                response_text=json.dumps(parsed),
                attempt_id="attempt:reader:fixture",
                required_roles=["occupancy", "revpar", "adr"],
                scope_contract=compiled_specs()["DISCLOSURE"]["compiled"][
                    "scope_contract"
                ],
                source_reference_ids=self.source_ids,
                derived_asset_ids=[self.asset["derived_asset_id"]],
            )


if __name__ == "__main__":
    unittest.main()
