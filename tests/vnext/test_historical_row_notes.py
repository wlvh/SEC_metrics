"""What a pinned historical row says about where its values come from.

Every historical row used to end with "the current value comes from the
selected filing and the prior value from the prior selected filing". That is
what a comparative metric does - Marriott FY2024's B02 row names both years'
annual filings as evidence - but an event count's evidence is the window's
filings (Pfizer 2025's E02 row names only the submissions index) and a text
metric's is the selected filing alone; neither has a prior value. The sentence
now follows the row's own evidence. Synthetic accessions taken from those two
rows; no filing is read.
"""
import inspect
import unittest

from vnext import historical_projection as projection

CURRENT = "0001628280-25-004818"
PRIOR = "0001628280-24-004372"


class TheRowSaysWhatItsEvidenceShows(unittest.TestCase):
    def test_a_comparative_row_keeps_its_words(self):
        # B02's evidence: this year's annual filing and last year's.
        self.assertEqual(projection.PRIOR_FILING_NOTE, projection.pinned_period_note(
            prior_accession=PRIOR, evidence_accessions=[CURRENT, PRIOR]))

    def test_an_event_count_claims_no_prior_value(self):
        # E02's evidence is the submissions index of the event window.
        self.assertEqual(projection.SELECTED_SOURCES_NOTE, projection.pinned_period_note(
            prior_accession=PRIOR, evidence_accessions=["SUBMISSIONS-78003"]))

    def test_a_text_row_from_the_selected_filing_alone_claims_none(self):
        self.assertEqual(projection.SELECTED_SOURCES_NOTE, projection.pinned_period_note(
            prior_accession=PRIOR, evidence_accessions=[CURRENT]))

    def test_a_withheld_row_and_a_period_without_a_prior_claim_none(self):
        self.assertEqual(projection.SELECTED_SOURCES_NOTE, projection.pinned_period_note(
            prior_accession=PRIOR, evidence_accessions=[]))
        self.assertEqual(projection.SELECTED_SOURCES_NOTE, projection.pinned_period_note(
            prior_accession=None, evidence_accessions=[CURRENT]))

    def test_the_prior_value_sentence_is_only_reached_through_the_evidence(self):
        """The renderer must not append the old sentence on its own again.

        The sentence is a module constant; the renderer's own body may name
        the chooser but never the sentence, so the only way a row can say it
        is through its evidence.
        """
        body = inspect.getsource(projection.render_historical_run)
        self.assertIn("pinned_period_note(", body)
        self.assertNotIn("prior value from the prior selected", body)
        self.assertNotIn("PRIOR_FILING_NOTE", body)


if __name__ == "__main__":
    unittest.main()
