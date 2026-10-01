"""C02 composition facts: each structure the reader accepts, and its near misses.

Synthetic documents keep one structure per case, so a failure names the rule
that broke. The real filings are read in ``test_historical_board_composition_
filings``; both are needed, because a rule that only a real filing exercises
can be broken without any synthetic case noticing, and the reverse.
"""
from __future__ import annotations

from pathlib import Path
import datetime as dt
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from vnext.canonical import content_hash, sha256_bytes  # noqa: E402
from vnext.historical_board_composition_v3 import (  # noqa: E402
    _committee_set, _mentions_person, board_composition_facts, committee_name, name_list, person_name,
    sentences, statement_labels)

# The target year of the synthetic filings: a proxy filed in 2026 reports 2025.
PERIOD_START = "2025-01-01"
START = dt.date.fromisoformat(PERIOD_START)


def _document(texts, *, emphasized=(), linked=(), registrant="Example Corporation"):
    """A governance document record with the frozen shape and a valid identity."""
    blocks, offset = [], 0
    for index, text in enumerate(texts):
        raw = text.encode("utf-8")
        blocks.append({"block_index": index, "text": text, "emphasized": index in emphasized,
                       "linked": index in linked, "raw_start_byte": offset,
                       "raw_end_byte": offset + len(raw), "raw_span_sha256": sha256_bytes(content=raw)})
        offset += len(raw) + 1
    body = {"blocks": blocks, "source_reference_id": "sha256:" + "1" * 64,
            "raw_asset_id": "sha256:" + "2" * 64,
            "source_filing": {"form": "DEF 14A", "accessionNumber": "0000000000-26-000001"},
            "source_state": "COMPLETE_LOCAL_DOCUMENT", "source_reasons": [],
            "registrant_names": [registrant]}
    return {**body, "text_document_id": content_hash(value=body)}


def _selected(texts, *, period_start=PERIOD_START, **kwargs):
    proposal = board_composition_facts(document=_document(texts, **kwargs), period_start=period_start)
    return {c["block_index"]: c["labels"] for c in proposal["candidates"]}


class TheLeadRoleIsReadFromTheCatalog(unittest.TestCase):
    """The lead-director role phrase lives in the catalog; four patterns carry it.

    It is one of the phrases the approved source strategy owns for this
    family, which executable code may not spell (tools/check_vnext_semantics).
    It goes into the patterns unescaped, so the reader refuses a phrase that
    could change a pattern's shape rather than its words.
    """

    def test_the_four_patterns_carry_the_catalog_s_phrase(self):
        import json
        from vnext import historical_board_composition_v3 as reader
        terms = json.loads(reader._TERMS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(terms["board_lead_role"], reader._LEAD_ROLE)
        for pattern in (reader._CHAIR_TAIL, reader._NOT_DIRECTOR_INDEPENDENCE, *reader._LEADERSHIP[:2]):
            self.assertIn(reader._LEAD_ROLE, pattern.pattern)
        self.assertTrue(reader._LEADERSHIP[0].search("She serves as our " + reader._LEAD_ROLE + "."))

    def test_terms_that_could_reshape_a_pattern_are_refused(self):
        import json
        import tempfile
        from unittest.mock import patch
        from vnext import historical_board_composition_v3 as reader
        good = json.loads(reader._TERMS_PATH.read_text(encoding="utf-8"))
        cases = {"a group": {**good, "board_lead_role": "lead (independent) director"},
                 "an alternation": {**good, "board_lead_role": "lead director|chair"},
                 "capitals": {**good, "board_lead_role": "Lead Independent Director"},
                 "another metric": {**good, "metric_id": "C03"},
                 "another record": {**good, "record_type": "SOMETHING_ELSE"}}
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "terms.json"
            for name, terms in cases.items():
                path.write_text(json.dumps(terms), encoding="utf-8")
                with self.subTest(case=name), patch.object(reader, "_TERMS_PATH", path):
                    with self.assertRaisesRegex(ValueError, "C02_COMPOSITION_TERMS_INVALID"):
                        reader._lead_role()
            path.write_text(json.dumps(good), encoding="utf-8")
            with patch.object(reader, "_TERMS_PATH", path):
                self.assertEqual(good["board_lead_role"], reader._lead_role())


class ANameIsTheWholeBlock(unittest.TestCase):

    def test_names_as_proxies_print_them(self):
        for text in ("Susan Desmond-Hellmann, MD, M.P.H.", "• William Clay Ford, Jr., Chair",
                     "Pierre R. Breber (Chair)*", "GoldbergCaposselaCollinsMcMillan", "Isabella D.",
                     "Goren", "BARBARA M. BYRNE", "Maynard Webb(1)", "General Kevin P. Chilton"):
            with self.subTest(text=text):
                self.assertTrue(person_name(text))

    def test_a_quoted_nickname_between_the_names(self):
        # Lumen's and Marriott's proxies print "Steven T. “Terry” Clontz": the
        # quotes failed the name, and a committee roster ended at it.
        for text in ("Steven T. “Terry” Clontz", "Isabella D. \"Bella\" Goren"):
            with self.subTest(text=text):
                self.assertTrue(person_name(text))
        # A quoted word that does not stand between two words of a name is no nickname.
        for text in ("Recovery “Clawback”", "“Board” means", "Definition of “Cause”:"):
            with self.subTest(text=text):
                self.assertFalse(person_name(text))
        texts = ["Nominating and Corporate Governance Committee", "Michael Roberts, Chair",
                 "Steven T. “Terry” Clontz", "Laurie Siegel", "Meetings in 2021: 4"]
        self.assertEqual({0: ["COMMITTEE_HEADING"], 1: ["COMMITTEE_CHAIR_NAME"], 2: ["COMMITTEE_MEMBER_NAME"],
                          3: ["COMMITTEE_MEMBER_NAME"]}, _selected(texts))

    def test_two_initials_printed_together_before_the_surname(self):
        # Marriott's proxies print "J.W. Marriott, Jr." and "Andrew P.C. Wright".
        for text in ("J.W. Marriott, Jr.", "Andrew P.C. Wright"):
            with self.subTest(text=text):
                self.assertTrue(person_name(text))
        # The same shape anywhere else is an abbreviation (blocks these proxies print).
        for text in ("U.S. Federal Income Tax Consequences", "Orange, S.A.", "Telefonica S.A.",
                     "B.A., Cornell University", "M.B.A., Harvard University", "U.S."):
            with self.subTest(text=text):
                self.assertFalse(person_name(text))

    def test_a_suffix_after_a_comma_ends_the_name_before_it(self):
        self.assertTrue(name_list("J.W. Marriott, Jr. (Chair), Anthony G. Capuano, Lawrence W. Kellner, and "
                                  "Debra L. Lee."))
        # One name printed surname first (Paramount's older proxies) is not a list.
        self.assertFalse(name_list("Phillips, Jr., Charles E."))

    def test_headings_captions_and_furniture_are_not_names(self):
        for text in ("Recent Committee Focus Areas", "Key Responsibilities", "Marriott International, Inc.",
                     "2026 Proxy Statement", "Meetings in 2025: 7", "Corporate Governance",
                     "Other Public Company Boards (Current)", "Chair", "Members", "Audit Committee"):
            with self.subTest(text=text):
                self.assertFalse(person_name(text))


class ACommitteeHeadingNamesOneCommittee(unittest.TestCase):

    def test_page_headings_signatures_and_row_labels(self):
        for text, name in (("The Audit Committee", "audit"), ("AUDIT COMMITTEE", "audit"),
                           ("Audit & Finance Committee", "audit & finance"),
                           ("Fleet Oversight Committee*", "fleet oversight"),
                           ("Members of the Compensation Committee", "compensation"),
                           ("Nominating and Corporate Governance Committee", "nominating and corporate governance")):
            with self.subTest(text=text):
                self.assertEqual(name, committee_name(text))

    def test_headings_about_committees_name_none(self):
        for text in ("Compensation Committee Report", "Board Committees", "Additional Committee Members:",
                     "Compensation Committee Interlocks and Insider Participation",
                     "Additional retainer Audit Committee chair", "Committee"):
            with self.subTest(text=text):
                self.assertIsNone(committee_name(text))


class ACommitteePageIsReadAsAStructure(unittest.TestCase):

    def test_heading_chair_label_members_and_determination_not_duties(self):
        texts = ["The Audit Committee", "Chair: Suzanne Nora Johnson",
                 "The Committee’s primary responsibilities include:",
                 "•reviewing the adequacy of internal control over financial reporting;",
                 "Additional Committee Members:", "Ronald E. Blaylock", "Cyrus Taraporevala",
                 "All Members are Independent and Financially Literate", "Meetings Held in 2025: 9"]
        chosen = _selected(texts, emphasized={0, 4, 8})
        self.assertEqual({0, 1, 4, 5, 6, 7}, set(chosen))

    def test_a_member_column_laid_out_after_the_duties(self):
        texts = ["Audit Committee", "Number of Meetings in 2025: 8", "Current Members", "Key Responsibilities",
                 "•", "Oversee accounting and financial reporting.", "Isabella D.", "Goren", "CHAIR",
                 "Frederick A.", "Henderson", "Human Resources and Compensation Committee"]
        chosen = _selected(texts)
        self.assertEqual({0, 2, 6, 7, 8, 9, 10}, set(chosen))

    def test_a_signature_is_a_roster_and_a_fee_table_is_not(self):
        chosen = _selected(["THE AUDIT COMMITTEE", "Suzanne Nora Johnson, Chair", "Ronald E. Blaylock",
                            "Audit Committee", "•Chair—$35,000", "•Member—$17,500"])
        self.assertEqual({0, 1, 2}, set(chosen))

    def test_a_roster_marked_with_each_glyph_filings_print(self):
        # Ford's older proxies print "◾" before each member's name and Macy's
        # "·". A glyph the reader does not know ends the roster before its
        # first name, so both rosters went unread.
        for glyph in ("◾", "·"):
            with self.subTest(glyph=glyph, form="labelled"):
                texts = ["Finance Committee", "Reviews the Company’s capital structure.", "MEMBERS", glyph,
                         "Jane A. Doe, Chair", glyph, "John B. Roe", glyph, "Mary C. Poe", "MEETINGS IN 2022: 4"]
                self.assertEqual({0: ["COMMITTEE_HEADING"], 2: ["COMMITTEE_MEMBERS_LABEL"],
                                  4: ["COMMITTEE_CHAIR_NAME"], 6: ["COMMITTEE_MEMBER_NAME"],
                                  8: ["COMMITTEE_MEMBER_NAME"]}, _selected(texts))
            with self.subTest(glyph=glyph, form="heading then names"):
                texts = ["Audit Committee", glyph, "John B. Roe", glyph, "Mary C. Poe", "Key Responsibilities"]
                self.assertEqual({0: ["COMMITTEE_HEADING"], 2: ["COMMITTEE_MEMBER_NAME"],
                                  4: ["COMMITTEE_MEMBER_NAME"]}, _selected(texts))

    def test_a_matrix_column_of_directors_is_not_a_roster(self):
        texts = ["Oversight", "Committee", "Lisa M. Atherton", "● ● ●", "Pierre R. Breber",
                 "● ●", "Douglas H. Brooks", "● ● ●"]
        self.assertEqual({}, _selected(texts, emphasized={0, 1}))

    def test_an_inline_members_line(self):
        chosen = _selected(["Compensation Committee",
                            "Members: Mason Morfit (Chair), Neelie Kroes, John V. Roos, Maynard Webb(1)"])
        self.assertEqual({0, 1}, set(chosen))

    def test_a_members_line_written_as_a_sentence(self):
        # Marriott's older proxies end the list with a period and put a comma
        # before its last "and"; either one alone failed the whole list.
        texts = ["Nominating and Corporate Governance Committee",
                 "Current Members: Frederick A. Henderson (Chair), Debra L. Lee, and Aylwin B. Lewis."]
        self.assertEqual({0: ["COMMITTEE_HEADING"], 1: ["COMMITTEE_MEMBERS_LIST"]}, _selected(texts))
        # Marriott FY2021 blocks 990 and 991: joined initials and a suffix in the list.
        texts = ["Executive Committee", "Current Members: J.W. Marriott, Jr. (Chair), Anthony G. Capuano, "
                 "Lawrence W. Kellner, and Debra L. Lee."]
        self.assertEqual({0: ["COMMITTEE_HEADING"], 1: ["COMMITTEE_MEMBERS_LIST"]}, _selected(texts))
        # Words that are not names are still no list, period or not.
        self.assertEqual({}, _selected(["Audit Committee", "Members: see the table on page 12."]))

    def test_a_lead_in_to_duties_does_not_carry_the_duties(self):
        # The sentence that ends in the colon introduces duties, even though an
        # earlier sentence of the same block states the committee's makeup.
        texts = ["Role of the Committee", "The Compensation Committee is composed solely of independent "
                 "directors. Its responsibilities include:", "\u2022Determining compensation for our CEO;",
                 "\u2022Reviewing equity incentive programs."]
        self.assertEqual({1}, set(_selected(texts, emphasized={0})))

    def test_a_composition_sentence_that_introduces_duties(self):
        # The sentence ending in the colon states the committee's makeup, but
        # what it introduces is duties.
        texts = ["As further described below, the Compensation Committee, which is composed solely of independent "
                 "directors, is responsible for, among other things, the following:",
                 "\u2022Determining and approving compensation for our CEO;",
                 "\u2022Reviewing the design of equity incentive programs."]
        self.assertNotIn(1, _selected(texts))

    def test_dated_changes_including_a_wrapped_line(self):
        texts = ["Audit Committee*", "Chair: Michelle J. Goldberg", "Additions", "May 2026: Michelle J. Goldberg",
                 "as Chair, Michael Collins and Stephen McMillan, if elected", "Departures",
                 "December 2025: James Fowler", "Key Responsibilities"]
        self.assertEqual({0, 1, 2, 3, 4, 5, 6}, set(_selected(texts)))


class ADirectorCardIsReadOnlyWhenItNamesItsDirector(unittest.TestCase):

    def test_committee_lines_then_the_director(self):
        texts = ["Director since: 2025", "Committees:", "• Audit Committee (Chair)",
                 "• Nominating and Governance Committee", "BARBARA M. BYRNE", "Ms. Byrne has served as a member."]
        self.assertEqual({1, 2, 3, 4}, set(_selected(texts)))

    def test_unlabelled_committees_on_the_lines_after_the_tenure(self):
        # Enphase's older proxies print each director's committees on the
        # lines after "Director since", with no "Committees:" label.
        texts = ["Jamie", "Haenggi", "Director since August 2020", "Nominating and Corporate Governance Committee",
                 "Audit Committee (Chair)", "Key Skills and Qualifications"]
        self.assertEqual({0: ["DIRECTOR_NAME"], 1: ["DIRECTOR_NAME"], 3: ["DIRECTOR_COMMITTEE_ITEM"],
                          4: ["DIRECTOR_COMMITTEE_ITEM"]}, _selected(texts, emphasized={0, 1, 5}))
        # A committee page's heading is emphasised and is not a card's item.
        self.assertEqual({}, _selected(["Benjamin Kortlang", "Director since May 2010", "Audit Committee",
                                        "The Audit Committee oversees the integrity of our financial statements."],
                                       emphasized={2}))
        # Items on a card that names no director are left out, as a labelled card's are.
        self.assertEqual({}, _selected(["Key Skills and Qualifications", "Director since May 2010",
                                        "Audit Committee", "Career Highlights"], emphasized={0, 3}))

    def test_the_director_named_above_the_card_fields(self):
        # Name, title, designation, age and tenure, then the committee label:
        # the card fields between the name and the label belong to one card.
        texts = ["Robert B. Chavez", "Founder and Chief Executive Officer, Chavez Luxury Advisers, LLC",
                 "Age: 71", "Director Since: 2016", "Committees:", "• Audit Committee", "Professional Background"]
        self.assertEqual({0, 4, 5}, set(_selected(texts)))

    def test_spacer_blocks_do_not_carry_a_committee_label_out_of_reach(self):
        # Ford's cards (2021, 2023, 2024) interleave zero-width spacer blocks
        # and lone bullet glyphs: ten raw blocks from Farley's name to his
        # "Committees: N/A", four of them printed.
        texts = ["James D. Farley, Jr.", "\u200b \u200b \u200b \u200b", "\u200b", "\u200b \u200b", "▪", "Age: 62",
                 "\u200b", "▪", "Director Since: 2020", "\u200b", "Committees: N/A", "\u200b \u200b",
                 "\u200b Experience: Mr. Farley was elected President and Chief Executive Officer of the company "
                 "effective October 1, 2020."]
        self.assertEqual({0: ["DIRECTOR_NAME"], 10: ["DIRECTOR_NO_COMMITTEE"]}, _selected(texts))

    def test_a_designation_s_reach_still_counts_every_block(self):
        # Macy's cards: printed blocks only would let the designation pass this
        # card's committee lines and reach the next card's name, and a name on
        # both sides leaves it out. Its reach stays eight blocks of any kind.
        texts = ["Jill Granoff", "Senior Advisor, Eurazeo Brands", "Independent", "Age: 62", "Director Since: 2022",
                 "Committees:", "●", "CMD (Chair)", "●", "Finance", "●", "Audit", "Torrence Boone"]
        selected = _selected(texts)
        self.assertEqual(["DIRECTOR_DESIGNATION"], selected.get(2))
        self.assertEqual(["DIRECTOR_NAME"], selected.get(0))

    def test_a_card_whose_director_is_not_beside_it_is_left_out(self):
        # A paragraph stands between the name and the label: nothing ties them.
        texts = ["Robert B. Chavez", "Mr. Chavez brings to the Board decades of experience leading luxury retail "
                 "businesses, including as chief executive of a publicly traded company, and a record of "
                 "building brands across markets.", "Committees:", "• Audit Committee", "Professional Background"]
        self.assertEqual({}, _selected(texts))

    def test_a_card_between_two_names_is_not_given_either(self):
        texts = ["Robert B. Chavez", "Age: 71", "Committees:", "• Audit Committee", "Jill Granoff", "Age: 60"]
        self.assertEqual({}, _selected(texts))

    def test_a_card_uses_the_filing_s_own_short_forms(self):
        texts = ["Human Resources and Compensation Committee", "Members: Quincy L. Allen (Chair), Martha Béjar",
                 "Audit Committee", "Members: Hal Stanley Jones (Chair), Michelle J. Goldberg",
                 "General Kevin P. Chilton", "INDEPENDENT", "71 years old", "Committees: A, HRC (Chair)",
                 "Skills:"]
        chosen = _selected(texts, emphasized={4, 5})
        self.assertEqual(["DIRECTOR_COMMITTEE_LABEL"], chosen[7])
        self.assertEqual(["DIRECTOR_NAME"], chosen[4])
        # A code the filing never uses for one of its committees is not one.
        texts[7] = "Committees: A, XYZ"
        self.assertNotIn(7, _selected(texts, emphasized={4, 5}))

    def test_none_is_a_fact_for_a_director_and_not_for_a_nominee(self):
        sitting = ["Director Nominee", "Age: 71", "Director since: 1994", "Committees:", "• None",
                   "SHARI E. REDSTONE", "Ms. Redstone has been a member of our Board since January 1994."]
        chosen = _selected(sitting)
        self.assertEqual(["DIRECTOR_NO_COMMITTEE"], chosen[3])
        self.assertIn(5, chosen)
        nominee = ["Director Nominee", "Age: 74", "Director since: N/A", "Committees: N/A", "MARY BOIES",
                   "Ms. Boies has served, since 2011, as Counsel to a law firm."]
        chosen = _selected(nominee)
        self.assertNotIn(3, chosen)
        # The card still says she is a nominee: its designation and her name.
        self.assertEqual({0, 4}, set(chosen))


class AProseFactIsAStatementAboutThisBoard(unittest.TestCase):

    def assertStates(self, text, label):
        self.assertIn(label, statement_labels(text, frozenset({"audit", "compensation", "example"}),
                                              period_start=START))

    def assertStatesNothing(self, text):
        self.assertEqual([], statement_labels(text, frozenset({"audit", "compensation", "example"}),
                                              period_start=START))

    def test_committee_board_and_leadership_facts(self):
        self.assertStates("The Audit Committee is composed of three directors: Messrs. Gomo, Kortlang and Mora.",
                          "COMMITTEE_COMPOSITION_STATEMENT")
        self.assertStates("The Board has determined that all of our current Directors (other than Dr. Albert "
                          "Bourla) are independent of the company.", "BOARD_INDEPENDENCE_STATEMENT")
        self.assertStates("9 out of 11 members of the Board are independent.", "BOARD_INDEPENDENCE_STATEMENT")
        self.assertStates("1.To elect 12 members of the Board of Directors.", "BOARD_SIZE_STATEMENT")
        self.assertStates("The Board appointed Douglas H. Brooks as independent Chair of the Board, effective "
                          "August 1, 2025.", "BOARD_LEADERSHIP_STATEMENT")
        self.assertStates("No member of the Compensation Committee has ever been an executive officer of the "
                          "Company.", "COMMITTEE_COMPOSITION_STATEMENT")
        self.assertStates("Dr. Hockfield will retire from the Board in April 2026.", "BOARD_MEMBERSHIP_CHANGE")

    def test_on_a_classified_board_the_slate_is_not_the_board_s_size(self):
        # Enphase's board is divided into classes: the nominees are one class
        # (c02-composition-facts/adjudicate.py, CLASSIFIED_SLATE_COUNT).
        slate = ("1.To elect our three nominees for director named in the accompanying proxy statement to the "
                 "Board of Directors, to hold office until the 2029 Annual Meeting of Stockholders.",
                 "Our Board of Directors (the “Board”) has nominated three directors to serve for three-year terms "
                 "until 2029.",
                 "•Election of our three nominees as Class II directors to serve until the 2029 Annual Meeting.")
        size = "The Board currently has seven members and is divided into three classes."
        for text in slate:
            with self.subTest(text=text[:40]):
                labels = statement_labels(text, frozenset({"example"}), period_start=START, classified=True)
                self.assertNotIn("BOARD_SIZE_STATEMENT", labels)
                # The same words on a board whose directors all stand each year
                # state its size.
                self.assertIn("BOARD_SIZE_STATEMENT",
                              statement_labels(text, frozenset({"example"}), period_start=START))
        self.assertIn("BOARD_SIZE_STATEMENT",
                      statement_labels(size, frozenset({"example"}), period_start=START, classified=True))

    def test_a_slate_of_sitting_directors_says_who_the_members_are(self):
        # Macy's proxies (c02-composition-facts/adjudicate.py, NOMINEES_ARE_SITTING_DIRECTORS).
        self.assertStates("Each nominee is currently a member of the Board.", "BOARD_ROSTER_STATEMENT")
        self.assertStates("All of the nominees are currently directors.", "BOARD_ROSTER_STATEMENT")
        for text in ("Each nominee has consented to serve if elected.",
                     "Each nominee is currently a member of the board of directors of another public company.",
                     "All of the nominees are currently directors of other public companies.",
                     "If elected, each nominee will serve for a one-year term."):
            with self.subTest(text=text[:40]):
                self.assertNotIn("BOARD_ROSTER_STATEMENT",
                                 statement_labels(text, frozenset({"audit", "compensation", "example"}),
                                                  period_start=START))

    def test_a_task_force_of_named_directors_is_a_body_of_the_board(self):
        # Macy's (c02-composition-facts/adjudicate.py, BOARD_TASK_FORCE).
        members = ("The Digital Innovation Task Force is made up of three directors, Torrence Boone, Ashley "
                   "Buchanan and Tracey Zhen, and senior members of our digital and merchandising teams.")
        self.assertStates(members, "COMMITTEE_COMPOSITION_STATEMENT")
        # A task force of management names no director.
        self.assertStatesNothing("The Integration Task Force is made up of senior leaders from each business.")
        chosen = _selected(["Digital Innovation Task Force", members, "Audit Committee"])
        self.assertEqual(["COMMITTEE_HEADING"], chosen[0])
        # A title is taken only over the members sentence of the same task force.
        self.assertNotIn(0, _selected(["Supply Chain Task Force", members]))

    def test_the_board_s_size_on_a_past_date_wherever_it_is_printed(self):
        # Ford reports attendance at last year's meeting with the board's size
        # then (c02-composition-facts/adjudicate.py, DIRECTOR_COUNT_ON_A_DATE).
        for text in ("Last year, of the twelve then current members of the Board, twelve attended the virtual "
                     "annual meeting.",
                     "Last year, of the 14 then-current members of the Board, 14 attended the virtual annual meeting."):
            with self.subTest(text=text[:40]):
                self.assertStates(text, "BOARD_SIZE_STATEMENT")
        # No count, no size.
        self.assertNotIn("BOARD_SIZE_STATEMENT", statement_labels(
            "All then current directors attended our 2022 annual meeting.", frozenset({"example"}),
            period_start=START))

    def labels_for(self, text, period_start):
        return statement_labels(text, frozenset({"audit", "compensation", "example"}),
                                period_start=dt.date.fromisoformat(period_start))

    def test_a_join_dated_before_the_year_is_tenure(self):
        # Enphase's director pay paragraph and Lumen's ownership-guideline
        # exceptions date each join; in a later year's filing that is how long
        # someone has served (c02-composition-facts/adjudicate.py,
        # JOIN_BEFORE_THE_YEAR).
        for text, year in (
                ("Notwithstanding the foregoing, Joseph Malchow (who joined our Board in February 2020) will not "
                 "receive equity compensation for serving on our Board during the term of his consulting "
                 "agreement.", "2021-01-01"),
                ("Mr. Allen, who joined our Board on February 25, 2021, has until February 25, 2026 to comply "
                 "with these guidelines.", "2022-01-01")):
            with self.subTest(text=text[:40]):
                self.assertNotIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(text, year))
                # The same sentence in the filing for the year of the join is a change.
                joined = text[text.index("20", text.index("joined")):][:4]
                self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(text, joined + "-01-01"))
        # Another change in the same sentence still counts.
        self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(
            "Mr. Jones, who joined our Board in 2015, will not stand for re-election.", "2025-01-01"))
        # A join without a date is a change, as before.
        self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for("Ms. Smith joined our Board.", "2025-01-01"))

    def test_a_join_dated_in_the_year_is_a_change(self):
        # Marriott's CEO joined the board in the year its 2021 filing reports
        # (JOIN_IN_THE_YEAR); the selector read "has served ... since" as
        # tenure in every year.
        text = ("Tony Capuano has served as Chief Executive Officer and a director of the Company since "
                "February 2021.")
        self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(text, "2021-01-01"))
        self.assertNotIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(text, "2022-01-01"))
        # A join in the year is read wherever it is printed, a pay sentence included.
        self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(
            "Ms. Lee, who joined our Board in March 2025, received a prorated annual cash retainer.",
            "2025-01-01"))
        # Another organisation's board is still not this one.
        self.assertNotIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(
            "Ms. Lee joined the board of directors of Acme Holdings in March 2025.", "2025-01-01"))

    def test_a_departure_dated_in_the_year_is_a_change_wherever_printed(self):
        # Macy's FY2024 footnote 1814 sits in a pay table (it mentions RSUs);
        # FY2023 footnote 1982 dates the departure by the annual meeting.
        rsu = "(5)Mr. Buchanan ceased serving on the Board on November 25, 2024 and forfeited the RSUs granted in May 2024."
        self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(rsu, "2024-02-04"))
        self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(
            "(5)Mr. Bryant and Ms. Hale ceased serving on the Board following our annual meeting of shareholders on "
            "May 19, 2023.", "2023-01-29"))
        # A departure before the year is not a change in it.
        self.assertNotIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(rsu, "2025-02-02"))
        # An officer leaving a post (Lumen FY2023 block 2324) is not the board.
        self.assertNotIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(
            "As previously disclosed and described elsewhere herein, Mr. Trezise ceased serving as EVP, Human "
            "Resources with Lumen effective April 24, 2023, and was involuntarily terminated on April 5, 2024.",
            "2023-01-01"))

    def test_appointed_with_an_office_and_as_a_member_of_the_board(self):
        # Marriott FY2021 block 1144 prints no date; Macy's FY2023 block 2737
        # prints it before the verb.
        self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(
            "Following Mr. Sorenson’s passing, the Board elected Anthony Capuano to serve as CEO of the Company and "
            "as a member of the Board.", "2021-01-01"))
        spring = ("Following a rigorous selection process, during which multiple internal and external candidates "
                  "were evaluated, in March 2023, the Board appointed Mr. Spring as Macy’s President and CEO-elect "
                  "and a member of the Board.")
        self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(spring, "2023-01-29"))
        # The same appointment read in a later year is tenure.
        self.assertNotIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(spring, "2024-02-04"))
        # Enphase FY2022 block 382: the date follows "a member of the Board" and
        # falls before the year, so the dated-join rule already sets it aside.
        self.assertNotIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(
            "Mr. Kothandaraman, 51, joined Enphase in April 2017 as COO, before being appointed President and CEO "
            "and a member of the Board in September 2017.", "2022-01-01"))

    def test_a_join_written_as_a_noun_is_dated_too(self):
        # Salesforce's related-party paragraph dates a director's appointment
        # as a noun; #28's content check found the FY2026 selection took it as
        # a change (c02-composition-facts/adjudicate.py, JOIN_BEFORE_THE_YEAR).
        tenure = ("Oscar Munoz’s daughter, Kellie Munoz, is a non-executive employee of Salesforce who joined the "
                  "Company in January 2020, prior to Mr. Munoz’s appointment to the Board in January 2022, and is "
                  "currently a Senior Director.")
        self.assertNotIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(tenure, "2025-02-01"))
        self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(tenure, "2021-02-01"))
        # The same noun in the year is a change, a pay sentence included.
        self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(
            "Upon their appointment to the Board in July 2025, Ms. Chang and Mr. Kirk each received a prorated "
            "RSU grant.", "2025-02-01"))
        # Undated, the noun is still a change, as before.
        self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(
            "The Board approved Ms. Chang’s appointment to the Board.", "2025-02-01"))

    def test_taking_over_a_chair_or_the_lead_role(self):
        # Salesforce FY2026 block 933, found by #28's content check: the day two
        # directors took up their roles, printed in a pay table's introduction.
        own = frozenset({"audit", "compensation", "governance", "example"})
        labels = statement_labels(
            "On March 21, 2025, Mr. Donald assumed the role of Lead Independent Director, and Mr. Roos assumed the "
            "role of Chair of the Governance Committee.", own, period_start=START)
        self.assertIn("BOARD_LEADERSHIP_STATEMENT", labels)
        self.assertIn("COMMITTEE_COMPOSITION_STATEMENT", labels)
        self.assertIn("BOARD_LEADERSHIP_STATEMENT", statement_labels(
            "Ms. Park took over the role of Chairman of the Board in May 2025.", own, period_start=START))
        # Another body's committee, and a role that is not the board's, are not.
        self.assertEqual([], statement_labels(
            "Mr. Roos assumed the role of Chair of the Audit Committee of Acme Holdings.", own, period_start=START))
        self.assertEqual([], statement_labels(
            "Ms. Park assumed the role of Chief Financial Officer in May 2025.", own, period_start=START))

    def test_a_long_title_before_the_join(self):
        # Paramount FY2025 block 100 (#28's content check): an officer's titles
        # stand between "has served as" and "a member of our Board".
        text = ("Mr. Brandon-Gordon has served as our Chief Strategy Officer and Chief Operating Officer and as a "
                "member of our Board since August 2025.")
        self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(text, "2025-01-01"))
        self.assertNotIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(text, "2026-01-01"))

    def test_a_named_director_s_term_ending_at_a_meeting(self):
        # Lumen's director-pay footnotes state each departure this way; the
        # FY2024 one (block 1506) is the only block naming the three leaving
        # at the 2025 meeting (c02-selector-repairs/ section 17).
        for text in ("(6)The terms of Mr. Brown, Mr. Clontz and Ms. Siegel will end in connection with the election "
                     "of directors at the 2025 annual meeting.",
                     "(7)Mr. Roberts’ term ended in connection with the election of directors at the 2024 annual "
                     "meeting.",
                     "(8)Mr. Hanks’ term ended immediately following the 2023 annual shareholders meeting."):
            with self.subTest(text=text[:40]):
                self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(text, "2024-01-01"))
        # A plan's or an option's term is not a person's, a person named
        # elsewhere in the sentence notwithstanding; nor is every director's.
        for text in ("(z) “Option Expiration Date” shall mean the date on which the term of a Stock Option ends.",
                     "The term of the Amended Plan will end at the 2030 annual meeting, as Mr. Smith noted.",
                     "Each director's term will expire at the next annual meeting of shareholders."):
            with self.subTest(text=text[:40]):
                self.assertNotIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(text, "2024-01-01"))

    def test_a_named_family_member_is_not_an_independence_standard(self):
        # Ford FY2021 block 760: the two Ford family directors joined at the
        # year's annual meeting. "Family member" vetoed it as a standard.
        self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(
            "In addition, having a Ford family member, William Clay Ford, Jr., as our Executive Chair brings a long-term "
            "perspective to Board deliberations, while Alexandra Ford English and Henry Ford III, who were first "
            "elected to the Board at the 2021 Annual Meeting, provide fresh perspectives.", "2021-01-01"))
        # The standards themselves name nobody and stay set aside (Paramount
        # 2021 block 387, Marriott 2021 block 848: without the word each reads
        # as committee composition).
        for text in ("The director is, or has a family member who is, employed as an executive officer of another "
                     "entity where at any time during the past three years any of the executive officers of Example "
                     "have served on the compensation committee of such other entity; or",
                     "(iv) the director or a family member is part of an interlocking directorate in which the director "
                     "or a family member serves on the compensation committee of another company."):
            with self.subTest(text=text[:40]):
                self.assertEqual([], self.labels_for(text, "2021-01-01"))

    def test_a_committee_that_changed_its_name(self):
        # Ford FY2021 states the rename three times (blocks 626, 3096, 4055).
        for text in ("The Compensation Committee changed its name to the Compensation, Talent and Culture Committee "
                     "to reflect its responsibilities related to significant people-related strategies.",
                     "In May 2021, the Charter of the CTC Committee was amended to update the name of the CTC Committee "
                     "from the “Compensation Committee” to the “Compensation, Talent and Culture Committee” in order "
                     "to reflect the expansion of its responsibilities."):
            with self.subTest(text=text[:40]):
                self.assertStates(text, "STANDING_COMMITTEES_STATEMENT")
        # A plan or a policy renamed is not a committee renamed.
        for text in ("The Committee renamed the Annual Incentive Plan as the Annual Performance Bonus Plan in 2023.",
                     "The Committee changed its name for the recoupment policy to the Officer Misconduct Policy."):
            with self.subTest(text=text[:40]):
                self.assertNotIn("STANDING_COMMITTEES_STATEMENT",
                                 statement_labels(text, frozenset({"audit", "compensation", "example"}),
                                                  period_start=START))

    def test_a_committee_the_board_set_up_under_its_own_name(self):
        # Enphase FY2023 block 447, Lumen FY2022 block 1879 and Southwest
        # FY2025 block 1225: the name sits between the article and "committee".
        for text in ("To help with this, the Audit Committee established a cybersecurity subcommittee, which includes "
                     "a board member with cybersecurity expertise, and holds regular meetings.",
                     "In early 2022, the Board formed a special CEO Succession Committee to evaluate internal and "
                     "external candidates to succeed Mr. Storey upon his retirement.",
                     "In July 2025, the Board also established an ad hoc Fleet Oversight Committee."):
            with self.subTest(text=text[:40]):
                self.assertStates(text, "STANDING_COMMITTEES_STATEMENT")
        # The company's own committee (Lumen FY2021 block 68), and a group
        # formed with a committee rather than as one (a constructed sentence).
        for text in ("We have also established a Lumen Sustainability Management committee which is responsible for "
                     "driving our sustainability agenda with the Board and senior leadership.",
                     "The Board formed a working group with the Audit Committee to review the plan."):
            with self.subTest(text=text[:40]):
                self.assertNotIn("STANDING_COMMITTEES_STATEMENT",
                                 statement_labels(text, frozenset({"lumen", "example"}), period_start=START))

    def test_standing_down_at_another_company_s_meeting(self):
        # Pfizer FY2022 blocks 446 and 547: the re-election is at Xerox's meeting.
        pfizer = frozenset({"pfizer", "example"})
        self.assertEqual([], statement_labels(
            "* Mr. Echevarria has informed Pfizer that he will not be standing for re-election at the Xerox Holdings "
            "Corporation’s Annual Meeting of Shareholders to be held on May 25, 2023.", pfizer, period_start=START))
        # The registrant's own meeting, by its name or as "the Company's"
        # (constructed sentences).
        for text in ("Mr. Smith will not be standing for re-election at the Company’s Annual Meeting of Shareholders.",
                     "Mr. Smith will not be standing for re-election at Pfizer’s Annual Meeting of Shareholders.",
                     # The article opening the sentence is not the name.
                     "The Company’s Annual Meeting will be held on May 1, 2023, when Mr. Smith will not stand for "
                     "re-election."):
            with self.subTest(text=text[:60]):
                self.assertIn("BOARD_MEMBERSHIP_CHANGE", statement_labels(text, pfizer, period_start=START))

    def test_no_change_to_the_committees_in_the_year(self):
        # Pfizer FY2022 block 799 and FY2023 block 884: the readers judged each
        # a fact about the committees' members that year.
        for text, start in (("There were no changes to Committee compositions in 2022.", "2022-01-01"),
                            ("There were no changes to Committee compositions in 2023.", "2023-01-01")):
            with self.subTest(text=text[:60]):
                self.assertIn("COMMITTEE_COMPOSITION_STATEMENT", self.labels_for(text, start))
        # An earlier year's stability says nothing about the year reported
        # (constructed: the 2022 sentence read in a FY2023 filing).
        self.assertNotIn("COMMITTEE_COMPOSITION_STATEMENT", self.labels_for(
            "There were no changes to Committee compositions in 2022.", "2023-01-01"))

    def test_a_role_taken_up_with_became(self):
        # Lumen FY2021 block 897: the registrant's chair, named by its possessive.
        lumen = frozenset({"lumen", "technologies"})
        self.assertIn("BOARD_LEADERSHIP_STATEMENT", statement_labels(
            "Effective May 20, 2020, Mr. Glenn became Lumen’s independent, non-executive Chairman, with Mr. Hanks "
            "continuing his role as Vice Chairman.", lumen, period_start=START, registrant=lumen))
        # Salesforce FY2025 block 1887: a committee's chair.
        self.assertStates("In December 2024, Craig Conway transitioned to the Audit & Finance Committee, and in "
                          "January 2025, Mr. Morfit became Chair of the Compensation Committee.",
                          "COMMITTEE_COMPOSITION_STATEMENT")
        # Another company's chair (a constructed sentence), and Paramount FY2021
        # block 728's chair of a law firm.
        for text in ("In 2010, she became Acme’s Chairman.",
                     "In 1999, Ms. Beinecke became the first woman to chair a major New York law firm."):
            with self.subTest(text=text[:40]):
                self.assertEqual([], statement_labels(text, lumen, period_start=START, registrant=lumen))

    def test_a_committee_formed_for_each_search_is_a_step(self):
        # Lumen FY2023 block 1085 (FY2022 block 842 is the same sentence): the
        # search committee is formed each time; its make-up names roles.
        step = ("The NCG Committee forms a search committee that is comprised of the Chairman of the Board, the "
                "HRCC and NCG Committee chairs, and the CEO who will request to interview with a diverse slate of "
                "candidates that best fit the profile.")
        self.assertNotIn("COMMITTEE_COMPOSITION_STATEMENT",
                         statement_labels(step, frozenset({"lumen", "example"}), period_start=START))
        # The same sentence telling of a committee that was formed (a constructed
        # past-tense pair) still states its make-up.
        formed = ("In 2022, the NCG Committee formed a search committee that was comprised of the Chairman of the "
                  "Board, the HRCC and NCG Committee chairs, and the CEO.")
        self.assertStates(formed, "COMMITTEE_COMPOSITION_STATEMENT")

    def test_the_committees_named_together_on_their_charters(self):
        # Ford's five years and Salesforce's two name every committee in one
        # sentence about their charters: which committees exist.
        for text in ("The Company has published on its website the charter of each of the Audit Committee, "
                     "Compensation, Talent and Culture Committee, Finance Committee, Nominating and Governance "
                     "Committee, and Sustainability, Innovation and Policy Committee of the Board.",
                     "The Board has adopted a written charter for the Audit and Finance Committee, the Compensation "
                     "Committee, and the Nominating and Corporate Governance Committee."):
            with self.subTest(text=text[:40]):
                self.assertStates(text, "STANDING_COMMITTEES_STATEMENT")
        # One committee's charter names no set, however often the sentence
        # repeats the committee or punctuates its name.
        # A rename names one committee three ways; the set rule does not count
        # it (it is a fact for the rename, test_a_committee_that_changed_its_name).
        self.assertFalse(_committee_set(
            "In May 2021, the Charter of the CTC Committee was amended to update the name of the CTC Committee "
            "from the “Compensation Committee” to the “Compensation, Talent and Culture Committee”."))
        for text in ("The Charter of the Audit Committee was reviewed by the Audit Committee and the full audit "
                     "committee in 2024.",
                     "The charter of the Compensation, Talent and Culture Committee is available on our website."):
            with self.subTest(text=text[:40]):
                self.assertNotIn("STANDING_COMMITTEES_STATEMENT",
                                 statement_labels(text, frozenset({"audit", "compensation", "example"}),
                                                  period_start=START))

    def test_a_statement_carrying_a_cross_reference_is_read(self):
        # Ford FY2024 block 1590 is linked only for "as noted on page 9"; every
        # independent director's card and summary-table status cites it.
        texts = ["The Board determined that none of the following directors had any material relationship with the "
                 "Company and, thus, are independent: Kimberly A. Casiano and Adriana Cisneros. Our committee "
                 "membership is as noted on page 9.",
                 "Board Independence"]
        selected = _selected(texts, linked={0, 1})
        self.assertIn("BOARD_INDEPENDENCE_STATEMENT", selected.get(0, []))
        # A table-of-contents line states nothing, linked or not.
        self.assertNotIn(1, selected)

    def test_a_footnote_number_printed_against_the_honorific(self):
        # Lumen FY2021/FY2022 print the mark with no space ("6Ms. Boulet’s
        # term ended ..."): the honorific is still the person's.
        text = "6Ms. Boulet’s term ended at the 2021 annual shareholders’ meeting."
        self.assertEqual(["6 Ms Boulet’s term ended at the 2021 annual shareholders’ meeting."], sentences(text))
        self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(text, "2021-01-01"))
        # A number that is part of an amount or a year is not a mark.
        self.assertIn("$15Mr", sentences("Paid $15Mr. Smith.")[0])
        self.assertIn("2021Mr", sentences("In 2021Mr. Smith joined.")[0])

    def test_a_join_is_dated_as_precisely_as_it_is_printed(self):
        # A 52/53-week year starts on its own day (Macy's 2022 year starts
        # January 30). A printed day settles the side; a month alone does
        # not say the join came before the year, so it is read as in it.
        start = "2022-01-30"
        self.assertNotIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(
            "Mr. Allen, who joined our Board on January 15, 2022, has until 2027 to comply.", start))
        self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(
            "Mr. Allen, who joined our Board in January 2022, has until 2027 to comply.", start))
        self.assertNotIn("BOARD_MEMBERSHIP_CHANGE", self.labels_for(
            "Mr. Allen, who joined our Board in December 2021, has until 2026 to comply.", start))

    def test_the_target_year_is_a_date_and_the_proposal_names_it(self):
        texts = ["Tony Capuano has served as Chief Executive Officer and a director of the Company since "
                 "February 2021."]
        for bad in (None, "", "2021", "2021-13-01"):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "C02_COMPOSITION_PERIOD_START_INVALID"):
                    board_composition_facts(document=_document(texts), period_start=bad)
        proposal = board_composition_facts(document=_document(texts), period_start="2021-01-01")
        self.assertEqual("2021-01-01", proposal["join_dates_judged_from"])
        self.assertEqual([0], [c["block_index"] for c in proposal["candidates"]])
        later = board_composition_facts(document=_document(texts), period_start="2022-01-01")
        self.assertEqual([], later["candidates"])
        self.assertNotEqual(proposal["proposal_id"], later["proposal_id"])

    def test_the_filing_says_whether_its_board_is_classified(self):
        slate = "To elect our three nominees for director to hold office until the 2029 Annual Meeting."
        classified = ["Class II Directors", "Steven J. Gomo", slate]
        self.assertNotIn(2, _selected(classified))
        self.assertIn(2, _selected(["Annual Meeting", "Steven J. Gomo", slate]))

    def test_a_determination_qualified_by_a_rule_is_still_a_determination(self):
        self.assertStates("The Board has determined that all members of the Audit Committee are independent, as "
                          "required by Rule 5605(c)(2)(A).", "COMMITTEE_MEMBER_QUALIFICATION")
        # Not an "as required by" phrase: the requirement word follows the
        # determination, and only its position says it qualifies it.
        self.assertStates("The Board also affirmatively determined that each member of the Audit Committee meets "
                          "the heightened independence standards required for audit committee members.",
                          "COMMITTEE_MEMBER_QUALIFICATION")

    def test_rules_hypotheticals_and_process_are_not_facts(self):
        self.assertStatesNothing("Our Principles require that a majority of the Board consist of directors who "
                                 "the Board has determined are independent.")
        self.assertStatesNothing("The Charter provides that the Committee will be comprised of at least three "
                                 "members.")
        self.assertStatesNothing("If the Chairman is not an independent director, the Board will designate a lead "
                                 "independent director.")
        self.assertStatesNothing("The director candidates are either immediately appointed to the Board or "
                                 "nominated to stand for election.")
        self.assertStatesNothing("Directors are elected by a plurality of the votes cast. The three nominees "
                                 "receiving the most votes will be elected.")

    def test_another_organisations_board_is_not_this_one(self):
        self.assertStatesNothing("She serves on the audit committee of Acme Corporation.")
        self.assertStatesNothing("Ms. Casiano also serves as a director of the Federal Home Loan Bank of Atlanta, "
                                 "where she serves as Vice Chair of the Audit Committee.")
        self.assertStatesNothing("At Vonage, he served on the audit and compensation committees.")
        self.assertStatesNothing("Ms. Chandoha serves as Chair of the Risk Committee on the State Street "
                                 "Corporation board.")

    def test_pay_and_letters_are_not_facts(self):
        self.assertStatesNothing("Includes $25,000 for service as Chair of the Audit Committee.")
        self.assertStatesNothing("As Chair of the Compensation Committee, I want to share some thoughts.")
        self.assertStatesNothing("Each outside director receives an annual retainer of $100,000.")

    def test_who_chaired_is_a_fact_even_where_a_fee_is_explained(self):
        self.assertStates("Cash fees paid to Mr. Roos relate to his service as Chair of the Compensation "
                          "Committee for the first quarter of fiscal 2026.", "COMMITTEE_COMPOSITION_STATEMENT")
        self.assertStates("As of March 25, 2026, there were approximately 83,093 employees, including six Named "
                          "Executive Officers and 11 non-employee directors, each of whom would be eligible to be "
                          "granted awards under the 2013 Plan.", "BOARD_SIZE_STATEMENT")

    def test_a_committee_of_management_is_not_the_board_s(self):
        # Lumen's, Pfizer's and Marriott's older proxies describe management
        # committees in the words a board committee's makeup is stated in.
        for text in ("Lumen’s Diversity and Inclusion Steering Committee (DISC), is made up of senior leaders and "
                     "executives, including Lumen’s Chief Diversity and Inclusion Officer.",
                     "In addition, the Pfizer PAC Steering Committee (Steering Committee), which is composed of "
                     "Pfizer employees from different divisions of the company, reviews and approves all political "
                     "contribution requests on a monthly basis.",
                     "Further, all PAC and corporate contribution requests are shared with the Pfizer Political "
                     "Contributions Policy Committee (PCPC), which is co-chaired by the Chief Corporate Affairs "
                     "Officer and the Chief Compliance, Quality & Risk Officer.",
                     "She was appointed Chair of our Global Operating Committee, which consists of senior Company "
                     "leaders who support our business operating platform."):
            with self.subTest(text=text[:40]):
                self.assertStatesNothing(text)
        # Directors who are not management, and a board chair chairing, still seat a board committee.
        for text in ("The Audit Committee is composed entirely of independent directors who are not officers or "
                     "employees of the Company.",
                     "The Committee is composed of three directors, none of whom is an officer or employee.",
                     "The Executive Committee is chaired by the Chairman of the Board."):
            with self.subTest(text=text[:40]):
                self.assertStates(text, "COMMITTEE_COMPOSITION_STATEMENT")

    def test_a_criterion_for_choosing_a_chair_seats_no_one(self):
        # A bullet from a list of what the Board looks for in a lead director,
        # as Macy's older proxies print it: "a Board" is not a committee's name.
        self.assertStatesNothing("●Previous service as a Board committee chair")
        self.assertStates("Ms. Lee serves as Audit Committee chair.", "COMMITTEE_COMPOSITION_STATEMENT")
        self.assertStates("He was appointed as our Compensation Committee chair in 2024.",
                          "COMMITTEE_COMPOSITION_STATEMENT")


class ALeadershipOrMembershipFactNamesThisBoardAndThePerson(unittest.TestCase):

    OWN = frozenset({"audit", "compensation", "example"})

    def labels(self, text):
        return statement_labels(text, self.OWN, period_start=START, acronyms=frozenset({"HRC", "HRCC"}),
                                registrant=frozenset({"example"}))

    def test_whose_chair_the_sentence_says(self):
        for text in ("T. Michael Glenn has served as Example's independent, non-executive Chairman since May 2020.",
                     "Mr. Ellison has served as our Chairman and Chief Executive Officer since August 2025.",
                     "Mr. Spring currently serves as Chairman and Chief Executive Officer of the company.",
                     "The Committee determined that it would be in the best interest of the company for Dr. "
                     "Bourla, the CEO, to continue serving as Chairman of the Board in 2026."):
            with self.subTest(text=text):
                self.assertIn("BOARD_LEADERSHIP_STATEMENT", self.labels(text))

    def test_whether_the_chair_and_the_chief_executive_are_one_person(self):
        # Marriott's, Ford's, Lumen's and Macy's proxies state the structure
        # without naming the holders (c02-composition-facts/adjudicate.py,
        # CHAIR_CEO_STRUCTURE).
        for text in ("Separate Board Chairman and CEO. Since 2012, the Board has chosen to separate the roles of "
                     "Chairman of the Board and CEO.",
                     "We believe that separation of the Chairman and CEO positions has functioned effectively over "
                     "the past many years.",
                     "Our Chairman and CEO functions currently are performed by a single individual.",
                     "The Board has maintained separate Chairman and CEO roles and a Lead Independent Director role "
                     "for many years."):
            with self.subTest(text=text[:50]):
                self.assertIn("BOARD_LEADERSHIP_STATEMENT", self.labels(text))

    def test_a_choice_a_policy_or_a_proposal_states_no_structure(self):
        # None of these is set aside earlier as a requirement or a hypothetical,
        # so each reaches the structure rule itself.
        for text in ("The Board periodically considers whether separating or combining the roles of Chairman and "
                     "CEO serves the Company.",
                     "The Board does not believe that adopting a rigid policy to separate the roles of Chairman and "
                     "CEO would be in the best interests of shareholders.",
                     "This proposal asks the Board to separate the roles of Chairman and CEO."):
            with self.subTest(text=text[:50]):
                self.assertNotIn("BOARD_LEADERSHIP_STATEMENT", self.labels(text))

    def test_another_body_s_chair_and_an_officer_s_vice_chair_are_not_this_board_s(self):
        for text in ("Mr. Varga has served as Acme's Chairman since 2010.",
                     "Mr. Lawler currently serves as Vice Chair of the Company.",
                     "Governor Huntsman served as Example's Vice Chair, Policy advising the Company's CEO."):
            with self.subTest(text=text):
                self.assertNotIn("BOARD_LEADERSHIP_STATEMENT", self.labels(text))

    def test_who_joined_left_or_stayed(self):
        for text in ("The Board appointed C. David Cush, Sarah E. Feinberg, and Patricia A. Watson to the Board, "
                     "each effective as of November 1, 2024.",
                     "Mr. Tresvant was appointed to the Board effective February 12, 2025.",
                     "Dennis Cinelli served as a member of the Board from September 2025 until January 2026.",
                     "On April 8, 2026, Mr. Shell ceased to serve as an employee of the Company and member of the "
                     "Board.",
                     "Following his appointment to the Board in July 2025, David B. Kirk joined the Compensation "
                     "Committee in December 2025.",
                     "Mr. Fowler served on Example's Board of Directors from 2023 until 2025.",
                     "In November 2022, our former President and CEO Jeffrey K. Storey retired from the Board.",
                     "The Board did not elect any new Directors during 2025.",
                     "Commitment to Board Refreshment, with Two New Directors Effective July 2025"):
            with self.subTest(text=text):
                self.assertIn("BOARD_MEMBERSHIP_CHANGE", self.labels(text))

    def test_a_person_is_named_by_an_honorific_or_a_full_name(self):
        for sentence in ("In November 2022, our former President and CEO Jeffrey K. Storey retired from the Board.",
                         "Mr. Rodgers will remain a member of the Board."):
            with self.subTest(sentence=sentence):
                self.assertTrue(_mentions_person(sentence))
        for sentence in ("We have added new directors in support of the new era of Agentic AI.",
                         "Write to our Corporate Secretary at 47281 Bayside Parkway, Fremont.",
                         "Directors who reach age 75 retire from the Board."):
            with self.subTest(sentence=sentence):
                self.assertFalse(_mentions_person(sentence))

    def test_a_process_or_an_adjective_is_not_a_change(self):
        for text in ("His leadership experience would add tremendous value to the Board.",
                     "Stockholders may recommend individuals to become nominees for election to the Board.",
                     "Investors asked about the recently elected Directors, Messrs. Buckley and Taraporevala, "
                     "including their contributions to the Board to date.",
                     "Over the past few years, we have thoughtfully added new directors to the Board in support "
                     "of the new era of Agentic AI.",
                     "The Board expects to add two new directors."):
            with self.subTest(text=text):
                self.assertNotIn("BOARD_MEMBERSHIP_CHANGE", self.labels(text))

    def test_size_setup_and_determinations(self):
        cases = (("With Ms. Lee's impending departure, the Board has reduced its size from 13 to 12.",
                  "BOARD_SIZE_STATEMENT"),
                 ("The Board has focused on refreshment, reducing the Board size to eleven members in 2026.",
                  "BOARD_SIZE_STATEMENT"),
                 ("Of the 12 directors then-serving on our Board, all 12 directors participated in the meeting.",
                  "BOARD_SIZE_STATEMENT"),
                 ("The former Finance Committee, which was dissolved in February 2026, met 9 times.",
                  "STANDING_COMMITTEES_STATEMENT"),
                 ("The Audit Committee has established a subcommittee that meets with management.",
                  "STANDING_COMMITTEES_STATEMENT"),
                 ("As a result, we determined that all Directors are in compliance with the company's Principles.",
                  "DIRECTOR_QUALIFICATION_DETERMINATION"),
                 ("In December 2025, the Board determined that the criteria for Board membership have been "
                  "satisfied.", "DIRECTOR_QUALIFICATION_DETERMINATION"),
                 ("The NCG Committee determined that the amounts involved were below the thresholds set forth in "
                  "the Standards for Director Independence.", "DIRECTOR_QUALIFICATION_DETERMINATION"),
                 ("The following directors served on the HRCC for some or all of 2025: Quincy L. Allen and "
                  "Martha Helena Béjar.", "COMMITTEE_COMPOSITION_STATEMENT"))
        for text, label in cases:
            with self.subTest(text=text):
                self.assertIn(label, self.labels(text))

    def test_the_statute_an_audit_committee_cites_is_not_a_setup_change(self):
        self.assertEqual([], self.labels("The Audit Committee was established by the Board in accordance with "
                                         "Section 3(a)(58)(A) of the Exchange Act, to monitor and oversee our "
                                         "financial reporting."))


class ACardOrTableStatesWhoAndWhat(unittest.TestCase):

    def test_a_signature_under_its_lead_in(self):
        texts = ["Submitted by the Audit Committee of the Board of Directors as of February 16, 2026.",
                 "Hal Stanley Jones", "(Chair)", "Christopher CaposselaKevin P. ChiltonMichelle Goldberg", "50"]
        self.assertEqual({0, 1, 2, 3}, set(_selected(texts)))

    def test_member_and_chair_tails_on_signatures(self):
        texts = ["Compensation Committee", "Thurman John Rodgers, Chair", "Richard Mora, Member",
                 "*The material in this report is not soliciting material."]
        chosen = _selected(texts)
        self.assertEqual({0, 1, 2}, set(chosen))
        self.assertIn("COMMITTEE_CHAIR_NAME", chosen[1])

    def test_a_blank_block_inside_a_roster_and_a_heading_with_information_in_it(self):
        texts = ["Technology and Information Security Oversight Committee", "Current Members",
                 "Key Responsibilities", "•", "Review privacy and information security policies.",
                 "Margaret M.", "McCarthy", "CHAIR", "\u200b", "Lauren R.", "Hobart", "Sean C.", "Tresvant",
                 "The Board also maintains an Executive Committee."]
        chosen = _selected(texts)
        self.assertTrue({0, 1, 5, 6, 7, 9, 10, 11, 12} <= set(chosen))

    def test_a_designation_on_a_card_and_not_a_table_header(self):
        card = ["ROBERT L. FORNARO", "Age: 73 | Director", "Expertise Relevant to the Business"]
        self.assertEqual({0: ["DIRECTOR_NAME"], 1: ["DIRECTOR_DESIGNATION"]}, _selected(card))
        header = ["Name", "Age", "Director Since", "Independent", "Director", "Shari E. Redstone", "70"]
        self.assertEqual({}, _selected(header))

    def test_a_title_line_at_this_registrant_and_not_elsewhere(self):
        self.assertEqual({0: ["BOARD_LEADERSHIP_TITLE"]},
                         _selected(["Chairman and Chief Executive Officer, Example Corporation (2024 to Present)"]))
        self.assertEqual({0: ["BOARD_LEADERSHIP_TITLE"]},
                         _selected(["President, CEO, and Vice Chairman of the Board of Example Corporation"]))
        for text in ("Member of the Board of PhRMA and Chair of the Board of The Example Foundation",
                     "Former Chairman and Chief Executive Officer, Example Corporation",
                     "Chairman and Chief Executive Officer, Example Corporation, until 2020",
                     "Chairman and Chief Executive Officer, Acme Industries"):
            with self.subTest(text=text):
                self.assertEqual({}, _selected([text]))

    def test_a_table_of_directors_by_class_and_not_a_card_under_a_heading(self):
        table = ["Continuing Class III Directors (Until 2027 Annual Meeting of Stockholders)",
                 "Badrinarayanan Kothandaraman", "President and CEO, Example Corporation", "54", "2017",
                 "Joseph Malchow", "Founding Partner, a venture firm", "IND", "40", "2020",
                 "Continuing Class I Directors (Until 2028 Annual Meeting of Stockholders)"]
        chosen = _selected(table, emphasized={0, 1, 5, 7, 10})
        # The names are the board's directors; the heading over them states
        # their class and term and is not taken
        # (c02-composition-facts/adjudicate.py, DIRECTOR_GROUP_HEADING).
        self.assertEqual({1, 5}, {i for i, labels in chosen.items() if labels[0].startswith("DIRECTOR_GROUP")})
        self.assertNotIn(0, chosen)
        self.assertNotIn(10, chosen)
        cards = ["Nominees for Election as Directors:", "Emilie Arel", "President, Mitchell & Ness", "Independent",
                 "Age: 44"]
        under_cards = _selected(cards, emphasized={1, 3})
        self.assertNotIn(0, under_cards)
        # One name under a heading begins a card, not a table.
        self.assertNotIn("DIRECTOR_GROUP_MEMBER", under_cards.get(1, []))

    def test_a_footnoted_departure_is_taken_with_the_names_that_carry_its_mark(self):
        texts = ["Director", "Eduardo F. Conrado(2)", "58,527", "Elaine Mendoza(2)", "70,000", "Gary Kelly", "(1)",
                 "Awards consist of shares of common stock.", "(2)", "Retired from the Board effective May 14, 2025."]
        self.assertEqual({1, 3, 9}, set(_selected(texts)))


class TheProposalKeepsTheFrozenShape(unittest.TestCase):

    def test_candidates_are_whole_blocks_in_document_order(self):
        document = _document(["Compensation Committee", "Members: Mason Morfit (Chair), Neelie Kroes",
                              "The Audit Committee is composed of two directors: Ms. Byrne and Mr. Hamill."])
        proposal = board_composition_facts(document=document, period_start=PERIOD_START)
        self.assertEqual([0, 1, 2], [c["block_index"] for c in proposal["candidates"]])
        self.assertTrue(all(c["section_id"] == "GOVERNANCE_DISCLOSURES" for c in proposal["candidates"]))
        self.assertEqual(document["blocks"][2]["text"], proposal["candidates"][2]["text"])
        self.assertEqual("BOARD_COMPOSITION_FACTS_V1", proposal["selection_policy"])
        self.assertFalse(proposal["numeric_board_counts_asserted"])

    def test_the_identity_moves_with_the_rules_not_with_the_comments(self):
        document = _document(["Compensation Committee", "Members: Mason Morfit (Chair), Neelie Kroes"])
        first = board_composition_facts(document=document, period_start=PERIOD_START)
        second = board_composition_facts(document=document, period_start=PERIOD_START)
        self.assertEqual(first["proposal_id"], second["proposal_id"])
        self.assertTrue(first["policy_hash"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
