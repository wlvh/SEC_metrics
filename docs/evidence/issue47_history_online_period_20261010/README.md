# Historical online period ignored at the company CLI

Actual main f6ef7886. The run --call-context dispatch does not inspect or forward period/fiscal-year-start/fiscal-year-end; company_online.run_online_company only selects the latest current period. Both an explicit historical range and latest mode with history years silently enter that current path. The saved-source path separately validates years, so its correctness does not cover this online branch.

`reproduce.py` patches only the downstream online function to record actual CLI dispatch before any ledger or HTTP. It returns a deliberate FLOW_COMPLETED control, not a financial result. `actual-reproduction.json` shows both requests exit0, call the current-only function and omit all period/year arguments. No state, sources, ledger or network accessed. This reproduces argument loss, not a real paid execution.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python docs/evidence/issue47_history_online_period_20261010/reproduce.py
```

The public CLI owner has received the exact path/arguments and expected behavior. Until historical online selection/acquisition is implemented, these combinations must fail explicitly before calling online acquisition, reading its allowance, or writing state; valid current online and saved historical commands remain. The full historical discovery/supplementation responsibility remains, and this guard is not its completion. No second caller or controller is introduced here.

## Public repair received and historical consumer verified

Public PR122 `ea7a1aaa8fa7376422578925348117b1888a9c61` adds five CLI lines after parse, before any online context/ledger/HTTP. Received as 5ad1d000 on this evidence branch; the production change is entirely public-owned. Its existing company-online tests/workflow are the automatic protection, not a new history runner.

The same four historical consumer methods now pass, together with existing dispatch and saved state controls: 27 tests/0.438s/zero skips. Original failure 4 tests/0.326s with 2 failures/1 error remains in guard-before.log. Constructed current online test confirms original arguments are forwarded; it is not a real acquisition.

`verify_entry.py` additionally starts separate actual CLI processes with online operation and socket connection forbidden. Historical online range and latest mode with either year bound exit2 explicitly; the call-context path does not exist and neither invalid state nor output directory is created. No allowance read or capture can occur. The saved-source JPM FY2021 B01 command actually reuses its existing result with historical factory/amount source/graph forbidden: 3.223s, NO_SOURCE_CONTENT_CHANGE/calculation_performed=false. Separate results read takes0.854s. All380 prior result/pointer/check files, including the other years and bank metrics, remain byte-identical. This does not redo the prior twenty structural calculations or expand their industry applicability claim.

The new guard closes the silent period-loss defect only. Historical online source discovery/supplementation remains unimplemented, not cancelled; prepared saved sources continue to work. Actual main remains f6ef7886 until public receiving. No merge/Ready, SEC/provider/paid call or business acceptance.
