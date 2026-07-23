# 05 | SEC_metrics — Project Overview and Expert Guide

**Purpose**: give project owners, auditors, and developers a complete working grasp of the SEC_metrics spike — its objective, architecture, computation logic, evidence chain, accuracy defenses, acceptance procedure, extension path, and the boundaries of expert review.

---

## Table of Contents

0. Confidence declaration and current status
1. What this project is: scope and actual deliverables
2. Where the data comes from: SEC's three data planes and an XBRL primer
3. Architecture: monolith, pipeline, and the three principles of knowledge placement
4. How the numbers are computed: the five data pathways
5. What guarantees accuracy: four lines of defense and one conservation law
6. Risk register: closed items and still-open items
7. How to extend: from the 11th company to the 1000th
8. File map and code-reading path
9. How to read the output files
10. How to hand-audit a single metric
11. Common failure modes and how to localize them
12. Acceptance: light review package vs. full evidence package
13. Productionization roadmap
14. Training checklist
15. Quick command reference
16. Glossary

---

## 0. Confidence declaration for this document (read this section first)

The current verdict must be split into two layers:

| Object of acceptance | Current conclusion | Reason |
|---|---|---|
| Removal of company-specific branching + light-review hardening | ACCEPT WITH CAVEATS | Company-name-keyed business dispatch is at zero; the profile / extractor / concept-probe architecture is in place; both the Basel threshold defect and the light-golden circular self-attestation defect are fixed. |
| Scale-ready productionization | Partially complete; a live pilot is still required | The old risks — scale route, 10-K/A fallback, Basel threshold, captive finance — are closed. Still outstanding: FI SIC coverage, lodging-table recall, and value-level assertions for newly consumed dimensional amount facts. All of it needs a real 11th company (Hilton / Citi / GM / ServiceNow) run end to end. |

Since the merge, this document carries a three-tier confidence marker:

```text
[MEASURED]         Code or an adversarial test was executed; the run output is the proof.
[SOURCE-VERIFIED]  The implementation itself was read and confirmed line by line.
[ASSERTED]         A claim inherited from a report or an earlier document, not independently re-verified this round.
```

Anything not explicitly marked defaults to [SOURCE-VERIFIED]. The numerical counts below are the explicitly labelled Round-3 historical snapshot, not proof of a later run. For current tracked validation or audit evidence, read `outputs/validation_run_manifest.json` first and use only its `refreshed_artifacts`; Golden, metrics, and other inputs need their own rerun provenance.

---

## 1. What this project is: one sentence, its boundary, and the deliverables as they actually stand

**In one sentence**: connect directly to the SEC's official data endpoints and, for ten US-listed companies drawn from ten different industries, compute the financial, governance, risk, and event metrics for the latest fiscal year covered by a filed annual report — emitting a metrics matrix in which every single value is traceable back to a raw SEC response.

**The nature of the work is a spike** — engineering jargon for a one-off exploratory build meant to establish feasibility, not a production system. Its success criterion is written into SOP 01 and is worth memorizing: **not "every metric has a number", but "every company × metric cell carries all six of value / status / formula / source / evidence / confidence."** Honestly labelling the status when the data cannot be found is a legitimate outcome. Guessing a number to fill the matrix is failure. That single value judgment drives every mechanism described in the rest of this document.

**Historical Round-3 deliverables** ([MEASURED] for that package only):

```text
Metrics matrix    230 rows = 10 companies × 22–27 metrics
                  (the count varies by industry applicability; 23 per company on average)
Valued cells      161 with a value, 69 empty; every valued cell carries an evidence chain
Status mix        OK 73 | TEXT_QUAL 50 | NOT_AVAILABLE_SEC 31 | 8K_ITEM_OK 30
                  DIM_XBRL_OK 12 | DEF14A_OK 8 | NOT_EXTRACTED 5
                  NOT_MEANINGFUL 10 | MDA_OK 6 | NEEDS_REVIEW 2
                  OK_APPROX 2 | N_A_STRUCTURAL 1
Source mix        8-K events 60 | derived 48 | standard XBRL 27 | dimensional XBRL 12
                  proxy statement 8 | MD&A 6
Verification      63 golden assertions + 75 repair-validation checks + 17 unittest regressions
                  + generalization scanner + stratified-sample re-audit + 11th-company behavior fixture
Code size         sec_pipeline.py monolith ≈14,000 lines + 13 numbered stage scripts (~20-line thin wrappers)
                  + sec_http.py / sec_urls.py + tools/ + tests/
```

The choice of the ten companies is itself an experiment design. Enphase: clean standard XBRL, serving as the numeric baseline seed. Ford: negative operating income, a captive finance subsidiary, and unconventional capex tags — picked specifically to step on mines. JPMorgan: a bank, where the entire metric system is different. Salesforce: fiscal year ending in late January plus SaaS-specific metrics. Marriott: KPIs buried inside MD&A tables. Paramount: reporting entity changed mid-fiscal-year. Macy's: fiscal year ending in early February. Each one stands for a class of structural problem that will certainly recur on the way to a thousand companies.

---

## 2. Where the data comes from: SEC's three data planes and a five-minute XBRL primer

To read this project you first need a mental model of SEC data. The machine-readable data the SEC publishes falls into three planes, and this project combines them under a "companyfacts first, accession materials to fill the gaps" strategy.

### 2.1 The three data planes

**Plane one: submissions (the filing index).** `https://data.sec.gov/submissions/CIK##########.json`. It answers "what has this company filed": the form type of each filing (10-K annual report, 10-Q quarterly, 8-K current report, DEF 14A proxy statement, ...), the accession number (the unique ID of a filing, formatted like `0001463101-26-000013`), the filing date, and the period-end date. It also carries company metadata: legal name, former names, SIC industry code, fiscal year end (`fiscalYearEnd`, e.g. `1231`, `0131`), and entity type. Stages M0 and M1 run entirely on this plane.

**Plane two: companyfacts (company-level standard fact aggregation).** `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`. The SEC aggregates, across all of a company's historical filings, every XBRL fact that sits **on a standard taxonomy and at the total-company level** into a single JSON: revenue, net income, total assets, cash, and so on. Each fact carries its concept name, unit, period, source accession, and filing date. Its fatal limitation: **it contains no dimensional facts** (anything tagged with an axis/member, such as "the CET1 ratio on the Basel standardized basis") and no company-extension concepts. That limitation is precisely why plane three is mandatory.

**Plane three: accession materials (the raw filing).** `https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/...`. The raw file directory of an individual filing. This project consumes four kinds of file from it: `index.json` (the directory listing), `{accession}.hdr.sgml` (the filing header, which contains the 8-K `<ITEMS>` list — the data source for every event signal), `FilingSummary.xml` (document role descriptions), and the **iXBRL instance** (the inline-XBRL primary document; see below).

### 2.2 XBRL in five minutes (the project's entire core vocabulary lives here)

XBRL (eXtensible Business Reporting Language) is the standard for turning financial numbers into machine-readable tags. iXBRL (inline XBRL) is its modern form: the tags are embedded directly inside the human-readable HTML of the annual report, so a single document serves both humans and machines.

- **concept (tag)**: the semantic name of a number, e.g. `RevenueFromContractWithCustomerExcludingAssessedTax`. There are two kinds. **Standard concepts** belong to the us-gaap taxonomy (namespace `fasb.org/us-gaap/...`, shared across the whole market). **Company extensions** are tags a company defines for itself (the namespace is the company's own domain — for instance JPM's company-defined `CommonEquityTier1CapitaltoRiskWeightedAssets`; note the non-conforming lowercase `to`). **The same economic fact can carry different tags at different companies.** That fact alone is the reason the candidate-chain mechanism has to exist.
- **context**: which period, which reporting entity, and which dimensions a number belongs to.
- **dimension = axis + member**: a qualifier attached to a fact. For example, `us-gaap:RiskWeightedAssetsCalculationMethodologyAxis = jpm:BaselIIIStandardizedMember` means "this capital ratio is computed on the Basel III standardized basis". The axis is usually standard; the member is frequently company-minted — and that asymmetry is the key constraint on every generalization decision in this project.
- **unit**: `iso4217:USD` is a dollar amount; `pure` is a dimensionless number (a ratio).
- **scale**: an iXBRL numeric tag may declare a power-of-ten scale (the rendered text reads 294,804 in millions, while the tag value is 294804 with scale=6).

### 2.3 HTTP discipline

[SOURCE-VERIFIED] as implemented in `sec_http.py`: every request carries `User-Agent: <organization> <email>`; each `SecHttpClient` instance applies process-local sleep pacing at the configured rate, with no coordination across clients or processes; 403/429/5xx responses use exponential backoff and retry; and every request attempt is appended to `evidence/requests_log.csv`. New attempts with a response body persist an immutable content-addressed body/header pair as well as the caller-visible working path. The historical Round-3 log contained 859 request records across exactly **www.sec.gov and data.sec.gov**, but 38 old rows no longer resolve to bytes matching their recorded hash; those observations are `NOT_EVALUATED_MISSING_EVIDENCE`, not reproducible PASS evidence.

---

## 3. Architecture: one monolith, one pipeline, and three principles of knowledge placement

### 3.1 Physical shape: one monolith plus thirteen thin wrappers

All logic lives in a single module, `scripts/sec_pipeline.py` (~14,000 lines). The thirteen numbered scripts from `00_smoke_test_sec_access.py` to `12_validate_repair.py` are about twenty lines each and do exactly one thing: `run_stage(stage_name="...")`. The dispatch table is the `STAGES` dict at the tail of the monolith. This shape is a pragmatic choice for a spike and should be split apart when the system is productionized — but what **must survive the split** is the logical architecture described below.

### 3.2 The pipeline: physical stages 00–12

```text
00-01 Identity resolution company_tickers + submissions ──> company_resolution.csv
02    Locate the filings  submissions ──> latest_filings_inventory.csv
                          (target 10-K / prior 10-K / DEF 14A / every 8-K in the fiscal-year window)
03-04 Standard metrics    companyfacts JSON ──> concept_inventory + selection algorithm
                          ──> standard and derived metrics
05-06 Dimensional facts   fetch and parse accession iXBRL ──> {company}_instance.csv
                          ──> consumed by the Basel / RPO / AuditorName resolvers
07    Event signals       hdr.sgml of every 8-K ──> <ITEMS> parse ──> events.csv
08    Governance & pay    ecd-taxonomy facts in DEF 14A ──> C03 compensation / C02 board
09    Text KPIs           MD&A text ──> lodging KPIs + risk/legal text signals
10    Golden assertions   independently recomputed acceptance assertions
11    Bounded repair      primarily local; C04 AuditorName may conditionally fetch official SEC material when required local facts are unavailable; then report generation
12    Independent gate    validation run manifest + repair validation + refreshed report verdict
```

Each stage's output is simultaneously the next stage's input and an independently auditable intermediate artifact. This "persist every layer" design is what lets an agent recompute and verify from any cut point in the pipeline.

### 3.3 The three principles of knowledge placement (the single most important architectural idea here)

Scalability to a thousand companies does not come from any particular function. It comes from a discipline: **company identity (name, CIK) is permitted to live in exactly three places — input config, test fixtures, and the exception ledger; every branch in business logic must be keyed on an observable attribute.** The discipline is machine-enforced by `tools/check_no_company_literals.py`, which does an AST-level scan of every constant in the codebase ([MEASURED]: injected probes covering 6 violation shapes, 5 of them caught).

Observable attributes come in three tiers, forming a dispatch ladder:

```text
Tier 1  Registry attributes  From submissions: SIC code, fiscal year end, entity type, former names.
                             Purpose: decide *which metrics apply to whom*.
Tier 2  Capability probes    From the filing itself: "does this instance contain concept X /
                             axis Y / member pattern Z?"
                             Purpose: decide *which extraction strategy to use*.
                             Interrogate the data; do not recognize the name.
Tier 3  Lexical config       The data-shaped home of human industry knowledge: KPI lexicons,
                             magnitude bands, basis priority orders.
                             Purpose: let human judgment exist as data rather than as control flow.
```

Concretely: `config/company_registry.csv` carries all individual-company information (column-by-column semantics in §7.1). `config/metric_applicability.yaml` is keyed on **industry profile** and defines which extractors each profile mounts (`lodging → LodgingKpiExtractor`, `financial_institution → BaselCapitalRatioExtractor`, ...), plus `profile_rules` (rules inferring profile from SIC range) and `settings` (magnitude bands, scope priority orders, and other lexical config). Business code dispatches through **capability queries** of the form `has_extractor(extractors, "XxxExtractor")`; the extractor classes themselves are empty marker classes — capability tags, nothing more. [MEASURED] A whole-repository scan with string concatenation folded finds **zero** company-identity references in business code.

### 3.4 Generality is not the goal: governing the fit between correctness and engineering cost

This project drove "company special cases" out of the production control flow, and that was necessary — but it must not be misread as "the more general, the better." The real goals are **sufficient correctness** and **bounded engineering cost**; generality is merely a means that happens to serve both. The moment generality starts sacrificing correctness, or produces a more complex and more brittle parser purely to cover every conceivable naming variant, it has turned from an asset into a liability.

Sound adaptation has five layers:

```text
Layer 0: The non-negotiable general skeleton
  SEC-only sourcing, evidence chain, period selection, status semantics,
  golden/validation, request logging.

Layer 1: Metric-level general logic
  companyfacts selection algorithm, the RPO standard concept, AuditorName,
  ecd:PeoTotalCompAmt. When SEC/XBRL already gives you a structured fact,
  consume it — never write a text regex.

Layer 2: Industry / business-model adaptation
  Basel for financial institutions, RevPAR for lodging, RPO for SaaS and
  contract-performance businesses, captive finance for manufacturers.
  Legitimate, because companies within an industry share disclosure habits,
  units, and invariants.

Layer 3: Config-level company facts
  CIK, fiscalYearEnd, successor/predecessor, related_ciks, roles, manual overrides.
  These may be written per-company into the registry, because they are
  *input facts*, not computation logic.

Layer 4: Controlled company patches (forbidden by default, but not forbidden forever)
  Permitted only when the company is high-value, its public disclosure form
  really is unique, and the cost of an industry-level abstraction is too high.
  Conditions: isolated into data/config or an adapter; backed by evidence;
  covered by a regression; the reason recorded in exceptions/docs; carrying a
  migration or expiry condition; and never polluting the main path.
```

The Basel capital-ratio resolver is the cautionary tale. Starting from JPM's private concept and chasing "generality," it once grew a concept matcher so wide that the **regulatory minimum requirement could outrank the actual capital ratio**. The right correction was neither a retreat to `if company == "JPM"` nor an infinitely permissive semantic regex, but **a positive/negative lexicon + anchoring on the standard axis + separation of candidate roles + behavior-level fixtures**. Good generalization is not "matching more strings." It is "knowing which strings must never be allowed to become the primary value."

When extending to a thousand companies, advance by industry cluster. For each cluster, first pick three to five real companies and run a live pilot. Extractors should be **precision-first**: when extraction fails, emit `NOT_EXTRACTED` or `NEEDS_REVIEW` rather than letting a generalizer manufacture a false-OK number. Only once the same failure mode has recurred should it be promoted to an industry rule or a standard extractor.

---

## 4. How the numbers are computed: the five data pathways, one by one

The 161 valued cells in the matrix arrive via five pathways. Each one's mechanism, error-prevention design, and known boundaries follow.

### 4.1 Pathway one: STD_XBRL standard metrics + DERIVED (69 cells — revenue, net income, assets, cash flow, and so on)

**The selection algorithm** (locked in definition document 02; [MEASURED] every Enphase and Ford value was recomputed by a fully independent implementation and reconciled against live SEC, with agreement):

```text
Duration facts (revenue, net income, cash flow):
  form starts with 10-K
  AND end == the target fiscal year end
  AND a start exists, and duration ∈ [300, 400] days
  If several facts match, take the most recently filed.
Instant facts (assets, liabilities, cash):
  Same, except no start is permitted (instant type).
Prior-year value: same algorithm, with end swapped to the prior fiscal year end.
```

The 300–400-day duration window is one of the core error preventers. It automatically rejects quarterly facts, and it automatically rejects **stub periods** (a reporting period shorter than a year, produced when an entity is created or restructured mid-fiscal-year — Paramount's successor entity has only five months of facts dating from 2025-08-08, and this filter correctly refuses to treat five months as a full year).

**The candidate-chain mechanism.** Because different companies tag the same economic fact differently, each metric defines a priority-ordered chain of concepts; the pipeline probes them in order and takes the first hit, and **the tag actually hit must be recorded in the evidence**. The revenue chain, for example:

```text
RevenueFromContractWithCustomerExcludingAssessedTax → Revenues
  → SalesRevenueNet → RevenueFromContractWithCustomerIncludingAssessedTax
```

Real-world evidence that this is necessary ([MEASURED]): Marriott and Pfizer fall back to `Revenues`; Ford's capex hits the tail of the chain at `PaymentsToAcquireProductiveAssets` — live SEC confirms the conventional concept at the head of the chain **simply does not exist** in Ford's companyfacts; Ford's net income hits `ProfitLoss` (a basis that includes non-controlling interests, transparently annotated in the notes).

**Derived formulas and basis discipline** (44 cells):

```text
EBITDA proxy       = operating income + D&A (impairment explicitly NOT added back;
                     named as a GAAP proxy)
Free cash flow FCF = operating cash flow − capex
Debt/equity D/E    = total debt / shareholders' equity
                     total debt = LongTermDebt (or Current+Noncurrent — pick one,
                                  never both, to prevent double counting)
                                + short-term borrowings + commercial paper
                                + finance lease liabilities
                     DebtSecurities* is hard-excluded (those are investment assets,
                     not borrowings)
Interest coverage    forced to NOT_MEANINGFUL when operating income ≤ 0 (Ford and
                     Lumen loss years — emitting a negative multiple can only mislead)
Current ratio        structurally inapplicable to banks → JPM is marked N_A_STRUCTURAL
                     ([MEASURED] assertion G2 deliberately requests JPM's AssetsCurrent
                     endpoint and confirms the 404, freezing "banks have no current-asset
                     line item" into machine evidence)
```

### 4.2 Pathway two: DIM_XBRL dimensional metrics (12 cells — JPM's two capital ratios plus AuditorName for all 10 companies)

This pathway consumes the instance inventory that M3 streams out (several thousand facts per company, with complete dimensions). Three resolvers:

**The Basel capital-ratio resolver** (A01 Tier 1 ratio / A02 CET1 ratio). This is the most-iterated component in the entire project. The final decision tree ([MEASURED] against a six-way adversarial test):

```text
Candidate eligibility = unit is pure
     AND period_end matches
     AND dimensions include the standard axis RiskWeightedAssetsCalculationMethodologyAxis
     AND NOT a threshold concept (reject if the normalized name contains any of:
         minimum / requiredforcapitaladequacy / requiredtobewellcapitalized /
         wellcapitalizedminimum / tobewellcapitalized / capitaladequacyminimum)
     AND semantic match:
         normalize = lowercase, strip symbols, and rewrite tierone → tier1
         must contain riskweightedassets or riskbasedcapitalratio
         A02 additionally requires commonequitytier1 or cet1
         A01 requires tier1 AND not CET1 (so CET1 cannot be misfiled as Tier 1)
Selection ordering    = ParentCompanyMember / consolidated basis first > Standardized first
                      > no LegalEntityAxis first > lexicographic order of context
```

Three design principles here are worth committing to memory:

**(a) Anchor on the standard axis, not on the member.** Every bank's member names differ (`jpm:BaselIIIStandardizedMember` versus whatever another bank mints) — but the axis is us-gaap standard.

**(b) Unify tierone → tier1.** The official us-gaap naming spells it out as `TierOne`, while JPM's extension uses the numeral `Tier1`; without unification the standard naming is silently missed. This was a real bug, fixed in round 3 ([MEASURED]: the spelled-out CET1 was at one point misclassified as A01).

**(c) Exclude thresholds.** A bank's 10-K tags both the actual ratio and the **regulatory minimum requirement** (the 7.0% adequacy floor, the 6.5% well-capitalized floor). The two share the same unit, the same dimensions, and the same period. Without lexical exclusion, the regulatory floor can be selected as the bank's actual ratio ([MEASURED]: a same-dimension head-to-head test defeated the earlier filter in round 4; the final version culls thresholds at the candidate-pool stage). Excluded threshold facts are **not discarded** — they are moved into `basel_ratio_candidates.csv` tagged `candidate_role=regulatory_threshold`. They are valuable context: the distance between the actual ratio and the floor *is* the capital buffer.

Final JPM output: A01 = 0.155, A02 = 0.146 (parent-company consolidated scope; the Basel basis is stated in the notes).

**The RPO resolver** (B12 — Salesforce's remaining performance obligation). RPO is a mandatory disclosure under ASC 606, the current revenue-recognition standard, and `us-gaap:RevenueRemainingPerformanceObligation` is a standard concept — which means this metric is obtainable for **any company in the market** with zero company-specific code. The resolver: exact-or-suffix concept match (tolerating a company-prefixed extension) + exclusion of timing-axis concepts + USD unit + prefer a total-type fact, falling back to summing the current and noncurrent components. [MEASURED] Salesforce total RPO = $72.4B = $35.1B current + $37.3B noncurrent — internally consistent.

The historical lesson: the first-generation implementation was a text regex with the date string `"as of January 31, 2026"` burned into it, laboriously reconstructing a number that was already sitting there, structured. **If a concept exists in the structured inventory, a text regex is forbidden.** That rule is now frozen into a validation gate.

**The AuditorName comparator** (C04 — auditor rotation signal). `dei:AuditorName` is a standard fact that every 10-K is required to tag. Two paths: scan 8-K item 4.01 (the item type dedicated to auditor changes), and compare AuditorName between the current-year and prior-year 10-K instances. All ten companies pass through as DIM_XBRL_OK.

### 4.3 Pathway three: MDA text KPIs (2 cells — Marriott's occupancy and RevPAR)

Technically the most delicate component in the project, because it has to reliably lift numbers out of a **free-text table with no structured tags**. RevPAR (revenue per available room), ADR (average daily rate), and occupancy are the lodging industry's three headline KPIs, and they appear only inside the operating-statistics tables of the MD&A. The final pipeline ([MEASURED] against four synthetic adversarial tables):

```text
1 Segment       Slice the body text on KPI keywords into 5,000-character table candidates.
2 Header map    Within a segment, find the first occurrence of the RevPAR / Occupancy / ADR
                headers, sort by position, and derive the column order from it
                (genuinely header-driven, not a positional assumption)
                + all permutations kept as fallback candidates.
3 Row anchor    Find the row label using the configured basis priority order:
                comparable systemwide worldwide > systemwide worldwide
                > companywide > worldwide
                (a footnote marker such as "(2)" is a tolerated optional pattern, never an
                anchor — the first-generation implementation anchored its regex on the
                footnote number, and that is the textbook counterexample).
4 Assembly      Take even positions from the numbers in the row, following the
                "absolute value / change value" alternating rhythm, and assign them
                according to the candidate column order.
5 Identity      RevPAR = ADR × Occupancy / 100 must hold (error ≤ 5%)
                — it is both a hard gate (a candidate failing it is discarded) and a
                ranking key (among several candidates, take the one with the smallest error).
6 Magnitude     RevPAR ∈ [30, 600] USD, occupancy ∈ [0, 100] % (configurable).
```

Step 5 is the keystone. Whichever assignment of the three numbers satisfies the industry identity *is* the true column order — **using an industry-algebraic invariant to self-identify column order** is more robust than any layout assumption you could make.

[MEASURED]: Marriott's column order (RevPAR first) and Hilton's customary column order (Occupancy first) are both resolved correctly, with an identity error of 0.02%. A three-year comparison table (whose rhythm does not match) and a growth-rate sentence such as "RevPAR increased 2.0%" (the prototype of the round-1 incident) both honestly come back empty-handed. The identity gate compresses the wrong-rhythm failure mode into **lost recall rather than a wrong value** — and that ordering of failure severities is the correct one. The evidence quote carries four segments at once: `raw_header= / raw_row= / parsed= / identity_error=`, so it is simultaneously verbatim and re-checkable.

### 4.4 Pathway four: DEF14A governance (8 cells — CEO compensation)

`ecd` is the executive-compensation XBRL taxonomy that the SEC's pay-versus-performance rule requires every filer to use in its proxy statement (DEF 14A). C03 consumes `ecd:PeoTotalCompAmt` directly (PEO = principal executive officer, i.e. the CEO): iterate over every company, filter on the same concept, require the USD unit and the target fiscal-year end — **zero company-identity keys, generalizing by construction**. Eight companies hit (JPM $40.6M, Salesforce $49.4M, ...); Marriott's and Paramount's proxies carry no such ecd concept, and are honestly marked NOT_EXTRACTED.

Multi-PEO scenarios (co-CEOs, a mid-year handover): all line items go into `governance_signals`, and the main matrix does not sum them (adding several people's pay into a single "CEO compensation" is a semantic error).

The historical lesson: the first-generation implementation captured meaningless small decimals mismatched by a text regex (66, 196, ...) while the correct answer lay unconsumed in the ecd inventory the pipeline had itself dumped to disk. That is the origin of the term **"last-mile consumption failure"**, and the reason the "inventory-first" gate exists.

### 4.5 Pathway five: 8-K event signals (60 cells)

An 8-K is a real-time report of a material event, and the `hdr.sgml` header of each one carries an `<ITEMS>` tag listing the item numbers (5.02 = executive change, 4.01 = auditor change, 4.02 = restatement, 1.03 = bankruptcy, 1.01 = material agreement, 2.01/8.01 = M&A-related). M4 parses the item numbers of every 8-K in the fiscal-year window (about 326 events in the final version, with 125 multi-item filings correctly split into separate rows) and maps them onto C01 and E01–E05.

Two design points. E01 (M&A) cannot rest on Item 8.01 alone — that is the "Other Events" catch-all — so body-text keyword confirmation is required. And when the E02 (bankruptcy) count is zero, the report explicitly states that **zero is the expected result**: the semantics of a zero must be declared, or a reader cannot distinguish "it did not happen" from "we did not look."

### 4.6 The status enumeration: this system's contract language

The thirteen statuses are not decoration. They are a semantic contract with every downstream consumer. The four most easily confused, told apart by the incidents that earned them:

```text
NOT_AVAILABLE_SEC   The data genuinely does not exist in the SEC filing.
                    Example: Pfizer does not present an operating-income subtotal on its
                    income statement; the OperatingIncomeLoss concept simply does not exist
                    in its companyfacts ([MEASURED] and verified).
NOT_EXTRACTED       The data may exist in text or in a table, but this round could not
                    extract it reliably. An honest declaration of a capability boundary —
                    not a claim that the data is absent.
NOT_MEANINGFUL      Structurally meaningless. Example: interest coverage in a loss year;
                    Paramount's YoY growth rate in the year it changed reporting entity
                    (a stub period is not comparable to a full year).
N_A_STRUCTURAL      Structurally inapplicable to the industry. Example: banks have no
                    current-asset / current-liability line items.
```

Historical lesson: the first generation labelled "the successor entity has only stub-period facts" as NOT_AVAILABLE_SEC (the data was disclosed; only the basis was mismatched) and labelled "AuditorName is sitting unconsumed in the inventory" as NOT_AVAILABLE_SEC as well. **Status-semantics pollution makes a downstream consumer read "we did not finish" as "it does not exist in the world."** That is a subtler poison than a wrong number.

---

## 5. What guarantees accuracy: four lines of defense and one conservation law

### 5.1 Defense one: the evidence chain is mandatory

Every value must carry three things: accession (which filing) + concept_or_section (which concept or section) + context_or_dimension (which context or dimension), with a verbatim quote additionally required for text-sourced values. **The quote must support the value** — a statement that sounds tautological, but is the epitaph of the largest incident in round 1: Marriott's RevPAR came out as 2.0, wearing an MDA_OK status, with an evidence quote consisting of an unrelated passage about timeshares (the 2.0 was a growth rate a regex had misgrabbed from "RevPAR increased 2.0%").

The meta-rule established from that: **a wrong value wearing an OK status is an order of magnitude more dangerous than a missing value.** A miss is a visible hole. A wrong number is a silent poison.

### 5.2 Defense two: the golden assertion system (63 assertions)

Golden assertions are the dedicated antidote to "the code ran, and the number is wrong." For two benchmark companies — Enphase (clean standard XBRL) and Ford (deliberately chosen to step on mines) — every core value was checked by hand against the original annual report in advance and **frozen as an expected value** (stored in `tests/fixtures/sec_10_company_spike/golden_expected_values.csv`). The pipeline must independently reproduce exactly the same numbers.

Four groups:

- **G1 structural assertions** — the CIK and fiscal-year-end of all 10 companies.
- **G2 anti-misuse assertions** — deliberately confirming that JPM has no current-assets endpoint and that Ford has no conventional capex concept. **Expected absences are frozen into assertions too**, so that nobody later "helpfully fixes" them.
- **G3/G4 value assertions** — 13 Enphase values and 11 Ford values, including derived quantities and assertions on which tag was hit.
- **G5 candidate values** — three values each for the remaining eight companies, for human cross-checking.

The iron rule: **an assertion failure halts the run and reports the actual value. Never modify the expected value. Never hard-code around it.**

On independence: the assertions and the computation share a selection function (they live in the same monolith), but the expected values were locked externally by a human. If the selection logic carries a systematic bug, the produced value will fail against the locked constant and expose it. [MEASURED] A completely independent third-party implementation recomputed every golden value and reconciled it against live SEC; all three agree.

### 5.3 Defense three: validation gates

Grouped by what they defend against:

- **Generalization gates.** The AST scanner guarantees zero company literals in business code; a consistency check ties SIC rules to registry profiles.
- **Behavior fixtures.** The 11th-company test: mock data streams for four real companies outside the seed set (Hilton / Citi / GM / ServiceNow) flow through the real extractors, and the output is asserted. The Citi fixture deliberately includes a regulatory-threshold row that shares **the same dimensions** as the actual ratio, and asserts that the actual value wins.
- **Semantic gates.** C03 forbids the fact-count pseudo-metric; algebraic-identity checks; a check that Ford special-casing has been removed.
- **The recall ratchet.** The set of cells holding OK-class statuses must not shrink relative to the previous snapshot; the snapshot is a read-only fixture file. This guards against silent capability regression — the "fix A, break B" pattern.
- **The stratified-audit gate.** A stratified sample of valued cells is re-reviewed for quote support, and any single FAIL turns validation red. It is also correct-by-construction: the gate bites on the **recomputed-on-the-spot** result, not on the persisted file, so tampering with the CSV achieves nothing ([MEASURED] and verified).

### 5.4 Defense four: regression tests + integrity recomputation

The verification system itself must be falsifiable. The light review package — the package with bulky raw evidence stripped out — once had a **circular self-attestation** defect: the golden check merely counted `PASS` strings in a CSV. The package shipped a piece of paper saying everything passed, and the validation then verified that the paper said everything passed.

The final snapshot-integrity check performs five classes of cross-recomputation: expected↔actual re-compared row by row; G3/G4 against the locked fixture file; golden against the metrics_matrix for value drift; G1 against company_resolution; G2 against matrix semantics. [MEASURED] All four tampering vectors were intercepted, with diagnostics precise to the row (`stored_status=PASS:recomputed=FAIL`, `fixture_expected_mismatch`, `metrics_value_drift:B01`).

Mode determination is an explicit three-state decision:

```text
Evidence present                            → FULL_VALIDATION
                                              (takes precedence over the marker, so a stray
                                               marker cannot downgrade a complete workspace)
Evidence absent + LIGHT_REVIEW_PACKAGE.marker → light mode
Evidence absent, no marker                  → WORKSPACE_INCOMPLETE, a hard failure
                                              (this is what distinguishes "reviewer sandbox"
                                               from "corrupted workspace")
```

The current regression suite also covers: the Basel same-dimension threshold head-to-head, captive-finance recall/exclusion, the FI value-level fixture, the iXBRL scale route, claim-level missing-evidence non-evaluation, run-manifest fail-closed behavior, clone-root/path-containment portability, immutable per-attempt request persistence, the 10-K/A full-instance fallback, AST string-concatenation folding, capability-contract alignment, and the I1–I8 implementation mapping.

### 5.5 The conservation law

The four defenses above are not four independent safety nets; they are four coordinates of a single measured surface. This project's engineering restatement of Goodhart's Law is the **conservation law**:

> **The boundary of the gate is the boundary of quality. Defects migrate to whichever dimension carries no assertion coverage.**

Every incident recounted above obeys it. A quote existed but nobody asserted it supported the value → the wrong RevPAR appeared there. A structured RPO fact existed but nobody asserted it had been consumed → the regex re-derived it, badly. A threshold and an actual ratio shared every dimension but nobody asserted which must win → the threshold won. The light package counted PASS strings but nobody asserted the strings were recomputed → the paper certified itself.

The operational corollary is stated in §7.3: **an extractor without a fixture and a gate is a front line without defenses — the conservation law will find it immediately.**

---

## 6. Risk register: what is closed and what is still open (as of 2026-07-09)

The risk register below is inherited from the Round-3 review. It is not evidence that a later validation run passed; use the current run manifest, refreshed validation artifacts, and current test output for that claim.

### 6.1 Closed risks (implemented in code + covered by validation/tests)

**C1 — the 10-K/A full-instance fallback is implemented.** The old version had only a local AuditorName fallback inside C04. There is now a general `original_full_instance_fallback_row`: when the target is a 10-K/A, or the target instance holds fewer than 500 facts, or a key fact group is missing, it locates the original 10-K for the same reporting period and writes it into the inventory with `source_role=target_original_full_instance`. The corresponding test asserts that an amended target finds the original 10-K and that a sparse target triggers the fallback reason.

**C2 — the bare `wellcapitalized` gap in the Basel filter is closed.** `BASEL_THRESHOLD_CONCEPT_FRAGMENTS` now includes the bare `wellcapitalized` fragment, so a threshold concept like `BankingRegulation...RatioWellCapitalized` — which carries no `minimum` or `required` modifier — is labelled a regulatory threshold and can never become the primary value for A01/A02. The same-dimension actual-vs-threshold head-to-head test confirms the actual ratio wins.

**C3 — the captive-finance member recall gap is closed.** The probe no longer relies on suffix anchoring alone; it does a containment match against the segment / legal-entity dimension members of debt facts, guarded by exclusions for `creditloss`, `creditfacility`, `financelease`, and `supplierfinance`. Members of the `GeneralMotorsFinancialCompanyIncMember` and `JohnDeereCapitalCorporationMember` shape are now inside the fixture gate.

**C4 — the iXBRL scale route is hardened.** `scaled_inline_value` handles scale, sign, and parenthesized-negative normalization. `parse_instance_with_fallback()` first detects `<ix:` or `xmlns:ix=` and routes inline files straight to `InlineFactParser`, preventing the XML streaming parser from treating `ix:nonFraction` as an ordinary XML node and dropping `name/contextRef/unitRef/scale/sign`. Current validation includes a synthetic inline-scale fixture plus a full evidence cross-check on JPM CET1 capital = 294,804,000,000.

**C5 — the FI 11th-company behavior fixture is upgraded to value level.** `mock_concept_inventory.csv` now has an `expected_value` column, and `check_eleventh_company_behavior_financial_institution()` asserts agreement on four things at once — selected concept, context, dimensions, and value — so it can catch a right-concept/wrong-period, wrong-dimension, or wrong-value selection.

**C6 — the AST string-concatenation blind spot is closed.** The scanner folds string `BinOp(Add)` nodes through `folded_ast_literal_value()`, so `"Ford Motor " + "Company"` can no longer slip past the company-literal gate.

### 6.2 Still-open risks (real; handle or explicitly accept before scaling)

**R1 — the FI SIC rule range is still too narrow.** `profile_rules` currently covers 6020–6029 (national commercial banks). Savings institutions (6035/6036) and investment banks (6211) will still fall into a non-FI profile unless the registry overrides them. The fix is a config-level range widening; no extractor change is required.

**R2 — the lodging table machine still carries a cell-rhythm recall risk.** The assembly step assumes an "absolute value / change value" alternating rhythm. A heterogeneous rhythm — a three-year comparison table, for instance, with three absolute values per KPI — will not match. The identity hard gate compresses that into an honest empty hand rather than a wrong value, but when this extends to real Hilton and Hyatt annual reports, it remains the likely primary recall bottleneck.

**R3 — the recall ratchet still needs a real change to prove itself.** The snapshot baseline is a read-only fixture and is correctly shaped, but passing today only proves there has been no regression relative to the baseline. Its first genuine bite has to wait for the next real change in metric output.

**R4 — the `raw_header` in the B11 quote is still hard to read.** Marriott's RevPAR evidence quote already contains parsed tokens, the raw row, and the identity error, so it is auditable; but the `raw_header` capture window still starts mid-sentence. This is an evidence-presentation quality issue, not a value or gate issue.

**R5 — any new dimensional amount fact entering a derived formula must bring a value-level assertion with it.** The scale route and the JPM CET1 capital cross-check cover the existing risk, but if other dimensional amounts are ever fed into a formula, parser generality alone is not sufficient cover: a metric-level golden assertion, or a companyfacts/table cross-check, must be added at the same time.

---

## 7. How to extend: the operating manual from the 11th company to the 1000th

### 7.1 Adding one company (the standard path — zero code change expected)

Append one row to `config/company_registry.csv`. The twelve columns mean:

```text
company_id                Machine identifier (lowercase, underscores).
display_name              Display name.
primary_cik               The SEC primary CIK (look it up on the submissions page).
ticker                    Ticker symbol.
sic / sic_description     Industry code and description (returned by submissions; copy verbatim).
industry_profile          Industry profile — decides which extractors get mounted. May be left
                          for the SIC rules to infer; if it disagrees with the rule-inferred value,
                          it must go through an override and carry a note (a consistency
                          validation check enforces this).
fiscal_year_end           Fiscal year end as MMDD (returned by submissions; copy verbatim). Every
                          period computation in the pipeline is data-driven from this field —
                          Macy's 0201 requires not one line of special-case code.
target_period_policy      Normally latest_10k.
entity_continuity_status  continuous; a mid-year change of reporting entity (an acquisition
                          succession) takes a successor-class value. Even if this is filled in
                          wrong, the 300–400-day duration precondition and the CIK-chain check
                          will still catch the YoY-incomparability judgment (belt and braces,
                          [MEASURED]).
related_ciks / roles      For the Paramount-style dual-CIK case: the predecessor CIK and its role
                          annotation. Event scanning will then cross CIKs automatically.
```

Then run stages 00→11 followed by the independent stage 12 gate. Read `validation_run_manifest.json` first, then `company_resolution.csv` (is the identity resolution right?), `coverage_matrix.csv` (which pathway did each metric take, and why was anything unavailable?), and `exceptions_and_review_items.md` (everything awaiting human judgment).

**The correct expectation**: NOT_EXTRACTED and NEEDS_REVIEW appearing on a new company's first run is a normal and honest result. A **suspiciously all-green** result is the one to be alarmed by.

### 7.2 Adding one industry

Three steps in `metric_applicability.yaml`. Under `profiles`, create a new profile and list its extractor set (the five standard ones plus the industry-specific additions). In `profile_rules`, add the SIC-range → profile mapping. In `settings`, add that industry's lexical config (KPI lexicon, magnitude bands, basis priority order).

**The decision order for choosing a pathway for a new industry KPI**: first check whether us-gaap or an industry taxonomy has a standard concept (if yes → the DIM_XBRL pathway; write a concept resolver, do zero text processing). Then check whether companies commonly mint a custom extension for it (→ suffix or semantic matching). Only last resort is an MD&A text table (→ reuse the lodging table-machine skeleton, swapping in a new lexicon and a new invariant).

Airline example: RASM / CASM / load factor go through the text pathway, and relationships of the form `RASM = (basis-adjusted PRASM) × load factor` exist — so the same RevPAR-identity trick can be used for column-order self-identification.

### 7.3 Adding one extractor (the only scenario that requires touching code)

The template is the five-stage structure of the lodging table machine: **segment → anchor (configurable basis priority order) → assemble → industry-invariant hard gate → magnitude band.** The invariant gate is the soul of it: find an algebraic relationship among that industry's metrics and make it do double duty as both a filter and a ranker.

Three things are **mandatory** alongside it: register the marker class in `EXTRACTOR_REGISTRY`; add mock data plus behavior assertions for one real company from that industry to the 11th-company fixture; add the corresponding gate to validation. An extractor without a fixture and a gate is a front line without defenses — the conservation law will find it immediately.

### 7.4 When a "company adaptation" is permitted

To avoid swinging from *over-special-casing* all the way to *over-generalization*, company adaptation needs a sanctioned channel. A permitted adaptation must satisfy all six of these:

```text
1. What is being adapted to is a disclosure fact or an entity relationship — not a formula
   bent to make a number come out.
2. It lives in config / fixture / an isolated adapter, never in the main control flow.
3. SEC evidence proves that this company's disclosure form really is different.
4. It has a regression: at least one positive case and one negative case.
5. exceptions or docs record why an industry rule cannot solve it.
6. It carries a review condition: when a second company shows the same form,
   it must be promoted to an industry rule.
```

Examples. Paramount's successor/predecessor CIK, Macy's actual reportDate, and Salesforce's fiscalYearEnd are all legitimate config-level facts. `if company == "Salesforce" then parse sentence "as of January 31, 2026"` is an illegal company-specific parser. If some future bank turns out to expose only custom Basel concepts, you may register a concept alias in config first — but you must simultaneously add that alias to the Basel resolver's positive and negative fixtures, rather than writing a company branch.

### 7.5 The live pilot (graduation criteria — strongly recommended before any bulk extension)

Static defenses can only stop the failures you thought of. Residual risk lives, by definition, in the ones you did not — and only the real world can prospect for those.

The plan: add one registry row each for Hilton (SIC 7011), Citigroup (6021), and GM (3711), and run the full pipeline against live SEC (a cost of a few hundred requests). Three targeted questions:

- **Citi's real Basel tagging** tests whether the FI profile rules need widening to a broader SIC range.
- **Hilton's real table layout** tests both the identity-driven column-order self-identification and the R2 rhythm assumption.
- **GM's real captive-finance members** test whether C3's recall/exclusion guards are sufficient in the wild.

The exceptions list the pilot produces *is* the first genuine requirements document for a thousand-company product.

---

## 8. File map and code-reading path

```text
scripts/
  sec_pipeline.py        The whole-logic monolith (~14,000 lines). Reading entry points below.
  sec_http.py            HTTP client: UA, rate limiting, backoff, logging.
  sec_urls.py            Endpoint URL construction (CIK zero-padding, etc.).
  00..12_*.py            Thirteen thin stage wrappers; they only call run_stage.
config/
  company_registry.csv          The company registry — the only legal home of individual-company info.
  metric_applicability.yaml     Industry profile → extractors + SIC rules + lexical config.
tools/check_no_company_literals.py              Entry point of the AST generalization gate.
tools/check_capability_contract_alignment.py   Mechanical anchor/path/symbol alignment only.
tests/
  fixtures/sec_10_company_spike/golden_expected_values.csv   The locked expected values.
  fixtures/eleventh_company_smoke/   The 11th-company behavior fixture
                                     (mock data for four real companies across four industries).
  fixtures/regression/previous_ok_status_snapshot.csv        The recall-ratchet baseline.
  test_sec_pipeline_validation.py    Deterministic regression and scenario tests.
outputs/   (the schema of every CSV is in §6 of instruction document 03)
  metrics_matrix.csv     The primary deliverable: 230 rows, 20 columns.
                         The whole row — not the value — is the minimum auditable unit.
  metric_evidence.csv    Evidence detail (quote / verbatim text / extraction method).
  coverage_matrix.csv    Per-cell pathway and availability attribution.
  golden_results.csv     Golden assertion results for its recorded run.
  validation_run_manifest.json    The latest validation run's refreshed/not-refreshed evidence list.
  repair_validation_results.csv   Repair-gate results; trust it only when the manifest marks it refreshed.
  basel_ratio_candidates.csv      The full candidate set of ratios, including role-tagged
                                  threshold context.
  stratified_audit.csv / scalability_audit.csv / events.csv
  governance_signals.csv / risk_legal_signals.csv
  company_resolution.csv / latest_filings_inventory.csv
  exceptions_and_review_items.md  Everything awaiting human judgment.
evidence/  (full package only)   requests_log.csv + raw SEC responses; new attempts retain content-addressed immutable body/header copies.
LIGHT_REVIEW_PACKAGE.marker      The explicit declaration marker of a light review package.
```

**Code-reading path** (in dependency order; the skeleton can be read end to end in roughly half a day):

`run_stage` dispatch table (tail of the file) → the three-state `validation_package_mode` decision → `select_component`, the selection algorithm (the beating heart of every number in this project) → `load_company_registry` + `extractor_names_for_profile`, the dispatch chain → one complete extractor (the five-stage lodging machine is the recommended one) → `stage_run_golden_assertions` + `light_golden_snapshot_integrity_failures`, the two verification paths → the `check_*` family of gates.

---

## 9. How to read the output files: navigating from the matrix to the evidence

This section is the hands-on entry point. Open `outputs/validation_run_manifest.json` first. It records the run id, source commit, UTC start, mode, result, and which tracked validation/audit artifacts were or were not refreshed. A CSV's mere existence is never freshness evidence. Golden, metrics, and other inputs are outside this minimal manifest and need their own rerun provenance. Everything below explains how to read artifacts that the manifest identifies as current.

### 9.1 `metrics_matrix.csv`: the primary deliverable, not the only evidence

`metrics_matrix.csv` is the master matrix of all metrics. Each row represents one `company × metric_id` — but a row is not merely a value. It is a *metric judgment*, carrying status, source, period, and evidence anchors.

A row answers this question:

```text
For a given company, in a given target reporting period, is there a consumable result
for a given metric?
If yes: what is the value, in what unit, from which SEC filing, and via which
concept/section was it obtained?
If no: what is the semantics of the gap, and what should be done next?
```

Read it in this order:

```text
1  status                  — can this row be consumed directly?
2  source_class            — standard XBRL, dimensional XBRL, MD&A, DEF14A, 8-K, or text?
3  value/unit              — interpret magnitude only when a value exists.
                             An empty value does not automatically mean failure.
4  concept_or_section /
   context_or_dimension    — confirm the basis of the number is the basis you wanted.
5  accession / filed_date /
   period_start / period_end — confirm which filing, and which period.
6  notes / confidence      — confirm whether a proxy, a substitute value, a boundary
                             condition, or a human-review requirement applies.
```

The fields to look at first:

```text
company / cik                    Company identity
metric_id / metric_name          Metric number and name
value / unit                     Value and unit; value may be empty when there is no number
status                           Semantic status — the contract language for downstream judgment
source_class                     STD_XBRL / DIM_XBRL / DERIVED / MDA / DEF14A / 8K_ITEM / TEXT ...
formula                          The derivation formula, or a summary of the selection rule
period_start / period_end        The period — used to confirm it is the target fiscal year
accession / form / filed_date    The source filing
concept_or_section               The XBRL concept, or the text section
context_or_dimension             The XBRL context / dimension — i.e. the basis
confidence / notes               Confidence and the key caveats
```

One habit is non-negotiable when using the matrix: **seeing a value in the matrix is not enough — you must chase the evidence in `metric_evidence.csv`.** The biggest incident of round 1 was precisely a case where the matrix had a value, a status, and a quote — and the quote did not support the value at all.

### 9.2 `metric_evidence.csv`: the evidence chain behind a number

Every OK-class value should have a matching row here. When auditing by hand, join on `company + metric_id`:

```text
company, cik, metric_id
source_url, repo_relative_path, content_sha256, accession, document_name
concept_or_section, context_or_dimension, unit
period_start, period_end
value_raw, value_normalized
evidence_quote, extraction_method, parser_version
```

Judging whether the evidence is adequate is not a matter of whether the columns are populated. It is a matter of three things:

1. **Object consistency.** Does the quote / concept actually talk about *this* metric? A RevPAR quote must contain RevPAR or "revenue per available room". C03 must be `PeoTotalCompAmt` or the compensation table — not a count of ecd facts.
2. **Period consistency.** Does `period_end` equal the target fiscal year end? For duration facts, is the span 300–400 days, rather than a quarter or a stub period?
3. **Basis consistency.** JPM's A01/A02 must state Basel standardized vs. advanced, and parent vs. bank subsidiary. Salesforce's B12 must state that it is RPO/cRPO, not ARR.

### 9.3 `coverage_matrix.csv`: why each cell is in the state it is in

The question this file answers is not "is there a value?" but "*why* does this metric have this status?" Look especially at:

```text
has_numeric_value
has_evidence
needs_text_extraction
needs_review
reason
```

An expert auditor should be alert to two kinds of pollution:

```text
has_evidence set to 1 everywhere, while the evidence table is actually missing rows.
NOT_AVAILABLE_SEC being abused to conceal "the code never consumed an inventory it already had."
```

### 9.4 `golden_results.csv`: the locked-value assertions

Golden is the core defense against "the code ran, and the number is wrong." Key fields:

```text
assertion_id, description, expected, actual, status, evidence_path, notes
```

In full-package mode, golden should be recomputed from raw evidence / companyfacts. In light-package mode, at minimum a snapshot integrity check must run: re-compare expected/actual/status, check against the fixture, against `metrics_matrix`, and against `company_resolution`. Merely counting `status=PASS` is circular self-attestation, and has already been fixed.

### 9.5 `repair_validation_results.csv`: gate results are not business results

This file records the validation gates — de-special-casing, Basel threshold, light golden integrity, stratified audit, the 11th-company behavior test, and so on. Read it only when the current manifest marks it refreshed, and use the closed five-status vocabulary:

```text
PASS                            Required evidence existed; the check ran and passed.
FAIL                            The check ran and found a failure.
SKIPPED_LIGHT_PACKAGE           A declared light package omitted a full-only check.
NOT_EVALUATED_MISSING_EVIDENCE  Required evidence was missing, so no pass/fail claim is possible.
WORKSPACE_INCOMPLETE             Structural material is missing outside the permitted light boundary.
```

Missing evidence is never PASS. In full mode, a critical `NOT_EVALUATED_MISSING_EVIDENCE` blocks GO. In light mode, skipped and not-evaluated rows remain explicit caveats, and the manifest result is `PASSED_WITH_CAVEATS` at most.

### 9.6 `basel_ratio_candidates.csv`: the separation layer between actual ratio and threshold

This is an important output added by the round-3 hardening. A bank's capital-ratio table discloses both of the following at once:

```text
actual_ratio           The company's actual capital ratio, e.g. CET1 = 14.6%
regulatory_threshold   The regulatory minimum, or the well-capitalized requirement, e.g. 7.0%
```

The primary value of A01/A02 may come only from `actual_ratio`. The threshold may be retained as context, but it must never enter `metric_evidence.csv` as support for the primary value. Any expert auditing a bank metric must open this file and check that the candidate-role separation is correct.

---

## 10. How to hand-audit a single metric: from a value back to the SEC fact

What follows is a repeatable manual audit procedure. Any cell holding a value can be checked with these seven steps.

### 10.1 The seven-step audit

```text
1. Find company + metric_id in metrics_matrix.csv.
2. Check status / source_class / value / unit / period / accession.
3. Join on the same company + metric_id in metric_evidence.csv.
4. Resolve repo_relative_path in the current clone (or relocate by accession/document/hash),
   then confirm the evidence_quote/concept supports the value. A legacy absolute path is only a hint.
5. Check that formula matches the metric definition in document 02.
6. Check that the status is honest: cannot extract → NOT_EXTRACTED; not applicable →
   N_A_STRUCTURAL; not comparable → NOT_MEANINGFUL.
7. If the value falls inside golden / validation coverage, check golden_results or
   repair_validation to see whether it is actually covered.
```

### 10.2 Worked example: Marriott B11 RevPAR

An expert should be able to answer:

```text
value = 128.8 USD
status = MDA_OK
source_class = MDA
Does the evidence carry raw_header / raw_row / parsed?
Does raw_header contain RevPAR / Occupancy / ADR?
Does RevPAR ≈ ADR × Occupancy / 100 hold?
Has "RevPAR increased 2.0%" been mistaken for 2.0 USD?
```

If `evidence_quote` lacks the verbatim header or the selected row, the evidence is incomplete — no matter how plausible the value looks.

### 10.3 Worked example: Salesforce B12 RPO/cRPO

An expert should be able to answer:

```text
value = 72.4B USD
status = DIM_XBRL_OK
concept = RevenueRemainingPerformanceObligation
Do the notes state that RPO ≠ ARR and cRPO ≠ ARR?
Was the accession instance consumed in preference to a text regex?
Do current + noncurrent add back to total RPO?
```

The lesson from the Salesforce incident: once a structured concept exists in the instance, reaching for a company-specific text regex is the wrong direction, full stop.

### 10.4 Worked example: JPM A02 CET1 ratio

An expert should be able to answer:

```text
Is the primary value the actual ratio, and not a regulatory threshold?
Is the unit pure?
Do the dimensions include RiskWeightedAssetsCalculationMethodologyAxis?
Does the basis state standardized vs. advanced, and parent vs. bank subsidiary?
Does metric_evidence exclude threshold concepts of the Minimum / Required /
WellCapitalized family?
```

The trap in this class of metric: the actual ratio and the regulatory threshold look almost identical — both are `pure`, both share the period, both carry the same Basel dimension. Only concept role and lexical exclusion can tell them apart.

### 10.5 Worked example: C03 CEO compensation

An expert should be able to answer:

```text
Is the concept PeoTotalCompAmt?
Is the unit USD?
Is the period the target fiscal year?
In a multi-PEO case, has anything been wrongly summed?
Is there any residue of a pseudo-metric such as ecd_fact_count?
```

C03 is this project's positive exemplar: iterate over every company, filter uniformly on a standard ecd concept. That is the attribute-keyed paradigm, and it scales by construction.

---

## 11. Common failure modes and how to localize them

### 11.1 A value exists, but the evidence does not support it

*Symptom*: the matrix status is `MDA_OK` or `DEF14A_OK`, but the quote is a table of contents, iXBRL context noise, an unrelated paragraph, or a random sentence that happened to sit near a keyword.

*Localize*:

```bash
# Join company + metric_id by hand.
# Check whether evidence_quote contains both the metric keyword and the raw number.
```

*Handle*: downgrade to `NOT_EXTRACTED`, or fix the extractor. Do not leave it as OK.

### 11.2 The concept hit a threshold, not an actual value

*Symptom*: a bank capital ratio equals the regulatory minimum — 7.0%, 6.5% — rather than the company's actual ratio.

*Localize*: open `basel_ratio_candidates.csv` and read `candidate_role`.

*Handle*: keep the threshold as context; it must not enter `metric_evidence.csv` as primary evidence.

### 11.3 A text KPI mistook a percentage change for an absolute value

*Symptom*: manifestly implausible results such as RevPAR = 2.0 USD or occupancy = 1.5%.

*Localize*: the quote contains increased / decreased / percentage / bps, but no absolute-value table.

*Handle*: add a magnitude band + quote keyword requirements + an industry identity, e.g. RevPAR = ADR × occupancy.

### 11.4 Company special-casing creeping back in

*Symptom*: production code containing things like:

```python
if company == "Salesforce":
if cik == 1108524:
pattern = "January 31, 2026"
```

*Handle*: company names may live only in config / fixtures / docs. Business logic must be triggered by profile, SIC, concept, dimension, or text probe.

### 11.5 A light package masquerading as full validation

*Symptom*: evidence / concept_inventory are missing, yet the run reports a full PASS.

*Handle*: `LIGHT_REVIEW_PACKAGE.marker` must be present. Full-only checks must emit `SKIPPED_LIGHT_PACKAGE` or `NOT_EVALUATED_MISSING_EVIDENCE`, and the run manifest must retain the caveat. Light mode may never impersonate full validation.

### 11.6 coverage and evidence disagree

*Symptom*: coverage says `has_evidence=1`, but `metric_evidence` has no corresponding row.

*Handle*: coverage must be generated from an actual join of `metrics_matrix` against `metric_evidence` — never by setting the column to 1 across the board.

---

## 12. Acceptance modes: light review package vs. full evidence package

### 12.1 What a light package can verify

Suitable for verifying:

```text
whether the code structure is free of company special-casing;
whether config / profile / extractor registry exist;
whether the validation snapshot is internally consistent;
whether golden snapshot integrity resists tampering;
whether scalability_audit reports 0 violations;
whether the 11th-company behavior fixture runs;
whether the stratified audit is all PASS.
```

Not suitable for verifying:

```text
whether the raw SEC responses genuinely exist;
whether requests_log covers every request;
whether companyfacts / submissions / accession materials are complete;
whether the full concept_inventory is recomputable;
whether every full evidence artifact resolves and matches its content hash.
```

### 12.2 Formal acceptance sequence for a full package

With a full package in hand, run this in order:

```bash
python3 scripts/00_smoke_test_sec_access.py
python3 scripts/01_resolve_companies.py
python3 scripts/02_inventory_filings.py
python3 scripts/03_companyfacts_inventory.py
python3 scripts/04_compute_standard_metrics.py
python3 scripts/05_fetch_accession_materials.py
python3 scripts/06_parse_xbrl_instances.py
python3 scripts/07_extract_8k_events.py
python3 scripts/08_extract_def14a.py
python3 scripts/09_extract_mda_and_risk_text.py
python3 scripts/10_run_golden_assertions.py
python3 scripts/11_build_report.py
python3 scripts/12_validate_repair.py
python3 tools/check_no_company_literals.py
python3 tools/check_capability_contract_alignment.py
```

Then check:

```text
does validation_run_manifest.json identify this run and mark each artifact refreshed or stale?
is evidence/requests_log.csv SEC-only, and does each hashed row still resolve to matching body/header evidence?
are evidence/submissions/, companyfacts/, accession_materials/ complete?
is golden_results.csv all PASS?
is repair_validation_results.csv free of FAIL, WORKSPACE_INCOMPLETE, and full-mode NOT_EVALUATED?
is stratified_audit.csv all PASS?
does the REPORT verdict agree with the gates?
do the exceptions list every remaining NOT_EXTRACTED / NEEDS_REVIEW?
```

### 12.3 Stratified spot-check strategy

Do not sample 20 values at random: the clean STD_XBRL metrics are so numerous that they will dilute the problems. Sample by stratum instead:

| Source layer | Sample size | What to look at |
|---|---:|---|
| STD_XBRL / DERIVED | 8 | concept, period, formula, candidate chain |
| DIM_XBRL | 4 | dimensions, actual vs. threshold, unit = pure/USD |
| MDA / TEXT | 3 | verbatim fidelity of the quote, header, paragraph localization |
| DEF14A | 3 | ecd concept, compensation basis, multi-PEO |
| 8K_ITEM | 2 | hdr.sgml `<ITEMS>`, item mapping |

### 12.4 Verdict rules

```text
ACCEPT               Full package, evidence chain, golden, coverage, and report all pass, with
                     no third-party data backfill anywhere.
ACCEPT WITH CAVEATS  A small number of text / MD&A / DEF14A extractions failed, but were honestly
                     marked NOT_EXTRACTED and recorded in exceptions.
REJECT               Core files missing; values without evidence; third-party backfill; a golden
                     failure reported as success; a key basis misapplied; results not reproducible.
```

---

## 13. Productionization roadmap: from spike to an operable system

### 13.1 Near term: a real 11th-company pilot

Before scaling in bulk, do not keep polishing static validation alone. Add three or four real companies and run them against live SEC:

```text
Hilton / Hyatt                     — tests the lodging table machine.
Citigroup / Bank of America        — tests the Basel concept resolver, threshold exclusion, FI profile.
GM / John Deere / Caterpillar      — tests the captive-finance debt basis.
ServiceNow / Adobe                 — tests RPO/cRPO instance-first behavior.
```

The pilot is not there to produce a pretty result. It is there to expose the layout, namespace, dimension, and period edge cases of real filings.

### 13.2 Medium term: modular decomposition

`sec_pipeline.py` is today a spike monolith. For productionization, suggested split:

```text
sec_client/         HTTP, rate limiting, retry, requests_log
filing_inventory/   submissions; locating target / prior / DEF14A / 8-K
xbrl_parser/        companyfacts + accession instance parser
extractors/         Standard, Basel, RPO, Lodging, DEF14A, AuditorName, 8K, RiskText
validators/         golden, repair, scalability, stratified audit, tamper regression
reporting/          matrix, coverage, exceptions, report
config/             company registry, metric applicability, concept maps
```

When splitting, do not chase a beautiful class hierarchy first — preserve the existing gates first. A refactor without validation is just moving code around.

### 13.3 Medium term: storage-layer upgrade

CSV is adequate for a spike, but a thousand companies will hit joins, versioning, and audit-query problems. Suggested upgrade:

```text
raw evidence object store     raw SEC responses
SQLite / DuckDB / Postgres    facts, metrics, evidence, coverage
versioned run_id              every run reproducible
immutable expected fixtures   golden / recall baselines stay read-only
```

Core data model:

```text
company
filing
fact
metric_result
metric_evidence
validation_result
exception_item
```

### 13.4 Long term: CI/CD and the regression suite

Every PR must run:

```text
unit tests        concept resolver, period selector, text parser
fixture tests     the 11th-company behavior test
golden tests      the Enphase / Ford benchmarks
scalability gate  the company-literal scan
light integrity   the snapshot tamper regression
full integration  a periodic small live-SEC sample
```

### 13.5 Long term: a human review interface

`NEEDS_REVIEW` should not sit in a CSV forever. A productionized system needs a review workbench:

```text
show the matrix value + evidence quote + a link to the source document;
let the reviewer approve / reject / override the status;
write every human decision into an audit trail;
let the next generation of extractors learn failure modes from the human reviews —
but never by hard-coding a company name.
```

---

## 14. Training checklist

After reading this document, you should be able to do the following:

1. **Trace a value by hand**: find the value in `metrics_matrix.csv`, then `metric_evidence.csv`, then the raw evidence or quote.
2. **Judge whether a status is honest**: know the boundaries between `NOT_AVAILABLE_SEC`, `NOT_EXTRACTED`, `NOT_MEANINGFUL`, and `N_A_STRUCTURAL`.
3. **Tell an actual value apart from context / threshold / noise**: especially for bank capital ratios, RevPAR, RPO, and C03 compensation.
4. **Distinguish industry specialization from company special-casing**: SIC / profile / extractor is a legitimate industry abstraction; `if company == ...` is a danger signal.
5. **Add a company without changing code**: touch only the registry, run validation, read the exceptions.
6. **Design a new extractor**: define the basis, the data source, the evidence, and the status *first*; then write the extraction logic; then write the validation and the fixture.
7. **Give Codex the right instruction**: not "fix Salesforce", but "`RpoCrpoExtractor` must consume the instance fact first; company-name branches are forbidden; add a behavior fixture."

All of which collapses into one simple test:

```text
A number is trustworthy = trustworthy source + correct basis + correct period
                          + supporting evidence + gate coverage.
Miss any one of the five, and what you have merely looks like a number.
```

---

## 15. Quick command reference

### 15.1 Light-package review

```bash
python3 -m py_compile scripts/sec_pipeline.py tools/check_no_company_literals.py
python3 scripts/10_run_golden_assertions.py
python3 scripts/12_validate_repair.py
python3 tools/check_no_company_literals.py
python3 tools/check_capability_contract_alignment.py
```

Expected:

```text
PASS: LIGHT_REVIEW_MODE for the light golden integrity scope
validation manifest result = PASSED_WITH_CAVEATS
full-only rows = SKIPPED_LIGHT_PACKAGE or NOT_EVALUATED_MISSING_EVIDENCE
scalability_audit.csv = 0 violations
```

### 15.2 Full-package re-run

```bash
python3 scripts/00_smoke_test_sec_access.py
python3 scripts/01_resolve_companies.py
python3 scripts/02_inventory_filings.py
python3 scripts/03_companyfacts_inventory.py
python3 scripts/04_compute_standard_metrics.py
python3 scripts/05_fetch_accession_materials.py
python3 scripts/06_parse_xbrl_instances.py
python3 scripts/07_extract_8k_events.py
python3 scripts/08_extract_def14a.py
python3 scripts/09_extract_mda_and_risk_text.py
python3 scripts/10_run_golden_assertions.py
python3 scripts/11_build_report.py
python3 scripts/12_validate_repair.py
```

### 15.3 Common grep / audit commands

```bash
# Look for company special-casing creeping back in
grep -RIn "JPMorgan Chase\|Marriott International\|Salesforce\|Ford Motor Company\|Paramount\|Enphase" scripts/ tools/

# Look for third-party data sources
grep -RIn "yfinance\|bloomberg\|refinitiv\|macrotrends\|stockanalysis\|wikipedia" scripts/ .

# Look for hard-coding that could bypass golden
grep -RIn "expected_value\|golden\|hardcode" scripts/ tests/

# Quick look at failing gates
python3 - <<'PYCODE'
import csv
import json
from pathlib import Path

manifest = json.loads(Path('outputs/validation_run_manifest.json').read_text(encoding='utf-8'))
if 'repair_validation_results.csv' not in manifest['refreshed_artifacts']:
    raise SystemExit('repair_validation_results.csv is stale for this run')
with Path('outputs/repair_validation_results.csv').open(encoding='utf-8', newline='') as file_obj:
    for row in csv.DictReader(file_obj):
        if row['status'] != 'PASS':
            print(row)
PYCODE
```

---

## 16. Glossary

```text
spike                     A one-off exploratory build undertaken to establish feasibility.
accession                 The unique ID of an SEC filing (e.g. 0001463101-26-000013).
10-K / 10-K/A             Annual report / amended annual report.
8-K / DEF 14A             Current report of a material event / shareholder-meeting proxy statement.
XBRL / iXBRL              The standard for tagging financial facts / its inline form embedded in HTML.
concept                   The semantic tag name of a fact; us-gaap = standard taxonomy,
                          company domain = a custom extension.
dimension                 A qualifier on a fact, composed of an axis and a member.
unit: pure / USD          A dimensionless number (a ratio) / a dollar amount.
scale                     An iXBRL numeric tag's power-of-ten declaration. The helper and the parse
                          route now carry regression coverage; any newly consumed amount fact still
                          requires a value-level assertion — see R5.
companyfacts              The SEC's company-level standard fact aggregation API (no dimensional facts).
hdr.sgml                  The filing header file, containing the 8-K <ITEMS> list.
ecd                       The executive-compensation XBRL taxonomy used in proxy statements
                          (the pay-versus-performance rule).
SIC                       The SEC's four-digit industry classification code.
ASC 606 / 842 / 326       Revenue recognition / leases / credit losses accounting standards.
                          (They explain, respectively, why RPO is universal, why FinanceLease
                          concepts are ubiquitous, and why CreditLoss concepts are ubiquitous.)
CET1 / Tier 1             Common equity tier 1 capital / tier 1 capital (bank regulatory capital tiers).
RWA                       Risk-weighted assets; the denominator of a capital ratio.
Basel standardized /      The two methodologies for computing RWA.
  advanced
regulatory threshold      The capital-adequacy floor (7.0%), the well-capitalized floor (6.5%), and
                          similar minimum requirements. They coexist with the actual ratio in the
                          annual report in identical format, and must be lexically isolated from it.
RPO / cRPO                Remaining performance obligation / the portion of it falling within the
                          next 12 months (≠ ARR).
RevPAR / ADR / occupancy  Revenue per available room / average daily rate / occupancy.
                          RevPAR = ADR × occupancy.
captive finance           A company's dedicated financing subsidiary (the Ford Credit pattern).
stub period               A reporting period shorter than a year, caused by an entity being created
                          part-way through the year.
candidate chain           The priority-ordered concept probe sequence for a single metric.
golden assertion          A human-locked expected value for a benchmark company, which the pipeline
                          must independently reproduce.
conservation law          This project's engineering restatement of Goodhart's Law: the boundary of
                          the gate is the boundary of quality; defects migrate to whichever
                          dimension carries no assertion coverage.
correct-by-construction   The gate bites on a live recomputation rather than on a persisted file,
                          so tampering achieves nothing.
tamper test               Deliberately corrupting an input to check whether a defense has teeth.
LIGHT_REVIEW_MODE         The review-package mode with bulky evidence stripped out; it must be
                          declared by an explicit marker.
```
