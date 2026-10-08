"""Named in-memory mutations, run only from an isolated checkout."""
import hashlib
import io
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

repo=Path.cwd()
sys.path[:0]=[str(repo/'scripts'),str(repo)]
from tests.vnext import test_historical_note_carrying as cases
source=(repo/'scripts/vnext/historical_note_carrying.py').read_text()
unit_clause=" and unit == {\n                        'measures':[('http://www.xbrl.org/2003/instance','pure')],'divided':False}"
mutations=[
 ('reverse-prior-date', "if dated >= target or not re.fullmatch(", "if dated < target or not re.fullmatch(",
  'HistoricalNoteCarryingTest.test_wholly_prior_principal_balance_is_not_current_debt'),
 ('ignore-dollar-sign-in-share-count', "match[1] is None and re.match", "re.match",
  'HistoricalNoteCarryingTest.test_mixed_cash_or_nonshare_quantities_are_not_excluded'),
 ('allow-note-count-as-equity', "r'\\s+shares\\b'", "r'\\s+(?:shares|notes)\\b'",
  'HistoricalNoteCarryingTest.test_mixed_cash_or_nonshare_quantities_are_not_excluded'),
 ('asset-without-concept', 'source_inventory =',
  'ASSET_FORMS += (("name == \'debtsecuritiesavailableforsaletabletextblock\' and label == \'Commercial paper\'", "label == \'Commercial paper\'"),)\nsource_inventory =',
  'HistoricalNoteCarryingTest.test_commercial_paper_liability_or_wrong_table_is_unresolved'),
 ('asset-all-borrowings', 'source_inventory =',
  'ASSET_FORMS += (("and label == \'Commercial paper\' and text.startswith(", "and label in {\'Commercial paper\', \'Borrowings\'} and text.startswith("),)\nsource_inventory =',
  'HistoricalNoteCarryingTest.test_commercial_paper_liability_or_wrong_table_is_unresolved'),
 ('rate-without-standard-namespace', "elif standard and local.casefold()", "elif local.casefold()",
  'HistoricalNoteRateMaterialTest.test_custom_rate_or_another_pure_financing_fact_remains_unresolved'),
 ('rate-without-pure-unit', 'source_inventory =',
  'SOURCE_FORMS = tuple((old, new.replace(' + repr(unit_clause) + ', "")) for old,new in SOURCE_FORMS)\nsource_inventory =',
  'HistoricalNoteRateMaterialTest.test_rate_caption_with_currency_is_not_a_nonmonetary_rate'),
 ('frozen-source-call', '_source=source_inventory', '_source=release_aware(frozen._source)',
  'HistoricalNoteRateMaterialTest.test_standard_pure_rate_leaves_complete_debt_and_equity_unchanged'),
 ('frozen-asset-call', '_related_tables_inventory=related_tables_inventory',
  '_related_tables_inventory=release_aware(frozen._related_tables_inventory)',
  'HistoricalNoteRateMaterialTest.test_article_in_actual_asset_note_does_not_move_debt'),
]


def run_suite(names=None):
    suite=(unittest.defaultTestLoader.loadTestsFromModule(cases) if names is None else
           unittest.defaultTestLoader.loadTestsFromNames(names,cases))
    output=io.StringIO()
    result=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    return result,output.getvalue()


control,log=run_suite()
assert control.wasSuccessful(),log
rows=[]
for i,(label,old,new,test) in enumerate(mutations):
    assert source.count(old)==1,(label,source.count(old))
    module=types.ModuleType('vnext._historical_note_mutant_'+str(i))
    module.__package__='vnext';module.__file__=str(repo/'scripts/vnext/historical_note_carrying.py')
    exec(compile(source.replace(old,new),module.__file__, 'exec'),module.__dict__)
    with patch.multiple(cases, narrative_inventory=module.narrative_inventory,
                       prior_principal_balance=module.prior_principal_balance,
                       related_tables_inventory=module.related_tables_inventory,
                       inspect_note_carrying=module.inspect_note_carrying):
        result,log=run_suite([test])
    caught=(not result.wasSuccessful() and any(t.id().split(' (')[0].endswith(test)
                                             for t,_ in result.failures+result.errors))
    row={'mutation':label,'named_case':test,'caught_by_named_case':caught,
         'failures':[t.id() for t,_ in result.failures], 'errors':[t.id() for t,_ in result.errors]}
    rows.append(row);print(json.dumps(row),flush=True)
    assert caught,(label,log)
record={'record_type':'ISSUE_47_B06_NOTE_FORMS_NAMED_INJECTIONS',
        'code_sha256':'sha256:'+hashlib.sha256(source.encode()).hexdigest(),
        'control_cases':control.testsRun,'control_passed':control.wasSuccessful(),
        'mutations':rows,'calls':{'provider':0,'paid':0,'sec':0},
        'isolation':'in-memory variants in a separate review checkout; no frozen file edited'}
Path(sys.argv[1]).write_text(json.dumps(record,indent=1)+'\n')
