"""Typed text carrier, raw replay attacks and unchanged numeric identities.

Fixture review decisions are explicitly TEST_ONLY, with no production approval
or provider/source credit. Tests use real validators and no acceptance mocks.
"""
import copy
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_text_coverage import BODY, annual, binding
from vnext.canonical import canonical_json_bytes, content_hash, execution_semantics_hash, sha256_bytes
from vnext.constraints import verify_trace_observation_values
from vnext.records import _expected_identifier, metric_result_contract_hash, validate_record
from vnext.review import build_review_unit, create_review_decision
from vnext.specs import SpecError, compile_spec, compile_spec_file
from vnext.text_results import (build_text_evidence, prepare_text_sources, replay_text_result,
    text_claim_from_block, verify_text_result, create_deterministic_text_candidate,
    verify_deterministic_text_candidate)


def spec_front():
    return {"metric_id": "D01", "name": "Risk source excerpts", "kind": "direct_text",
        "canonical_unit": "text", "source_mode": "ai_text",
        "applicability": {"all": [], "none": []}, "required_claims": {"entity_scope": "consolidated"},
        "legacy_projection": {}, "disclosure_group": "risk_text_v1", "text_policy": {
            "version": "TEXT_V1", "content_kind": "SOURCE_EXCERPTS", "required_sections": ["ITEM_1A"],
            "allowed_source_roles": ["target_primary"], "renderer": "ORDERED_NEWLINE_V1",
            "max_items": 64, "max_text_chars": 64000, "review_required": True}}


def compiled(front=None):
    return compile_spec(text="---\n" + json.dumps(front or spec_front()) + "\n---\n", dependency_specs={})


def rehash(record):
    record = copy.deepcopy(record)
    field, value = _expected_identifier(record_type=record["record_type"], record=record)
    record[field] = value
    return record


def source_arguments(source=None, *, front=None):
    if source is None:
        body = BODY.replace("<p>A supply constraint could affect production.</p>",
            '<p><b>Supply constraints may affect production</b>. The explanatory text remains separate.</p>'
            '<p><strong>Cybersecurity threats may affect operations</strong>. These are risks, not events.</p>')
        source = binding(annual(body))
    ref, blob = source["source_reference"], source["raw_blob"]
    scope = {"entity_scope": "consolidated"}
    from vnext.deterministic_router import parse_accession_xbrl_source
    parsed = parse_accession_xbrl_source(raw_bytes=source["raw_bytes"])
    context = next(parsed.contexts[f["context_ref"]] for f in parsed.facts
                   if f["qualified_name"].split(":")[-1].casefold() == "documentperiodenddate")
    target = {"company_id": ref["company_id"], "entity": source["expected_cik"],
        "accession": ref["accession"], "period_start": context["period_start"], "period_end": context["period_end"],
        "scope": scope, "scope_key": content_hash(value=scope)}
    return {"compiled_spec": compiled(front), "target": target, "source_references": [ref],
            "raw_blobs": {blob["raw_asset_id"]: blob}, "raw_bytes_by_id": {blob["raw_asset_id"]: source["raw_bytes"]}}


def make_candidate(arguments, *, extent="LEADING_EMPHASIS", limit=2):
    documents, _ = prepare_text_sources(**arguments)
    document = next(iter(documents.values()))
    section = document["sections"]["ITEM_1A"]["candidates"][0]
    blocks = document["blocks"][section["start_block"]:section["end_block_exclusive"]]
    if extent == "LEADING_EMPHASIS":
        blocks = [block for block in blocks if block["leading_emphasis"]]
    selected = {"excerpt_" + str(i): text_claim_from_block(document=document, section_id="ITEM_1A",
        block_index=block["block_index"], order=i, extent=extent) for i, block in enumerate(blocks[:limit])}
    body = {"disclosure_group": "risk_text_v1", "source_reference_ids": [source["source_reference_id"] for source in arguments["source_references"]],
            "derived_asset_ids": [], "selected": selected, "competing_candidates": [], "unresolved_competing_claims": []}
    return validate_record(record={"record_type": "OBSERVATION_CANDIDATE", "candidate_hash": content_hash(value=body),
        "attempt_id": "attempt:recorded:TEST_ONLY_TEXT", "assistant_output_sha256": sha256_bytes(content=canonical_json_bytes(value=selected)),
        "status": "CANDIDATE", **body})


def reviewed(arguments=None, *, extent="LEADING_EMPHASIS", candidate=None):
    arguments = arguments or source_arguments()
    candidate = candidate or make_candidate(arguments, extent=extent)
    evidence = build_text_evidence(candidate=candidate, **arguments)
    unit = build_review_unit(candidate=candidate, evidence_check=evidence,
        source_bindings=arguments["source_references"], compiled_spec=arguments["compiled_spec"],
        review_context_hash="a" * 64, rendered_review_hash="b" * 64, renderer_semantic_version="TEXT_V1")
    decision = create_review_decision(review_unit=unit, decision="APPROVE",
        approved_claims=arguments["target"]["scope"], required_claims=arguments["target"]["scope"],
        reviewer_id="human:TEST_ONLY_REVIEW", decided_at_utc="2026-09-12T00:00:00Z",
        reason="TEST_ONLY exact source excerpt review; no production approval.", supersedes_decision_id=None)
    return {**arguments, "company_traits": [], "candidate": candidate, "evidence_check": evidence,
            "review_unit": unit, "review_decisions": [decision]}


class TextResultTest(unittest.TestCase):
    def setUp(self):
        network = patch.object(socket.socket, "connect", side_effect=AssertionError("TEST_FORBIDS_NETWORK"))
        network.start(); self.addCleanup(network.stop)

    def test_titles_and_multiple_text_values_roundtrip_through_existing_record_types(self):
        args = reviewed()
        result, trace, observations = replay_text_result(**args)
        self.assertEqual("METRIC_RESULT", result["record_type"])
        self.assertEqual("TEXT_V1", result["value_kind"])
        self.assertEqual("EXACT", result["quality"])
        self.assertEqual("PUBLISHED", result["publication"])
        self.assertEqual("Supply constraints may affect production\nCybersecurity threats may affect operations", result["value"])
        self.assertNotIn("explanatory", result["value"])
        self.assertEqual(2, len(observations))
        self.assertEqual(["VERIFIED_OBSERVATION"] * 2, [o["record_type"] for o in observations])
        stored = json.loads(canonical_json_bytes(value={"result": result, "trace": trace, "observations": observations}))
        verify_trace_observation_values(trace=stored["trace"], observations={o["observation_id"]: o for o in stored["observations"]})
        self.assertEqual((result, trace, observations), verify_text_result(**stored, **args))

    def test_persisted_evidence_preserves_source_order_with_more_than_ten_headings(self):
        headings = ''.join('<p><b>Risk number %s</b>. Disclosure.</p>' % i for i in range(14))
        body = BODY.replace('<p>A supply constraint could affect production.</p>', headings)
        front = spec_front()
        front['quality_rule'] = {'deterministic_text_method': 'RISK_FACTOR_HEADINGS_V1'}
        args = source_arguments(binding(annual(body)), front=front)
        candidate = create_deterministic_text_candidate(**args)
        evidence = build_text_evidence(candidate=candidate, **args)
        persisted = json.loads(canonical_json_bytes(value=candidate))
        self.assertEqual(14, len(candidate['selected']))
        self.assertEqual(evidence, build_text_evidence(candidate=persisted, **args))

    def test_existing_projector_preserves_text_and_each_original_excerpt(self):
        from vnext.projector import _projection_value, _evidence_row, ProjectionError
        args = reviewed()
        result, trace, observations = replay_text_result(**args)
        projection = {'concept_or_section': 'Item 1A', 'evidence_context_style': 'text_source_span',
                      'evidence_unit_policy': 'observation', 'evidence_extraction_method': 'verbatim_source_excerpt',
                      'parser_version': 'TEXT_V1'}
        self.assertEqual(result['value'], _projection_value(result=result, projection=projection))
        rows = [_evidence_row(observation=observation, result=result,
                company={'display_name': 'Test Registrant', 'primary_cik': args['target']['entity']},
                projection=projection, source_index={r['source_reference_id']: r for r in args['source_references']},
                raw_index=args['raw_blobs'], fiscal_year='2025') for observation in observations]
        self.assertEqual([o['value'] for o in observations], [r['evidence_quote'] for r in rows])
        self.assertTrue(all('ITEM_1A:bytes:' in row['context_or_dimension'] for row in rows))
        with self.assertRaisesRegex(ProjectionError, 'numeric conversion'):
            _projection_value(result=result, projection={**projection, 'value_multiplier': '100'})
        changed = copy.deepcopy(result); changed['value'] = 'Unsupported summary'
        with self.assertRaisesRegex(ProjectionError, 'differs from Result'):
            _projection_value(result=changed, projection=projection)

    def test_native_text_requires_installed_metric_spec_and_discovered_run_identity(self):
        from vnext.text_run_validation import prepare_text_run_contexts, D01_SPEC_PATH
        from vnext.canonical import sha256_file
        official = compile_spec_file(path=REPO_ROOT / D01_SPEC_PATH, dependency_specs={})
        front = spec_front(); front['metric_id'] = 'B06'
        candidate = create_deterministic_text_candidate(**source_arguments(front={
            **front, 'quality_rule': {'deterministic_text_method': 'RISK_FACTOR_HEADINGS_V1'}}))
        manifest = {'company_id': 'marriott_international', 'run_id': 'run:arbitrary:text',
                    'spec_file_hashes': {D01_SPEC_PATH: sha256_file(path=REPO_ROOT / D01_SPEC_PATH)}}
        requirement = {'policy': {'native_deterministic_text_methods': ['RISK_FACTOR_HEADINGS_V1']},
                       'requirement_closure_hash': 'sha256:' + 'a' * 64}
        base = dict(repo_root=REPO_ROOT, records=[candidate], raw_bytes_by_id={}, requirement=requirement)
        with self.assertRaisesRegex(ValueError, 'INSTALLED_D01_SPEC_REQUIRED'):
            prepare_text_run_contexts(manifest=manifest, compiled_specs={'B06': compiled(front)}, **base)
        alias = copy.deepcopy(manifest)
        alias['spec_file_hashes'] = {'catalog/r6/copied_D01.md': next(iter(manifest['spec_file_hashes'].values()))}
        with self.assertRaisesRegex(ValueError, 'INSTALLED_D01_SPEC_REQUIRED'):
            prepare_text_run_contexts(manifest=alias, compiled_specs={'D01': official}, **base)
        with self.assertRaisesRegex(ValueError, 'NORMAL_INPUT_IDENTITY_CHANGED'):
            prepare_text_run_contexts(manifest=manifest, compiled_specs={'D01': official}, **base)

    def test_full_block_and_leading_emphasis_are_controlled_source_extents(self):
        full = reviewed(extent="FULL_BLOCK")
        result, _, _ = replay_text_result(**full)
        self.assertIn("explanatory text", result["value"])
        args = source_arguments(); candidate = make_candidate(args)
        for mutate in [lambda c: c.update(extent="CALLER_SUBSTRING"),
                       lambda c: c.update(raw_start_byte=c["raw_start_byte"] + 1),
                       lambda c: c.update(text="A misleading new claim")]:
            changed = copy.deepcopy(candidate); mutate(changed["selected"]["excerpt_0"]); changed = rehash(changed)
            with self.assertRaisesRegex(ValueError, "EXTENT|SPAN|EXCERPT"):
                build_text_evidence(candidate=changed, **args)

    def test_missing_coverage_and_cross_source_or_period_do_not_become_results(self):
        args = source_arguments(); candidate = make_candidate(args)
        wrong = copy.deepcopy(candidate); wrong["selected"]["excerpt_0"]["source_reference_id"] = "sha256:" + "f" * 64
        with self.assertRaisesRegex(ValueError, "CROSS_SOURCE"):
            build_text_evidence(candidate=rehash(wrong), **args)
        front = spec_front(); front["text_policy"]["required_sections"].append("ITEM_99")
        with self.assertRaisesRegex(ValueError, "COVERAGE_MISSING"):
            prepare_text_sources(**{**args, "compiled_spec": compiled(front)})
        wrong = copy.deepcopy(args); wrong["target"]["period_start"] = "2025-10-01"
        with self.assertRaisesRegex(ValueError, "ANNUAL_PERIOD_CHANGED"):
            build_text_evidence(candidate=candidate, **wrong)
        wrong = copy.deepcopy(args); raw_id = next(iter(wrong["raw_bytes_by_id"]))
        wrong["raw_bytes_by_id"][raw_id] = wrong["raw_bytes_by_id"][raw_id].replace(b"Supply", b"Demand")
        with self.assertRaisesRegex(ValueError, "BYTES_CHANGED"):
            build_text_evidence(candidate=candidate, **wrong)

    def test_missing_and_revoked_reviews_and_forged_pass_are_rejected(self):
        args = reviewed()
        with self.assertRaisesRegex(ValueError, "no decision"):
            replay_text_result(**{**args, "review_decisions": []})
        revoked = create_review_decision(review_unit=args["review_unit"], decision="REJECT", approved_claims={},
            required_claims=args["target"]["scope"], reviewer_id="human:TEST_ONLY_REVIEW",
            decided_at_utc="2026-09-12T00:01:00Z", reason="TEST_ONLY revocation",
            supersedes_decision_id=args["review_decisions"][0]["review_decision_id"])
        with self.assertRaisesRegex(ValueError, "APPROVAL_REQUIRED"):
            replay_text_result(**{**args, "review_decisions": args["review_decisions"] + [revoked]})
        fake = copy.deepcopy(args["evidence_check"]); fake["normalized_values"]["excerpt_0"] = "Unsupported conclusion"
        with self.assertRaisesRegex(ValueError, "EVIDENCE_REPLAY_CHANGED"):
            replay_text_result(**{**args, "evidence_check": rehash(fake)})

    def test_fully_rehashed_text_graph_still_fails_independent_original_replay(self):
        args = reviewed(); result, trace, observations = replay_text_result(**args)
        observations = copy.deepcopy(observations); observations[0]["value"] = "Fabricated risk occurrence"
        observations[0] = rehash(observations[0]); validate_record(record=observations[0])
        changed = copy.deepcopy(result["text_payload"])
        changed["items"][0].update(text=observations[0]["value"], observation_id=observations[0]["observation_id"])
        from vnext.text_results import build_text_result_and_trace
        result, trace = build_text_result_and_trace(compiled_spec=args["compiled_spec"], target=args["target"], payload=changed)
        verify_trace_observation_values(trace=trace, observations={o["observation_id"]: o for o in observations})
        with self.assertRaisesRegex(ValueError, "TEXT_NATIVE_REPLAY_CHANGED"):
            verify_text_result(result=result, trace=trace, observations=observations, **args)

    def test_payload_and_input_set_cannot_escape_contract_or_trace(self):
        args = reviewed(); result, trace, observations = replay_text_result(**args)
        changed = copy.deepcopy(result); changed["text_payload"]["coverage_hashes"] = ["sha256:" + "a" * 64]
        self.assertNotEqual(metric_result_contract_hash(result=result), metric_result_contract_hash(result=changed))
        with self.assertRaisesRegex(ValueError, "identity differs"):
            validate_record(record=changed)
        changed = copy.deepcopy(trace); changed["input_observation_ids"].pop(); changed = rehash(changed)
        with self.assertRaisesRegex(ValueError, "EXACT_SET_CHANGED"):
            verify_trace_observation_values(trace=changed, observations={o["observation_id"]: o for o in observations})

    def test_text_is_explicit_and_cannot_enter_old_numeric_or_unreviewed_structured_path(self):
        for changes in [{"kind": "direct_numeric"}, {"source_mode": "structured"}, {"formula": {"op": "add", "args": ["1", "2"]}}]:
            front = spec_front(); front.update(changes)
            with self.assertRaises(SpecError): compiled(front)
        args = reviewed(); result, trace, _ = replay_text_result(**args)
        old = {k: value for k, value in result.items() if k not in {"value_kind", "text_payload"}}
        old = rehash(old)
        with self.assertRaisesRegex(ValueError, "value is invalid"):
            validate_record(record=old)
        incomplete = {k: value for k, value in result.items() if k != "value_kind"}
        with self.assertRaisesRegex(ValueError, "MARKER_INVALID"):
            validate_record(record=incomplete)
        from vnext.calculator import calculate_metric
        with self.assertRaisesRegex(ValueError, "bypass review"):
            calculate_metric(compiled_spec=args["compiled_spec"], target=args["target"], company_traits=[],
                             structured_facts=[{"value": "1"}], verified_observations=[])

    def test_missing_content_uses_typed_withheld_without_a_fake_text_value(self):
        from vnext.calculator import withheld_metric_result
        args = source_arguments()
        target = {k: value for k, value in args["target"].items() if k not in {"accession", "entity"}}
        result, trace = withheld_metric_result(compiled_spec=args["compiled_spec"], target=target,
                                              reason_code="TEXT_REQUIRED_COVERAGE_MISSING")
        self.assertEqual(("TEXT_V1", "WITHHELD", "NONE", None, None),
                         (result["value_kind"], result["publication"], result["quality"], result["value"], result["text_payload"]))
        verify_trace_observation_values(trace=trace, observations={})

    def test_retained_numeric_records_specs_and_runtime_hash_remain_unchanged(self):
        index = json.loads((REPO_ROOT / "docs/evidence/b06_new_source/replay-index.json").read_text())
        paths = {row["path"]: row for row in index["files"]}
        name = next(name for name in paths if name.startswith("cases/salesforce/accepted-run/") and name.endswith("records.jsonl"))
        records = [json.loads(line) for line in (REPO_ROOT / paths[name]["repository_path"]).read_text().splitlines()]
        for record in records: self.assertEqual(record, validate_record(record=record))
        result = next(r for r in records if r["record_type"] == "METRIC_RESULT")
        trace = next(r for r in records if r["record_type"] == "EXECUTION_TRACE")
        self.assertEqual(trace["result_contract_hash"], metric_result_contract_hash(result=result))
        self.assertEqual(execution_semantics_hash(), trace["execution_semantics_hash"])
        spec = compile_spec_file(path=REPO_ROOT / "catalog/r5/B06_new_source.md", dependency_specs={})
        self.assertEqual(spec["spec_closure_hash"], result["spec_closure_hash"])
        self.assertNotIn("text_policy", spec["compiled"])
        self.assertNotIn("value_kind", result)

    def test_saved_original_titles_enter_same_native_value_carrier(self):
        from tests.vnext.test_annual_input import independent_inputs
        from vnext.normal_annual_input import prepare_saved_annual_input
        from vnext.sources import raw_blob_record, source_reference_record
        with independent_inputs():
            prepared = prepare_saved_annual_input(repo_root=REPO_ROOT, company_id="marriott_international")
            source = prepared["table_input"]
            blob = raw_blob_record(repo_root=REPO_ROOT, repo_relative_path=source["source_repo_relative_path"], media_type="text/html")
            ref = source_reference_record(raw_blob=blob, company_id=prepared["company_id"], source_url=source["source_url"],
                accession=source["accession"], document_name=source["document_name"], source_role="target_primary",
                request_attempt_id=source["request_attempt_id"])
            a = {"raw_bytes": (REPO_ROOT / source["source_repo_relative_path"]).read_bytes(), "raw_blob": blob,
                 "source_reference": ref, "expected_cik": prepared["entity"]}
            front = spec_front(); front["quality_rule"] = {"deterministic_text_method": "RISK_FACTOR_HEADINGS_V1"}
            source_args = source_arguments(a, front=front)
            candidate = create_deterministic_text_candidate(**source_args)
            args = reviewed(source_args, candidate=candidate)
            result, trace, observations = replay_text_result(**args)
            self.assertGreater(len(result["text_payload"]["items"]), 10)
            self.assertEqual(len(candidate["selected"]), len(result["text_payload"]["items"]))
            self.assertTrue(all(o["source_binding"]["text_binding"]["extent"] == "LEADING_EMPHASIS" for o in observations))
            self.assertTrue(all(o["value"] in result["value"] for o in observations))
            verify_text_result(result=result, trace=trace, observations=observations, **args)

    def test_deterministic_candidate_has_no_ai_identity_and_replays_all_headings(self):
        front = spec_front(); front["quality_rule"] = {"deterministic_text_method": "RISK_FACTOR_HEADINGS_V1"}
        args = source_arguments(front=front)
        candidate = create_deterministic_text_candidate(**args)
        self.assertEqual("DETERMINISTIC_TEXT_CANDIDATE", candidate["record_type"])
        self.assertNotIn("attempt_id", candidate)
        self.assertNotIn("assistant_output_sha256", candidate)
        self.assertEqual(2, len(candidate["selected"]))
        self.assertEqual(candidate, verify_deterministic_text_candidate(candidate=candidate, **args))
        replay = reviewed(args, candidate=candidate)
        result, trace, observations = replay_text_result(**replay)
        verify_text_result(result=result, trace=trace, observations=observations, **replay)
        fake_ai = make_candidate(args)
        with self.assertRaisesRegex(ValueError, "TYPE_REQUIRED"):
            build_text_evidence(candidate=fake_ai, **args)

    def test_rehashed_deterministic_selection_method_and_source_omissions_reject(self):
        front = spec_front(); front["quality_rule"] = {"deterministic_text_method": "RISK_FACTOR_HEADINGS_V1"}
        args = source_arguments(front=front)
        # A second complete source has different bytes and a distinct document
        # identity in the same filing. The trusted input set retains both.
        from vnext.sources import source_reference_record
        raw = next(iter(args["raw_bytes_by_id"].values())).replace(b"Supply constraints", b"Different supply constraints")
        blob = {"record_type": "RAW_BLOB", "raw_asset_id": "sha256:" + sha256_bytes(content=raw),
                "byte_length": len(raw), "media_type": "text/html", "storage_uri": "fixture/source2.htm"}
        old = args["source_references"][0]
        source = source_reference_record(raw_blob=blob, company_id=old["company_id"], accession=old["accession"],
            source_url=old["source_url"].replace("source.htm", "source2.htm"), document_name="source2.htm",
            source_role="target_primary", request_attempt_id="test-only-second-source")
        args["source_references"].append(source); args["raw_blobs"][blob["raw_asset_id"]] = blob
        args["raw_bytes_by_id"][blob["raw_asset_id"]] = raw
        candidate = create_deterministic_text_candidate(**args)
        for change in ["replace_selected", "remove_selected", "remove_source", "change_method"]:
            altered = copy.deepcopy(candidate)
            if change == "replace_selected":
                altered["selected"]["excerpt_0"] = {**altered["selected"]["excerpt_1"], "order": 0}
            elif change == "remove_selected":
                altered["selected"].pop("excerpt_3")
            elif change == "remove_source":
                removed = altered["source_reference_ids"].pop(); altered["document_bindings"].pop(removed)
                altered["source_set_hash"] = content_hash(value=args["source_references"][:1])
            else:
                altered["method"] = "UNREVIEWED_SELECTOR"
            altered = rehash(altered)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "CANDIDATE_(REPLAY_CHANGED|SCOPE|PROTOCOL)"):
                build_text_evidence(candidate=altered, **args)


if __name__ == "__main__":
    unittest.main()
