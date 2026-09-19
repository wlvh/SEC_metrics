"""The successor protocol carries one more bound and not one fewer check.

A copy of a validator that silently stops validating still passes everything it
is asked to check, so the guarantee here is differential rather than
descriptive: for any payload at or under the frozen bound, the successor must
return exactly what the frozen implementation returns and raise exactly the
error it raises. Every mutation below is applied to a real, valid payload, and
each one is run through both implementations.

The capacity cases then check the part that did change - and check it on the
items past the frozen bound, because validating only the first 64 of 92 is the
specific way this could be wrong and still look right.
"""
import copy
import unittest

from vnext import historical_text_protocol as successor
from vnext import text_results as frozen
from vnext.historical_text_protocol import (FROZEN_PROTOCOL_MAX_ITEMS, declared_spec_ceiling,
                                            revised_spec_ceilings)
from vnext.text_results import TextResultError

REVISED_SPEC = "catalog/r6/D02_legal_disclosures_v2.md"


def _payload(count, *, start=0):
    return {"version": "TEXT_V1", "content_kind": "SOURCE_EXCERPTS",
            "renderer": "ORDERED_NEWLINE_V1",
            "coverage_hashes": ["sha256:" + "a" * 64],
            "candidate_hash": "sha256:" + "b" * 64,
            "review_unit_hash": "sha256:" + "c" * 64,
            "approval_effect_hash": "sha256:" + "d" * 64,
            "items": [{"order": n, "role": "ROLE_%d" % n, "text": "excerpt %d" % n,
                       "observation_id": "sha256:" + ("%064x" % (n + start))}
                      for n in range(count)]}


def _outcome(function, **kwargs):
    """What one implementation did: the value, or the exact refusal."""
    try:
        return ("VALUE", function(**kwargs))
    except TextResultError as error:
        return ("REFUSED", str(error))


# Each mutation takes the payload and the item index to corrupt, so the same
# corruption can be applied inside the frozen bound and past it. They are the
# frozen renderer's own checks, one per check, so a copy that dropped any of
# them would differ here rather than pass quietly.
PAYLOAD_MUTATIONS = {
    "unknown_field": lambda p, i: p.__setitem__("extra", 1),
    "missing_field": lambda p, i: p.pop("coverage_hashes"),
    "wrong_version": lambda p, i: p.__setitem__("version", "TEXT_V2"),
    "wrong_content_kind": lambda p, i: p.__setitem__("content_kind", "SUMMARY"),
    "wrong_renderer": lambda p, i: p.__setitem__("renderer", "OTHER_V1"),
    "bad_candidate_hash": lambda p, i: p.__setitem__("candidate_hash", "not-a-hash"),
    "bad_review_hash": lambda p, i: p.__setitem__("review_unit_hash", 7),
    "bad_effect_hash": lambda p, i: p.__setitem__("approval_effect_hash", None),
    "empty_coverage": lambda p, i: p.__setitem__("coverage_hashes", []),
    "unsorted_coverage": lambda p, i: p.__setitem__(
        "coverage_hashes", ["sha256:" + "b" * 64, "sha256:" + "a" * 64]),
    "duplicate_coverage": lambda p, i: p.__setitem__(
        "coverage_hashes", ["sha256:" + "a" * 64, "sha256:" + "a" * 64]),
    "no_items": lambda p, i: p.__setitem__("items", []),
    "items_not_a_list": lambda p, i: p.__setitem__("items", {}),
}
# These corrupt one item, named by index, so the same case runs at an index the
# frozen bound covers and at one only the raised bound reaches.
ITEM_MUTATIONS = {
    "item_order_wrong": lambda p, i: p["items"][i].__setitem__("order", 999),
    "item_order_swapped": lambda p, i: p["items"].__setitem__(
        slice(i, i + 2), list(reversed(p["items"][i:i + 2]))),
    "item_extra_key": lambda p, i: p["items"][i].__setitem__("extra", 1),
    "item_missing_key": lambda p, i: p["items"][i].pop("role"),
    "item_empty_text": lambda p, i: p["items"][i].__setitem__("text", "   "),
    "item_control_character": lambda p, i: p["items"][i].__setitem__("text", "a\x00b"),
    "item_not_nfc": lambda p, i: p["items"][i].__setitem__("text", "e\u0301"),
    "item_text_too_long": lambda p, i: p["items"][i].__setitem__("text", "x" * 64001),
    "item_bad_observation_id": lambda p, i: p["items"][i].__setitem__("observation_id", "x"),
    "item_empty_role": lambda p, i: p["items"][i].__setitem__("role", ""),
    "item_not_a_dict": lambda p, i: p["items"].__setitem__(i, ["order", i]),
    "duplicate_role": lambda p, i: p["items"][i].__setitem__("role", p["items"][0]["role"]),
    "duplicate_observation_id": lambda p, i: p["items"][i].__setitem__(
        "observation_id", p["items"][0]["observation_id"]),
}
MUTATIONS = {**PAYLOAD_MUTATIONS, **ITEM_MUTATIONS}


class FrozenBehaviourIsInheritedTest(unittest.TestCase):
    def test_a_valid_payload_renders_identically_at_every_size_up_to_the_frozen_bound(self):
        for count in (1, 2, 17, 63, FROZEN_PROTOCOL_MAX_ITEMS):
            with self.subTest(items=count):
                payload = _payload(count)
                self.assertEqual(
                    _outcome(frozen.render_text_payload, payload=copy.deepcopy(payload)),
                    _outcome(successor.render_text_payload, payload=copy.deepcopy(payload),
                             max_items=FROZEN_PROTOCOL_MAX_ITEMS))

    def test_every_refusal_the_frozen_renderer_makes_is_made_identically(self):
        """Same error, same message - not merely "both refused"."""
        for name, mutate in MUTATIONS.items():
            with self.subTest(mutation=name):
                payload = _payload(FROZEN_PROTOCOL_MAX_ITEMS)
                mutate(payload, 7)
                inherited = _outcome(frozen.render_text_payload, payload=copy.deepcopy(payload))
                carried = _outcome(successor.render_text_payload, payload=copy.deepcopy(payload),
                                   max_items=FROZEN_PROTOCOL_MAX_ITEMS)
                self.assertEqual("REFUSED", inherited[0], name)
                self.assertEqual(inherited, carried)

    def test_the_default_bound_is_the_frozen_one(self):
        """Nothing gains capacity by omitting the argument."""
        payload = _payload(FROZEN_PROTOCOL_MAX_ITEMS + 1)
        self.assertEqual(_outcome(frozen.render_text_payload, payload=copy.deepcopy(payload)),
                         _outcome(successor.render_text_payload, payload=copy.deepcopy(payload)))
        self.assertEqual(64, FROZEN_PROTOCOL_MAX_ITEMS)


class CapacityIsTheOnlyThingThatChangedTest(unittest.TestCase):
    def test_the_frozen_bound_still_refuses_sixty_five(self):
        with self.assertRaises(TextResultError) as raised:
            successor.render_text_payload(payload=_payload(65), max_items=64)
        self.assertEqual("TEXT_PAYLOAD_ITEMS_INVALID", str(raised.exception))

    def test_a_raised_bound_renders_sixty_five_ninety_two_and_its_own_limit(self):
        for count in (65, 92, 192):
            with self.subTest(items=count):
                rendered = successor.render_text_payload(payload=_payload(count), max_items=192)
                self.assertEqual(count, len(rendered.split("\n")))
                self.assertEqual("excerpt %d" % (count - 1), rendered.split("\n")[-1])

    def test_one_item_past_the_raised_bound_is_refused(self):
        with self.assertRaises(TextResultError) as raised:
            successor.render_text_payload(payload=_payload(193), max_items=192)
        self.assertEqual("TEXT_PAYLOAD_ITEMS_INVALID", str(raised.exception))

    def test_items_past_the_frozen_bound_are_checked_like_every_other_item(self):
        """Validating the first 64 of 92 is how this could be wrong and look right.

        Every item-level corruption is applied at index 80, which no payload
        within the frozen bound reaches, and must be refused with the same
        reason it gives at index 7.
        """
        for name, mutate in ITEM_MUTATIONS.items():
            with self.subTest(mutation=name):
                inside = _payload(92)
                mutate(inside, 7)
                beyond = _payload(92)
                mutate(beyond, 80)
                near = _outcome(successor.render_text_payload, payload=inside, max_items=192)
                far = _outcome(successor.render_text_payload, payload=beyond, max_items=192)
                self.assertEqual("REFUSED", near[0], name)
                self.assertEqual(near, far, name)

    def test_a_valid_item_past_the_frozen_bound_is_not_silently_dropped(self):
        """The 92nd excerpt has to be in the rendered value, not merely allowed."""
        rendered = successor.render_text_payload(payload=_payload(92), max_items=192)
        lines = rendered.split("\n")
        self.assertEqual(92, len(lines))
        self.assertEqual(["excerpt %d" % n for n in range(92)], lines)

    def test_the_character_bound_is_unchanged_and_counts_the_separators(self):
        """More items must not become more text."""
        payload = _payload(192)
        for item in payload["items"]:
            item["text"] = "x" * 332
        rendered = successor.render_text_payload(payload=payload, max_items=192)
        # 191 separators are inside the 64,000, which is what makes 192 items
        # of 332 characters fit and 192 of 333 not.
        self.assertEqual(192 * 332 + 191, len(rendered))
        self.assertLessEqual(len(rendered), 64000)
        payload = _payload(192)
        for item in payload["items"]:
            item["text"] = "y" * 333
        with self.assertRaises(TextResultError) as raised:
            successor.render_text_payload(payload=payload, max_items=192)
        self.assertEqual("TEXT_VALUE_EMPTY_OR_TOO_LARGE", str(raised.exception))
        self.assertEqual(192 * 333 + 191, 64127)


def _observations(payload, *, closure):
    """Observations the trace names, built by the production factory.

    Hand-rolled dicts would be refused by validate_record for the wrong reason
    and prove nothing about the trace checks, so this uses the same constructor
    reviewed_text_observations uses.
    """
    from vnext.observations import _build_text_observation
    scope = {"kind": "CONSOLIDATED"}
    built = {}
    for item in payload["items"]:
        binding = {"raw_asset_id": "sha256:" + "3" * 64,
                   "source_reference_id": "sha256:" + "4" * 64,
                   "accession": "0000000000-25-000001", "document_name": "form10k.htm",
                   "source_role": "PRIMARY",
                   "text_binding": {
                       "protocol": "TEXT_V1", "spec_closure_hash": closure,
                       "candidate_hash": payload["candidate_hash"],
                       "review_unit_hash": payload["review_unit_hash"],
                       "coverage_hash": payload["coverage_hashes"][0],
                       "extent": "FULL_BLOCK", "document_id": "sha256:" + "2" * 64,
                       "section_id": "ITEM_3", "block_index": item["order"],
                       "raw_start_byte": item["order"] * 100,
                       "raw_end_byte": item["order"] * 100 + 50,
                       "raw_span_sha256": "%064x" % item["order"],
                       "order": item["order"]}}
        observation = _build_text_observation(
            metric_id="D02", semantic_role=item["role"], company_id="pfizer",
            period_start="2025-01-01", period_end="2025-12-31", scope=scope,
            value=item["text"], source_binding=binding,
            approval_effect_hash=payload["approval_effect_hash"])
        built[observation["observation_id"]] = observation
        item["observation_id"] = observation["observation_id"]
    return built


def _trace(payload, *, closure):
    from vnext.canonical import content_hash
    return {"record_type": "EXECUTION_TRACE", "value_kind": "TEXT_V1",
            "spec_closure_hash": closure, "quality": "EXACT",
            "result": "\n".join(item["text"] for item in payload["items"]),
            "input_observation_ids": [item["observation_id"] for item in payload["items"]],
            "steps": [{"event": "TEXT_RESULT_RENDER", "text_payload": payload,
                       "payload_hash": content_hash(value=payload)}]}


def _rebuilt(observation, **changes):
    """A valid observation carrying different content, not a corrupted one.

    Mutating a built observation in place is caught one layer earlier, by
    validate_record recomputing its identity - which proves the record layer
    works, not the trace comparison. The attack that reaches the trace checks
    is a well-formed observation substituted for the expected one, so this
    rebuilds through the production factory and the caller registers it under
    the identity the trace still names.
    """
    from vnext.observations import _build_text_observation
    fields = {"metric_id": observation["metric_id"],
              "semantic_role": observation["semantic_role"],
              "company_id": observation["company_id"],
              "period_start": observation["period_start"],
              "period_end": observation["period_end"],
              "scope": observation["scope"], "value": observation["value"],
              "source_binding": copy.deepcopy(observation["source_binding"]),
              "approval_effect_hash": observation["approval_effect_hash"]}
    binding_changes = changes.pop("text_binding", {})
    fields.update(changes)
    fields["source_binding"]["text_binding"].update(binding_changes)
    return _build_text_observation(**fields)


# What verify_text_trace checks per item after the renderer has passed: the
# observation's own content, and the review bindings tying it to this payload.
# Each swaps in a valid observation under the identity the trace names, except
# the two fields that are not part of observation identity and so can be set
# directly, and the removal case.
TRACE_SUBSTITUTIONS = {
    "value_replaced": lambda o, k: o.__setitem__(
        k, _rebuilt(o[k], value="substituted disclosure text")),
    "role_replaced": lambda o, k: o.__setitem__(k, _rebuilt(o[k], semantic_role="OTHER_ROLE")),
    "order_replaced": lambda o, k: o.__setitem__(
        k, _rebuilt(o[k], text_binding={"order": 999})),
    "spec_identity_replaced": lambda o, k: o.__setitem__(
        k, _rebuilt(o[k], text_binding={"spec_closure_hash": "sha256:" + "8" * 64})),
    "candidate_replaced": lambda o, k: o.__setitem__(
        k, _rebuilt(o[k], text_binding={"candidate_hash": "sha256:" + "7" * 64})),
    "review_unit_replaced": lambda o, k: o.__setitem__(
        k, _rebuilt(o[k], text_binding={"review_unit_hash": "sha256:" + "6" * 64})),
    "coverage_replaced": lambda o, k: o.__setitem__(
        k, _rebuilt(o[k], text_binding={"coverage_hash": "sha256:" + "5" * 64})),
    # Quality and the approval effect are not part of observation identity, so
    # these are the trace's own checks with a still-valid record.
    "quality_lowered": lambda o, k: o[k].__setitem__("quality", "APPROXIMATE"),
    "approval_effect_replaced": lambda o, k: o[k].__setitem__(
        "approval_effect_hash", "sha256:" + "9" * 64),
    "observation_removed": lambda o, k: o.pop(k),
}


class TraceChecksReachEveryItemTest(unittest.TestCase):
    """The per-item trace checks are copied code, so they are checked past 64.

    The renderer's own checks are covered above. These are the ones
    verify_text_trace makes afterwards, comparing each item against the
    observation it names. A copy that stopped comparing after the 64th item
    would still render 92 items and still pass everything above.
    """
    def setUp(self):
        self.closure = next(iter(revised_spec_ceilings()))

    def _refusal(self, substitution, index):
        payload = _payload(92)
        observations = _observations(payload, closure=self.closure)
        trace = _trace(payload, closure=self.closure)
        substitution(observations, payload["items"][index]["observation_id"])
        try:
            successor.verify_text_trace(trace=trace, observations=observations)
            return ("ACCEPTED", None)
        except Exception as error:      # noqa: BLE001 - the refusal is the result
            return ("REFUSED", str(error))

    def test_an_unaltered_ninety_two_item_trace_is_accepted(self):
        payload = _payload(92)
        observations = _observations(payload, closure=self.closure)
        successor.verify_text_trace(trace=_trace(payload, closure=self.closure),
                                    observations=observations)

    def test_every_substitution_is_refused_identically_inside_and_past_the_old_bound(self):
        for name, substitution in TRACE_SUBSTITUTIONS.items():
            with self.subTest(substitution=name):
                inside = self._refusal(substitution, 7)
                beyond = self._refusal(substitution, 80)
                self.assertEqual("REFUSED", inside[0], name)
                self.assertEqual(inside, beyond, name)

    def test_the_trace_input_set_must_still_name_exactly_the_payload_items(self):
        """Dropping everything past the frozen bound is the failure being ruled out."""
        payload = _payload(92)
        observations = _observations(payload, closure=self.closure)
        trace = _trace(payload, closure=self.closure)
        trace["input_observation_ids"] = trace["input_observation_ids"][:64]
        with self.assertRaises(TextResultError) as raised:
            successor.verify_text_trace(trace=trace, observations=observations)
        self.assertEqual("TEXT_TRACE_INPUT_EXACT_SET_CHANGED", str(raised.exception))


class CapacityFollowsSpecIdentityTest(unittest.TestCase):
    def test_only_a_spec_identity_this_repository_can_rebuild_raises_the_bound(self):
        ceilings = revised_spec_ceilings()
        self.assertEqual([192], sorted(set(ceilings.values())))
        revised = next(iter(ceilings))
        self.assertEqual(192, declared_spec_ceiling(spec_closure_hash=revised))
        for unknown in ("sha256:" + "f" * 64, "", None, 192, "192"):
            with self.subTest(declared=unknown):
                self.assertEqual(FROZEN_PROTOCOL_MAX_ITEMS,
                                 declared_spec_ceiling(spec_closure_hash=unknown))

    def test_a_record_cannot_widen_its_own_bound_by_asserting_one(self):
        """The only capacity signal a record carries is a Spec identity."""
        revised = next(iter(revised_spec_ceilings()))
        forged = {"record_type": "METRIC_RESULT", "value_kind": "TEXT_V1",
                  "spec_closure_hash": "sha256:" + "e" * 64, "max_items": 192,
                  "text_payload": _payload(92), "unit": "text", "quality": "EXACT"}
        forged["value"] = "\n".join(i["text"] for i in forged["text_payload"]["items"])
        with self.assertRaises(TextResultError) as raised:
            successor.validate_text_record(record=forged)
        self.assertEqual("TEXT_PAYLOAD_ITEMS_INVALID", str(raised.exception))
        # The same record under the identity the repository can rebuild passes.
        successor.validate_text_record(record={**forged, "spec_closure_hash": revised})

    def test_the_predecessor_spec_identity_still_gets_the_frozen_bound(self):
        from pathlib import Path
        from tests.vnext.common import REPO_ROOT as ROOT
        from vnext.specs import compile_spec_file
        v1 = compile_spec_file(path=Path(ROOT) / "catalog/r6/D02_legal_disclosures_v1.md",
                               dependency_specs={})
        self.assertEqual(FROZEN_PROTOCOL_MAX_ITEMS,
                         declared_spec_ceiling(spec_closure_hash=v1["spec_closure_hash"]))

    def test_the_ceiling_is_recomputed_when_the_spec_bytes_change(self):
        """A cached authority is a different and worse thing than a cached parse."""
        import tempfile
        from pathlib import Path
        from tests.vnext.common import REPO_ROOT as ROOT
        first = revised_spec_ceilings()
        with tempfile.TemporaryDirectory(prefix="protocol-root-") as temporary:
            root = Path(temporary)
            (root / "catalog/r6").mkdir(parents=True)
            for name in ("D02_legal_disclosures_v1.md", "D02_legal_disclosures_v2.md"):
                (root / "catalog/r6" / name).write_bytes(
                    (Path(ROOT) / "catalog/r6" / name).read_bytes())
            self.assertEqual(first, revised_spec_ceilings(repo_root=root))
            edited = (root / "catalog/r6" / "D02_legal_disclosures_v2.md")
            edited.write_text(edited.read_text(encoding="utf-8").replace(
                '"max_items": 192', '"max_items": 100'), encoding="utf-8")
            again = revised_spec_ceilings(repo_root=root)
        self.assertEqual([100], sorted(set(again.values())))
        self.assertNotEqual(sorted(first), sorted(again))
        self.assertEqual(first, revised_spec_ceilings())


if __name__ == "__main__":
    unittest.main()
