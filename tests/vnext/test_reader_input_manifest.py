"""Reader complete-table input manifest and strict output contract tests."""

from __future__ import annotations

import copy
import inspect
import json
import unittest

from tests.vnext.common import compiled_specs, reader_response, sample_asset
from vnext.reader import ReaderError, validate_reader_output
from vnext.reader_input import ReaderInputError, build_reader_input_manifest
from vnext.reader_input import build_reader_payload, build_reader_shard_payload
from vnext.reader_input import verify_reader_table_set
from vnext.table_payload import build_contiguous_table_shard
from vnext.table_payload import encode_compact_table_payload
from vnext.table_payload import validate_contiguous_table_shard_set


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

    def test_shard_payload_keeps_full_manifest_and_exact_contiguous_slice(
        self,
    ) -> None:
        """Expose one table's bytes while retaining full-set coverage authority."""
        parent = encode_compact_table_payload(derived_asset=self.asset)
        shards = [
            build_contiguous_table_shard(
                parent_transport=parent,
                shard_index=index,
                shard_count=2,
                start_table_order=index,
                end_table_order=index,
            )
            for index in range(2)
        ]
        coverage = validate_contiguous_table_shard_set(
            shards=shards, parent_transport=parent,
        )
        payload = build_reader_shard_payload(
            manifest=self.manifest,
            derived_asset=self.asset,
            task_contract={"metric_words": ["must-not-select"]},
            table_shard=shards[1],
            table_shard_set_id=coverage["shard_set_id"],
        )
        self.assertEqual(
            self.manifest,
            payload["body"]["reader_input_manifest"],
        )
        self.assertEqual(
            [self.asset["tables"][1]["table_id"]],
            payload["body"]["table_shard_contract"]["table_ids"],
        )
        self.assertEqual(
            shards[1], payload["body"]["untrusted_table_data"],
        )
        self.assertFalse(
            payload["body"]["table_shard_contract"]["semantic_prefilter"]
        )
        self.assertFalse(
            payload["body"]["table_shard_contract"]["selector"]
        )

    def test_shard_payload_rejects_substitution_before_reader_use(self) -> None:
        """Reject a shard whose parent entry or set identity was substituted."""
        parent = encode_compact_table_payload(derived_asset=self.asset)
        shard = build_contiguous_table_shard(
            parent_transport=parent,
            shard_index=0,
            shard_count=1,
            start_table_order=0,
            end_table_order=1,
        )
        mutated = copy.deepcopy(shard)
        mutated["table_ids"][0] = "table_substituted"
        with self.assertRaises(ReaderInputError):
            build_reader_shard_payload(
                manifest=self.manifest,
                derived_asset=self.asset,
                task_contract={"metric_words": []},
                table_shard=mutated,
                table_shard_set_id="sha256:" + ("a" * 64),
            )
        with self.assertRaises(ReaderInputError):
            build_reader_shard_payload(
                manifest=self.manifest,
                derived_asset=self.asset,
                task_contract={"metric_words": []},
                table_shard=shard,
                table_shard_set_id="not-content-addressed",
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
