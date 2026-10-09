# Shared short selectors: fixed receiving patch

PR75's existing statement-scope, source-inventory and current/history dispatch controls were not selected by its inherited foundation fast runner. This patch is fixed to PR75 `46c30d29712c7db05a4550417fa5f9bccc3c97f7`. It appends three existing class selectors to the v2 list and adds one explicit unittest step in the existing fast job. All sixteen methods run in one process; there is no new runner, long material, source/formula change or broad CI scope expansion.

Parent actually compared runner function ASTs (unchanged), counted the existing 2+5+9 methods, and checked `git apply --cached --check` against a temporary index of that exact commit. These are static checks, not actual consumer test passes. The receiver owns applying the patch and executing the command in its existing branch, then observing that head's real CI. No peer worktree, original ledger, Run or Result was edited. No model/SEC call or permission change.

```
python3 -m unittest -v tests.vnext.test_historical_statement_cases.HistoricalStatementScopeTest tests.vnext.test_historical_filing_inventory_small.ABlockIsHeldToThePriorYearWalksChecks tests.vnext.test_history_company_dispatch.HistoryCompanyDispatchTest
```

Use `PYTHONPATH=scripts:tools`, `PYTHONDONTWRITEBYTECODE=1`, and `TMPDIR=/private/tmp` for the receiver's existing macOS fixture rules. Patch and exact hashes are adjacent; previous PR58/62 shared test-foundation records remain under their original paths and credit.

## PR76 existing liquidity checks

Fixed580667f2 requires only its new two-method HistoricalLiquidityScopeTest in the existing selector list/explicit CI command. HistoryCompanyDispatchTest is already selected as a whole class and now has10methods, so no duplicate per-method registration is added. The actual source classes count2+5+10+2=19. Parent compared unchanged runner function AST and checked cached patch application on that exact tree; actual tests/CI are the receiver's next action, not parentPASS. No controller/source/Result change or rerun of existing historical materials.

## PR77 capital and PR78 bank boundary controls

Fixed PR77 e3339f46 receives only its five-method capital class. Fixed PR78 a457040a first receives that same patch, then two bank classes (2+4methods). The existing whole dispatch class automatically covers11/12methods; no per-method duplicate is added. Totals are25 and32 respectively. Each patch appends v2 selectors and extends the existing single-process CI step; runner function ASTs are unchanged. Temporary indexes verified exact fixed-source patch application and expected resulting two-file bytes; no peer worktree or runtime was edited. This is static coverage/application validation, not a parent rerun of historical inputs or new acceptance. The receiver runs the command and observes its real new head CI.

## Joint receiving seam for PR58 / PR62

Actual fixed372f4b74 +09563892 merge-tree conflicts only in v2 appended selectors and the two explicit CI steps. The adjacent patch resolves that exact virtual merge tree621ce1b5 by preserving all four independent selectors and both existing short steps; runner functions are unchanged. Temporary-index application and final two-file hashes are checked. Each existing branch passed its own tests/CI; A subsequent actual joint30-test execution passes0.006s/zero skip: fixed combined source/test modules loaded in one process,66actual imported project files byte-equal to that tree, five exact fixtures. The adjacent verification/log preserve this scope; it is not a new whole-company or model run. The receiver still observes its actual merged-head CI. PR67 now receives PR61 explicitly at5496164a, retaining all tested5f production/tool/test/workflow bytes;34 short controller/partition regressions pass0.146s. This removes the previously assumed61→67 mergeability gap, without addingH1/H2 to67.

The one-shot joint verifier takes --code-root (a clean main-compatible tree) and --objects-root (an existing repository with both fixed commits). It regenerates the merge tree locally, so it does not depend on this machine's unreachable temporary Git object or fetch/create a new workspace. It rejects any imported project dependency that differs; expected local roots are command inputs, not result authority.

2026-10-09 已固定PR81/cf78cf3c与PR82/d279dcd0，只补其新增annual4/period4 class进入原runner末尾及现有单进程显式CI命令。原whole dispatch自然13项，不重复逐方法登记；runner函数AST不变。父在隔离的Git精确源码/元数据树实际37例0.051s、41例0.054s均通过（whole命令0.688/0.558s），不写对方工作树、不重跑公司财报。初次元数据树缺known_result_defects导致一个环境错误，补该固定树实际文件后过；不改业务预期。新补丁/日志/固定摘要在本目录，先导源/旧结果不改。

该后续短测试包不扩大10月9日首批61/67/71/58/62范围；71两个已有历史测试触发/显式执行由#47负责，本方没有为71另写补丁。
