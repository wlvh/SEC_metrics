# 往年 B06 的四个附注形式

在已恢复的 50 期间框架上，Enphase FY2024 有完整债务表、股东权益和明确无融资租赁陈述，却在固定最新版式的语法中被扣留。`stages.json` 保存逐步试验：维度化有效利率 → 明示往期本金余额 → 期权/权证股份数量 → 商业票据资产表开头的 `The`；前三步单独仍被后续具名检查扣留，不能当答案。

正式历史后继 `scripts/vnext/historical_note_carrying.py` 复用已有 successor / DEI 机制，仅改变以下四个库存判断，不改 #28 的 `b06_note_carrying.py`、普通入口、已批定义或任何旧 Run：

1. 标准 US GAAP `DebtInstrumentInterestRateEffectivePercentage` 的单一 pure 单位是利率，不是美元余额；自定义同名、货币单位或其它融资事实继续拒绝。
2. 整句余额断言仅归于一个明确、有效且早于目标期末的日期；引导句只允许已支持的回购描述，不能夹带另一金额、日期、当期或额外余额。
3. 期权/权证句里每一个被金额解析器抓到的量都必须无美元符号、紧跟 `shares`，才记为股份数量；混合现金、票据数量或借款句继续拒绝。
4. 同一个已明确可供出售债券资产表、同一 `Commercial paper` 行和同一资产前导句，仅允许开头加 `The`；不把其它表或借款行归为资产。

其它来源绑定、主文/XML附注一致、逐票据本金/费用/账面值勾稽、完整融资库存、当期无融资租赁依据、账表与同主体权益检查仍执行。没有公司名、CIK、固定申报、金额或财年分支。

## 全帧实测与阅读

`baseline-probe.json.gz` 是固定 `68025386` 加注册补丁、闭包 `ed67e401` 的 50 期间原级联及三个未安装试验；`frame-measured.json.gz` 保存正式后继与其中原基线的逐期比较。两份 gzip 的原始 JSON 可以解压查看，`frame-summary.json` 是轻量摘要。比较 stage、完整 selection audit、value / quality / publication / reason_code；不是全部原生对象身份的等价声明。

50 期间无异常。持久 JSON 比较只移动 Enphase FY2024：`WITHHELD` → `PUBLISHED / EXACT / PASS`，比值 `1.563451362278755750189672227`；其余 49 份投影完整 JSON 相同。初次内存比较还把 Macy’s/Paramount FY2025 的 tuple 与基线 JSON array 差别报作移动，持久 JSON 完全相同；保留原列表及更正原因，复用脚本现先统一 JSON 表示再比较。没有把这两项写作业务变化。

在建新 Run 前，既有、不导入债务路线的 `tools/read_debt_to_equity.py` 直接从 Enphase 原件读得：当期债务 101,291,000 + 非当期 1,201,089,000 = 1,302,380,000；股东权益 833,016,000；原文明示公司没有融资租赁，加入量 0。独立重算比值相同，原件 SHA 和行标题见 `balance-sheet-reference.json`。这是执行者的开发阅读，不是外部独立业务验收；原生 Run / 冷读 / 绑定阅读另行归档，不能用本探针代替。

## 检查与重现

新测试分开登记到 fast 的六个句式/表边界用例和 saved-source 的四个原件变体用例。原件变体在完整当期文件中加入标准 pure 利率（账面值与权益不动），再验证美元、自定义同名和其它融资事实不能漏过；资产前导句变体经过完整 inspector。另把八个既有附注原件反例交给新 inspector，全部通过，涵盖融资租赁缺失/历史/引用/矛盾、额外借款、未知组成、跨文档和单位冲突；完整历史债务模块 13/13 通过。

`injections.py` 仅在隔离 review 克隆中生成内存变体，九个改错必须由对应具名用例捕获。原件或冻结源文件不修改。快照新增这个历史规则文件，57 rule / 495 authority，继承 #28 authority 不变。零 provider / paid / SEC 调用，不执行 acquire / resume，不恢复原账本的 96 次余额。

实测重现：在使用当前历史代码、且已经自行 restore 来源的克隆中，执行 `python3 <本目录>/frame_compare.py <恢复根>/source-inputs <本目录>/baseline-probe.json.gz <新输出.json>`。脚本禁用网络，不建 Run；用 `python3 <本目录>/injections.py <新记录.json>` 重现注错，仅在隔离克隆执行。基线解压 SHA 写在实测记录里。正式接线只换历史 note inspector；其它六个级联阶段和所有其它公司的判断不变。
