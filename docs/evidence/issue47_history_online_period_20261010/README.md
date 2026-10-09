# Historical online period ignored at the company CLI

Actual main f6ef7886. The run --call-context dispatch does not inspect or forward period/fiscal-year-start/fiscal-year-end; company_online.run_online_company only selects the latest current period. Both an explicit historical range and latest mode with history years silently enter that current path. The saved-source path separately validates years, so its correctness does not cover this online branch.

`reproduce.py` patches only the downstream online function to record actual CLI dispatch before any ledger or HTTP. It returns a deliberate FLOW_COMPLETED control, not a financial result. `actual-reproduction.json` shows both requests exit0, call the current-only function and omit all period/year arguments. No state, sources, ledger or network accessed. This reproduces argument loss, not a real paid execution.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python docs/evidence/issue47_history_online_period_20261010/reproduce.py
```

The public CLI owner has received the exact path/arguments and expected behavior. Until historical online selection/acquisition is implemented, these combinations must fail explicitly before calling online acquisition, reading its allowance, or writing state; valid current online and saved historical commands remain. The full historical discovery/supplementation responsibility remains, and this guard is not its completion. No second caller or controller is introduced here.
