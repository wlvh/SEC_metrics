# Macy’s FY2025：完整原 D04 回答进入当期公司入口

本次使用 actual main `e16ca31653886aecb1a254696f84849b3e8f03c5`，只有本文件及验证脚本/收据未提交。没有改生产函数、提示、模型/限额、原来源或响应，不重复已完成的 Salesforce/Southwest/Enphase 公司链。

## 实际用户路径

```bash
python3 tools/vnext_company.py run --company macys --source-root <完整保存来源根> \
  --metric D04 --work-dir <新的公司状态目录> --output-dir <公司输出父目录>
python3 tools/vnext_company.py results --company macys --state-root <上述状态目录> \
  --output-root <新的日常读取目录>
```

真实来源准备、请求与旧响应核对、完整组检查、现有汇总/Calculator、普通记录保存和CSV走当前正式入口；不替换为旧Result或mock成功。网络、DNS、SDK send及新调用申领均设置尝试即报错。独立 results 是新进程，D04处理和Calculator代码禁止。

原调用165—169五组都为真实SUCCEEDED，对应同一来源 `e614739d…`。5＋4＋4＋7＋2单元恰好覆盖全部22个规定来源单元，无重叠/遗漏，详见 `original-group-map.json`。五个原接受记录均是零发现，这是原模型的实际回答，不是构造空控制；没有因此独立证明模型未漏报。

当前新普通Result为 `sha256:a2a0bb5fe143c07d445284f9b0d3def00f887440032ac1031a3e31bfc3aa2069`，WITHHELD/null、`D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE`；公开行为 TEXT_QUAL，说明限定保存的完整年报/本期修订、可见及原生事实/续接对象，不是财务健康保证。

## 非自然年与来源范围核对

Macy’s本报告 **FY2025 = 2025-02-02至2026-01-31**，不是按结束年推FY2026。原申报 `0001628280-26-021721`，CIK794367，原 `m-20260131.htm` SHA256 `47e1df1c9e94a3e0de3def3d714f16496c25f6461504899e4476b203bb91f4c7`。Root实际读原HTML的 `dei:DocumentFiscalYearFocus`=2025，并核对保存的财政标签解析及实际期间；见 `original-period-authority.json`。与既有Salesforce FY2026虽然同为2026年1月结束，各自标签责任不混用。

## 实测

| 阶段 | 秒 | 结果 |
|---|---:|---|
| 首次正式公司处理 | 78.863 | CANDIDATE_WITHHELD、完整公司结论/CSV与来源证据 |
| 真实处理/计算函数 code guard 禁止后的复跑 | 0.121 | PREVIOUS_INPUT_WITHHELD，同Result、计算/新候选false、无新结果目录 |
| 独立新进程 results | 0.442 | 同FY2025/期间/CIK/TEXT_QUAL/出处，不计算、不写原状态 |

7个结果文件共32,672字节；独立读取保持17个状态文件。原165—169所有调用材料、claims/binding及来源元数据共100文件逐字节保持。原terminal/Run/Result不改签，原response没有成为新请求执行；本段新增SEC/provider/paid **0/0/0**。

`verify_company.py` 给出可重复的离线 CLI 演练，要求新的本方/审查方状态目录和完整保存材料，不覆盖旧任务。`first.json`、`repeat.json`、`independent-read.json`、`summary.json` 分别是实际执行收据；不是取其他机器/指标的时间拼比例。已经安装的Python3.12.14/tokenizers0.22.2环境用于原请求重建，默认配置与4096/200000不改。

期间/CIK/原件哈希及请求组完整性、处理/保存/读取实际成立；内容遗漏/真实模型准确性和正式采纳仍分开。本次不全读整份财报，也不以零发现或完整unit覆盖单独支持全面无疑虑结论。既有完整组/缺答/未决负例及当期D04接线证据按未变责任复用，不为仅增一份公司实测全套重跑。

证据定位时最初按下游text candidate寻找source_assessment字段，实际下游selected为空；没有把这一诊断脚本形状假设当业务错误。改读原组接受记录及实际完整汇总，原公司链没有重复执行。原历史路径/证据文件在轻量main不全存在，直接按固定提交或保留原workspace读取，不重新制造这些材料。

代码未改变，因此作为独立 evidence-only 提交供接收阅读，不新增功能PR/runner/台账。当前39项、正常更新、390和旧入口退出责任仍未完成；不Ready、合并、正式采纳、部署或active。Goal仍推进原范围。
