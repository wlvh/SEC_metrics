"""D04's single-object bound, widened only where the frozen grouping refuses.

The frozen D04 source grouping refuses any single source object whose encoded
payload exceeds 300,000 bytes. Pfizer's FY2022 annual report carries an inline
continuation of its pension plan-asset table that is 313,218 bytes encoded and
about 137,000 reference tokens: over the byte bound, inside the request's own
bound (``continuous_request_context``: reference tokens plus the output reserve
within the model context). The successor groups such a document again with the
single-object bound set to the request's byte limit, records it, and leaves
every document the frozen grouping accepts as it was.

Reads Pfizer's filing from the acquisition's export (saved-source tier) and an
Enphase annual report from the checkout. Zero calls.
"""
import unittest
from unittest.mock import Mock, patch

from tests.vnext.common import REPO_ROOT as ROOT
from tools.acceptance_readings import saved_bytes
from vnext import historical_semantic_source as pinned
from vnext import r6_semantic_source as frozen
from vnext.continuous_request_context import MAX_BYTES, measured_groups
from vnext.historical_dei import overrides_of

PFIZER_2022 = ("evidence/request_attempts/3f/3f7fbed78fb0df432afcb1463bf372283a07eae770503e00cc9190d01e6d9f5e/"
               "pfe-20221231.htm")
ENPHASE_2025 = "evidence/accession_materials/enphase_energy_1463101_000146310126000013/enph-20251231.htm"
COMPONENT = {"document": {"text_document_id": "document"}}
FROZEN_BOUND = frozen.POLICY["max_single_object_payload_bytes"]


class AFilingOverTheFrozenBoundTest(unittest.TestCase):
    """Pfizer FY2022: refused by the frozen grouping, grouped by the successor."""

    @classmethod
    def setUpClass(cls):
        cls.raw = saved_bytes(repo_root=ROOT, relative=PFIZER_2022)
        cls.visible, cls.native, cls.coverage, cls.bound = pinned._document_units(
            [], cls.raw, COMPONENT, "document")

    def test_the_frozen_grouping_refuses_it(self):
        with self.assertRaisesRegex(frozen.SemanticSourceError, "^" + pinned.SINGLE_OBJECT_REFUSAL + "$"):
            frozen._native_units(self.raw, COMPONENT)

    def test_the_document_says_which_bound_admitted_it_and_names_the_unit(self):
        record = self.bound["single_object_bound"]
        self.assertEqual((FROZEN_BOUND, MAX_BYTES, pinned.SINGLE_OBJECT_REFUSAL),
                         (record["frozen_bytes"], record["successor_bytes"], record["frozen_refusal"]))
        over = record["units_over_the_frozen_bound"]
        self.assertEqual([("NATIVE_SUPPLEMENTS", 313218)], [(u["kind"], u["payload_bytes"]) for u in over])
        named = [u for u in self.native if u["unit_id"] == over[0]["unit_id"]]
        self.assertEqual(1, len(named))
        self.assertEqual(len(frozen._bytes(named[0]["payload"])), named[0]["payload_bytes"])

    def test_the_named_unit_is_one_whole_continuation_copied_from_the_filing(self):
        unit = next(u for u in self.native
                    if u["unit_id"] == self.bound["single_object_bound"]["units_over_the_frozen_bound"][0]["unit_id"])
        [obj] = unit["payload"]["objects"]
        self.assertEqual("continuation", obj["local_name"])
        text = self.raw.decode("utf-8-sig")
        self.assertEqual(text[obj["start_character"]:obj["end_character"]], obj["raw_xml"])

    def test_the_grouping_rule_is_otherwise_the_frozen_one(self):
        # As in the frozen grouping, a unit over the unit limit holds exactly
        # one source row; the only units over the frozen single-object bound
        # are the ones the record names.
        limit = frozen.POLICY["max_unit_payload_bytes"]
        rows = {"VISIBLE_TEXT": "blocks", "NATIVE_FACTS": "facts", "NATIVE_SUPPLEMENTS": "objects"}
        units = self.visible + self.native
        for unit in units:
            if unit["payload_bytes"] > limit:
                self.assertEqual(1, len(unit["payload"][rows[unit["kind"]]]), unit["unit_id"])
        self.assertEqual({u["unit_id"] for u in self.bound["single_object_bound"]["units_over_the_frozen_bound"]},
                         {u["unit_id"] for u in units if u["payload_bytes"] > FROZEN_BOUND})
        self.assertTrue(self.coverage["native_roundtrip_verified"])

    def test_the_request_bound_admits_it_and_refuses_one_twice_its_size(self):
        unit = next(u for u in self.native
                    if u["unit_id"] == self.bound["single_object_bound"]["units_over_the_frozen_bound"][0]["unit_id"])

        def request(group):
            return {"metric_id": "D04", "system_prompt": "Review every unit.", "units": group}

        admitted = {**unit, "document_id": "document"}
        self.assertEqual([[admitted]], measured_groups([admitted], request))
        doubled = {**admitted, "unit_id": "doubled",
                   "payload": {"objects": unit["payload"]["objects"] * 2}}
        with self.assertRaisesRegex(ValueError, "CONTINUOUS_CONTEXT_SINGLE_SOURCE_UNIT_EXCEEDS_BOUND:doubled"):
            measured_groups([doubled], request)


class ADocumentTheFrozenGroupingAcceptsTest(unittest.TestCase):
    """Enphase FY2025: the frozen answer, unchanged, and no record."""

    def test_it_is_the_frozen_grouping(self):
        raw = (ROOT / ENPHASE_2025).read_bytes()
        native, coverage = frozen._native_units(raw, COMPONENT)
        self.assertEqual(([], native, coverage, {}), pinned._document_units([], raw, COMPONENT, "document"))


class OnlyTheSingleObjectRefusalIsWidenedTest(unittest.TestCase):

    def test_another_frozen_refusal_is_raised_unchanged(self):
        wider = Mock()
        with patch.object(frozen, "_native_units",
                          side_effect=frozen.SemanticSourceError("SEMANTIC_NATIVE_CONTEXT_MISSING")), \
                patch.object(pinned, "_WIDER_NATIVE_UNITS", wider), \
                self.assertRaisesRegex(frozen.SemanticSourceError, "^SEMANTIC_NATIVE_CONTEXT_MISSING$"):
            pinned._document_units([], b"", COMPONENT, "document")
        wider.assert_not_called()

    def test_the_successor_policy_changes_one_number(self):
        changed = {k for k in frozen.POLICY if frozen.POLICY[k] != pinned.SINGLE_OBJECT_POLICY[k]}
        self.assertEqual(set(frozen.POLICY), set(pinned.SINGLE_OBJECT_POLICY))
        self.assertEqual({"max_single_object_payload_bytes"}, changed)
        self.assertEqual(MAX_BYTES, pinned.SINGLE_OBJECT_POLICY["max_single_object_payload_bytes"])
        self.assertEqual({"POLICY": pinned.SINGLE_OBJECT_POLICY}, overrides_of(pinned._WIDER_GROUP))
        self.assertEqual({"_group": pinned._WIDER_GROUP}, overrides_of(pinned._WIDER_NATIVE_UNITS))


if __name__ == "__main__":
    unittest.main()
