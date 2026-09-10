# vNext formal publication bundle

- batch_manifest_id: `sha256:918784f24383b5ad5aa5d29a540389ccc50d1fa82a94665b451e0e1345904946`
- projection_manifest_id: `sha256:09a151fb95d49a84e16f040303ae352f8310a91958c1359aecb44d7a5d650e07`
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
