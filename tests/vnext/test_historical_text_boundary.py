"""A numbered Form 10-K item stops at the form's unnumbered Part I item.

Every expectation here is read out of the filing's own blocks, never produced by
calling the boundary rule under test: the closing block is found by matching the
caption text directly, and the control cases are the frozen derivation's own
output. The corpus supplies both directions - Pfizer files no Item 4 and carries
the unnumbered item inside Item 3, and Macy's and Paramount carry blocks naming
a chief executive officer inside Item 8 that must not close anything.
"""
import collections
import copy
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import historical_text_results as fixed
from vnext import text_results_v2 as frozen
from vnext.historical_text_input import prepare_historical_business_text_input
from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_results import TEXT_SPEC_PATHS
from vnext.historical_spec_revision import compile_historical_spec_file
from vnext.specs import compile_spec_file
from vnext.text_coverage import build_text_document
from vnext.text_results_v2 import TextResultV2Error, text_policy

PFIZER = "pfizer"
MACYS = "macys"
LUMEN = "lumen_technologies"
MARRIOTT = "marriott_international"
PARAMOUNT = "paramount_skydance_paramount_global"
SALESFORCE = "salesforce"
ENPHASE = "enphase_energy"
SOUTHWEST = "southwest_airlines"
FORD = "ford_motor_company"
CAPTION = "information about our executive officers"


# Preparing a filing's input and deriving its document are the same work for
# every case that reads the same filing, and this module reads Pfizer in ten of
# them. The saved-source CI job was already fifteen seconds over its
# thirty-five minute cap before these cases were added, so the fixture is built
# once per filing and handed out as a copy - the cases assert on what the
# selector does with the input, never on the preparation, so sharing the input
# cannot weaken one.
_PREPARED = {}
_DOCUMENTS = {}


def _text_arguments(company_id, report_end):
    key = (company_id, report_end)
    if key not in _PREPARED:
        _PREPARED[key] = _prepare_text_arguments(company_id, report_end)
    return copy.deepcopy(_PREPARED[key])


def _prepare_text_arguments(company_id, report_end):
    with original_sources_only():
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=report_end)
        prepared = prepare_historical_business_text_input(
            repo_root=ROOT, company_id=company_id, metric_id="D02",
            period_selection=selection)
    spec = compile_historical_spec_file(repo_root=ROOT, repo_relative_path=TEXT_SPEC_PATHS["D02"],
                                        dependency_specs={})
    return spec, prepared


def _frozen_document(prepared, company_id):
    key = (company_id, prepared["target_period"]["period_end"])
    if key not in _DOCUMENTS:
        _DOCUMENTS[key] = _build_frozen_document(prepared, company_id)
    return copy.deepcopy(_DOCUMENTS[key])


def _build_frozen_document(prepared, company_id):
    arguments = prepared["text_arguments"]
    reference = arguments["source_references"][0]
    return build_text_document(
        raw_bytes=arguments["raw_bytes_by_id"][reference["raw_asset_id"]],
        raw_blob=arguments["raw_blobs"][reference["raw_asset_id"]],
        source_reference=reference, expected_company_id=company_id,
        expected_cik=prepared["prepared_input"]["entity"],
        expected_period_end=prepared["target_period"]["period_end"])


class FormUnnumberedItemBoundaryTest(unittest.TestCase):
    def test_item_three_stops_at_the_caption_block_the_filing_itself_carries(self):
        """The expectation is the caption's own block index, read from the document.

        Pfizer files no Item 4, so `_SUCCESSOR` closes Item 3 at Item 5 and the
        officer section between them is reported as legal proceedings. The
        corrected range must end at the caption, and the block before it - the
        one sentence Item 3 actually holds - must survive.
        """
        spec, prepared = _text_arguments(PFIZER, "2025-12-31")
        document = _frozen_document(prepared, PFIZER)
        blocks = document["blocks"]
        captions = [i for i, block in enumerate(blocks)
                    if block["text"].strip().casefold() == CAPTION and not block["linked"]]
        self.assertEqual(1, len(captions), captions)
        caption = captions[0]
        original = document["sections"]["ITEM_3"]["candidates"]
        self.assertEqual(1, len(original))
        self.assertLess(original[0]["start_block"], caption)
        self.assertLess(caption, original[0]["end_block_exclusive"])

        corrected = fixed.narrow_document_sections(document=document)
        candidates = corrected["sections"]["ITEM_3"]["candidates"]
        self.assertEqual("LOCATED", corrected["sections"]["ITEM_3"]["status"])
        self.assertEqual(1, len(candidates))
        self.assertEqual(original[0]["start_block"], candidates[0]["start_block"])
        self.assertEqual(caption, candidates[0]["end_block_exclusive"])
        self.assertEqual(document["blocks"], corrected["blocks"])
        self.assertEqual(document["text_document_id"], corrected["frozen_text_document_id"])
        self.assertNotEqual(document["text_document_id"], corrected["text_document_id"])

    def test_nothing_outside_the_two_deliberate_removals_is_lost(self):
        """The no-under-capture guarantee, stated on the excerpt sets.

        It was a strict-subset assertion on the candidate. Two things changed
        it: the corrected set now also gains Note 16A, so it is no longer a
        subset, and Pfizer's candidate cannot be built at all while its 92
        excerpts exceed the Spec's 64-item bound. The guarantee itself is
        unchanged and is asserted on the proposals, which the bound does not
        gate.

        There are now two deliberate removals rather than one, so the
        guarantee names both: the officer section and the independent
        auditor's report. Both are computed from the document - the officer
        section from its own caption, the audit report from the same span rule
        the successor applies - rather than listed by index, because a
        guarantee that had to be handed the answer would not be one.
        """
        spec, prepared = _text_arguments(PFIZER, "2025-12-31")
        document = _frozen_document(prepared, PFIZER)
        with original_sources_only():
            before = frozen.prepare_business_text_sources(
                metric_id="D02", **prepared["text_arguments"])
            after = fixed.prepare_business_text_sources(
                metric_id="D02", **prepared["text_arguments"])
        reference_id = next(iter(before["documents"]))
        had = {e["block_index"] for e in before["proposals"][reference_id]["D02"]["candidates"]}
        kept = {e["block_index"] for e in after["proposals"][reference_id]["D02"]["candidates"]}

        captions = [i for i, block in enumerate(document["blocks"])
                    if block["text"].strip().casefold() == CAPTION and not block["linked"]]
        officer_start = captions[0]
        officer_end = document["sections"]["ITEM_3"]["candidates"][0]["end_block_exclusive"]
        officer = set(range(officer_start, officer_end))
        audited = {index for span in fixed.audit_report_spans(
                       document=document,
                       ranges=document["sections"]["ITEM_8"]["candidates"])["spans"]
                   for index in range(span["start_block"], span["end_block_exclusive"])}
        self.assertEqual(set(), (had - kept) - officer - audited)
        self.assertEqual(set(), kept & officer)
        self.assertEqual(set(), kept & audited)
        # Both removals actually removed something, so neither half of the
        # subtraction above is idle.
        self.assertTrue(had & officer)
        self.assertTrue(had & audited)

    def test_a_signature_line_naming_an_officer_does_not_close_an_item(self):
        """Macy's block 774 sits inside Item 8 and names a chief executive officer.

        A rule keyed on the words rather than on the whole caption would cut Item
        8 there. The assertion is that this filing's ranges come back unchanged
        and its whole record set is the frozen module's, byte for byte.
        """
        spec, prepared = _text_arguments(MACYS, "2026-01-31")
        document = _frozen_document(prepared, MACYS)
        officer_blocks = [i for i, block in enumerate(document["blocks"])
                          if "executive officer" in block["text"].casefold()
                          and not block["linked"]
                          and any(c["start_block"] <= i < c["end_block_exclusive"]
                                  for c in document["sections"]["ITEM_8"]["candidates"])]
        self.assertTrue(officer_blocks)
        self.assertIs(document, fixed.narrow_document_sections(document=document))

        arguments = {"compiled_spec": spec, **prepared["text_arguments"]}
        with original_sources_only():
            self.assertEqual(frozen.create_deterministic_text_candidate(**arguments),
                             fixed.create_deterministic_text_candidate(**arguments))

    def test_only_the_caption_item_three_incorporates_is_taken_from_the_note(self):
        """Include and exclude are both literal, read from the filings here.

        `legal_risk_candidates` gives a located note its own range only when no
        other range contains it, as a deduplication guard, so a note inside
        Item 8 was filtered by a six-word list instead. Restoring its note
        identity is right; taking the whole note is not. Marriott's Item 3
        incorporates one caption in Note 7, and the note also holds a guarantee
        table, letters of credit and insurance recoveries; Lumen's names two
        subheadings in a note whose remaining sections are contractual
        commitments, right-of-way and purchase commitments.

        The block numbers below were read out of those filings, not returned by
        the code under test, and the third assertion is that nothing the frozen
        derivation selected is lost.
        """
        cases = [
            (MARRIOTT, "2025-12-31",
             [1312, 1313, 1316, 1317, 1318],
             [1292, 1293, 1304, 1305, 1306, 1307, 1308, 1319, 1320]),
            (LUMEN, "2025-12-31",
             [3389, 3392, 3394, 3399, 3403, 3409, 3415, 3424, 3426, 3427, 3428],
             [3433, 3434, 3435, 3444, 3445, 3453, 3454]),
            (PARAMOUNT, "2025-12-31",
             [3226, 3231, 3236, 3238, 3245, 3248, 3256, 3257, 3259],
             [3201, 3202, 3225, 3233, 3234, 3235, 3241, 3252]),
        ]
        for company, report_end, include, exclude in cases:
            with self.subTest(company=company):
                spec, prepared = _text_arguments(company, report_end)
                arguments = {"compiled_spec": spec, **prepared["text_arguments"]}
                with original_sources_only():
                    before = frozen.create_deterministic_text_candidate(**arguments)
                    after = fixed.create_deterministic_text_candidate(**arguments)
                    evidence = fixed.build_text_evidence(candidate=after, **arguments)
                self.assertEqual("PASS", evidence["status"])
                kept = {claim["block_index"] for claim in after["selected"].values()}
                had = {claim["block_index"] for claim in before["selected"].values()}
                self.assertEqual(set(), set(include) - kept)
                self.assertEqual(set(), set(exclude) & kept)
                self.assertEqual(set(), had - kept)

    def test_a_quoted_note_title_names_the_whole_note_not_a_caption_in_it(self):
        """Salesforce quotes Note 14's own title, which is not a limit inside it.

        "see Note 14 “Legal Proceedings and Claims”" reads like the two filings
        that name a caption, and is not: the quoted text is the note's heading.
        Treating it as a caption would take one block; treating it as a name
        for the note takes the note, which is what the filing means.
        """
        spec, prepared = _text_arguments(SALESFORCE, "2026-01-31")
        arguments = {"compiled_spec": spec, **prepared["text_arguments"]}
        with original_sources_only():
            after = fixed.create_deterministic_text_candidate(**arguments)
            sources = fixed.prepare_business_text_sources(
                metric_id="D02", **prepared["text_arguments"])
        kept = {claim["block_index"] for claim in after["selected"].values()}
        self.assertEqual(set(), {2092, 2093, 2094, 2095, 2097, 2100, 2102, 2103, 2106} - kept)
        reference_id = next(iter(sources["documents"]))
        scopes = [r for r in sources["coverages"][reference_id]["ranges"]
                  if r["section_id"].startswith("NOTE_")]
        self.assertEqual(1, len(scopes))
        self.assertEqual("EXACT_NOTE", scopes[0]["scope_relation"])

    def test_a_lettered_sub_note_is_located_inside_the_parent_it_resolved_to(self):
        """Pfizer names Note 16A; no heading is numbered 16A, so Note 16 came back.

        `_note_references` records that as WIDER_PARENT_NOTE, and taking the
        parent whole would be over-capture by the resolver's own
        classification. The sub-note is there: Note 16 carries
        "A. Legal Proceedings", and B, C, D and E - guarantees,
        commitments, contingent consideration and insurance - follow it. The
        expectations here are the letters' own block indices, found by matching
        their text, not by calling the locator under test.
        """
        spec, prepared = _text_arguments(PFIZER, "2025-12-31")
        with original_sources_only():
            sources = fixed.prepare_business_text_sources(
                metric_id="D02", **prepared["text_arguments"])
        reference_id = next(iter(sources["documents"]))
        document = sources["documents"][reference_id]
        blocks = document["blocks"]
        references = sources["proposals"][reference_id]["note_references"]
        located = references[0]["range_candidates"][0]
        self.assertEqual("WIDER_PARENT_NOTE", located["scope_relation"])

        letters = {}
        for index in range(located["start_block"], located["end_block_exclusive"]):
            text = blocks[index]["text"].strip()
            for letter in "ABCDE":
                if text.startswith(letter + ". ") and len(text) <= 90:
                    letters.setdefault(letter, index)
        self.assertEqual({"A", "B", "C", "D", "E"}, set(letters))

        scopes = fixed.incorporated_scopes(
            document=document,
            raw_bytes=prepared["text_arguments"]["raw_bytes_by_id"][document["raw_asset_id"]],
            reference=references[0], note=located)
        self.assertEqual(1, len(scopes))
        self.assertEqual("LOCATED_LETTERED_SUB_NOTE", scopes[0]["scope_relation"])
        self.assertEqual(letters["A"], scopes[0]["start_block"])
        self.assertEqual(letters["B"], scopes[0]["end_block_exclusive"])
        # Guarantees, commitments, contingent consideration and insurance are
        # in the parent note and are not what Item 3 incorporates.
        for letter in "BCDE":
            self.assertGreaterEqual(letters[letter], scopes[0]["end_block_exclusive"])

    def test_the_route_declares_only_a_bound_the_runtime_can_honour(self):
        """The routed Spec's declared bound has to be one the renderer delivers.

        64 turned out to be two bounds, not one: what a Spec may declare, and
        what `ORDERED_NEWLINE_V1` will render. While only the first was raised,
        routing v2 would have been a false contract, and this case said so by
        asserting the route still pointed at v1. Both are raised now, so what
        it asserts is the property rather than the state: the route points at
        v2, the frozen renderer still refuses 65, and the successor renderer
        delivers 192 for that Spec identity - so the declared number is one the
        runtime can actually honour.

        The earlier form of this case went on asserting v1 after the route
        moved to v2 and was red at HEAD 3e45533; the source tier is not run in
        CI, so nothing said so.
        """
        from vnext.historical_results import TEXT_SPEC_PATHS
        from vnext import historical_text_protocol as protocol
        from vnext.specs import compile_spec_file
        from vnext.text_results import TextResultError, render_text_payload

        self.assertEqual("catalog/r6/D02_legal_disclosures_v2.md", TEXT_SPEC_PATHS["D02"])
        v1 = compile_spec_file(path=ROOT / "catalog/r6/D02_legal_disclosures_v1.md",
                               dependency_specs={})
        v2 = compile_historical_spec_file(
            repo_root=ROOT, repo_relative_path=TEXT_SPEC_PATHS["D02"], dependency_specs={})
        self.assertEqual(64, text_policy(v1)["max_items"])
        self.assertEqual(192, text_policy(v2)["max_items"])
        # Both bounds read out of the renderers by handing them well-formed
        # items rather than by reading a literal.
        def payload(count):
            return {"version": "TEXT_V1", "content_kind": "SOURCE_EXCERPTS",
                    "renderer": "ORDERED_NEWLINE_V1", "coverage_hashes": ["sha256:" + "a" * 64],
                    "candidate_hash": "sha256:" + "b" * 64,
                    "review_unit_hash": "sha256:" + "c" * 64,
                    "approval_effect_hash": "sha256:" + "d" * 64,
                    "items": [{"order": n, "role": "R%d" % n, "text": "t%d" % n,
                               "observation_id": "sha256:" + ("%064x" % n)}
                              for n in range(count)]}

        with self.assertRaises(TextResultError) as frozen_refusal:
            render_text_payload(payload=payload(65))
        self.assertIn("TEXT_PAYLOAD_ITEMS_INVALID", str(frozen_refusal.exception))
        self.assertEqual(64, len(render_text_payload(payload=payload(64)).split("\n")))
        # The successor honours what v2 declares, and only for v2's identity.
        self.assertEqual(192, protocol.declared_spec_ceiling(
            spec_closure_hash=v2["spec_closure_hash"]))
        self.assertEqual(protocol.FROZEN_PROTOCOL_MAX_ITEMS, protocol.declared_spec_ceiling(
            spec_closure_hash=v1["spec_closure_hash"]))
        self.assertEqual(192, len(protocol.render_text_payload(
            payload=payload(192), max_items=192).split("\n")))

    def test_the_located_sub_note_is_the_only_thing_the_old_bound_was_refusing(self):
        """Pfizer's D02 excerpt set is complete; only the item count stopped it.

        The scope and the volume were never the problem, and the way to show
        that is to run the same arguments through both Spec identities: the old
        bound refuses the set for its count, the raised one accepts exactly the
        same set. The earlier form asserted the refusal on the routed Spec,
        which stopped being v1 when the route moved; that form was red at HEAD
        3e45533.

        It then pinned the set at 92 items and 41,860 characters, and went red
        again the moment the heading repair made it 99 - a state assertion in a
        case whose claim is a relationship. Every content repair moves that
        number and none of them touches what this is about, so the bounds are
        what is asserted: over the old item bound, under the character bound.
        The measured set is 95 items as of this commit and the register carries
        that number, where it belongs.
        """
        _, prepared = _text_arguments(PFIZER, "2025-12-31")
        from vnext.specs import compile_spec_file
        old_spec = compile_spec_file(path=ROOT / "catalog/r6/D02_legal_disclosures_v1.md",
                                     dependency_specs={})
        arguments = {"compiled_spec": old_spec, **prepared["text_arguments"]}
        with original_sources_only():
            with self.assertRaises(TextResultV2Error) as raised:
                fixed.create_deterministic_text_candidate(**arguments)
        self.assertIn("EXCEEDS_ITEM_BOUND", str(raised.exception))
        # The set it refused is 92 items and 41,860 rendered characters - 144
        # percent of the old item bound and 65 percent of the character bound -
        # so what stopped this coordinate is the count, not the scope or the
        # volume.
        from vnext.historical_spec_revision import compile_historical_spec_file as revised
        raised_spec = revised(repo_root=ROOT,
                              repo_relative_path="catalog/r6/D02_legal_disclosures_v2.md",
                              dependency_specs={})
        with original_sources_only():
            candidate = fixed.create_deterministic_text_candidate(
                **{**arguments, "compiled_spec": raised_spec})
            evidence = fixed.build_text_evidence(candidate=candidate,
                                                 **{**arguments, "compiled_spec": raised_spec})
        selected = candidate["selected"]
        characters = sum(len(c["text"]) for c in selected.values()) + len(selected) - 1
        self.assertEqual("PASS", evidence["status"])
        old_policy = text_policy(old_spec)
        self.assertGreater(len(selected), old_policy["max_items"])
        self.assertLess(characters, old_policy["max_text_chars"])
        self.assertLess(characters, text_policy(raised_spec)["max_text_chars"])
        # The sub-note's own text is in, and the sections after it are not.
        sections = {claim["section_id"] for claim in selected.values()}
        self.assertTrue({s for s in sections if s.endswith("_SUB_A")}, sections)

    def test_a_repeated_heading_is_not_page_furniture_unless_it_travels_with_one(self):
        """Read off the filing: a product can be the subject of two matters.

        Repetition alone dropped "Comirnaty (tozinameran)" at 3858 and 3874,
        once under "Actions in Which We are the Defendant" and once under
        "Matters Involving Pfizer and its Collaboration/Licensing Partners".
        The twenty running-header blocks it is right about all have a
        repeating neighbour; those two do not.
        """
        _, prepared = _text_arguments(PFIZER, "2025-12-31")
        with original_sources_only():
            source = fixed.prepare_business_text_sources(metric_id="D02",
                                                         **prepared["text_arguments"])
        coverage = source["coverages"][next(iter(source["coverages"]))]
        note = next(scope for scope in coverage["ranges"]
                    if scope["section_id"].startswith("NOTE_"))
        furniture = set(note["repeated_furniture_blocks"])
        self.assertNotIn(3858, furniture)
        self.assertNotIn(3874, furniture)
        # The five page-header runs are still gone, all four text blocks of
        # each - the page number in the middle occurs once and is dropped by
        # the inherited length rule instead.
        self.assertEqual({3825, 3826, 3828, 3829, 3842, 3843, 3845, 3846,
                          3865, 3866, 3868, 3869, 3892, 3893, 3895, 3896,
                          3913, 3914, 3916, 3917}, furniture)
        blocks = source["documents"][next(iter(source["documents"]))]["blocks"]
        for index in sorted(furniture):
            self.assertIn(blocks[index]["text"].strip(),
                          {"Pfizer Inc.", "2025 Form 10-K",
                           "Notes to Consolidated Financial Statements",
                           "Pfizer Inc. and Subsidiary Companies"})

    def test_a_short_heading_inside_an_incorporated_note_is_content(self):
        """Whether a product heading survived depended on its generic name.

        The inherited twelve-character minimum kept Orgovyx (relugolix) and
        dropped Zantac, so the paragraphs beneath the short ones lost the label
        saying which matter they are about. Inside a note an Item incorporated
        by reference, a short emphasized heading is content.
        """
        _, prepared = _text_arguments(PFIZER, "2025-12-31")
        from vnext.historical_spec_revision import compile_historical_spec_file as revised
        spec = revised(repo_root=ROOT,
                       repo_relative_path="catalog/r6/D02_legal_disclosures_v2.md",
                       dependency_specs={})
        arguments = {"compiled_spec": spec, **prepared["text_arguments"]}
        with original_sources_only():
            candidate = fixed.create_deterministic_text_candidate(**arguments)
            evidence = fixed.build_text_evidence(candidate=candidate, **arguments)
        selected = {claim["block_index"]: claim for claim in candidate["selected"].values()}
        # The seven the reading found, by index and by the text at that index.
        recovered = {3858: "Comirnaty (tozinameran)", 3874: "Comirnaty (tozinameran)",
                     3870: "Paxlovid", 3882: "Asbestos", 3886: "Docetaxel",
                     3889: "Zantac", 3899: "Chantix"}
        for index, text in recovered.items():
            self.assertIn(index, selected, text)
            self.assertEqual(text, selected[index]["text"].strip())
        self.assertEqual("PASS", evidence["status"])
        # Not a total. This case is about seven headings, and pinning the whole
        # set here is what made two other cases in this file go red on repairs
        # that had nothing to do with them.
        # Nothing the bound was guarding came back with them: the bare page
        # numbers in the same runs stay out.
        for index in (3827, 3844, 3867, 3894, 3915):
            self.assertNotIn(index, selected)

    def test_four_of_the_six_are_gone_and_the_keyword_two_are_still_open(self):
        """The repair is four of the six, and the register says which four.

        The audit report is not Item 3, not the legal proceedings section and
        not a contingencies note, so the four blocks of the auditor's critical
        audit matter leave. The two admitted on a single keyword - a
        credit-loss policy whose match is "written off after all reasonable
        means to collect ... (including litigation, where appropriate)" and a
        risk list containing the word - are a different defect and stay, named,
        so a later change cannot quietly decide them.
        """
        _, prepared = _text_arguments(PFIZER, "2025-12-31")
        from vnext.historical_spec_revision import compile_historical_spec_file as revised
        spec = revised(repo_root=ROOT,
                       repo_relative_path="catalog/r6/D02_legal_disclosures_v2.md",
                       dependency_specs={})
        with original_sources_only():
            candidate = fixed.create_deterministic_text_candidate(
                **{"compiled_spec": spec, **prepared["text_arguments"]})
        selected = {claim["block_index"] for claim in candidate["selected"].values()}
        self.assertEqual(set(), {1881, 1882, 1883, 1884} & selected)
        self.assertTrue({2175, 2240} <= selected)
        # And the two that belong there are still there. A narrowing that
        # reached them would satisfy the line above and be wrong.
        self.assertTrue({2302, 2351} <= selected)

    def test_the_report_closes_on_a_signature_or_on_the_tenure_sentence(self):
        """A signature-only rule passes five filings and fails the sixth.

        Five of the six filings read close their audit report with a /s/ block.
        Pfizer's has none - the tenure sentence is the last thing before the
        city and the date, and it does not even use the usual wording: it says
        the firm cannot determine the year it began. So a rule built on the
        signature alone would have left both of Pfizer's openings unbounded,
        which is exactly the filing the exclusion exists for.
        """
        _, prepared = _text_arguments(PFIZER, "2025-12-31")
        document = _frozen_document(prepared, PFIZER)
        item_8 = document["sections"]["ITEM_8"]["candidates"]
        found = fixed.audit_report_spans(document=document, ranges=item_8)
        self.assertEqual([], found["unclosed_openings"])
        self.assertEqual(["AUDITOR_TENURE_STATEMENT"] * 2,
                         [span["closed_by"] for span in found["spans"]])
        blocks = document["blocks"]
        # The closer is read out of the document, not taken from the rule.
        closer = max(span["end_block_exclusive"] for span in found["spans"]) - 1
        self.assertIn("auditor", blocks[closer]["text"])
        self.assertFalse(blocks[closer]["text"].strip().startswith("/s/"))
        # And a filing that does sign closes on the signature instead.
        _, southwest = _text_arguments("southwest_airlines", "2025-12-31")
        other = _frozen_document(southwest, "southwest_airlines")
        signed = fixed.audit_report_spans(
            document=other, ranges=other["sections"]["ITEM_8"]["candidates"])
        self.assertEqual(["SIGNATURE"] * 2, [span["closed_by"] for span in signed["spans"]])

    def test_a_report_outside_every_scanned_range_is_not_reported_as_unclosed(self):
        """Pfizer carries a third report and it never closes.

        The internal control report sits in Item 9A and has no signature block
        and no tenure sentence, so no closer exists for it anywhere. It is also
        outside every range the scan considers, so it could not exclude a block
        even if it closed. Reporting it would invite a reader to think
        something was missed when nothing was at stake.
        """
        _, prepared = _text_arguments(PFIZER, "2025-12-31")
        document = _frozen_document(prepared, PFIZER)
        whole = fixed.audit_report_spans(document=document)
        self.assertTrue(whole["unclosed_openings"],
                        "this case is only meaningful while that report exists")
        item_8 = document["sections"]["ITEM_8"]["candidates"]
        start, stop = item_8[0]["start_block"], item_8[0]["end_block_exclusive"]
        for opening in whole["unclosed_openings"]:
            self.assertFalse(start <= opening < stop)
        self.assertEqual([], fixed.audit_report_spans(
            document=document, ranges=item_8)["unclosed_openings"])

    def test_a_report_title_with_no_closer_excludes_nothing(self):
        """An unbounded exclusion could drop real disclosures silently.

        A registered over-take is the lesser of the two, so an opening without
        a closer is reported and excludes nothing.
        """
        _, prepared = _text_arguments(PFIZER, "2025-12-31")
        document = _frozen_document(prepared, PFIZER)
        item_8 = document["sections"]["ITEM_8"]["candidates"]
        opening = fixed.audit_report_spans(
            document=document, ranges=item_8)["spans"][0]["start_block"]
        blocks = [{**block} for block in document["blocks"]]
        for block in blocks[opening:]:
            # Remove every closer after the first opening, leaving the title.
            if block["text"].strip().startswith("/s/") or "auditor" in block["text"]:
                block["text"] = "redacted for this case"
        found = fixed.audit_report_spans(document={**document, "blocks": blocks},
                                         ranges=item_8)
        self.assertEqual([], found["spans"])
        self.assertTrue(found["unclosed_openings"])

    def test_the_exclusion_reaches_d02_only(self):
        """D03 has its own approved source and was not measured here.

        The first version of this skipped the whole block, which took the same
        blocks out of the regulatory candidate set as well - on four filings
        the rule was supposed to leave alone. The candidate counts were
        identical either way, so only comparing the records found it.
        """
        _, prepared = _text_arguments("southwest_airlines", "2025-12-31")
        document = _frozen_document(prepared, "southwest_airlines")
        arguments = prepared["text_arguments"]
        reference = arguments["source_references"][0]
        proposal = fixed.referenced_note_candidates(
            document=fixed.narrow_document_sections(document=document),
            raw_bytes=arguments["raw_bytes_by_id"][reference["raw_asset_id"]])
        spans = fixed.audit_report_spans(
            document=document,
            ranges=document["sections"]["ITEM_8"]["candidates"])["spans"]
        inside = {index for span in spans
                  for index in range(span["start_block"], span["end_block_exclusive"])}
        self.assertTrue(inside, "this filing is only useful if it has an audit report")
        regulatory = {claim["block_index"] for claim in proposal["D03"]["candidates"]}
        self.assertTrue(inside & regulatory,
                        "and only useful if D03 takes something from inside it")
        legal = {claim["block_index"] for claim in proposal["D02"]["candidates"]}
        self.assertEqual(set(), inside & legal)

    def test_the_successor_routes_only_the_metric_it_corrects(self):
        module, _ = fixed.text_api("D02")
        self.assertIs(fixed, module)
        parent, _ = fixed.text_api("C02")
        self.assertIs(frozen, parent)


def _selected(company_id, report_end="2025-12-31"):
    """The excerpt set's block indices, and the document they came out of."""
    spec, prepared = _text_arguments(company_id, report_end)
    arguments = {"compiled_spec": spec, **prepared["text_arguments"]}
    with original_sources_only():
        candidate = fixed.create_deterministic_text_candidate(**arguments)
        sources = fixed.prepare_business_text_sources(
            metric_id="D02", **prepared["text_arguments"])
    reference_id = next(iter(sources["documents"]))
    return ({claim["block_index"] for claim in candidate["selected"].values()},
            sources["documents"][reference_id],
            sources["coverages"][reference_id]["ranges"])


def _running_headers(document, ranges):
    """Blocks that repeat inside their scope next to another repeating block.

    Recomputed here from the document rather than read off the scope, so the
    expectation does not come from the field the rule under test writes.
    """
    found = set()
    for scope in ranges:
        start, stop = scope["start_block"], scope["end_block_exclusive"]
        counts = collections.Counter(
            " ".join(document["blocks"][index]["text"].split()).strip(" .:;,\u2014-").casefold()
            for index in range(start, stop))
        repeats = {index for index in range(start, stop)
                   if counts[" ".join(document["blocks"][index]["text"].split())
                             .strip(" .:;,\u2014-").casefold()] > 1}
        found |= {index for index in repeats
                  if (index - 1) in repeats or (index + 1) in repeats}
    return found


class PageFurnitureInEveryScopeTest(unittest.TestCase):
    """A running header is not a disclosure, in any scope.

    The criterion existed and ran, but only on the scopes this successor
    builds. Item 3 and a wholesale note went without it, and reading Ford's
    excerpt set against the filing found the consequence: three page breaks
    inside Note 24, each contributing the registrant name, "NOTES TO THE
    FINANCIAL STATEMENTS" and "NOTE 24 ... (Continued)". Its Item 3 names no
    caption, so the whole note is taken and nothing dropped them.
    """

    def test_fords_result_holds_no_running_header(self):
        """The header is identified by the document's own repetition."""
        selected, document, ranges = _selected(FORD)
        headers = _running_headers(document, ranges)
        note = [index for index in headers if 3955 <= index < 3992]
        self.assertEqual(8, len(note), sorted(note))
        self.assertEqual(set(), selected & headers)
        self.assertEqual(45, len(selected))

    def test_no_other_filing_loses_an_excerpt_to_it(self):
        """Dropping more than furniture would show up as a smaller set.

        These five counts are facts about the filings, measured before the
        criterion was widened and unchanged by it. A criterion that took a
        heading for a header would move one of them.
        """
        for company_id, report_end, excerpts in ((PFIZER, "2025-12-31", 96),
                                                 (LUMEN, "2025-12-31", 41),
                                                 (SALESFORCE, "2026-01-31", 15),
                                                 (SOUTHWEST, "2025-12-31", 25),
                                                 (ENPHASE, "2025-12-31", 18)):
            with self.subTest(company_id):
                selected, document, ranges = _selected(company_id, report_end)
                self.assertEqual(excerpts, len(selected))
                self.assertEqual(set(), selected & _running_headers(document, ranges))

    def test_d03_keeps_the_repeated_table_rows_this_criterion_would_take(self):
        """The skip is D02's, because the same loop builds D03's set.

        Macy's pension note states "Settlement(189)(123)— —" twice, a few
        blocks apart and among other repeating rows, so the criterion sees a
        run of repeats and calls it a header. Both are D03 candidates carrying
        ACTION_LANGUAGE_PRESENT. Letting the skip apply to both metrics drops
        them - measured, 42 regulatory candidates to 40 - in a filing whose D02
        set does not move at all, which is why the cost of getting this wrong
        is invisible from the metric being worked on. It is also the reason
        this criterion is not obviously safe to widen: it can see a repeated
        table row as furniture.
        """
        spec, prepared = _text_arguments(MACYS, "2026-01-31")
        with original_sources_only():
            sources = fixed.prepare_business_text_sources(
                metric_id="D02", **prepared["text_arguments"])
        reference_id = next(iter(sources["documents"]))
        proposal = sources["proposals"][reference_id]
        blocks = {candidate["block_index"] for candidate in proposal["D03"]["candidates"]}
        self.assertEqual(42, len(proposal["D03"]["candidates"]))
        self.assertEqual(set(), {1566, 1573} - blocks)
        document = sources["documents"][reference_id]
        headers = _running_headers(document, sources["coverages"][reference_id]["ranges"])
        self.assertEqual({1566, 1573}, {1566, 1573} & headers)

    def test_enphases_footer_survives_and_this_records_why(self):
        """The one page-furniture block this criterion cannot see.

        Enphase writes its footer as one block carrying the page number, so no
        two instances share a text and repetition finds nothing to compare.
        It is a registered content defect rather than a reason to invent a
        second criterion from one filing; this asserts both halves, so a later
        fix fails here and sends whoever wrote it to the defect register.
        """
        selected, document, ranges = _selected(ENPHASE)
        footer = [index for index in selected
                  if document["blocks"][index]["text"].startswith("Enphase Energy, Inc. |")]
        self.assertEqual(1, len(footer), footer)
        self.assertNotIn(footer[0], _running_headers(document, ranges))
        register = json.loads(
            (ROOT / "docs/evidence/issue47_history/known_result_defects.json").read_text())
        self.assertIn("D02_ENPHASE_2025_PAGE_FOOTER_CARRIES_ITS_PAGE_NUMBER",
                      {entry["defect_id"] for entry in register["defects"]})


def _proposal(company_id, report_end="2025-12-31"):
    _, prepared = _text_arguments(company_id, report_end)
    document = _frozen_document(prepared, company_id)
    arguments = prepared["text_arguments"]
    reference = arguments["source_references"][0]
    return fixed.referenced_note_candidates(
        document=fixed.narrow_document_sections(document=document),
        raw_bytes=arguments["raw_bytes_by_id"][reference["raw_asset_id"]]), document


class HyperlinkedSentenceTest(unittest.TestCase):
    """A sentence the registrant wrapped in an anchor is still a sentence.

    `_substantive` drops any linked block under 120 characters. Pfizer's whole
    Item 3 is one such block - a 77-character hyperlinked sentence - so the
    item the approved source names first contributed nothing. Lumen is the
    control and the reason the pair is load-bearing: its Item 3 is the same
    kind of sentence, an incorporation by reference to a note, and it is taken
    because it is 226 characters and carries no anchor. A rule that keyed on
    anything but the anchor would leave the two filings as they were.
    """

    def test_the_hyperlinked_sentence_is_taken_and_the_unlinked_one_still_is(self):
        """Both expectations are read out of the filings, not from the rule."""
        for company_id, linked in ((PFIZER, True), (LUMEN, False)):
            with self.subTest(company_id):
                proposal, document = _proposal(company_id)
                item_3 = document["sections"]["ITEM_3"]["candidates"]
                self.assertEqual(1, len(item_3), item_3)
                sentences = [
                    index for index in range(item_3[0]["start_block"],
                                             item_3[0]["end_block_exclusive"])
                    if document["blocks"][index]["text"].strip().endswith(".")
                    and "Note" in document["blocks"][index]["text"]]
                self.assertEqual(1, len(sentences), sentences)
                block = document["blocks"][sentences[0]]
                self.assertIs(linked, bool(block["linked"]),
                              "the corpus has to supply both sides of the contrast")
                taken = {claim["block_index"] for claim in proposal["D02"]["candidates"]}
                self.assertIn(sentences[0], taken, block["text"])

    def test_a_navigation_link_in_the_same_position_stays_out(self):
        """What the dropped clause was protecting, and still is.

        Three filings carry `Table of Contents` links inside a declared range.
        Nothing new rejects them: asking the frozen rule with the anchor taken
        off is enough, because its navigation-header pattern already knows
        what they are. Admitting every linked block instead adds nine of them
        here.
        """
        for company_id in (MARRIOTT, SOUTHWEST, ENPHASE):
            with self.subTest(company_id):
                proposal, document = _proposal(company_id)
                ranges = proposal["checked_ranges"]
                links = [index for scope in ranges
                         for index in range(scope["start_block"],
                                            scope["end_block_exclusive"])
                         if document["blocks"][index]["linked"]
                         and document["blocks"][index]["text"].strip().casefold()
                         == "table of contents"]
                self.assertTrue(links, "this filing is only useful if it carries them")
                taken = {claim["block_index"] for claim in proposal["D02"]["candidates"]}
                self.assertEqual(set(), set(links) & taken)

    def test_a_hyperlinked_block_still_has_to_sit_where_d02_takes_blocks(self):
        """Item 8 at large is not the approved source, anchor or no anchor.

        Pfizer's Item 8 is full of short hyperlinked cross-references - "(a)See
        Note 17A.", "See Note 5 for further information regarding income
        taxes." - and none of them carries the legal keyword. Admitting a
        hyperlinked block without asking where it sits takes twenty more
        blocks from this filing alone.
        """
        proposal, document = _proposal(PFIZER)
        owner = {}
        for scope in proposal["checked_ranges"]:
            for index in range(scope["start_block"], scope["end_block_exclusive"]):
                held = owner.get(index)
                width = scope["end_block_exclusive"] - scope["start_block"]
                if held is None or width < held[1]:
                    owner[index] = (scope["section_id"], width)
        elsewhere = [index for index, (section, _) in owner.items()
                     if section == "ITEM_8"
                     and document["blocks"][index]["linked"]
                     and fixed._hyperlinked_sentence(document=document,
                                                     block=document["blocks"][index])
                     and not fixed._LEGAL.search(document["blocks"][index]["text"])]
        self.assertTrue(elsewhere, "this filing is only useful if it carries them")
        taken = {claim["block_index"] for claim in proposal["D02"]["candidates"]}
        self.assertEqual(set(), set(elsewhere) & taken)

    def test_the_admission_is_d02_s_and_d03_is_not_asked(self):
        """Stated because the placement is a choice, not because a filing shows it.

        The branch appends to D02's list rather than opening the shared gate,
        which is the shape the audit-report rule had to be corrected into after
        it silently moved D03's candidates on four filings. Wiring this one
        into the shared gate instead leaves every D03 set in this corpus
        byte-identical, so no case here can tell the two apart - the narrow
        placement is kept because it bounds what the change can touch, and
        that is recorded rather than claimed to be tested.
        """
        proposal, document = _proposal(PFIZER)
        item_3 = document["sections"]["ITEM_3"]["candidates"][0]
        admitted = [index for index in range(item_3["start_block"],
                                             item_3["end_block_exclusive"])
                    if document["blocks"][index]["linked"]]
        self.assertEqual(1, len(admitted), admitted)
        self.assertIn(admitted[0],
                      {claim["block_index"] for claim in proposal["D02"]["candidates"]})
        self.assertNotIn(admitted[0],
                         {claim["block_index"] for claim in proposal["D03"]["candidates"]})

    def test_one_section_rule_serves_both_paths(self):
        """Two copies of the same policy is how the two paths come apart."""
        self.assertTrue(fixed._d02_section("ITEM_3", "anything at all"))
        self.assertTrue(fixed._d02_section("NOTE_16_SUB_A", "anything at all"))
        self.assertFalse(fixed._d02_section("ITEM_8", "anything at all"))
        self.assertTrue(fixed._d02_section("ITEM_8", "various legal proceedings"))
        self.assertFalse(fixed._d02_section("ITEM_1A", "various legal proceedings"))


if __name__ == "__main__":
    unittest.main()
