# vNext formal publication bundle

- batch_manifest_id: `sha256:3956a72dfec64017b6aca6adea00ad52af0ec3a21605589d4c5b2bb01d99ee0b`
- projection_manifest_id: `sha256:96d22e118418ea963e9419841858c08888a14c4a7cc50b2fa2b7e464b91b1ce8`
- rows: `327`
- boundary: formal PUBLISHABLE bundle; active only when the verified pointer names this publication

## 正式读取入口

业务用户继续读取 root `outputs/metrics_matrix.csv`、`outputs/metric_evidence.csv` 与根报告；内部读取必须先打开并 pin `PublicationView`。
root mirrors 不向未持有 PublicationView 的任意并发读取者承诺组原子。
rollback 只切换 active pointer 并恢复 mirrors，不会重新启用 legacy parser，也不会回滚 SEC request ledger。

## 验收

```bash
python3 scripts/12_validate_repair.py
python3 tools/check_validation_snapshot.py
```

Candidate-specific content validation; production authority is external to this immutable package.
Original OPEN Runs keep their execution rules. No Reader qualification or inherited-coordinate recertification.
Use PublicationView and internal/annual_complete_version.json for all 2 selected / 238 inherited bindings.
