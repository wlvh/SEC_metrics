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
