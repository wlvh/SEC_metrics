# Issue #47 historical five-year evidence

当前开发入口：[#47唯一历史队列](https://github.com/wlvh/SEC_metrics/issues/47#history-simplification-20261006)，共同规则唯一正本为[#28今天的简化决定](https://github.com/wlvh/SEC_metrics/issues/28#collab-28-47-v1)。新开发按main短分支、小Draft PR及实际受影响验证接续；旧COLLAB v1.1–v1.3、同一大PR和旧防伪流程不再是新工作前置。公共AGENTS、CI、runtime及CLI由#28集成，本方维护历史说明、历史消费者和既有C02/D02共用核心。下列旧收据、失败和日志保留历史含义，不作为每个小PR必经检查。

历史公司入口的实际边界：main8588已交付当期公司入口；`fiscal-years`仍在PR52存量分支（本轮读取be366047），尚未入main。已完成并复用Macy两年B01保存来源后的范围计算、复跑/缺年与当期消费者验证。历史`run`要求预备`source-root`，其中“来源准备”只代表已保存来源的公司交接/导入；它不自行发现或获取缺少的历史来源，不是完整五年自动获取到CSV。历史发现/缺件声明已有`normal_history_plan`/`declared_frame`，补齐仍经独立获取入口和具体许可；把公司/期间/指标选择传入发现、缺件报告与必要补齐，再由同一公司入口调度计算/结果表，仍属H4/H6未完成接线。新路径消费#28轻量runtime/来源/读取增量，不再另造历史pipeline；原三公司五年先导和1950位置业务验收保持。

H1共用引文检查已从main短分支提交为[小Draft PR58](https://github.com/wlvh/SEC_metrics/pull/58)，尚未合入；本历史分支的`historical_legal_review.py`改为消费相同`legal_review_contract.py`，登记接口保留。14项短测试覆盖8份原失败回答/14条逐字但过长引文；全部12个原D02请求在内存逐字节重建相同，4份原合同通过回答解析结果相同、8份仍失败但报因为长度。历史侧12项形状/未决测试及1项原登记读取正例通过，不复跑整家公司；完整验证说明与必要夹具只在PR58维护。该报因修复不解决D02内容误纳/遗漏，不给旧失败补接受。

H3已提交为[小Draft PR59](https://github.com/wlvh/SEC_metrics/pull/59)，尚未合入main；本历史分支的B10/B11标准和旧年说明适配改为显式传来源/期间/政策，消费相同`read_selected_lodging_source`，退出表格读取中的`release_aware`/运行环境重写。Marriott保存FY2021–FY2025的已知值及当期消费者核对通过；公共短测试（14项）、定向完整原件（2项）和主要验证说明在PR59维护。上游历史DEI准备及公司任务固定版本/CSV接收仍待H4继续，不把组件验证写成完整公司或五年交付。

归档e1828579两项CI（37192293732/37192293730）已只读核到最终success，未重跑。PR58自动fast作业的119旧入口中两项`normal_annual_input`命中原30秒超时，无业务断言报错；新D02定向测试通过。公共CI分层由#28 T1集成，PR59补有最小DEI期间/主体反例供快速层消费，未放宽原时限或手工触发全量。

本轮不新增调用；原35模型机会不重复，SEC1771/1867。指定附件既有具体许可保留且未消费，此轮不执行。两年B01接线材料见[已保存验证](company-entry-history-2026-10-06/README.md)，不为说明修订重复运行。

Immutable development evidence for the Issue #47 historical backfill. Nothing
here is a publication, an adoption receipt or an acquisition authorization.

## baseline-ed8bf11/

`fast-suite-v2-jobs2.json` — `tools/run_fast_tests_v2.py --jobs 2` executed on
the unmodified development baseline `ed8bf11cbab76bc3d9b766d4b96d065a6cda10e6`
before any Issue #47 change, in the Issue #47 development container
(Python 3.11.15, `tokenizers==0.22.2` from `requirements-continuous-context.txt`).

Result: 122 selected entries, 121 return code 0, 1 entry at return code 124.
The single non-zero entry is
`tests.vnext.test_table_context_qualification_guard.TableContextQualificationGuardTest.test_missing_or_excess_usage_is_terminal_and_skips_ordinal_two`,
which is the runner's fixed 30-second per-case cap, not an assertion failure:
the same case run alone in the same container passes in 28.1 seconds. This is
an inherited environment boundary of the baseline, recorded as such. The count
122 is this report's snapshot, not a required future total.

## source-plan-2026-09-18/

`historical-source-plan.json` — output of `tools/vnext_history_plan.py --years 5`
against the repository's own saved SEC bytes. Regenerate with:

```
python3 tools/vnext_history_plan.py --years 5 \
  --output docs/evidence/issue47_history/source-plan-2026-09-18/historical-source-plan.json
```

The plan reads saved request bytes only. `calls` is `{"provider":0,"paid":0,"sec":0}`
for every company and `fetch_authorized` is `false`: producing it neither spends
nor grants any SEC or model business call.

What it establishes, per company, for the five most recent annual report ends:

* the target report end dates and their exact original 10-K accessions, taken
  from saved submissions metadata — never from a filing date or a calendar year;
* each target's prior-year dependency, kept as an input of that target rather
  than as a sixth output year;
* every declared document dependency, deduplicated by URL with all consumer
  relations retained, classified as `SUBMISSIONS_INDEX`, `SUBMISSIONS_HISTORY`,
  `COMPANYFACTS`, `ANNUAL_PERIOD_IDENTITY` or `ACCESSION_INSTANCE_DISCOVERY`;
* the saved state of each dependency, and where a target's own primary HTML is
  not saved, whether that accession's own authenticated XBRL instance already
  establishes the same annual period. That alternative closes the period
  identity dependency only; `substitutes_html_text_range` is `false`.

`fiscal_year` is deliberately `null` on every candidate. A report end date is
SEC metadata; the issuer fiscal-year label belongs to that filing's own DEI
contexts and is established when the document is read.

`complete_plan_proven` is `false` wherever accession index discovery has not
yet run for a target accession. Those accessions are listed in
`accession_indexes_not_yet_discovered`; the additional instance documents behind
them are reported as not yet known rather than estimated as a number.

## pilot-2026-09-18/

`historical-period-outcomes.json` — output of `tools/vnext_history_pilot.py` over the four pilot
companies' five most recent annual report ends. Regenerate with:

```
python3 tools/vnext_history_pilot.py --company marriott_international --company ford_motor_company \
  --company salesforce --company macys --years 5 \
  --output docs/evidence/issue47_history/pilot-2026-09-18/historical-period-outcomes.json
```

Every outcome is the real one: a value with its filing identity, a source limitation naming the
exact missing document, or an implementation gap. `calls` is `{"provider":0,"paid":0,"sec":0}`.

## coverage-2026-09-18/

`coverage-matrix.json` — output of `tools/vnext_history_coverage.py`. The frame is
companies × declared metrics × requested annual report ends, fixed before any position is
filled. The declared metric count is read from the installed policy and checked against that
policy's own `declared_issue_metric_count`, so D03 and the other pending metrics stay inside the
denominator instead of being removed from it. Regenerate with:

```
python3 tools/vnext_history_coverage.py --years 5 \
  --output docs/evidence/issue47_history/coverage-2026-09-18/coverage-matrix.json
```

Each position carries exactly one status under a fixed precedence, so a later limitation never
hides an earlier one: the period is not established from metadata; the period is established but
its own original document is not saved; the period is established but resolving it stopped, split
into a source limitation and a missing implementation by the failure's own category; or the
metric's own resolved outcome. No status here is a statement about what an issuer disclosed.

### baseline-ed8bf11/source-material-v2-jobs2.json

`tools/run_fast_tests_v2.py --suite source-material --jobs 2` on this branch, which is the tier
the three Issue #47 short entries were registered into. Result: 70 selected entries, 69 at return
code 0, one at return code 124.

The three Issue #47 entries all pass well inside the tier's 240-second per-case cap:
`test_normal_history_catalog` 19.0s, `test_historical_coverage` 28.7s,
`test_historical_period_results` 72.3s.

The single non-zero entry is `tests.vnext.test_normal_zero_ai_results`. It is an inherited
boundary, not a regression from this branch:

* the entry is pre-existing — it appears at line 47 of the base branch's own runner;
* this branch changes `tools/run_fast_tests_v2.py` only by appending its own three entries, and
  does not modify `scripts/vnext/normal_zero_ai_results.py` or that test at all;
* run alone in this container it passes, `Ran 10 tests in 263.053s`, which is 23 seconds past the
  tier's fixed 240-second cap. So this is the case genuinely exceeding the cap on this machine
  rather than losing a race for CPU.

Neither the test nor the cap was changed to make this green.

## reconciled-2026-09-18/

The plan and the matrix regenerated together on one commit, after the review
that rejected "only two decisions remain". `RECONCILIATION.md` in that directory
explains, per company, why the acquisition budget is 142 and not the 122 that
was quoted on Issue #47, and why 130 is a real number that was never the whole
budget. It also states the limited pilot this asks for — 22 requests over one
additional annual year for 8 companies — and says what that pilot is predicted
to establish, in a form that can be shown wrong.

`source-plan-2026-09-18/` and `coverage-2026-09-18/` above are kept unchanged.
They are the artifacts the wrong number was read from, and deleting them would
remove the evidence of how it was produced.

## github-ci-2026-09-18/

The hosted-runner conclusions for this branch, per commit, read from the GitHub
API rather than summarised. It records which run did not finish and the measured
reason, and it is deliberately separate from `baseline-ed8bf11/`: the local
records describe this development container and are not replaced by what a
hosted runner did. On one point the two disagree, and the disagreement is stated
rather than resolved in the branch's favour.

## frame-ceiling-today.json

How much of the 10 x 39 x 5 frame can be attempted at all, measured from
`plan_historical_sources` rather than inferred from a batch: **11 of 50 target
periods have their original saved**. Only Marriott has more than one, with
three; JPMorgan has none. So a batch over the eleven is not a sample, it is
everything currently reachable, and the three-company five-year pilot on the
open list is blocked on acquisition rather than on implementation.

## d02-content-read/

`finding.json` — the content read of Pfizer's D02 excerpt set, judged against
the approved source definition rather than against the selector that produced
it. Two claims in its first version were too strong and are withdrawn inside
it: the archived block dump prints 150 characters per block and cannot support
a judgement about a sentence further in, and `entity_scope: registrant` answers
which entity a disclosure concerns rather than who is speaking.

`pfizer-2025-scope-blocks.txt` — every block inside the four declared scope
ranges with its index, flags, full length and the first 150 characters. It
supports which blocks were selected, not what each one says in full.

`pfizer-2025-decisive-blocks.json` — the six over-taken blocks whole, each with
the byte span and span digest that locate it in the saved original, so the
quotes can be checked without trusting the file.

`audit-report-boundary.json` — the six filings read to settle where the audit
report ends, including the candidate rule that passes five of them and fails
the one it was written for.

`keyword-proxy-scope.json` — what the `_LEGAL` keyword proxy on Item 8 actually
carries across those six filings: seventeen blocks, fourteen of them correct.
Narrowing it would cost the fourteen to remove three.

## part-iii-statement-review/

`finding.json` — the review the approved amendment policy asks for when it sets
`original_statement_admission_requires_further_review`. Three independent
grounds, the recommended option and its counter-argument. No policy file or
clearing rule was changed: whether the finding should clear the input class is
a correctness standard, not an implementation choice.
