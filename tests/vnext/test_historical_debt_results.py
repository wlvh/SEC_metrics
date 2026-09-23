"""B06's cascade for a pinned period, and why all of it had to be wired.

The load-bearing case is the differential: the ordinary chain and this copy
answer the same company for the same period, and must agree field for field.
A copy checked against itself always agrees, so nothing else here could find a
transcription error.

The second load-bearing case is the cascade's shape. Two companies reach two
different stages under two different Specs, and the last stage - the one a
single-stage wiring would have used for everything - is shown giving a
different answer than the cascade does. That is the evidence for wiring seven
stages rather than one, stated as a test rather than as a claim.
"""
import difflib
import inspect
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.historical_coverage import WIRED_HISTORICAL_METRICS
from vnext.historical_debt_results import (SUPPORTED_METRICS, HistoricalDebtError,
                                           resolve_historical_debt_metric)
from vnext.historical_results import prepare_historical_run_input
from vnext.normal_period_selection import resolve_period_selection
from vnext.normal_annual_input_v2 import prepare_saved_annual_input
import vnext.normal_bond_debt_results as bond
import vnext.normal_inclusive_debt_results as inclusive

# Five companies whose current filings reach five different stages. Asked of
# all ten rather than chosen - though two of the ten did not answer, which is
# what the note below is about: Marriott's equity is nonpositive so the guard
# answers, Ford is an industrial-dimension filer so the special scope does,
# Enphase matches the note-carrying grammar, Macy's matches the bond grammar,
# and Southwest matches none so the last stage answers. Two of the five share
# a Spec, so the stage is what distinguishes them.
#
# The sixth stage - the inclusive grammar - is reached by the one company not
# in this table: Paramount, whose subject policy this route used to refuse
# outright, which is how it came to be recorded as reached by nobody. It is
# exercised by real material in SuccessorSubjectTest below. The seventh - a
# current input whose amendment changed debt or equity - is still reached by
# no filing here, and the frozen-equivalence case below is what stands behind
# the shared implementation either way.
STAGES = {"marriott_international": "DENOMINATOR_GUARD",
          "ford_motor_company": "SPECIAL_SCOPE",
          "enphase_energy": "NOTE_CARRYING",
          "macys": "BOND",
          "southwest_airlines": "FALLBACK_RESOLVER"}
GUARD_COMPANY = "marriott_international"
GRAMMAR_COMPANY = "enphase_energy"

_RESULT_FIELDS = ("metric_id", "status", "quality", "value", "unit", "reason_code",
                  "publication", "period_start", "period_end")


def _latest_end(company_id):
    with original_sources_only():
        return prepare_saved_annual_input(repo_root=ROOT,
                                          company_id=company_id)["filing"]["reportDate"]


def _resolve(company_id, report_end):
    with original_sources_only():
        selection = resolve_period_selection(repo_root=ROOT, company_id=company_id,
                                             report_end=report_end)
        return resolve_historical_debt_metric(repo_root=ROOT, company_id=company_id,
                                              metric_id="B06", period_selection=selection)


class HistoricalDebtCascadeTest(unittest.TestCase):
    def test_the_copy_answers_what_the_ordinary_chain_answers(self):
        """The only check that can find a transcription error in this module.

        Both chains are asked for the same company and the same period - the
        issuer's latest, the one period on which both are defined - and the
        Result, the Spec it is under and the coordinate must all match. A stage
        copied with a changed concept, a dropped reconciliation or a different
        withheld reason shows up here and nowhere else.
        """
        from vnext.normal_run_v3 import prepare_case
        for company in sorted(STAGES):
            with self.subTest(company=company):
                with original_sources_only():
                    ordinary = prepare_case(data_root=ROOT, company_id=company,
                                            metric_id="B06")
                historical = _resolve(company, _latest_end(company))
                self.assertEqual({k: ordinary["results"]["B06"].get(k) for k in _RESULT_FIELDS},
                                 {k: historical["result"].get(k) for k in _RESULT_FIELDS})
                self.assertEqual(ordinary["spec_paths"]["B06"], historical["spec_path"])
                self.assertEqual(ordinary["target_period"], historical["target_period"])

    def test_five_companies_reach_five_different_stages(self):
        """The cascade is a cascade, not one reader with a period argument.

        Five of the seven stages answer, each for a different company, on this
        repository's own current filings. Two of them share a Spec, so a route
        that reported the Spec and not the stage would look like four.
        """
        reached = {company: _resolve(company, _latest_end(company))
                   for company in sorted(STAGES)}
        self.assertEqual(STAGES, {c: r["cascade_stage"] for c, r in reached.items()})
        self.assertEqual(5, len({r["cascade_stage"] for r in reached.values()}))
        self.assertEqual(4, len({r["spec_path"] for r in reached.values()}))
        guarded = reached[GUARD_COMPANY]
        self.assertEqual("NOT_MEANINGFUL", guarded["result"]["quality"])
        self.assertEqual("DENOMINATOR_NONPOSITIVE", guarded["result"]["reason_code"])

    def test_the_last_stage_alone_would_have_answered_differently(self):
        """Why seven stages were wired rather than the one that always answers.

        The fallback resolver is reachable for every company, so a route that
        wired only it would look complete. Run on its own against the company
        the guard answers, it gives a different Result - which is what wiring
        one stage would have published.
        """
        from vnext.historical_debt_results import (historical_b06_preparation,
                                                   prepare_historical_guarded_b06_result)
        from vnext.historical_annual_input import prepare_historical_annual_input
        from vnext.normal_candidates import _b06_resolution
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=GUARD_COMPANY,
                                                 report_end=_latest_end(GUARD_COMPANY))
            prepared = prepare_historical_annual_input(repo_root=ROOT, company_id=GUARD_COMPANY,
                                                       period_selection=selection)
            preparation = historical_b06_preparation(repo_root=ROOT, company_id=GUARD_COMPANY,
                                                     prepared=prepared)
            guarded = prepare_historical_guarded_b06_result(
                repo_root=ROOT, company_id=GUARD_COMPANY, preparation=preparation)
            _, fallback = _b06_resolution(data_root=ROOT, preparation=preparation)
        cascade = _resolve(GUARD_COMPANY, _latest_end(GUARD_COMPANY))
        # The guard is what stops the cascade here, and the fallback resolver
        # does not reproduce its answer.
        self.assertEqual("NOT_MEANINGFUL", guarded["status"])
        self.assertNotEqual({k: fallback["result"].get(k) for k in _RESULT_FIELDS},
                            {k: cascade["result"].get(k) for k in _RESULT_FIELDS})

    def test_the_two_reconciled_grammars_are_still_one_algorithm(self):
        """The licence for one implementation serving both, re-derived each run.

        The bond and inclusive stages differ in six names, in how their policy
        lists its concepts and in the message their scope refusal carries. This
        module implements them once. If the frozen pair ever stopped reducing
        to each other, that single implementation would no longer be faithful
        to both, and this is where that is noticed.
        """
        def normalised(module, names):
            text = inspect.getsource(module)
            body = text.split("def prepare_", 1)[1]
            for was, now in names:
                body = body.replace(was, now)
            return [line.rstrip() for line in body.splitlines()]

        left = normalised(bond, [
            ("bond_debt_case", "X_case"), ("BondLeaseError", "XError"),
            ("inspect_bond_debt_scope", "inspect_X"), ("ORDINARY_BOND_DEBT", "ORDINARY_X"),
            ("BONDS_AND_SEPARATE_FINANCE_LEASES", "XCLASS"),
            ("POLICY['note_concepts'].values()", "CONCEPTS"),
            ("BOND_LEASE_SEPARATE_BANK_OR_INDUSTRIAL_SCOPE_REQUIRED", "XSCOPE")])
        right = normalised(inclusive, [
            ("inclusive_debt_case", "X_case"), ("InclusiveDebtError", "XError"),
            ("inspect_inclusive_debt_scope", "inspect_X"),
            ("ORDINARY_INCLUSIVE_DEBT", "ORDINARY_X"),
            ("TOTAL_WITH_FINANCE_LEASE_INCLUDED", "XCLASS"),
            ("POLICY['note_concepts']+POLICY['extension_note_concepts']", "CONCEPTS"),
            ("INCLUSIVE_DEBT_SEPARATE_BANK_OR_INDUSTRIAL_SCOPE_REQUIRED", "XSCOPE")])
        self.assertEqual([], list(difflib.unified_diff(left, right, "bond", "inclusive",
                                                       lineterm="", n=0)))
        # And the normalisation is not vacuous: without it they differ.
        self.assertNotEqual(inspect.getsource(bond), inspect.getsource(inclusive))

    def test_the_source_walk_reads_the_original_input_not_the_relabelled_one(self):
        """One pinned input substituted for two ordinary anchors is a bug.

        The ordinary cascade reads two different preparations of the same
        filing: `normal_annual_input`, whose fiscal year comes from the report
        end, and `normal_annual_input_v2`, which overwrites that label with the
        issuer's own. They agree for every calendar-year filer here, so a copy
        that used one for both passes nine of this repository's ten companies.
        Salesforce is where it fails: its year ending 2026-01-31 is 2025 to the
        first and 2026 to the second, and the denominator guard re-derives the
        period from the filing's own bytes and compares.
        """
        from vnext.normal_annual_input import prepare_saved_annual_input as original
        from vnext.normal_annual_input_v2 import prepare_saved_annual_input as relabelled
        from vnext.historical_annual_input import prepare_historical_annual_input
        from vnext.historical_debt_results import (historical_b06_preparation,
                                                   prepare_historical_guarded_b06_result)
        company, end = "salesforce", "2026-01-31"
        with original_sources_only():
            first = original(repo_root=ROOT, company_id=company)["table_input"]["target_period"]
            second = relabelled(repo_root=ROOT, company_id=company)["table_input"]["target_period"]
        self.assertNotEqual(first["fiscal_year"], second["fiscal_year"])
        self.assertEqual(first["period_end"], second["period_end"])

        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=company,
                                                 report_end=end)
            pinned = prepare_historical_annual_input(repo_root=ROOT, company_id=company,
                                                     period_selection=selection)
            self.assertEqual(second["fiscal_year"],
                             pinned["table_input"]["target_period"]["fiscal_year"])
            self.assertEqual(first["fiscal_year"],
                             pinned["original_input"]["table_input"]["target_period"]["fiscal_year"])
            # The route reads the original, and the guard accepts it.
            walked = historical_b06_preparation(repo_root=ROOT, company_id=company,
                                                prepared=pinned["original_input"])
            guarded = prepare_historical_guarded_b06_result(repo_root=ROOT, company_id=company,
                                                            preparation=walked)
            self.assertIn(guarded["status"], {"NOT_MEANINGFUL", "CONTINUE_DEBT_PATH"})
            # Handed the relabelled one instead, the same guard refuses by name.
            from vnext.b06_guarded_result_v3 import B06GuardError
            wrong = historical_b06_preparation(repo_root=ROOT, company_id=company,
                                               prepared=pinned)
            with self.assertRaises(B06GuardError) as raised:
                prepare_historical_guarded_b06_result(repo_root=ROOT, company_id=company,
                                                      preparation=wrong)
            self.assertIn("ANNUAL_SOURCE_IDENTITY_CONFLICT", str(raised.exception))
        # And the Run this company's B06 is filed under carries the issuer's
        # own label, not the one the source walk used.
        component = _resolve(company, end)
        self.assertEqual(second["fiscal_year"], component["target_period"]["fiscal_year"])

    def test_one_company_two_periods_two_answers(self):
        """A pinned period whose material is missing says so, and keeps going.

        Marriott's 2023 filing has no saved accession directory index, which
        the cascade reads before it can choose a stage. The position is a
        withheld Result naming the route that could not resolve, not an
        exception that loses it - and the same company's 2025 period, whose
        material is saved, still answers with a stage and a Spec.
        """
        delivered = _resolve(GUARD_COMPANY, "2025-12-31")
        withheld = _resolve(GUARD_COMPANY, "2023-12-31")
        self.assertEqual("DENOMINATOR_GUARD", delivered["cascade_stage"])
        self.assertEqual("NO_STAGE_REACHED", withheld["cascade_stage"])
        self.assertEqual("PUBLISHED", delivered["result"]["publication"])
        self.assertEqual("WITHHELD", withheld["result"]["publication"])
        self.assertEqual("HISTORICAL_B06_SOURCE_ROUTE_UNRESOLVED",
                         withheld["result"]["reason_code"])
        # The reason names the material, not just the route.
        self.assertIn("SAVED_SOURCE_MISSING", withheld["selection"]["reason"])
        self.assertEqual(2023, withheld["target_period"]["fiscal_year"])
        # Whatever the walk did read before the gap is still in the record.
        self.assertTrue(withheld["source_proofs"])

    def test_an_installed_authority_change_is_not_a_source_gap(self):
        """The refusal that becomes a Result is separated from the one that must not.

        A missing filing is a fact about this repository and belongs in the
        Result. A policy file that no longer matches the installed one is a
        fact about the code, and turning it into a withheld Result would
        publish a position under an authority nobody checked.
        """
        from vnext.historical_debt_results import (HistoricalDebtError,
                                                   HistoricalDebtSourceError)
        self.assertTrue(issubclass(HistoricalDebtSourceError, HistoricalDebtError))
        with self.assertRaises(HistoricalDebtError) as raised:
            resolve_historical_debt_metric(repo_root=ROOT, company_id=GUARD_COMPANY,
                                           metric_id="B01", period_selection={})
        self.assertNotIsInstance(raised.exception, HistoricalDebtSourceError)

    def test_an_unwired_metric_is_refused_by_name(self):
        """The route says which metric it is for rather than answering for any."""
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=GUARD_COMPANY,
                                                 report_end=_latest_end(GUARD_COMPANY))
        with self.assertRaises(HistoricalDebtError) as raised:
            resolve_historical_debt_metric(repo_root=ROOT, company_id=GUARD_COMPANY,
                                           metric_id="B01", period_selection=selection)
        self.assertIn("METRIC_NOT_WIRED:B01", str(raised.exception))

    def test_the_run_factory_routes_b06_here(self):
        """Wiring the component without routing it delivers nothing."""
        self.assertEqual(("B06",), SUPPORTED_METRICS)
        self.assertIn("B06", WIRED_HISTORICAL_METRICS)
        with original_sources_only():
            selection = resolve_period_selection(repo_root=ROOT, company_id=GUARD_COMPANY,
                                                 report_end=_latest_end(GUARD_COMPANY))
            prepared = prepare_historical_run_input(repo_root=ROOT, company_id=GUARD_COMPANY,
                                                    metric_id="B06",
                                                    period_selection=selection)
        self.assertEqual("B06", prepared["primary_metric_id"])
        self.assertEqual("DENOMINATOR_GUARD", prepared["component"]["cascade_stage"])
        self.assertEqual(prepared["results"]["B06"], prepared["component"]["result"])


# The one successor registrant in this repository, and the period its own
# 10-K covers. Every other company here is a continuous primary, which is why
# a blanket refusal on the subject policy went unnoticed: it changed nothing
# for nine of ten.
SUCCESSOR_COMPANY = "paramount_skydance_paramount_global"
SUCCESSOR_END = "2025-12-31"


class SuccessorSubjectTest(unittest.TestCase):
    """B06 for a successor registrant, which the ordinary chain already answers.

    This route used to refuse the whole cascade whenever the subject policy
    was not CONTINUOUS_PRIMARY. The ordinary chain has no such refusal for
    B06: it reads one filing, and the obligations a successor adds are
    discharged inside the stages that can see them. So the refusal was
    stricter than the chain being copied, on a position that chain answers
    with a value - and the differential below is what says so rather than an
    argument about it.
    """

    def test_the_successor_gets_what_the_ordinary_chain_gives_it(self):
        """The load-bearing case, and the same one the continuous companies get.

        A route that invented an answer for the successor - a different stage,
        a different Spec, a wider column, a coordinate from somewhere else -
        passes every other case in this class and fails here.
        """
        from vnext.normal_run_v3 import prepare_case
        with original_sources_only():
            ordinary = prepare_case(data_root=ROOT, company_id=SUCCESSOR_COMPANY,
                                    metric_id="B06")
        historical = _resolve(SUCCESSOR_COMPANY, SUCCESSOR_END)
        self.assertEqual({k: ordinary["results"]["B06"].get(k) for k in _RESULT_FIELDS},
                         {k: historical["result"].get(k) for k in _RESULT_FIELDS})
        self.assertEqual(ordinary["spec_paths"]["B06"], historical["spec_path"])
        self.assertEqual(ordinary["target_period"], historical["target_period"])
        # And it is a value, not an agreed refusal: two chains agreeing that
        # they cannot answer would satisfy the comparison above.
        self.assertEqual("PUBLISHED", historical["result"]["publication"])
        self.assertEqual("EXACT", historical["result"]["quality"])
        self.assertTrue(historical["result"]["value"])

    def test_the_stage_it_reaches_was_the_one_recorded_as_unreached(self):
        """The inclusive grammar is exercised by real material after all.

        It was recorded as implemented but reached by no filing here. That was
        measured over the companies this route could answer, and the one
        company it refused is the one whose filing matches it - which is how
        an absence gets recorded for something that was never looked at.
        """
        historical = _resolve(SUCCESSOR_COMPANY, SUCCESSOR_END)
        self.assertEqual("INCLUSIVE", historical["cascade_stage"])
        self.assertNotIn(historical["cascade_stage"], set(STAGES.values()))

    def test_the_grammar_is_told_the_real_subject_policy(self):
        """Passing the policy through is what lets a stage do its own checking.

        The inclusive grammar asks the current column to carry the successor
        label, and can only ask when it is told the subject is a successor. A
        route that relabelled the subject to get past its own refusal would
        deliver the same value on this filing - measured, not assumed, because
        the column the selector picks here is the successor column either way
        - so what is asserted is that the grammar was told, not that the
        outcome moved.
        """
        import vnext.b06_inclusive_table as table
        seen = []
        frozen = table._current_column

        def spy(*args, **kwargs):
            bound = inspect.signature(frozen).bind(*args, **kwargs).arguments
            seen.append(bound["prepared"]["subject_policy"]["mode"])
            return frozen(*args, **kwargs)

        table._current_column = spy
        try:
            _resolve(SUCCESSOR_COMPANY, SUCCESSOR_END)
        finally:
            table._current_column = frozen
        self.assertTrue(seen)
        self.assertEqual({"SUCCESSOR_REGISTRANT_ONLY"}, set(seen))

    def test_a_subject_policy_this_cascade_has_no_answer_for_stops_here(self):
        """A third mode must stop, not flow through unexamined.

        `_subject_policy` produces two modes today and refuses anything else
        upstream. If a third is ever added, this route has not been shown to
        answer for it, and naming the two is what makes that visible instead
        of silent.
        """
        from vnext.historical_annual_input import prepare_historical_annual_input
        import vnext.historical_debt_results as module
        self.assertEqual(("CONTINUOUS_PRIMARY", "SUCCESSOR_REGISTRANT_ONLY"),
                         module.SUBJECT_MODES)
        for broken, expected in (
                ({"mode": "SOME_FUTURE_MODE"}, "SUBJECT_POLICY_MODE_NOT_IMPLEMENTED"),
                ({"cross_entity_combination_authorized": True},
                 "CROSS_ENTITY_COMBINATION_NOT_IMPLEMENTED")):
            with self.subTest(broken=sorted(broken)):
                with original_sources_only():
                    selection = resolve_period_selection(repo_root=ROOT,
                                                         company_id=SUCCESSOR_COMPANY,
                                                         report_end=SUCCESSOR_END)
                    real = prepare_historical_annual_input(repo_root=ROOT,
                                                           company_id=SUCCESSOR_COMPANY,
                                                           period_selection=selection)
                    edited = {**real,
                              "subject_policy": {**real["subject_policy"], **broken}}
                    patched = lambda **kwargs: edited        # noqa: E731 - one call
                    was = module.prepare_historical_annual_input
                    module.prepare_historical_annual_input = patched
                    try:
                        with self.assertRaises(HistoricalDebtError) as raised:
                            module.resolve_historical_debt_metric(
                                repo_root=ROOT, company_id=SUCCESSOR_COMPANY,
                                metric_id="B06", period_selection=selection)
                    finally:
                        module.prepare_historical_annual_input = was
                self.assertIn(expected, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
