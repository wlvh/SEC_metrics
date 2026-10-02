"""Undo each condition of version 2 of the D02 category-mention rule; the case written for it must fail.

Usage: python3 injections.py <out.json> [NAME ...]

Same harness as ../../c03-first-ecd-release/injections.py: each injection edits
the module in place (exactly one match, must compile), runs the module holding
the cases with a fresh bytecode prefix, and restores the bytes. The control
run must pass first. It edits the tree it lives in, so run it from a clone or
worktree nothing else reads. Zero calls.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "ecd_injections", HERE.parents[1] / "c03-first-ecd-release/injections.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)

RULE = "scripts/vnext/d02_item_8_category_mentions.py"
CASES = "tests.vnext.test_d02_item_8_category_mentions"
harness.SOURCE, harness.NOTE = RULE, RULE
harness.MODULES, harness.CASES = (CASES,), CASES
TAIL = ('    if (_MENTION["clause_word"].search(tail) or _MENTION["clause_starter"].search(tail)\n'
        '            or _MENTION["party_preposition"].search(tail)):\n')
EXPOSURE = ('_EXPOSURE = tuple((item["name"], re.compile(item["pattern"], re.I))\n'
            '                  for item in _TERMS["exposure"])\n')


def _drop(name):
    return EXPOSURE + "_EXPOSURE = tuple(x for x in _EXPOSURE if x[0] != %r)\n" % name


harness.INJECTIONS = {
    "VERSION_ONE_S_EVIDENCE_ALONE": (
        RULE, "            why = _structure(text, match.start(), match.end())\n",
        '            why = "LIST_MEMBER"\n',
        "test_the_two_reported_sentences_stay_by_structure_alone"),
    "A_CLAUSE_IN_THE_KEYWORD_S_PHRASE_IS_ALLOWED": (
        RULE, TAIL, '    if _MENTION["party_preposition"].search(tail):\n',
        "test_the_keyword_s_phrase_is_no_clause"),
    "A_PARTY_IN_THE_KEYWORD_S_PHRASE_IS_ALLOWED": (
        RULE, TAIL,
        '    if _MENTION["clause_word"].search(tail) or _MENTION["clause_starter"].search(tail):\n',
        "test_the_keyword_s_phrase_names_no_party"),
    "THE_REGISTRANT_IN_THE_KEYWORD_S_PHRASE_IS_ALLOWED": (
        RULE, '    if _MENTION["registrant_reference"].search(tail):\n'
              '        return "KEYWORD_PHRASE_NAMES_THE_REGISTRANT_S_OWN_MATTER"\n', "",
        "test_the_keyword_s_phrase_names_not_the_registrant"),
    "THE_FIRST_ITEM_IS_A_LIST_MEMBER": (
        RULE, '    if k == 0:\n        return "GOVERNED_BY_ITS_SENTENCE"\n', "",
        "test_the_first_item_of_a_sentence_is_governed_by_it"),
    "A_CLAUSE_BEFORE_THE_KEYWORD_IS_ALLOWED": (
        RULE, '    if (_MENTION["clause_word"].search(head) or _MENTION["clause_starter"].search(head)\n'
              '            or _MENTION["first_person_subject"].search(head)):\n'
              '        return "KEYWORD_PHRASE_IS_A_CLAUSE"\n', "",
        "test_a_clause_before_the_keyword_in_its_item"),
    "THE_REGISTRANT_HEADING_THE_PHRASE_IS_ALLOWED": (
        RULE, '    if _governed_by_the_registrant(head):\n'
              '        return "GOVERNED_BY_THE_REGISTRANT_AS_SUBJECT"\n', "",
        "test_a_series_governed_by_the_registrant_as_subject"),
    "THE_REGISTRANT_GOVERNING_THE_SERIES_IS_ALLOWED": (
        RULE, '    if _governed_by_the_registrant(governing):\n'
              '        return "GOVERNED_BY_THE_REGISTRANT_AS_SUBJECT"\n', "",
        "test_a_series_governed_by_the_registrant_as_subject"),
    "A_LIST_ITEM_MAY_BE_THE_REGISTRANT_ACTING": (
        RULE, '                and not _MENTION["first_person_subject"].search(text)\n'
              '                and not _governed_by_the_registrant(text))\n',
        '                and not _MENTION["first_person_subject"].search(text))\n',
        "test_a_series_governed_by_the_registrant_as_subject"),
    "A_PREDICATE_AFTER_THE_SERIES_IS_ALLOWED": (
        RULE, '            if _OPENS_WITH_CLAUSE_WORD.search(following):\n'
              '                return "SERIES_IS_A_SUBJECT"\n', "",
        "test_a_series_that_is_the_subject_of_a_predicate"),
    "ANY_SEPARATOR_IS_A_SERIES": (
        RULE, '    return "LIST_MEMBER" if coordinated else "NO_COORDINATED_SERIES"\n',
        '    return "LIST_MEMBER"\n',
        "test_a_separator_without_a_coordinated_series"),
    "A_COORDINATOR_INTO_THE_GOVERNING_WORDS_COUNTS_WITH_WORDS": (
        RULE, '            if coordinates and index == k and not re.search(r"\\w", tail):\n',
        "            if coordinates and index == k:\n",
        "test_a_coordinator_into_the_governing_words_counts_for_the_keyword_alone"),
    "A_FULL_STOP_IS_READ_AS_WORDS_AFTER_THE_KEYWORD": (
        RULE, '            if coordinates and index == k and not re.search(r"\\w", tail):\n',
        "            if coordinates and index == k and not tail.strip():\n",
        "test_a_coordinator_into_the_governing_words_counts_for_the_keyword_alone"),
    "AN_OXFORD_COMMA_IS_TWO_SEPARATORS": (
        RULE, EXPOSURE,
        EXPOSURE + '_MENTION["series_separator"] = re.compile('
                   'r"(?:\\s*[,;]\\s*|\\s+(?:and/or|and|or|as\\s+well\\s+as)\\s+)+", re.I)\n',
        "test_an_oxford_comma_is_one_separator"),
    "EXPOSED_TO_OR_NAMED_IN_IS_NOT_READ": (
        RULE, EXPOSURE, _drop("REGISTRANT_EXPOSED_TO_OR_NAMED_IN_A_LEGAL_MATTER"),
        "test_each_relation_keeps_the_paragraph"),
    "AGAINST_THE_REGISTRANT_IS_NOT_READ": (
        RULE, EXPOSURE, _drop("A_MATTER_AGAINST_THE_REGISTRANT"),
        "test_each_relation_keeps_the_paragraph"),
    "BROUGHT_BY_OR_AGAINST_IS_NOT_READ": (
        RULE, EXPOSURE, _drop("A_MATTER_BROUGHT_BY_OR_AGAINST_A_PARTY"),
        "test_each_relation_keeps_the_paragraph"),
    "SUITS_AND_ARBITRATION_ARE_NOT_READ": (
        RULE, EXPOSURE, _drop("A_SUIT_OR_AN_ARBITRATION"),
        "test_each_relation_keeps_the_paragraph"),
}
if __name__ == "__main__":
    sys.exit(harness.main(sys.argv[1], sys.argv[2:]))
