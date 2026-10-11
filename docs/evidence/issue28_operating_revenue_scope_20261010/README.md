# Prove a reported consolidated operating revenue total

Progress on #28. Actualmain84d15f35; knownSWFY25 B01 frompeer116 source reading was28063m butcomplete_scope_proven=false. Parentread original0000092380-26-000004/primarySHA4f687048…:table_000033,row7,col15 literalTotaloperatingrevenues, nativeRevenueFromContractWithCustomerExcludingAssessedTax/ordinal168/currentannualUSD. Passenger25535+freight171+other2357are reportedcomponents; no calculator summing them into an inventedtotal. Income statement also reports totalOperatingCostsAndExpenses27635 andNetIncome441; SourceFiscalYear2025 is full2025-01-01..12-31.

## Minimal source interpretation

The V2 reader recognizes only the actualtotalOperatingRevenue label with approvednativeRevenueconcept. Its expense side requires the nativeOperatingCostsAndExpenses total in the same context/table afterrevenue and exactTotaloperatingexpenses rowlabel. This doesnotreplace income basis with revenue-minus-expense arithmetic. Originalnetincome/fullconsolidatedtitle/unit/entity/annualcolumn/XML/Facts/unknownscope guards remain. Additionalexpensefacts are internal to the operatingcase and storedwith its proof; nonoperating/defaultreported-total results retain the same outputfields and originalreportset.

The shared_statement_scope helper gains default-empty optionalunit/sectionheaders; only the operatingbranch supplies literalstandardOperatingRevenue/OperatingExpense/Non-operatingExpense(Income) headings plus `(in millions, except per share amounts)`. Parenthesis in the literalheading is preserved instead of being mistaken for an arbitraryfootnotemarker. Unknownscope/exclusions/othercompany/subtotal/units/date stillreject. No companyname/CIK/year/table/amount specialcase, frozenSpec revision or businessdefinition change. B01 remains the same approvedRevenueconcept, sourceoriginalamount/unit/annualperiod. Existing APIs/defaultkwargs preserveoldvalid behavior.

## Actual evidence

Original synthetic positive failed tocomplete beforepatch, original-regressions.log retained. Directed61tests7.834s/zero errors/fails/skips; later2targetedtests.217s add expense-subtotal/nonnative-expense negatives. Real source firstfailed an unrecognizedstandardsection after the initial patch, section-caption-normalization-failure.log/emptyJSON retained, then raw originalsection handling repaired. These are program/harness observations, not alteredoldResults.

Actualoriginal verifier reads selectedsavedcurrentinput andauthenticatedprimary/XML/CompanyFacts,7.327s, selects28063000000USD/table33r7c15/XMLMATCH; no source acquisition/provider or companyResult bythis component. It used uncommittedcode, not a falselypostcommitSHA run.

ActualformalcompanyCLI run on source-only input (rawbody/header/requestCSV/registry, no oldResult/AIanswer/program payload), thenfactory-forbiddenrepeat, separateprocessresults/CSV:3.832577/.104933/.439522s. Same28063000000USD,CIK92380/FY2025/fullcalendar2025, reportedconsolidatedscope proof + originalsourcecitations. Sevenresultfiles/no secondresultdirectory keep. DefaultCSVcanread; full scope remainsininput-assessments. The priorcorrectvalue is retained, but SOURCE_PROOFnow complete, not merely reference-value matching. final-actual-company.json records exactroots/CLI/failedsourceobservation/unchangedfiles/tested uncommittedcodehashes. No automatic financialhealthclaim or currentonlinevalidation.

Company import-path-diagnostic.log preserves a missingtests PYTHONPATH attempt; correctedcontrolledCLI above uses PYTHONPATH=scripts:. . The actual case/calculator/store/read were not mocked; onlynetwork andrepeatfactory wereblocked. Unknownproviderusage/cost untouched; calls0/0/0.

## Remaining validation and ownership

Necessarynewdifference limitedreview and new-headCI are separate from previoussource136/139 reviews. Validatedsavedcurrentpositive is onecompanycoordinate, not all39/390 or everyoperatingstatement. Sourcecode belongs28;47 thin consumerwillreceiveversion and check its actualselectedperiod dependencies/CSV/oldcorrect records. Currentbank/period parsers/modelroutes are notexpanded. Newsource findings or inconsistentcost/net/context keep unresolved, no zero/N_A fallback.

Tests: `TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 python3 tests/required_unittests.py tests.vnext.test_selected_reported_revenue_v2 tests.vnext.test_selected_revenue_scope_v1 tests.vnext.test_single_revenue_line tests.vnext.test_financial_duration`; data-only component verifier `--source-root` same savedcorpus. FormalCLI driver accepts localpaths inits record and mustwriteisolatednewstate; no ledger/import/retry. No Ready/merge/adoption/deploy/active. Originalsource/oldRuns/counts/opportunities keep.

## Parenthesis scope repair after independent P2

Independent review of `7a2ffdd20b95888dbf0b518e6b3096f2dc67b056` returned REQUIRES_FIX: `_label_key` discarded `(domestic)` and `(subtotal)` before admitting the newly supported operating total. The original independent conclusion stays unchanged. Three matching-native-XML counterexamples failed before repair (`parenthetical-original-failure.log`). The repair changes only the two new operating revenue/expense label checks to raw case/whitespace comparison; existing total/single-line normalization and default statement rules remain untouched.

The repaired uncommitted tree passed 62 directed tests in 7.731 seconds, zero failures/errors/skips (`parenthetical-repair-tests.log`). The earlier saved Southwest positive has literal unqualified labels and therefore follows the same two admitted branches; its actual large-source and formal company execution remain evidence for their original recorded tree, not newly claimed executions of this repair. Parent tests are not independent acceptance. Increment review and new-head CI remain separate gates. Initial7a2 CI now actually has eleven successful checks; it does not cover this repair. Provider/paid/SEC remain 0/0/0.

The exact `e98a26c1828e3a794e2a931c5541e2c0d6ae79b9` two-line repair now has independent limited PASS (`independent-parenthetical-repair/conclusion.md`): 3 directed tests and 8 finite base/patch controls, 10 tool nodes / 2 messages. Four parenthetical-scope negative variants are rejected; unqualified operating and old ordinary/single-line positive full dictionaries remain identical. No large-source/company rerun by reviewer. Original7a2 REQUIRES_FIX remains historical. This archive commit changes only this existing evidence directory, not tested source/test bytes.
