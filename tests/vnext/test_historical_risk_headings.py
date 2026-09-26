"""D01 for a pinned annual period, against the chain it is a pinned version of.

D01 is the cheapest shape in this frame: one filing, one text role, no prior
accession and no second source, so what the pinned route had to change is which
filing the role means. Everything else - the selector, the compiler, the
renderer, the review unit - is the frozen current route's and is imported.

The current period's expectations are the ordinary chain's own candidate,
compared as a whole record rather than as a heading count. A pinned route that
quietly widened or narrowed its source set would produce a candidate just as
readily as a correct one, and a count would not tell them apart.

Two things asserted here cannot be produced by the saved corpus, and both say
so where they are: the reuse of D02's frozen source plan, and the argument
shape the frozen v1 result API accepts. Both are inherited checks rather than
new rules, so they are kept and exercised by constructing the divergence they
guard - as the lodging route's scope check was - instead of dropped for having
no example.
"""
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import historical_text_input as pinned_input
from vnext.historical_results import TEXT_METRICS, TEXT_SPEC_PATHS
from vnext.historical_spec_revision import compile_historical_spec_file
from vnext.historical_text_input import prepare_historical_business_text_input
from vnext import historical_risk_results as successor_v1
from vnext import text_results as frozen_v1
from vnext.historical_text_emphasis import (UNCHANGED_BLOCK_FIELDS, UnderlineBlocks,
                                            build_text_document_admitting_underline)
from vnext.historical_text_results import text_api
from vnext.text_coverage import _Blocks, build_text_document
from vnext.normal_period_selection import resolve_period_selection
from vnext.ordinary_remaining_cases import prepare_current_source_case
from vnext.specs import compile_spec_file

MARRIOTT = "marriott_international"
ENPHASE = "enphase_energy"
FORD = "ford_motor_company"
MACYS = "macys"
SALESFORCE = "salesforce"
PARAMOUNT = "paramount_skydance_paramount_global"
SOUTHWEST = "southwest_airlines"


def _spec(metric_id="D01"):
    return compile_historical_spec_file(repo_root=ROOT,
                                        repo_relative_path=TEXT_SPEC_PATHS[metric_id],
                                        dependency_specs={})


def _candidate(arguments, spec):
    """The selected headings for this input, through D01's own API.

    ``text_api`` is asked rather than a module imported directly, because which
    implementation answers D01 is part of what this file checks. The cases
    below compare two INPUTS under that one selector; the selector's own
    relationship to the frozen one is a different question and is asserted
    separately, in TheSuccessorChainMovesOnlyWhatTheHeadingsMoveTest.
    """
    api, _ = text_api("D01")
    return api.create_deterministic_text_candidate(
        **{"compiled_spec": spec,
           **{key: value for key, value in arguments.items() if key != "compiled_spec"}})


def _pinned(company_id, report_end, metric_id="D01"):
    with original_sources_only():
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=report_end)
        return prepare_historical_business_text_input(
            repo_root=ROOT, company_id=company_id, metric_id=metric_id,
            period_selection=selection)


def _current(company_id, metric_id="D01"):
    with original_sources_only():
        return prepare_current_source_case(data_root=ROOT, company_id=company_id,
                                           metric_id=metric_id)


class PinnedRiskHeadingsTest(unittest.TestCase):
    """The pinned route against the ordinary chain, on the current period."""

    def test_the_current_period_gets_the_ordinary_chain_s_own_candidate(self):
        """Two companies at opposite ends of the observed heading range.

        Enphase carries 60 headings and Ford 30, so a route that truncated,
        re-scoped or re-ordered the selection would move one of them. The
        candidate record carries each heading's exact text and raw byte span,
        so equality is not a count agreeing by coincidence.
        """
        spec = _spec()
        for company_id in (ENPHASE, FORD):
            with self.subTest(company_id):
                ordinary = _current(company_id)
                pinned = _pinned(company_id, "2025-12-31")
                self.assertEqual("PREPARED", pinned["input_status"])
                self.assertEqual(ordinary["target"], pinned["text_arguments"]["target"])
                self.assertEqual(ordinary["target_period"], pinned["target_period"])
                self.assertEqual(_candidate(ordinary["text_arguments"], spec),
                                 _candidate(pinned["text_arguments"], spec))

    def test_the_pinned_route_compiles_the_same_spec_the_ordinary_one_does(self):
        """D01 declares the frozen bound, so the two compilers must agree.

        The comparison above passes one compiled Spec to both sides, which
        proves the inputs agree and says nothing about the Spec. D02's two
        compilations differ - its successor declares 192 items where the frozen
        compiler caps a declaration at 64 - so this is the assertion that D01
        was not quietly given that revision along with the route.
        """
        self.assertEqual(compile_spec_file(path=ROOT / TEXT_SPEC_PATHS["D01"],
                                           dependency_specs={}), _spec())

    def test_an_earlier_year_reads_that_year_s_filing(self):
        """The point of pinning: the year asked for, not the year filed last.

        Marriott has three annual primaries saved, so it is the one company
        where the two answers can differ. The assertion is on the accession -
        a route taking the latest filing would return the 2025 one for all
        three - and on the candidates differing, because three pinned periods
        returning one candidate would mean the pin reached the selection but
        not the bytes.
        """
        spec, seen = _spec(), {}
        for report_end in ("2025-12-31", "2024-12-31", "2023-12-31"):
            with self.subTest(report_end):
                prepared = _pinned(MARRIOTT, report_end)
                self.assertEqual("PREPARED", prepared["input_status"])
                target = prepared["text_arguments"]["target"]
                self.assertEqual(report_end, target["period_end"])
                self.assertEqual(report_end, prepared["target_period"]["period_end"])
                candidate = _candidate(prepared["text_arguments"], spec)
                seen[report_end] = (target["accession"], candidate["candidate_hash"])
        self.assertEqual(3, len({accession for accession, _ in seen.values()}))
        self.assertEqual(3, len({candidate for _, candidate in seen.values()}))

    def test_a_same_period_amendment_is_context_for_d01_as_it_is_for_d02(self):
        """Paramount is the one company where all three text rules can differ.

        Its pinned period carries a 10-K/A, and that same amendment is context
        for D01 and D02 - the target is the original 10-K - while for C02 it is
        the source, because that is where this company's governance
        information is. So the assertion is that D01 agrees with D02 and that
        C02 does not, which a rule keyed on D02 alone fails on the first half
        and a rule keyed on "has amendments" fails on the second.

        Southwest is the second company with an amendment in the period and is
        included because it resolves C02 through the proxy instead: the C02
        answer there has to be the same for the opposite reason.
        """
        for company_id in (PARAMOUNT, SOUTHWEST):
            with self.subTest(company_id):
                statuses = {metric: _pinned(company_id, "2025-12-31",
                                            metric_id=metric)["input_status"]
                            for metric in ("C02", "D01", "D02")}
                self.assertEqual("PREPARED_ORIGINAL_WITH_AMENDMENTS", statuses["D02"])
                self.assertEqual(statuses["D02"], statuses["D01"])
                self.assertEqual("PREPARED", statuses["C02"])

    def test_d01_is_not_answered_by_d02s_successor(self):
        """Which implementation answers D01, asserted rather than assumed.

        This named ``vnext.text_results`` until D01 gained its own successor,
        and then expired - a case that names an implementation stops meaning
        anything the moment that implementation is replaced, which is the
        second time this file has had to learn that. So what is asserted is
        the property that survives a replacement: D01 must not be answered by
        D02's successor, because that one corrects D02's section boundary and
        carries its raised item capacity, and nothing in D01's own Spec asks
        for either; and it must run on the v1 protocol with the v1 review
        builder, which is what its Spec declares.
        """
        d02, d02_review = text_api("D02")
        d01, d01_review = text_api("D01")
        self.assertEqual("vnext.historical_text_results", d02.__name__)
        self.assertNotEqual(d02.__name__, d01.__name__)
        self.assertEqual("vnext.text_review", d01_review.__module__)
        self.assertNotEqual(d01_review, d02_review)
        self.assertEqual("TEXT_V1", d01.VALUE_KIND)
        self.assertEqual(("C02", "D01", "D02"), TEXT_METRICS)


class TheD01InputShapeIsNotInheritedByAccidentTest(unittest.TestCase):
    """The two reuses the saved corpus cannot exercise on its own."""

    def test_the_v1_api_is_not_handed_an_argument_it_rejects(self):
        """``source_filings`` is v2's; the v1 API refuses a shape it lacks.

        The corpus cannot show this, because D01's preparation simply does not
        add the key. So the positive is that the prepared arguments are exactly
        what the frozen entry point accepts, and the negative hands it the v2
        shape and requires a refusal - which is what adding the key for every
        text metric alike would produce.
        """
        prepared = _pinned(FORD, "2025-12-31")
        self.assertEqual({"target", "source_references", "raw_blobs", "raw_bytes_by_id"},
                         set(prepared["text_arguments"]))
        self.assertIn("source_filings",
                      set(_pinned(FORD, "2025-12-31", metric_id="D02")["text_arguments"]))
        api, _ = text_api("D01")
        with self.assertRaises(TypeError):
            api.create_deterministic_text_candidate(compiled_spec=_spec(), source_filings={},
                                                    **prepared["text_arguments"])

    def test_a_second_filing_in_the_reused_plan_stops_d01(self):
        """D02's plan is reused; the guard is what keeps the reuse honest.

        ``_source_plan``'s D02 branch is byte-frozen by the parent rule set, so
        no saved filing can make it return two text filings - the divergence is
        constructed here, and said to be constructed. Without the guard, a
        future generation that gave D02 a second source would silently give
        D01 one as well, and D01's Spec allows a single role.
        """
        real = pinned_input._source_plan

        def two_filings(**kwargs):
            plan = real(**kwargs)
            return {**plan, "text_filings": [*plan["text_filings"], plan["text_filings"][0]]}

        with patch.object(pinned_input, "_source_plan", side_effect=two_filings):
            prepared = _pinned(FORD, "2025-12-31")
        self.assertEqual("BLOCKED", prepared["input_status"])
        self.assertEqual(["HISTORICAL_TEXT_D01_PLAN_SHAPE_CHANGED"],
                         [limitation["reason"]
                          for limitation in prepared["input_binding"]["limitations"]])

    def test_widening_the_forms_is_keyed_off_the_metric(self):
        """Macy's has proxies in the same block; D01 must not be given them.

        C02 needed the governance forms admitted into the pinned metadata
        view. A version that widened them for every text metric would fill
        D01's governance selection here and change which inventories its scope
        record names, without changing any heading - so the assertion is on the
        scope record rather than on the candidate.
        """
        scope = _pinned(MACYS, "2026-01-31")["input_binding"]["current_metadata_scope"]
        self.assertIsNone(scope["selection"]["latest_def14a"])
        self.assertEqual([], scope["selection"]["def14a_amendments"])
        self.assertEqual([], scope["governance_inventories"])


if __name__ == "__main__":
    unittest.main()


class TheUnderlineParserIsTheFrozenOnePlusUnderlineTest(unittest.TestCase):
    """The copied font-weight rule, held to the one it was copied from.

    The successor parser restates the frozen emphasis computation so that
    inheritance can be read from the bold component alone, which is what lets
    `text-decoration:none` cancel an underline without taking a bold with it.
    A restated rule can drift, so the relationship is asserted rather than
    described: with underline switched off it has to produce the frozen
    parser's blocks, and with it on it may only add.
    """
    FILINGS = (("enphase_energy", "2025-12-31"), ("ford_motor_company", "2025-12-31"),
               (MARRIOTT, "2025-12-31"))

    @classmethod
    def setUpClass(cls):
        cls.documents = {}
        for company_id, report_end in cls.FILINGS:
            prepared = _pinned(company_id, report_end)
            arguments = prepared["text_arguments"]
            reference = [source for source in arguments["source_references"]
                         if source["source_role"] == "target_primary"][0]
            cls.documents[company_id] = (
                arguments["raw_bytes_by_id"][reference["raw_asset_id"]],
                arguments["raw_blobs"][reference["raw_asset_id"]], reference,
                arguments["target"], report_end)

    def _blocks(self, text, parser):
        parser.feed(text)
        parser.close()
        parser._flush()
        return parser.blocks

    def test_with_underline_off_it_produces_the_frozen_parsers_blocks(self):
        """The guarantee on the copied rule, on three real filings.

        They are not interchangeable: measured, admitting underline adds 3
        leading emphases to one of these documents and 251 to another, so a
        drift that only showed on heavily decorated markup would still be
        visible here.
        """
        for company_id, _ in self.FILINGS:
            with self.subTest(company_id):
                raw = self.documents[company_id][0]
                text = raw.decode("utf-8-sig", errors="strict")
                # Both switches off: the restated flush has to be the frozen
                # one too, not only the copied font-weight rule. With only
                # underline off these three filings would pass anyway - none of
                # them holds a bridged gap - which is why both are named.
                self.assertEqual(self._blocks(text, _Blocks(text)),
                                 self._blocks(text, UnderlineBlocks(
                                     text, admit_underline=False, bridge_punctuation=False)))

    def test_with_underline_on_it_only_adds(self):
        """No leading emphasis may be cleared or shortened anywhere.

        The rule this replaces - one flag, set on underline and cleared on
        `none` - cannot tell which contribution it is clearing, and measured on
        this repository's saved filings it clears 1,599 bold leading emphases
        in one document. That is the failure this asserts the absence of.
        """
        for company_id, _ in self.FILINGS:
            with self.subTest(company_id):
                raw = self.documents[company_id][0]
                text = raw.decode("utf-8-sig", errors="strict")
                frozen = self._blocks(text, _Blocks(text))
                widened = self._blocks(text, UnderlineBlocks(text))
                self.assertEqual(len(frozen), len(widened))
                for before, after in zip(frozen, widened):
                    self.assertEqual(before["text"], after["text"])
                    if before["leading_emphasis"] is None:
                        continue
                    self.assertIsNotNone(after["leading_emphasis"])
                    self.assertGreaterEqual(len(after["leading_emphasis"]["text"]),
                                            len(before["leading_emphasis"]["text"]))

    def test_a_none_under_a_bold_does_not_clear_the_bold(self):
        """The case the two stacks exist for, constructed because it must be.

        The saved filings do not put `text-decoration:none` inside a bold run
        often enough to rely on, so this is built rather than found, and says
        so. A one-flag rule answers None here.
        """
        markup = ('<html><body><div><span style="font-weight:700">Bold '
                  '<span style="text-decoration:none">still bold</span></span>'
                  '</div></body></html>')
        blocks = self._blocks(markup, UnderlineBlocks(markup))
        self.assertEqual(1, len(blocks))
        self.assertEqual("Bold still bold", blocks[0]["leading_emphasis"]["text"])

    def test_emphasis_crosses_punctuation_only_when_it_resumes(self):
        """Paramount's "U.S." with its periods unbolded, and the cases around it.

        Constructed because the boundaries have to be pinned exactly: a bold
        lead sentence followed by its paragraph must still end at the
        paragraph, and an unbolded word between bold runs is not bridged -
        only punctuation was measured, so only punctuation is admitted.
        """
        cases = (
            ('<b>changes in U</b>.<b>S</b>.<b> or foreign laws</b>',
             "changes in U.S. or foreign laws"),
            ('<b>Our industry is competitive</b>. Guests choose among many brands.',
             "Our industry is competitive"),
            # The period as its own part and the paragraph as the next one: the
            # gap is punctuation, and what follows is not emphasised, so the
            # lead sentence still ends before it. Without the resumption check
            # this reads "Our industry is competitive." - the case that makes
            # the check necessary rather than decorative.
            ('<b>Our industry is competitive</b><span>.</span><span> Guests choose.</span>',
             "Our industry is competitive"),
            ('<b>Risks</b> in <b>Detail</b>', "Risks"),
            ('<b>Note 7A</b>, <b>7B</b>', "Note 7A, 7B"))
        for inner, expected in cases:
            with self.subTest(expected):
                markup = "<html><body><div>" + inner + "</div></body></html>"
                blocks = self._blocks(markup, UnderlineBlocks(markup))
                self.assertEqual(expected, blocks[0]["leading_emphasis"]["text"])
        markup = "<html><body><div>" + cases[0][0] + "</div></body></html>"
        off = self._blocks(markup, UnderlineBlocks(markup, bridge_punctuation=False))
        self.assertEqual("changes in U", off[0]["leading_emphasis"]["text"])

    def test_the_document_builder_changes_only_the_emphasis_fields(self):
        """Sections and every other per-block field come from the frozen build.

        Section boundaries do not depend on emphasis - the frozen `_heading`
        reads `linked` and the text - so they are inherited rather than
        recomputed, and this is what makes that safe to say.
        """
        for company_id, _ in self.FILINGS:
            with self.subTest(company_id):
                raw, blob, reference, target, report_end = self.documents[company_id]
                frozen = build_text_document(
                    raw_bytes=raw, raw_blob=blob, source_reference=reference,
                    expected_company_id=company_id, expected_cik=target["entity"],
                    expected_period_end=report_end)
                widened = build_text_document_admitting_underline(
                    raw_bytes=raw, raw_blob=blob, source_reference=reference,
                    expected_company_id=company_id, expected_cik=target["entity"],
                    expected_period_end=report_end)
                self.assertEqual(frozen["sections"], widened["sections"])
                self.assertNotEqual(frozen["text_document_id"], widened["text_document_id"])
                for before, after in zip(frozen["blocks"], widened["blocks"]):
                    self.assertEqual(
                        {field: before[field] for field in UNCHANGED_BLOCK_FIELDS},
                        {field: after[field] for field in UNCHANGED_BLOCK_FIELDS})
                    self.assertEqual(sorted(before), sorted(after))


class TheSuccessorChainMovesOnlyWhatTheHeadingsMoveTest(unittest.TestCase):
    """The duplicated chain against the frozen one, on real filings.

    "Identical" is not what can be required, and the narrowing is measured:
    the document hash covers every block's emphasis fields, so admitting
    underline moves the document identity on every filing. What must not move
    is anything else.
    """
    DERIVED_FROM_THE_DOCUMENT_IDENTITY = ("document_id", "proposal_id",
                                          "coverage_hash", "candidate_hash")
    # Salesforce is here because it is the one filing that discriminates:
    # measured, admitting italic as well as underline adds exactly one block
    # in this corpus and it is that filing's lead-in sentence. Without it the
    # ADMIT_ITALIC_TOO injection passes every case - Ford's fourteen italic
    # running heads, which an earlier note said italic would take, are already
    # refused by the frozen item-label rule.
    UNCHANGED = ((ENPHASE, "2025-12-31"), (FORD, "2025-12-31"),
                 (SOUTHWEST, "2025-12-31"), (SALESFORCE, "2026-01-31"))

    @staticmethod
    def _scrub(value, identities):
        if isinstance(value, dict):
            return {key: ("<DOCUMENT_IDENTITY>"
                          if key in (TheSuccessorChainMovesOnlyWhatTheHeadingsMoveTest
                                     .DERIVED_FROM_THE_DOCUMENT_IDENTITY)
                          else TheSuccessorChainMovesOnlyWhatTheHeadingsMoveTest._scrub(
                              item, identities))
                    for key, item in value.items()}
        if isinstance(value, list):
            return [TheSuccessorChainMovesOnlyWhatTheHeadingsMoveTest._scrub(item, identities)
                    for item in value]
        return "<DOCUMENT_IDENTITY>" if value in identities else value

    def _candidates(self, company_id, report_end):
        arguments = _pinned(company_id, report_end)["text_arguments"]
        spec = _spec()
        return (frozen_v1.create_deterministic_text_candidate(compiled_spec=spec, **arguments),
                successor_v1.create_deterministic_text_candidate(compiled_spec=spec, **arguments))

    def test_nothing_but_the_document_identity_moves_where_no_heading_does(self):
        """Three filings, none of which uses underline for a heading."""
        for company_id, report_end in self.UNCHANGED:
            with self.subTest(company_id):
                before, after = self._candidates(company_id, report_end)
                identities = {before["candidate_hash"], after["candidate_hash"]}
                self.assertNotEqual(before["candidate_hash"], after["candidate_hash"])
                self.assertEqual(self._scrub(before, identities),
                                 self._scrub(after, identities))

    def test_the_route_actually_reaches_the_successor(self):
        """Asserted behaviourally, because a name check does not see this.

        Found by injection: making the D01 branch of ``text_api``
        unreachable sends it to the frozen v1 chain, not to D02's successor,
        so every name comparison still passes while the delivered value loses
        the four headings. What the route has to deliver is the thing to
        assert, so this asks the routed API for Marriott's candidate and
        requires an underlined group heading in it.
        """
        api, _ = text_api("D01")
        arguments = _pinned(MARRIOTT, "2025-12-31")["text_arguments"]
        candidate = api.create_deterministic_text_candidate(compiled_spec=_spec(),
                                                            **arguments)
        texts = [claim["text"] for claim in candidate["selected"].values()]
        self.assertIn("Operational Risks", texts)
        self.assertIn("General Risk Factors", texts)
        self.assertEqual(38, len(texts))

    def test_paramount_s_heading_is_delivered_whole(self):
        """The registered truncation, on the filing itself, through the route."""
        api, _ = text_api("D01")
        arguments = _pinned(PARAMOUNT, "2025-12-31")["text_arguments"]
        candidate = api.create_deterministic_text_candidate(compiled_spec=_spec(),
                                                            **arguments)
        texts = [claim["text"] for claim in candidate["selected"].values()]
        self.assertIn("Failures to comply with or changes in U.S. or foreign laws or "
                      "regulations could have an adverse effect on our business, financial "
                      "condition or results of operations.", texts)
        self.assertNotIn("Failures to comply with or changes in U", texts)
        self.assertEqual(38, len(texts))

    def test_marriott_gains_exactly_the_headings_it_underlines(self):
        """And gains them in each of its three saved years.

        The fourth differs between 2023 and the later years, which is how it
        is visible that these come from each filing's own bytes.
        """
        expected = {"2025-12-31": 4, "2024-12-31": 4, "2023-12-31": 4}
        for report_end, count in expected.items():
            with self.subTest(report_end):
                before, after = self._candidates(MARRIOTT, report_end)
                texts = [claim["text"] for claim
                         in sorted(after["selected"].values(), key=lambda c: c["order"])]
                previous = [claim["text"] for claim
                            in sorted(before["selected"].values(), key=lambda c: c["order"])]
                added = [text for text in texts if text not in previous]
                self.assertEqual(count, len(added))
                self.assertEqual([], [text for text in previous if text not in texts])
                self.assertIn("Operational Risks", added)
