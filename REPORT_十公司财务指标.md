# REPORT_十公司财务指标

## Executive Summary

- Verdict: **GO WITH CAVEATS**。
- SEC 请求总数：634；状态分布：`{"403":5,"200":604,"404":25}`。
- 指标格子：230；OK/TEXT 类：175；待复核/不可得类：55。
- 本次只使用 SEC 官方响应和本地 evidence 文件；未使用第三方数据或模型记忆补数。
- Repair validation 若有 P0 FAIL，verdict 强制为 NO-GO。
- Stratified audit 任一 FAIL 会进入 repair validation gate，不能被报告静默吞掉。

## 数据来源和请求统计

- company_tickers_exchange、submissions、companyfacts、accession materials、8-K hdr.sgml、DEF 14A primary document 均通过 SEC 官方 URL 请求。
- 所有请求记录在 `evidence/requests_log.csv`，原始响应保存在 `evidence/` 子目录，并带 headers/hash 旁路文件。

## 公司身份解析表

| company | resolved_cik | entity_role | name | fiscalYearEnd | tickers |
|---|---|---|---|---|---|
| Marriott International | 0001048286 | primary | MARRIOTT INTERNATIONAL INC /MD/ | 1231 | ["MAR"] |
| Southwest Airlines | 0000092380 | primary | SOUTHWEST AIRLINES CO | 1231 | ["LUV"] |
| Ford Motor Company | 0000037996 | primary | FORD MOTOR CO | 1231 | ["F","F-PB","F-PC","F-PD"] |
| Pfizer | 0000078003 | primary | PFIZER INC | 1231 | ["PFE"] |
| JPMorgan Chase | 0000019617 | primary | JPMORGAN CHASE & CO | 1231 | ["JPM","JPM-PC","AMJB","JPM-PD","JPM-PJ","JPM-PK","JPM-PL","JPM-PM","VYLD"] |
| Salesforce | 0001108524 | primary | Salesforce, Inc. | 0131 | ["CRM"] |
| Lumen Technologies | 0000018926 | primary | Lumen Technologies, Inc. | 1231 | ["LUMN"] |
| Macy's | 0000794367 | primary | Macy's, Inc. | 0201 | ["M"] |
| Paramount Skydance / Paramount Global | 0002041610 | successor | Paramount Skydance Corp | 1231 | ["PSKY"] |
| Paramount Skydance / Paramount Global | 0000813828 | predecessor | Paramount Global | 1231 | [] |
| Enphase Energy | 0001463101 | primary | Enphase Energy, Inc. | 1231 | ["ENPH"] |

## 指标覆盖率摘要

- 8K_ITEM_OK: 30
- DEF14A_OK: 8
- DIM_XBRL_OK: 12
- MDA_OK: 2
- NEEDS_REVIEW: 2
- NOT_AVAILABLE_SEC: 42
- NOT_EXTRACTED: 7
- NOT_MEANINGFUL: 3
- N_A_STRUCTURAL: 1
- OK: 69
- TEXT_QUAL: 54

## 十公司指标矩阵摘要

| company | metric_id | metric_name | value | unit | status | concept_or_section |
|---|---|---|---|---|---|---|
| Marriott International | B01 | Revenue | 26186000000 | USD | OK | Revenues |
| Marriott International | B04 | Net income | 2601000000 | USD | OK | NetIncomeLoss |
| Marriott International | B05 | Free cash flow | 2608000000 | USD | OK | NetCashProvidedByUsedInOperatingActivities+PaymentsToAcquireProductiveAssets |
| Marriott International | B08 | Current ratio | 0.4267682781614670159561800429 | ratio | OK | AssetsCurrent+LiabilitiesCurrent |
| Marriott International | B09 | Cash reserves | 358000000 | USD | OK | CashAndCashEquivalentsAtCarryingValue |
| Southwest Airlines | B01 | Revenue | 28063000000 | USD | OK | RevenueFromContractWithCustomerExcludingAssessedTax |
| Southwest Airlines | B04 | Net income | 441000000 | USD | OK | NetIncomeLoss |
| Southwest Airlines | B05 | Free cash flow | -831000000 | USD | OK | NetCashProvidedByUsedInOperatingActivities+PaymentsToAcquireProductiveAssets |
| Southwest Airlines | B08 | Current ratio | 0.5168940573207581723285413424 | ratio | OK | AssetsCurrent+LiabilitiesCurrent |
| Southwest Airlines | B09 | Cash reserves | 3231000000 | USD | OK | CashAndCashEquivalentsAtCarryingValue |
| Ford Motor Company | B01 | Revenue | 187267000000 | USD | OK | RevenueFromContractWithCustomerExcludingAssessedTax |
| Ford Motor Company | B04 | Net income | -8162000000 | USD | OK | ProfitLoss |
| Ford Motor Company | B05 | Free cash flow | 12467000000 | USD | OK | NetCashProvidedByUsedInOperatingActivities+PaymentsToAcquireProductiveAssets |
| Ford Motor Company | B08 | Current ratio | 1.074828096440073113412829663 | ratio | OK | AssetsCurrent+LiabilitiesCurrent |
| Ford Motor Company | B09 | Cash reserves | 23356000000 | USD | OK | CashAndCashEquivalentsAtCarryingValue |
| Pfizer | B01 | Revenue | 62579000000 | USD | OK | Revenues |
| Pfizer | B04 | Net income | 7771000000 | USD | OK | NetIncomeLoss |
| Pfizer | B05 | Free cash flow | 9075000000 | USD | OK | NetCashProvidedByUsedInOperatingActivities+PaymentsToAcquirePropertyPlantAndEquipment |
| Pfizer | B08 | Current ratio | 1.159906986805104910231451438 | ratio | OK | AssetsCurrent+LiabilitiesCurrent |
| Pfizer | B09 | Cash reserves | 1142000000 | USD | OK | CashAndCashEquivalentsAtCarryingValue |
| JPMorgan Chase | A05 | ROA | 0.01353819078340816975991354239 | ratio | OK | NetIncomeLoss+Assets+Assets |
| JPMorgan Chase | A06 | ROE | 0.1613357541615054383791763528 | ratio | OK | NetIncomeLoss+StockholdersEquity+StockholdersEquity |
| JPMorgan Chase | A07 | Net income trends | -1423000000 | USD | OK | NetIncomeLoss+NetIncomeLoss |
| JPMorgan Chase | B08 | Current ratio |  |  | N_A_STRUCTURAL | Bank current ratio is structurally not applicable. |
| Salesforce | B01 | Revenue | 41525000000 | USD | OK | RevenueFromContractWithCustomerExcludingAssessedTax |
| Salesforce | B04 | Net income | 7457000000 | USD | OK | NetIncomeLoss |
| Salesforce | B05 | Free cash flow | 14402000000 | USD | OK | NetCashProvidedByUsedInOperatingActivities+PaymentsToAcquirePropertyPlantAndEquipment |
| Salesforce | B08 | Current ratio | 0.7603319144350449916482569104 | ratio | OK | AssetsCurrent+LiabilitiesCurrent |
| Salesforce | B09 | Cash reserves | 7327000000 | USD | OK | CashAndCashEquivalentsAtCarryingValue |
| Lumen Technologies | B01 | Revenue | 11331000000 | USD | OK | RevenueFromContractWithCustomerExcludingAssessedTax |
| Lumen Technologies | B04 | Net income | -1739000000 | USD | OK | NetIncomeLoss |
| Lumen Technologies | B05 | Free cash flow | 371000000 | USD | OK | NetCashProvidedByUsedInOperatingActivities+PaymentsToAcquireProductiveAssets |
| Lumen Technologies | B08 | Current ratio | 1.801594533029612756264236902 | ratio | OK | AssetsCurrent+LiabilitiesCurrent |
| Lumen Technologies | B09 | Cash reserves | 1003000000 | USD | OK | CashAndCashEquivalentsAtCarryingValue |
| Macy's | B01 | Revenue | 21764000000 | USD | OK | RevenueFromContractWithCustomerExcludingAssessedTax |
| Macy's | B04 | Net income | 642000000 | USD | OK | NetIncomeLoss |
| Macy's | B05 | Free cash flow | 1057000000 | USD | OK | NetCashProvidedByUsedInOperatingActivities+PaymentsToAcquirePropertyPlantAndEquipment |
| Macy's | B08 | Current ratio | 1.485199198753616737146672602 | ratio | OK | AssetsCurrent+LiabilitiesCurrent |
| Macy's | B09 | Cash reserves | 1246000000 | USD | OK | CashAndCashEquivalentsAtCarryingValue |
| Paramount Skydance / Paramount Global | B01 | Revenue |  |  | NOT_AVAILABLE_SEC |  |
| Paramount Skydance / Paramount Global | B04 | Net income |  |  | NOT_AVAILABLE_SEC |  |
| Paramount Skydance / Paramount Global | B05 | Free cash flow |  | USD | NOT_AVAILABLE_SEC |  |
| Paramount Skydance / Paramount Global | B08 | Current ratio | 1.256722332295499575431644495 | ratio | OK | AssetsCurrent+LiabilitiesCurrent |
| Paramount Skydance / Paramount Global | B09 | Cash reserves | 3274000000 | USD | OK | CashAndCashEquivalentsAtCarryingValue |
| Enphase Energy | B01 | Revenue | 1472985000 | USD | OK | RevenueFromContractWithCustomerExcludingAssessedTax |
| Enphase Energy | B04 | Net income | 172133000 | USD | OK | NetIncomeLoss |
| Enphase Energy | B05 | Free cash flow | 95901000 | USD | OK | NetCashProvidedByUsedInOperatingActivities+PaymentsToAcquirePropertyPlantAndEquipment |
| Enphase Energy | B08 | Current ratio | 2.065412193479380422295289783 | ratio | OK | AssetsCurrent+LiabilitiesCurrent |
| Enphase Energy | B09 | Cash reserves | 474318000 | USD | OK | CashAndCashEquivalentsAtCarryingValue |

## FI track：BaselCapitalRatioExtractor 指标解释

- A01/A02 从 financial_institution profile 的 Basel ratio facts 读取，未用 capital amount / RWA amount 自行相除。
- regulatory threshold / requirement concept 不进入 A01/A02 primary metric evidence；候选与 threshold 分流写入 `outputs/basel_ratio_candidates.csv`。
- FI 专属 A03/A04/A08/A09/A10/A11/A12/A13 未用普通资产负债表硬算；LCR、AUM、VaR 等仍需要 MD&A 或表格维度事实。
- financial_institution 的 B08 current ratio 标为 `N_A_STRUCTURAL`，避免把银行资产负债表错误套入商业公司流动比率。

## Non-FI track

- B01/B04/B05/B08/B09 优先从 companyfacts 标准事实计算，并在 `metric_evidence.csv` 记录 accession、concept、context。
- B03 是 GAAP EBITDA proxy：Operating income + D&A，不加回 impairment。
- CaptiveFinanceDebtExtractor 只在债务事实具有 captive/credit segment 或 legal entity 维度时标注工业口径复核要求。
- RpoCrpoExtractor 优先消费 accession instance 的 RPO/cRPO facts，文本 fallback 仍明确 `RPO != ARR; cRPO != ARR`。
- LodgingKpiExtractor 通过表头映射抽取 RevPAR/Occupancy/ADR 绝对值；percentage change 不作为金额。
- EntityContinuityYoyRule 对 successor/predecessor、stub period 或 duration 不可比链路标 `NOT_MEANINGFUL`。

## Governance / Risk / Event signals 摘要

- FY-window 8-K item rows: 326。
- DEF 14A 输出 governance_signals，并在存在 ecd facts 时 dump 到 concept_inventory。
- C04 auditor change 使用 current/prior 10-K instance 的 `dei:AuditorName` 对照；缺失时只针对 AuditorName 补抓 SEC 官方 XBRL instance，仍不可判定才标 NEEDS_REVIEW。
- D01-D04 风险法律文本来自 10-K primary document 的章节/关键词片段；未披露 going concern doubt 时写明未披露，而不是 parse failure。

## Fixture golden assertion 结果

| assertion_id | expected | actual | status |
|---|---|---|---|
| G1_marriott_international_cik | 1048286 | 1048286 | PASS |
| G1_marriott_international_fye | 1231 | 1231 | PASS |
| G1_southwest_airlines_cik | 92380 | 92380 | PASS |
| G1_southwest_airlines_fye | 1231 | 1231 | PASS |
| G1_ford_motor_company_cik | 37996 | 37996 | PASS |
| G1_ford_motor_company_fye | 1231 | 1231 | PASS |
| G1_pfizer_cik | 78003 | 78003 | PASS |
| G1_pfizer_fye | 1231 | 1231 | PASS |
| G1_jpmorgan_chase_cik | 19617 | 19617 | PASS |
| G1_jpmorgan_chase_fye | 1231 | 1231 | PASS |
| G1_salesforce_cik | 1108524 | 1108524 | PASS |
| G1_salesforce_fye | 0131 | 0131 | PASS |
| G1_lumen_technologies_cik | 18926 | 18926 | PASS |
| G1_lumen_technologies_fye | 1231 | 1231 | PASS |
| G1_macy_s_cik | 794367 | 794367 | PASS |
| G1_macy_s_fye | 0201 | 0201 | PASS |
| G1_paramount_skydance_paramount_global_cik | 2041610 | 2041610 | PASS |
| G1_paramount_skydance_paramount_global_fye | 1231 | 1231 | PASS |
| G1_paramount_skydance_paramount_global_role_chain | 2041610;813828 | 2041610;813828 | PASS |
| G1_enphase_energy_cik | 1463101 | 1463101 | PASS |
| G1_enphase_energy_fye | 1231 | 1231 | PASS |
| G2_financial_assetscurrent_b08 | B08=N_A_STRUCTURAL | companyconcept_status=404; B08_status=N_A_STRUCTURAL | PASS |
| G2_financial_a01_not_std | source_class != STD_XBRL | DIM_XBRL | PASS |
| G2_financial_a02_not_std | source_class != STD_XBRL | DIM_XBRL | PASS |
| G2_captive_finance_b06_dimension_review | NEEDS_REVIEW or DIM_XBRL_OK or OK | NEEDS_REVIEW | PASS |
| G2_auditorname_material_source | at least one AuditorName fact | 19 | PASS |
| G3_clean_xbrl_revenue | 1472985000 | 1472985000 | PASS |
| G3_clean_xbrl_prior_revenue | 1330383000 | 1330383000 | PASS |
| G3_clean_xbrl_net_income | 172133000 | 172133000 | PASS |
| G3_clean_xbrl_operating_income | 157526000 | 157526000 | PASS |
| G3_clean_xbrl_da | 80645000 | 80645000 | PASS |
| G3_clean_xbrl_ocf | 136540000 | 136540000 | PASS |
| G3_clean_xbrl_capex | 40639000 | 40639000 | PASS |
| G3_clean_xbrl_current_assets | 2606860000 | 2606860000 | PASS |
| G3_clean_xbrl_current_liabilities | 1262150000 | 1262150000 | PASS |
| G3_clean_xbrl_cash | 474318000 | 474318000 | PASS |
| G3_clean_xbrl_equity | 1087023000 | 1087023000 | PASS |
| G3_clean_xbrl_total_assets | 3509792000 | 3509792000 | PASS |
| G3_clean_xbrl_long_term_debt | 1204377000 | 1204377000 | PASS |
| G3_clean_xbrl_ebitda | 238171000 | 238171000 | PASS |
| G3_clean_xbrl_fcf | 95901000 | 95901000 | PASS |
| G3_clean_xbrl_current_ratio | 2.07 | 2.065412193479380422295289783 | PASS |
| G3_clean_xbrl_debt_to_equity | 1.11 | 1.107959077222837051285943352 | PASS |
| G3_clean_xbrl_revenue_tag | RevenueFromContractWithCustomerExcludingAssessedTax | RevenueFromContractWithCustomerExcludingAssessedTax | PASS |
| G4_captive_finance_revenue | 187267000000 | 187267000000 | PASS |
| G4_captive_finance_prior_revenue | 184992000000 | 184992000000 | PASS |
| G4_captive_finance_operating_income | -9169000000 | -9169000000 | PASS |
| G4_captive_finance_da | 15974000000 | 15974000000 | PASS |
| G4_captive_finance_ocf | 21282000000 | 21282000000 | PASS |
| G4_captive_finance_capex | 8815000000 | 8815000000 | PASS |
| G4_captive_finance_current_assets | 123487000000 | 123487000000 | PASS |
| G4_captive_finance_current_liabilities | 114890000000 | 114890000000 | PASS |
| G4_captive_finance_cash | 23356000000 | 23356000000 | PASS |
| G4_captive_finance_equity | 35952000000 | 35952000000 | PASS |
| G4_captive_finance_interest_expense | 1254000000 | 1254000000 | PASS |
| G4_captive_finance_capex_tag | PaymentsToAcquireProductiveAssets | PaymentsToAcquireProductiveAssets | PASS |
| G4_captive_finance_b07_status | NOT_MEANINGFUL | NOT_MEANINGFUL | PASS |

## Repair validation

| check_id | severity | status | details |
|---|---|---|---|
| validation_package_mode | P0 | PASS | mode=FULL_VALIDATION |
| no_company_identity_branch_in_production | P0 | PASS | no identity literals in production branches |
| registry_profile_matches_sic_rules_or_has_override_reason | P0 | PASS | registry profiles match SIC rules |
| rpo_crpo_prefers_instance_fact | P0 | PASS | B12 instance preference verified |
| basel_ratio_extractor_not_single_issuer_specific | P0 | PASS | Basel ratios verified |
| basel_concept_resolver_handles_tierone_spelling | P0 | PASS | TierOne spelling resolves to CET1/A02 |
| basel_concept_resolver_handles_banking_regulation_ratio_family | P0 | PASS | banking regulation ratio family matched |
| basel_cet1_never_classified_as_a01 | P0 | PASS | CET1 concepts excluded from A01 |
| basel_threshold_concepts_never_match_primary_metric | P0 | PASS | Basel threshold concepts excluded from primary metrics |
| basel_primary_selection_prefers_actual_ratio_over_threshold | P0 | PASS | actual CET1 selected over same-dimension threshold |
| a01_a02_metric_evidence_excludes_threshold_concepts | P0 | PASS | A01/A02 metric_evidence contains actual ratio concepts only |
| lodging_kpi_extractor_not_marriott_specific | P0 | PASS | lodging KPI checks passed |
| lodging_header_mapping_not_position_regex | P0 | PASS | header order swap parsed by name |
| lodging_revpar_adr_occupancy_identity | P0 | PASS | RevPAR identity within 5% |
| lodging_ok_recall_not_regressed_without_reason | P0 | PASS | lodging B10/B11 recall preserved |
| captive_finance_debt_not_ford_specific | P0 | PASS | B06 captive finance verified |
| captive_finance_signal_requires_segment_dimension | P0 | PASS | dimension required |
| captive_finance_excludes_normal_finance_lease_terms | P0 | PASS | normal finance terms excluded |
| enphase_b06_not_captive_finance_false_positive | P0 | PASS | no non-signal company is marked captive review |
| gm_like_captive_finance_fixture_triggers_review | P0 | PASS | GM-like captive segment matched |
| entity_continuity_yoy_not_paramount_specific | P0 | PASS | B02 continuity rule verified |
| no_c03_ecd_fact_count | P0 | PASS | bad_rows=0 |
| c03_def14a_ok_requires_peototalcompamt | P0 | PASS | all DEF14A_OK C03 rows backed |
| c03_uses_ecd_peototalcompamt_for_all_companies | P0 | PASS | C03 PeoTotalCompAmt generic gate mirrors DEF14A evidence check |
| c04_uses_auditorname_for_all_companies | P0 | PASS | C04 AuditorName verified |
| eleventh_company_smoke_extractors_mount | P0 | PASS | fixture extractors mounted and behavior gates pass |
| eleventh_company_behavior_lodging | P0 | PASS | lodging fixture extracted B10/B11 |
| eleventh_company_behavior_financial_institution | P0 | PASS | FI fixture selects actual A01/A02 ratios over thresholds |
| eleventh_company_behavior_captive_finance | P0 | PASS | manufacturing fixture triggers B06 NEEDS_REVIEW |
| eleventh_company_behavior_rpo_crpo | P0 | PASS | value=5000000000;note=RPO != ARR; cRPO != ARR |
| ok_status_recall_not_regressed_without_reason | P0 | PASS | snapshot_rows=120 |
| coverage_has_evidence_matches_metric_evidence_join | P0 | PASS | coverage join matches |
| numeric_ok_status_requires_evidence_row | P0 | PASS | all numeric OK rows evidenced |
| d04_missing_going_concern_has_explicit_text | P0 | PASS | D04 text explicit |
| existing_golden_results_still_pass | P0 | PASS | rows=57 |
| requests_log_sec_only | P0 | PASS | rows=634 |
| stratified_audit_all_pass_or_explicitly_caveated | P0 | PASS | rows=19 |
| existing_repair_validation_still_pass | P0 | PASS | all gates pass |

## Scalability gate

- `tools/check_no_company_literals.py` 写入 `outputs/scalability_audit.csv`，生产路径不得按公司名、CIK、ticker、固定 accession 或固定财年日期分支。
- `repair_validation_results.csv` 中 `eleventh_company_behavior_*` 必须 PASS；新增同行业公司应只改 `config/company_registry.csv` 和 `tests/fixtures/`，不改 `scripts/sec_pipeline.py`。

## 分层抽样 audit

| audit_id | source_bucket | company | metric_id | value | unit | status | audit_verdict | audit_notes |
|---|---|---|---|---|---|---|---|---|
| AUDIT_01 | STD_XBRL_DERIVED | Marriott International | B01 | 26186000000 | USD | OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_02 | STD_XBRL_DERIVED | Marriott International | B02 | 0.04326693227091633466135458167 | ratio | OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_03 | STD_XBRL_DERIVED | Marriott International | B04 | 2601000000 | USD | OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_04 | STD_XBRL_DERIVED | Marriott International | B05 | 2608000000 | USD | OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_05 | STD_XBRL_DERIVED | Marriott International | B06 | -0.006099177936886767435693450013 | ratio | OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_06 | STD_XBRL_DERIVED | Marriott International | B07 | 5.118665018541409147095179234 | ratio | OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_07 | STD_XBRL_DERIVED | Marriott International | B08 | 0.4267682781614670159561800429 | ratio | OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_08 | STD_XBRL_DERIVED | Marriott International | B09 | 358000000 | USD | OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_09 | DIM_XBRL | Marriott International | C04 | 0 | flag | DIM_XBRL_OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_10 | DIM_XBRL | Southwest Airlines | C04 | 0 | flag | DIM_XBRL_OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_11 | DIM_XBRL | Ford Motor Company | C04 | 0 | flag | DIM_XBRL_OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_12 | DIM_XBRL | Pfizer | C04 | 0 | flag | DIM_XBRL_OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_13 | DEF14A | Southwest Airlines | C03 | 16587882 | USD | DEF14A_OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_14 | DEF14A | Ford Motor Company | C03 | 27519558 | USD | DEF14A_OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_15 | DEF14A | Pfizer | C03 | 27585301 | USD | DEF14A_OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_16 | MDA_TEXT | Marriott International | B10 | 69.3 | percent | MDA_OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_17 | MDA_TEXT | Marriott International | B11 | 128.8 | USD | MDA_OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_18 | 8K_ITEM | Marriott International | C01 | 3 | count | 8K_ITEM_OK | PASS | value, period, accession, concept/section, and quote/concept align |
| AUDIT_19 | 8K_ITEM | Marriott International | E03 | 3 | count | 8K_ITEM_OK | PASS | value, period, accession, concept/section, and quote/concept align |

## NOT_AVAILABLE_SEC / NOT_EXTRACTED / NEEDS_REVIEW 清单

| company | metric_id | metric_name | status | notes |
|---|---|---|---|---|
| Marriott International | B03 | EBITDA margin | NOT_AVAILABLE_SEC | Required revenue, operating income, or D&A missing. |
| Marriott International | C03 | Executive compensation signals | NOT_EXTRACTED | No numeric ecd:PeoTotalCompAmt fact matched target fiscal year; C03 degraded from previous ecd_fact_count. |
| Marriott International | E01 | M&A announcements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no M&A item rule matched. |
| Marriott International | E02 | Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. |
| Marriott International | E04 | Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. |
| Marriott International | E05 | Material agreements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 1.01 found. |
| Southwest Airlines | D01 | Risk factors summary | NOT_EXTRACTED | Risk factor heading or theme evidence. |
| Southwest Airlines | D02 | Litigation disclosures | NOT_AVAILABLE_SEC | Legal proceedings or litigation text evidence. |
| Southwest Airlines | E02 | Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. |
| Southwest Airlines | E04 | Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. |
| Ford Motor Company | B06 | Debt-to-equity | NEEDS_REVIEW | Captive finance segment/dimension detected; industrial-only debt-to-equity unavailable. |
| Ford Motor Company | E02 | Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. |
| Ford Motor Company | E04 | Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. |
| Pfizer | B03 | EBITDA margin | NOT_AVAILABLE_SEC | Required revenue, operating income, or D&A missing. |
| Pfizer | B07 | Interest coverage ratio | NOT_AVAILABLE_SEC | Operating income or interest expense missing. |
| Pfizer | C01 | CEO / CFO changes | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 5.02 found. |
| Pfizer | E01 | M&A announcements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no M&A item rule matched. |
| Pfizer | E02 | Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. |
| Pfizer | E03 | Leadership departures | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 5.02 found. |
| Pfizer | E04 | Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. |
| Pfizer | E05 | Material agreements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 1.01 found. |
| JPMorgan Chase | A08 | Fee income vs interest income | NOT_EXTRACTED | Requires bank-specific revenue composition review. |
| JPMorgan Chase | A09 | Non-performing loans / NPL ratio | NOT_EXTRACTED | Requires credit risk table or reviewed dimensions. |
| JPMorgan Chase | A10 | Loan loss reserves | NOT_EXTRACTED | Requires allowance and loans denominator review. |
| JPMorgan Chase | A13 | Geographic exposure | NOT_EXTRACTED | Requires geographic dimensions or segment table. |
| JPMorgan Chase | E01 | M&A announcements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no M&A item rule matched. |
| JPMorgan Chase | E02 | Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. |
| JPMorgan Chase | E04 | Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. |
| JPMorgan Chase | E05 | Material agreements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 1.01 found. |
| Salesforce | E02 | Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. |
| Salesforce | E04 | Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. |
| Lumen Technologies | B06 | Debt-to-equity | NOT_AVAILABLE_SEC | Debt or equity missing. |
| Lumen Technologies | E02 | Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. |
| Lumen Technologies | E04 | Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. |
| Macy's | B06 | Debt-to-equity | NOT_AVAILABLE_SEC | Debt or equity missing. |
| Macy's | E02 | Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. |
| Macy's | E04 | Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. |
| Paramount Skydance / Paramount Global | B01 | Revenue | NOT_AVAILABLE_SEC | Revenue candidate chain from metric definition. |
| Paramount Skydance / Paramount Global | B03 | EBITDA margin | NOT_AVAILABLE_SEC | Required revenue, operating income, or D&A missing. |
| Paramount Skydance / Paramount Global | B04 | Net income | NOT_AVAILABLE_SEC | Net income candidate chain from metric definition. |
| Paramount Skydance / Paramount Global | B05 | Free cash flow | NOT_AVAILABLE_SEC | Capex chain allows PaymentsToAcquireProductiveAssets. |
| Paramount Skydance / Paramount Global | B06 | Debt-to-equity | NOT_AVAILABLE_SEC | Debt or equity missing. |
| Paramount Skydance / Paramount Global | B07 | Interest coverage ratio | NOT_AVAILABLE_SEC | Operating income or interest expense missing. |
| Paramount Skydance / Paramount Global | C03 | Executive compensation signals | NOT_EXTRACTED | No numeric ecd:PeoTotalCompAmt fact matched target fiscal year; C03 degraded from previous ecd_fact_count. |
| Paramount Skydance / Paramount Global | C04 | Auditor changes | NEEDS_REVIEW | 需复核: current auditor read from dei:AuditorName, but prior 10-K instance is missing or lacks AuditorName (prior_10k inventory row). |
| Paramount Skydance / Paramount Global | E02 | Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. |
| Paramount Skydance / Paramount Global | E04 | Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. |
| Enphase Energy | E01 | M&A announcements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no M&A item rule matched. |
| Enphase Energy | E02 | Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. |
| Enphase Energy | E04 | Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. |
| Enphase Energy | E05 | Material agreements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 1.01 found. |

## 产品化判断

- 可产品化：companyfacts 标准公司级事实、8-K item inventory、基础 risk heading/keyword 定性信号、请求日志/hash 证据链。
- 暂不可直接产品化：复杂 Basel/NPL/AUM/VaR 表格抽取、工业/金融维度债务拆分、DEF 14A 董事会结构化计数、复杂 MD&A 表格 KPI。

## Verdict: GO WITH CAVEATS

- 本 spike 未构建生产系统、报价模型、前端或 daily update 调度。
