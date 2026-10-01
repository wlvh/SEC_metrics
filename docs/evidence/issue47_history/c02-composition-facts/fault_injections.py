"""Break one C02 rule at a time and require the case written for it to fail.

Each injection edits ``scripts/vnext/historical_board_composition_v2.py`` in
memory, compiles it, and runs the synthetic suite in a child process whose
``vnext`` package searches a temporary directory holding only the edited
module before the checkout's own package, so every other module and data file
is the checkout's and the checkout is never written. An edit that does not
apply exactly once, or does not compile, is reported as such and not counted.

The control run - the unedited module through the same path - must pass and
must run the whole suite. A child that loads nothing reports no failures, and
without that check every injection would read as "missed" for a reason that
has nothing to do with the rules (the first version of this runner copied the
whole package, which then could not find its data files).

Usage:
    python3 docs/evidence/issue47_history/c02-composition-facts/fault_injections.py
"""
from __future__ import annotations

import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
MODULE = REPO / "scripts/vnext/historical_board_composition_v2.py"
HERE = Path(__file__).resolve().parent
SUITE = "tests.vnext.test_historical_board_composition"

INJECTIONS = [
    ("SKIP_MATRIX_MARKS_AS_LIST_BULLETS", "        if _ONE_BULLET.match(text) or not text:\n            j += 1",
     "        if _BULLETS_ONLY.match(text):\n            j += 1", "test_a_matrix_column_of_directors_is_not_a_roster"),
    ("READ_ANOTHER_BODY_AS_THIS_BOARD", "        if _other_organization(sentence, own_words):\n            continue\n",
     "", "test_another_organisations_board_is_not_this_one"),
    ("ANY_REQUIREMENT_WORD_VETOES",
     "        if policy and (determination is None or policy.start() < determination.start()):",
     "        if policy:", "test_a_determination_qualified_by_a_rule_is_still_a_determination"),
    ("NO_REQUIREMENT_VETO",
     "        if policy and (determination is None or policy.start() < determination.start()):",
     "        if False:", "test_rules_hypotheticals_and_process_are_not_facts"),
    ("PASS_OVER_A_PARAGRAPH_TO_A_NAME", "        if preceding or not _card_field(blocks[k]):\n            break",
     "        if preceding:\n            break", "test_a_card_whose_director_is_not_beside_it_is_left_out"),
    ("GIVE_A_CARD_BETWEEN_TWO_NAMES", "    if following and preceding:\n        return None\n", "",
     "test_a_card_between_two_names_is_not_given_either"),
    ("DROP_A_WRAPPED_CHANGE_LINE", "            if _CHANGE_LINE.match(line) or (lines and line[:1].islower()):",
     "            if _CHANGE_LINE.match(line):", "test_dated_changes_including_a_wrapped_line"),
    ("READ_ONLY_THE_NAMES_BESIDE_THE_LABEL", "                if count == 0:\n", "                if False:\n",
     "test_a_member_column_laid_out_after_the_duties"),
    ("ACCEPT_A_LETTER_IN_THE_FIRST_PERSON", "        if _FIRST_PERSON.search(sentence):\n            continue",
     "        if False:\n            continue", "test_pay_and_letters_are_not_facts"),
    ("LET_A_TITLE_S_PERIOD_END_THE_SENTENCE",
     '    t = _ABBREVIATION.sub(lambda m: m.group(1).replace(".", ""), _GLUED_MARK.sub(r"\\1 ", clean(text)))', '    t = _GLUED_MARK.sub(r"\\1 ", clean(text))',
     "test_committee_board_and_leadership_facts"),
    ("CONTINUE_A_LEAD_IN_TO_DUTIES", "        if last and _introduces_people(last) and statement_labels(",
     "        if last and statement_labels(", "test_a_composition_sentence_that_introduces_duties"),
    ("IGNORE_THE_MEMBER_TAIL", "    t = _MEMBER_TAIL.sub(\"\", t)\n", "",
     "test_member_and_chair_tails_on_signatures"),
    ("STOP_AT_A_BLANK_BLOCK", "        if _ONE_BULLET.match(text) or not text:\n            j += 1",
     "        if _ONE_BULLET.match(text):\n            j += 1",
     "test_a_blank_block_inside_a_roster_and_a_heading_with_information_in_it"),
    ("INFORMATION_ENDS_A_COMMITTEE_NAME", "refreshment memberships membership functions",
     "refreshment memberships membership information functions",
     "test_a_blank_block_inside_a_roster_and_a_heading_with_information_in_it"),
    ("NO_SIGNATURE_LEAD_IN", "            lead = _SIGNATURE_LEAD.match(clean(block[\"text\"]))",
     "            lead = None", "test_a_signature_under_its_lead_in"),
    ("CARD_ITEMS_MUST_SAY_COMMITTEE", "    return committee_name(bare) or vocabulary.get(bare.casefold())",
     "    return committee_name(bare)", "test_a_card_uses_the_filing_s_own_short_forms"),
    ("ANY_CODE_IS_A_COMMITTEE", "    return committee_name(bare) or vocabulary.get(bare.casefold())",
     "    return committee_name(bare) or bare", "test_a_card_uses_the_filing_s_own_short_forms"),
    ("NONE_ON_A_NOMINEE_S_CARD",
     "        if negative and any(_NOT_YET_DIRECTOR.match(field) for field in _card_fields(blocks, i, name[0])):",
     "        if False:", "test_none_is_a_fact_for_a_director_and_not_for_a_nominee"),
    ("A_DESIGNATION_NEEDS_NO_CARD",
     "        if not (_AGE_PREFIX.match(text) or any(_CARD_EVIDENCE.match(field) for field in near)):",
     "        if False:", "test_a_designation_on_a_card_and_not_a_table_header"),
    ("A_TITLE_LINE_AT_ANY_BODY", "            if runs and all(_is_registrant(run, cores) for run in runs):",
     "            if runs:", "test_a_title_line_at_this_registrant_and_not_elsewhere"),
    ("A_FORMER_TITLE_COUNTS",
     "            if not _TITLE_LINE_CHAIR.search(clause) or _TITLE_LINE_PAST.search(clause):",
     "            if not _TITLE_LINE_CHAIR.search(clause):",
     "test_a_title_line_at_this_registrant_and_not_elsewhere"),
    ("ONE_NAME_MAKES_A_TABLE", "        if len(names) >= 2:\n            taken.extend((k, \"DIRECTOR_GROUP_MEMBER\")",
     "        if names:\n            taken.extend((k, \"DIRECTOR_GROUP_MEMBER\")",
     "test_a_table_of_directors_by_class_and_not_a_card_under_a_heading"),
    ("A_FOOTNOTE_WITHOUT_ITS_NAMES", "            taken.extend((k, \"FOOTNOTED_DIRECTOR\") for k in names)\n", "",
     "test_a_footnoted_departure_is_taken_with_the_names_that_carry_its_mark"),
    ("A_VICE_CHAIR_IS_THE_BOARD_S", "_SOLE_CHAIR = r\"(?<!vice )(?<!vice-)chair(?:man|person|woman)?\"",
     "_SOLE_CHAIR = _CHAIR_WORD",
     "test_another_body_s_chair_and_an_officer_s_vice_chair_are_not_this_board_s"),
    ("ANY_POSSESSIVE_OWNS_THE_CHAIR",
     "                or (owned and owned.group(\"owner\").casefold() in registrant)):\n            labels.add(\"BOARD_LEADERSHIP_STATEMENT\")",
     "                or owned):\n            labels.add(\"BOARD_LEADERSHIP_STATEMENT\")",
     "test_another_body_s_chair_and_an_officer_s_vice_chair_are_not_this_board_s"),
    ("APPOINT_ANYTHING_TO_THE_BOARD",
     "    re.compile(r\"\\b(?:appoint|elect|add)(?:ed|ing|s)?\\s+\" + _NAME_LIST + r\"\\s*,?\\s+to (?:the|our) board\\b\", re.I),",
     "    re.compile(r\"\\b(?:appoint|elect|add)(?:ed|ing|s)?\\s+[^.;]{0,160}?\\bto (?:the|our) board\\b\", re.I),",
     "test_a_process_or_an_adjective_is_not_a_change"),
    ("ANY_CAPITALISED_SPAN_IS_A_PERSON",
     "        if (len(tokens) >= 2 and person_name(span) and not tokens[0].isupper()\n"
     "                and re.fullmatch(\"[\" + _UPPER + \"][\" + _LOWER + \"]{2,}(?:[-'’][\" + _UPPER + \"]?[\" + _LOWER + \"]+)*\",\n"
     "                                 tokens[-1])):",
     "        if person_name(match.group(0)):", "test_a_person_is_named_by_an_honorific_or_a_full_name"),
    ("AN_UNDATED_SETUP_CHANGE",
     "r\"|constituted|reorganized)\\b[^.;]{0,60}?\\b(?:19|20)\\d{2}\\b\", re.I),",
     "r\"|constituted|reorganized)\\b\", re.I),",
     "test_the_statute_an_audit_committee_cites_is_not_a_setup_change"),
    ("PAY_HIDES_WHO_CHAIRED", "        if _SERVICE_AS_CHAIR.search(sentence) and _mentions_person(sentence):",
     "        if False:", "test_who_chaired_is_a_fact_even_where_a_fee_is_explained"),
    ("NO_COMMITTEE_ACRONYMS", "    if not acronyms:\n        return False", "    if True:\n        return False",
     "test_size_setup_and_determinations"),
    # Repairs from the older-year readings (c02-selector-repairs/README.md).
    ("A_LOWER_CASE_WORD_NAMES_A_COMMITTEE", "(?:(?-i:[A-Z])", "(?:[A-Z]",
     "test_a_criterion_for_choosing_a_chair_seats_no_one"),
    ("THE_SQUARE_BULLET_IS_NOT_A_BULLET", "◾·", "·", "test_a_roster_marked_with_each_glyph_filings_print"),
    ("THE_MIDDLE_DOT_IS_NOT_A_BULLET", "◾·", "◾", "test_a_roster_marked_with_each_glyph_filings_print"),
    ("A_SERIAL_COMMA_ENDS_A_LIST", 'r",\\s*(?:and\\s+)?|', 'r",\\s*|', "test_a_members_line_written_as_a_sentence"),
    ("A_FINAL_PERIOD_ENDS_A_LIST", "_LIST_SEPARATOR.split(_LIST_END.sub(\"\", t))", "_LIST_SEPARATOR.split(t)",
     "test_a_members_line_written_as_a_sentence"),
    ('AN_EMPHASISED_HEADING_IS_A_CARD_ITEM', '            if blocks[j]["linked"] or blocks[j].get("emphasized") or not _card_item(text, vocabulary):', '            if blocks[j]["linked"] or not _card_item(text, vocabulary):',
     "test_unlabelled_committees_on_the_lines_after_the_tenure"),
    ('UNLABELLED_ITEMS_NEED_NO_DIRECTOR', '        if name is None:\n            continue\n        taken.extend((k, "DIRECTOR_COMMITTEE_ITEM") for k in items)', '        taken.extend((k, "DIRECTOR_COMMITTEE_ITEM") for k in items)\n        if name is None:\n            continue',
     "test_unlabelled_committees_on_the_lines_after_the_tenure"),
    ('UNLABELLED_CARD_ITEMS_UNREAD', '*_unlabelled_card_items(blocks, vocabulary, registrant), ', '',
     "test_unlabelled_committees_on_the_lines_after_the_tenure"),
    ('NICKNAMES_STAY_IN_THE_NAME', '    t = _NICKNAME.sub("", _BULLET.sub("", clean(text)))', '    t = _BULLET.sub("", clean(text))',
     "test_a_quoted_nickname_between_the_names"),
    ('ANY_QUOTED_WORD_IS_A_NICKNAME', '[”\\"](?=\\\\s+\\\\S)', '[”\\"]',
     "test_a_quoted_nickname_between_the_names"),
    ('MANAGEMENT_SEATS_A_BOARD_COMMITTEE', '\n                and not _MANAGEMENT_MEMBERS.search(sentence)):', '):',
     "test_a_committee_of_management_is_not_the_board_s"),
    ('ANY_WORDS_OPEN_THE_MEMBER_LIST', "|(?-i:[A-Z])[\\w&’'\\-]*\\s+){0,6}", '|\\w+\\s+){0,6}',
     "test_a_committee_of_management_is_not_the_board_s"),
    # Repair 7: whether the chair and the chief executive are one person.
    ('THE_CHAIR_CEO_STRUCTURE_STATES_NOTHING',
     '        if (_CHAIR_CEO_STRUCTURE.search(sentence) and not _BOTH_STRUCTURES.search(sentence)\n'
     '                and not _STRUCTURE_POLICY.search(sentence)):\n'
     '            labels.add("BOARD_LEADERSHIP_STATEMENT")\n', '',
     "test_whether_the_chair_and_the_chief_executive_are_one_person"),
    ('NAMING_BOTH_CHOICES_STATES_A_STRUCTURE', ' and not _BOTH_STRUCTURES.search(sentence)\n', '\n',
     "test_a_choice_a_policy_or_a_proposal_states_no_structure"),
    ('A_POLICY_OR_A_PROPOSAL_STATES_A_STRUCTURE', '\n                and not _STRUCTURE_POLICY.search(sentence)):', '):',
     "test_a_choice_a_policy_or_a_proposal_states_no_structure"),
    # Repair 8: a classified board's slate is not its size.
    ('A_CLASSIFIED_BOARD_STILL_COUNTS_ITS_SLATE', '*(() if classified else _SLATE_SIZE)', '*_SLATE_SIZE',
     "test_on_a_classified_board_the_slate_is_not_the_board_s_size"),
    ('NO_FILING_IS_CLASSIFIED',
     '    classified = any(_CLASSIFIED.search(block["text"]) for block in blocks if not block["linked"])',
     '    classified = False', "test_the_filing_says_whether_its_board_is_classified"),
    ('HAS_NOMINATED_COUNTS_AS_THE_BOARD_S_SIZE', '(?:(?!\\bnominat|\\belect|\\bpropos)[^.;]){0,30}?', '[^.;]{0,30}?',
     "test_on_a_classified_board_the_slate_is_not_the_board_s_size"),    # Repair 9: a director-group heading is not taken.
    ('THE_GROUP_HEADING_IS_TAKEN_AGAIN', '            taken.extend((k, "DIRECTOR_GROUP_MEMBER") for k in names)',
     '            taken.append((i, "DIRECTOR_GROUP_HEADING"))\n'
     '            taken.extend((k, "DIRECTOR_GROUP_MEMBER") for k in names)',
     "test_a_table_of_directors_by_class_and_not_a_card_under_a_heading"),
    # Repair 10: a slate of sitting directors.
    ('A_SITTING_SLATE_STATES_NOTHING', ' or _SITTING_SLATE.search(sentence)', '',
     "test_a_slate_of_sitting_directors_says_who_the_members_are"),
    ('ANOTHER_BOARD_SEATS_THE_SLATE', '(?:\\s+of\\s+directors)?(?!\\s+of\\b)|directors?\\b(?!\\s+of\\b))',
     '|directors?\\b)', "test_a_slate_of_sitting_directors_says_who_the_members_are"),
    # Repair 11: a task force of named directors.
    ('A_TASK_FORCE_STATES_NOTHING', '        if _TASK_FORCE_MEMBERS.search(sentence) and _mentions_person(sentence):\n'
     '            labels.add("COMMITTEE_COMPOSITION_STATEMENT")\n', '',
     "test_a_task_force_of_named_directors_is_a_body_of_the_board"),
    ('A_TASK_FORCE_TITLE_IS_NOT_TAKEN', ', *_task_force_titles(blocks)):', '):',
     "test_a_task_force_of_named_directors_is_a_body_of_the_board"),
    ('ANY_TASK_FORCE_TITLE_HEADS_THE_MEMBERS', ' and title.casefold() in \\\n'
     '                    clean(block["text"]).casefold():', ':', "test_a_task_force_of_named_directors_is_a_body_of_the_board"),
    # Repair 12: the board's size on a past date, printed with attendance.
    ('A_PAST_COUNT_IS_SET_ASIDE_WITH_ATTENDANCE', ' or _THEN_CURRENT_MEMBERS.search(sentence)', '',
     "test_the_board_s_size_on_a_past_date_wherever_it_is_printed"),
    ('A_DATED_JOIN_COUNTS_IN_ANY_YEAR', 'undated = _DATED_JOIN.sub(" ", sentence) if joins else sentence',
     'undated = sentence', "test_a_join_dated_before_the_year_is_tenure"),
    ('AN_IN_YEAR_JOIN_STATES_NOTHING',
     'if any(not _joined_before(date, period_start) for date in joins) and _mentions_person(sentence):',
     'if False:', "test_a_join_dated_in_the_year_is_a_change"),
    ('A_JOIN_IN_A_PAY_SENTENCE_IS_SET_ASIDE',
     'if any(not _joined_before(date, period_start) for date in joins) and _mentions_person(sentence):',
     'if any(not _joined_before(date, period_start) for date in joins) and _mentions_person(sentence) '
     'and not _EXCLUDED_TOPIC.search(sentence):', "test_a_join_dated_in_the_year_is_a_change"),
    ('A_PRINTED_DAY_IS_IGNORED', '    return dt.date(year, number, int(day.group(1))) < start',
     '    return (year, number) < (start.year, start.month)', "test_a_join_is_dated_as_precisely_as_it_is_printed"),
    ('A_MONTH_ALONE_IS_PLACED_AT_ITS_START', '        return (year, number) < (start.year, start.month)',
     '        return (year, number) <= (start.year, start.month)',
     "test_a_join_is_dated_as_precisely_as_it_is_printed"),
    ('A_NOUN_FORM_JOIN_IS_NOT_DATED',
     '    r"|(?:appointment|election) to (?:the|our) board(?: of directors)?\\s+(?:on|in|effective))\\s+(?:the\\s+)?"',
     '    r")\\s+(?:the\\s+)?"', "test_a_join_written_as_a_noun_is_dated_too"),
    ('TAKING_OVER_A_COMMITTEE_CHAIR_IS_NOT_READ',
     '               r"chair(?:man|person|woman)?\\s+of\\s+(?:the|our|its)\\b[^.;]{0,60}\\bcommittee\\b", re.I),\n)',
     '               r"chair(?:man|person|woman)?\\s+of\\s+(?:the|our|its)\\b[^.;]{0,60}\\bcommittee\\bNEVER", re.I),\n)',
     "test_taking_over_a_chair_or_the_lead_role"),
    ('TAKING_OVER_THE_LEAD_ROLE_IS_NOT_READ',
     '               + r"|presiding (?:independent )?director)\\b", re.I),\n)',
     '               + r"|presiding (?:independent )?director)\\bNEVER", re.I),\n)',
     "test_taking_over_a_chair_or_the_lead_role"),
    ('THE_JOIN_REACH_IS_SIXTY', 'r"\\b(?:has served as (?:[^.;]{0,80}?\\b)?', 'r"\\b(?:has served as (?:[^.;]{0,60}?\\b)?',
     "test_a_long_title_before_the_join"),
    ('ANY_TARGET_YEAR_IS_ACCEPTED', '        raise ValueError("C02_COMPOSITION_PERIOD_START_INVALID:" + repr(period_start)) from None',
     '        start = dt.date(1900, 1, 1)', "test_the_target_year_is_a_date_and_the_proposal_names_it"),
    ('A_TERM_ENDING_IS_NOT_READ', 'r"\\s+(?:will\\s+)?(?:end(?:ed|s)?|expire[sd]?)\\b[^.;]{0,80}?\\b(?:annual(?:\\s+(?:general"', 'r"\\s+(?:will\\s+)?(?:end(?:ed|s)?|expire[sd]?)\\bNEVER[^.;]{0,80}?\\b(?:annual(?:\\s+(?:general"',
     'test_a_named_director_s_term_ending_at_a_meeting'),
    ('A_TERM_OF_ANYTHING_IS_A_PERSONS', '\\bterms?(?:\\s+of\\s+office)?\\s+of\\s+(?:mr|ms|mrs|dr|messrs|mses)\\b[^.;]{0,120}?', '\\bterms?(?:\\s+of\\s+office)?\\s+of\\s+[^.;]{0,120}?',
     'test_a_named_director_s_term_ending_at_a_meeting'),
    ('A_GLUED_MARK_HIDES_THE_PERSON', '_GLUED_MARK.sub(r"\\1 ", clean(text))', 'clean(text)',
     'test_a_footnote_number_printed_against_the_honorific'),
    ('AN_AMOUNT_IS_A_MARK', '(?<![\\w$.,])(\\d{1,2})', '(?<![\\w])(\\d{1,2})',
     'test_a_footnote_number_printed_against_the_honorific'),
    ('A_LINKED_STATEMENT_IS_NAVIGATION', '        if not re.search(r"[A-Za-z]", text) or re.sub(r"\\W", "", text.casefold()) in registrant:\n            continue\n        labels = statement_labels(', '        if block["linked"] or not re.search(r"[A-Za-z]", text) or re.sub(r"\\W", "", text.casefold()) in registrant:\n            continue\n        labels = statement_labels(',
     'test_a_statement_carrying_a_cross_reference_is_read'),
    ('SPACERS_COUNT_FOR_A_COMMITTEE_LABEL', '        name = _card_name(blocks, i, j, registrant, passable=lambda block: False, spacers_free=True)', '        name = _card_name(blocks, i, j, registrant, passable=lambda block: False)',
     'test_spacer_blocks_do_not_carry_a_committee_label_out_of_reach'),
    ('SPACERS_ARE_FREE_FOR_A_DESIGNATION', '        name = _card_name(blocks, i, i + 1, registrant, passable=passable)', '        name = _card_name(blocks, i, i + 1, registrant, passable=passable, spacers_free=True)',
     'test_a_designation_s_reach_still_counts_every_block'),
    ('A_CHARTER_SET_IS_NOT_READ', 'if any(p.search(sentence) for p in (*_STANDING, *_COMMITTEE_SETUP)) or _committee_set(sentence):', 'if any(p.search(sentence) for p in (*_STANDING, *_COMMITTEE_SETUP)):',
     'test_the_committees_named_together_on_their_charters'),
    ('COMMITTEE_WORDS_COUNT_AS_COMMITTEES', 'len({m.group(1) for m in _LISTED_COMMITTEE.finditer(listed.group("list"))}) >= 3', 'len(re.findall(r"(?i)\\bcommittees?\\b", listed.group("list"))) >= 3',
     'test_the_committees_named_together_on_their_charters'),
    ('A_RENAME_COUNTS_AS_A_SET', '    return (bool(listed) and not _RENAME.search(sentence)\n', '    return (bool(listed)\n',
     'test_the_committees_named_together_on_their_charters'),
    ('A_RENAME_IS_NOT_READ', '    re.compile(r"\\bcommittee\\s+changed\\s+its\\s+name\\s+to\\s+(?:the\\s+)?[^.;]{0,80}?\\bcommittee\\b", re.I),\n', '    re.compile(r"(?!x)x", re.I),\n',
     'test_a_committee_that_changed_its_name'),
    ('A_RENAMED_PLAN_IS_A_COMMITTEE', '    re.compile(r"\\bcommittee\\s+changed\\s+its\\s+name\\s+to\\s+(?:the\\s+)?[^.;]{0,80}?\\bcommittee\\b", re.I),\n', '    re.compile(r"\\bchanged\\s+its\\s+name\\b|\\brenamed\\b", re.I),\n',
     'test_a_committee_that_changed_its_name'),
    ('A_NAMED_FAMILY_MEMBER_IS_A_STANDARD', '        family = None if _mentions_person(sentence) else _FAMILY.search(unqualified)\n', '        family = _FAMILY.search(unqualified)\n',
     'test_a_named_family_member_is_not_an_independence_standard'),
    ('A_FAMILY_MEMBER_IS_NEVER_A_STANDARD', '        family = None if _mentions_person(sentence) else _FAMILY.search(unqualified)\n', '        family = None\n',
     'test_a_named_family_member_is_not_an_independence_standard'),
]


# Files the module reads relative to itself. It reads the lead-director phrase
# from the catalog (tools/check_vnext_semantics.py keeps it out of code), so
# the edited copy is laid out as scripts/vnext/ under a temporary root holding
# that file. Before that layout the control run failed - the module could not
# import - and the runner stopped there rather than reporting every injection
# as missed.
READ_BESIDE = ("catalog/r6/C02_board_composition_terms_v1.json",)


def run_one(text):
    """Run the suite against ``text`` as the module; return (failed tests, tests run)."""
    with tempfile.TemporaryDirectory() as tmp:
        package = Path(tmp) / "scripts/vnext"
        package.mkdir(parents=True)
        for relative in READ_BESIDE:
            (Path(tmp) / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / relative, Path(tmp) / relative)
        target = package / MODULE.name
        target.write_text(text, encoding="utf-8")
        py_compile.compile(str(target), doraise=True)
        code = ("import sys; sys.path.insert(0, %r); import vnext; vnext.__path__.insert(0, %r); "
                "sys.argv=['x', %r]; import unittest; unittest.main(module=None)"
                ) % (str(REPO / "scripts"), str(package), SUITE)
        # A fresh bytecode directory, as every injection script here uses: the
        # child neither reads nor writes the checkout's __pycache__.
        env = {**os.environ, "PYTHONPYCACHEPREFIX": str(Path(tmp) / "pycache")}
        run = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, timeout=600,
                             env=env)
        failed = sorted({line.split(" ")[1] for line in run.stderr.splitlines()
                         if line.startswith(("FAIL: ", "ERROR: "))})
        ran = [int(line.split()[1]) for line in run.stderr.splitlines() if line.startswith("Ran ")]
        return failed, (ran[-1] if ran else 0), run.returncode


def main():
    original = MODULE.read_text(encoding="utf-8")
    control, control_ran, control_code = run_one(original)
    if control or control_code != 0 or control_ran == 0:
        raise SystemExit("C02_INJECTION_CONTROL_DID_NOT_RUN_CLEAN: failed=%s ran=%s rc=%s"
                         % (control, control_ran, control_code))
    results = []
    for name, old, new, expected in INJECTIONS:
        if original.count(old) != 1:
            results.append({"injection": name, "result": "EDIT_DOES_NOT_APPLY", "count": original.count(old)})
            continue
        try:
            failed, ran, _code = run_one(original.replace(old, new))
        except py_compile.PyCompileError as error:
            results.append({"injection": name, "result": "EDIT_DOES_NOT_COMPILE", "error": str(error)[:200]})
            continue
        if ran != control_ran:
            # The edited module broke the suite's loading: whatever failed, the
            # named case was not what caught it.
            results.append({"injection": name, "expected": expected, "result": "SUITE_DID_NOT_RUN", "ran": ran})
            continue
        results.append({"injection": name, "expected": expected,
                        "result": "CAUGHT" if expected in failed else ("CAUGHT_ELSEWHERE" if failed else "MISSED"),
                        "failed": failed})
    out = {"record_type": "C02_COMPOSITION_FAULT_INJECTIONS", "suite": SUITE, "control_failures": control,
           "control_tests_run": control_ran,
           "caught": sum(r["result"] == "CAUGHT" for r in results), "total": len(results), "results": results}
    (HERE / "fault-injections.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("control_failures", "control_tests_run", "caught", "total")}))
    for row in results:
        if row["result"] != "CAUGHT":
            print(json.dumps(row))
    assert MODULE.read_text(encoding="utf-8") == original
    return 0 if not control and out["caught"] == out["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
