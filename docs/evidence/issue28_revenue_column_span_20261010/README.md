# Preserve a valid revenue period under the common-share unit caption

Progress on #28. Actual main84d15f35 receivedPR136; Claude [fresh receiving failure6094536012](https://github.com/wlvh/SEC_metrics/pull/137#issuecomment-6094536012) stopsPR137. The oldcachedFY22value surviving does not prove a fresh task can produce it. Public source fix is #28; freshfive-yearB02company validation is #47.

## Measured cause and minimal fix

Parent actually parsed savedFY2021 primary7,350,907bytes, SHAa6dc538da8dd8c78563933a612ccb61bcc77ed9d067383ee6ed394612d5f0dd8. Actual-grid.log: table_000112/row2/year2021 originatescolumn15 withcolspan3, correctly coveringamountcolumn16 onrow3; dollar symbol iscolumn15. The existing span matcher already covers the amount. `_column_period` rejects the row because its other header is `(MILLIONS, EXCEPT PER COMMON SHARE DATA)`, while UNIT_HEADER acceptedonlyPER SHARE/PER-SHARE. Thus it never adds the otherwise correctly aligned year hit. This is not evidence that currency cells require column shifting.

Only the existing shared UNIT_HEADER descriptor changes: accept the optionalwordCOMMON in the per-share exception. The statedmain unit remainsmillions/thousands; native currency andscale checks, actualyear/date, wholeconsolidatedstatement, wrongsubject, otheramounts, source/XML/Facts and oldsingle-optiondefault all remain. financial_duration/table_grid/column positions are unchanged. No company/CIK/file-name special case, scope reclassification or latercomparative substitution.

## Actual parent evidence

- original-regression.log: newfull source-scope test fails beforepatch with FISCAL_COLUMN_UNRESOLVED.
- directed-tests.log:60 executions7.696s,0failure/error/skip. Fullpositive combines common-shareunitcaption, yearcolspan andsplitcurrency; wrongyear/nativeunit magnitude/segmentexception fail. Olddefault remainsNO_REPORTED_TOTAL_PROVEN for plainRevenues. Existing preciseperiods/quarters/noncalendar/header and originalsinglelineP2 guards execute.
- actual-original.json/log: actual saved original2021source preparation/authenticatedprimary+XML+CompanyFacts through currentpublicsource reader. 18.878832s returns81,288,000,000USD,table_000112,row3,column16; yearheadercolumn15,colspan3,2021; XMLMATCH and matchingoriginalCompanyFacts admitted. Defaultfalse stillNoReportedTotal. No companyResult/Run created byparent, noReferenceanswer input, no newcalls0/0/0. This execution used uncommitted source changes onmain84, not falsely labelled as a latercommittedSHA run.

Import-path-diagnostic.log and original-grid-diagnosis.log preserve early diagnostic harness mistakes (missingPYTHONPATH, parsernotfed/builderattribute), not source acceptance or product failures. Actual-grid.log is the completed direct source-grid diagnostic.

## Receiving and remaining scope

This source increment does not claim freshFY2022companyB02 or fullfive-year acceptance byitself. #47 must use freshwork-dir to verifyFY2022=.2342535183544926680444838106, FY2023=-.4169640187381640586065982259, FY2025priorcorrect; FY2021/FY2024 stay businesscomparisonconflicts. No ignoring source/periodfailures, oldanswers or cache asgoldeninput. Main currentB01/B03 and other business scope remains; newdifference limitedreview/receiver review is separate from existinge486reviews and owner merge permission.

Reproduce: `TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 python3 tests/required_unittests.py tests.vnext.test_single_revenue_line tests.vnext.test_selected_reported_revenue_v2 tests.vnext.test_selected_revenue_scope_v1 tests.vnext.test_financial_duration`. Source-only verifier accepts `--source-root` restoredsame saved corpus and reads source/request proof only. No requestacquisition/model/network/account operation. No Ready/merge/acceptance/deployment/activechange. Currentcaps/opportunities preserved.


Actual later receivercomment [6094654752](https://github.com/wlvh/SEC_metrics/pull/137#issuecomment-6094654752) was read. It corrects the earlier statement that freshownerreapproval is required: existingreceiverauthorization covers repair/revalidation/conditionalreceipt; root still does not mergeitself. The requested smallstructural positive preserves separatedollar/amount andcolspan; explicit two-year grouped positive and cross-group mismatchnegative were added. No sharedcolumnparser changed. Receiver and historicalowner will verify freshcompany output separately; no exception-to-business-string conversion.
