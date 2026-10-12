# Salesforce FY2026：原D04回答进入普通公司结果

本次复用原152–156五组真实响应，没有模型/SEC网络、没有新申领、没有改签旧回答。正式公司run选择Salesforce/D04，从新空任务开始，来源匹配、请求与原执行重验、完整组检查、既有文本汇总和普通结果保存都走真实实现。外部网络/DNS和CallLedger.claim设为调用即报错，不替换结果工厂为成功。

## 用户读到的结果

实际注册人CIK1108524、申报0001108524-26-000060、原crm-20260131.htm；公司CSV保留发行人FY2026，实际期间2025-02-01至2026-01-31。Result为：

`sha256:04d871d8e70b59a77db1b2aa305d21c2588c2600be542bb87920b27735f55207`

它与原 `d04-remaining-20260922/native-results/salesforce/summary.json` 完整ResultID相同。公开行是TEXT_QUAL，原生WITHHELD/null，原因D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE：在保存的规定年报/修订、可见及原生范围内未发现持续经营疑虑披露，不保证未来财务健康，不替代正式内容接受。

五个实际响应涵盖25个必答单元，全部组对应原源/请求，原响应发现数为0。这是真实零发现回答的公司级处理，不是合成空控制；它也不是对模型漏报率的独立证明。非空真实回答的公司接缝继续复用已完成Enphase173–178材料，不为本轮重跑该长链。

## 实际执行及恢复

系统Python3.14缺少已锁定tokenizers0.22.2，首次3.655s在请求准备前形成INPUT_OR_EXECUTION_FAILED。原log、报告及失败结果目录保留，没有把程序环境错误当成披露不足。依现有requirements-continuous-context.txt的版本/哈希，在代码树外独立Python3.12环境安装（--no-deps/--require-hashes），没有变模型、4096、输入限额、提示或真实用途。

在同一失败任务上恢复后，首次完整处理86.494s，退出2/CANDIDATE_WITHHELD，保存上述结论及CSV/出处。随后同一输入复跑：prepare_current_d04_case设为调用即报错，0.062s返回PREVIOUS_INPUT_WITHHELD、calculation_performed=false、new_candidate_created=false，同一ResultID。

独立系统Python3.14进程（无tokenizers）执行正式results入口，0.130s退出0，输出相同FY2026/期间/ResultID及CSV/证据；读取不需请求构造依赖，不重放模型。成功结论目录7文件、33,420B；另一个目录仅保首次环境失败的write.lock/failure.json，不能把两个目录说成两份业务结果。独立读取前后所有9个结果区域文件哈希一致。

原152–156及claims/binding共97个保护文件哈希保持，0新SEC/provider/paid。读口明确显示SAVED_RECORD_CHECKED_CONTENT_NOT_ACCEPTED、SOURCE_FRESHNESS_NOT_CHECKED（实际JSON为NOT_CHECKED_BY_SAVED_READER）；读取不是新的来源发现或业务采纳。

```sh
# 构造/处理需要既有锁定tokenizer；读取不需要它。
python3 tools/vnext_company.py run --company salesforce --metric D04 \
  --source-root /path/to/original-ledger/source-inputs \
  --work-dir /path/to/new/state --output-dir /path/to/output
python3 tools/vnext_company.py results --company salesforce \
  --state-root /path/to/state --output-root /path/to/read-output
```

需要原账本已有且与本次源/合同对应的五组回答；仅有SEC原件的新来源不自动获得模型判断。旧答案留计算侧，不打入SEC来源包；新用途/调用仍按原权限。实际演练使用verify_company.py及原私有账本，初始失败与恢复日志分开。只替换网络/禁止新申领和复跑工厂，不mock安装/选择/计算/保存为成功。

源码实际基于本地d31884db且带本证据未提交文件，未倒称后来公开SHA执行。D04代码与当前main对应；B06独立增量没有改D04处理。没有新生产代码变化，因此原完整组缺响应/未决/错误身份/失败不覆盖旧成功的有效回归按未变字节复用。原Record状态、Native Result及五次调用保，未给全390或生产权限。
