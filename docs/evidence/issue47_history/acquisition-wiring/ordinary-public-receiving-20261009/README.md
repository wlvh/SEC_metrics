# 原历史SEC账本的公共调用接缝接收

固定公共PR94/20398f3e，接续原一次EX99/零重试，不增加用途/额度。实际原根SEC_metrics-issue47-sec-ledger-resume-20261006保持，只读检查不构造Capture、不加锁或写账本。

原HistoricalCallLedger.snapshot .486s核1547槽+224保守数=1771、blocked为空；原binding限1354保持。新company_online._ledger显式E01上下文/snapshot/check_request 1.476s核有效1354+513=1867、窄用途1772，claims SHAa238db91…1262、2531日志；指定URL通过，错URL及refresh均OUTSIDE_BOUNDED_PURPOSE，counter主要文件/镜像/resume/CSV/manifest前后相同。运输配置身份已验证、不输出contact，旧CSV是当前14列；读库测试不代替真实根核查，不等于GET已执行。

向实际Capture.get请求前路径再做内存预检：不构造Capture/transport，claim/socket调用即失败，原上下文没有requirement_closure_hash，该函数无条件读取该字段而在claim前KeyError。历史claim只用requirement_id；不编造hash或重铸旧包绕过，不报缺新许可。公共#28已收到此具体迁移缺项，修后重做这一受影响预检再决定原获准动作。旧counter和单次机会未消费，原模型35等不动。

所有操作新增SEC/provider/paid/Run/接受0，完整旧计划/响应/slot/失败保留。原许可仍是指定Paramount FY2024附件、最多1GET、retry0、1771→最多1772，UNKNOWN不重试。源只有开发用途，不回填旧Run或复用旧模型额度。代码只在独立接收worktree使用，未修改公共作者树、主分支或实际active。

## 原一次动作已完成

公共后继ca457364已修缺closure历史路径，真实根运输前检查到claim边界而未申领，原上下文不伪造旧哈希。实际执行只用该固定版本、原root/source-inputs、同一指定URL、最多1GET/0重试，不走宽发现。HTTP200，原件18964B/SHA0baae3b3…8e7e8，2.453秒；原计数1771→1772（1548slot+224），2532请求行，旧binding不改、旧claims精确prefix，model0，terminal/receipt全保存。原一次机会永久消费，不再GET；有效总额1867的余额95不授其他用途。原HistoricalCallLedger.snapshot再次.484秒读1772/无block，验证了旧读取，不以小模拟账本代替本次实耗。

原件完整阅读是2024年4月29日新领导层公告：Bakish离任、三人CEO办公室；2019合并为历史背景，履历里九内部业务整合/影视合作不是本期并购公告。按既定内容确认定义，该附件对应未决item的开发参考为非并购，见attachment-development-reference.json。不改旧请求/回答/Run/失败或年度E01结果，不给旧模型包或全年计数信用。现有historical_event_attachments实际读取父原件/精确link和新原件，返回VERIFIED_SAVED_SOURCE/new_acquisition_required=false，见ex99-attachment-consumer.json；下载后必要消费者接点已核，后继完整输入/独立目标模型及全年结果仍待原权限。

ex99-increment.tar.gz是本次最小可取得增量，含原件/headers、当前源CSV/manifest/registry及1548slot审查记录；index逐成员SHA。没有复制完整来源/程序树。解包到新目录后，既有_Sources只读读新附件逐字节同一；restored-source-read.json保实际恢复核对。它是源材料及调用事实备份，不初始化/恢复新的可执行账本或许可。已有旧源版本不能原地覆盖，以免旧结果漂移；后继来源版本须在新目录使用当前源CSV及两原件文件，其余来源依原已提交导出恢复。若当前源CSV已经9cb8adec…9dc，只核缺件，不重复追加或GET。

旧source-only导出仍按旧版本解释；本增量不重签旧export/checkpoint，也不改变正在使用的运行包。初恢复记录器误取item['proof']（实际proof在reader.proofs）失败，修后仅读取已解包目录，不重取材料，原失败保留本地work。

现行E01输入消费边界进一步核对：historical_ma_confirmation.confirmation_request及SYSTEM_PROMPT明确只读每个item自身text，validate_answer只许quote为该text的子串；历史e01_confirmation_request仍走此V1。附件依赖已取到并验证不等于现程序把附件提供给抽取上下文。后继输入需显式保父item全文及独立附件全文/SourceReference/proof、在独立源上定位quote，并有不同输入/请求身份；不能把附件拼进原V1text或给原35包/旧回答补成功。指定来源已获准，后继开发接线可继续；任何新目标模型执行仍无额度，完整年度E01接受未证明。此为具体消费者开发缺口，不重新申请已批准的GET、不重启旧批次、不引入压缩/第三轮模型试验或新的信任证明层。

## 完整附件输入接线（分支开发，未改变公司执行分派）

`historical_e01_incorporated_input.prepare_incorporated_e01_input` 从原已保存 V1 source 对象消费整个候选池，调用已有附件依赖和普通来源读取器；只给声明中的父 item 增加独立附件全文、完整原 HTML、块位置及 SourceReference。八个原 item ID/全文/窗口不变；实际附件 18964 字节、50 个来源证明验证通过，准备 3.815 秒。新输入合同为 `E01_SUPPLIED_ITEM_AND_INCORPORATED_TEXT_V2_DEVELOPMENT`，请求身份与旧请求不同。

实际输入、完整两消息请求及本地计量已提交为本目录的 `e01-incorporated-*.json.gz/json`。既有 `continuous_semantic_calls.request_body` 封装后逐项核对，供应文本、原 HTML 和位置保持相同；既有参考 tokenizer 计量输入 53761、输出预留 4096、总 57857，原上限 200000。这个数是本地参考计量，不是服务商实耗或执行批准。gzip 只保存文件，不改变解码后的模型输入；没有筛掉候选、压缩源文本或提高输出预算。

`validate_incorporated_answer` 将源定位约束到相同 item，区分并购、非并购及材料不能判断；只机械核对结构、类型、逐 item 完整性、原文匹配和原 20–600 字符合同，不判断法律/交易含义。29 个短回归 0.012 秒通过、零 skip，包含跨 item 引用、幻觉引文、缺源、缺答、重复答、类型错误、真实但过长引文和旧 V1 拒绝新格式。构造答案只用于控制测试，不冒充真实模型结果。原 V1、旧回答、原注册、失败和 Run 未改。

复核保存输入可直接解码本目录文件；重建时在新的来源目录使用已提交 SEC 导出的 `restore`，再消费上面的 EX99 源增量。它只是来源恢复，不能把增量审查记录初始化成新执行账本。原 source 对象从已提交模型归档抽取，不依赖本地未提交阅读材料：

```bash
mkdir -p work/e01-incorporated-review
tar -xzf evidence/issue47_model_calls/9a368413797ddef1/model-ledger.tar.gz \
  -C work/e01-incorporated-review root/calls/0005/source.json
PYTHONPATH=scripts:tools:. python3 -m unittest -v \
  tests.vnext.test_historical_e01_incorporated_input \
  tests.vnext.test_historical_event_attachments \
  tests.vnext.test_historical_ma_confirmation
```

```python
import json
from pathlib import Path
from vnext.historical_e01_incorporated_input import prepare_incorporated_e01_input

original = json.loads(Path('work/e01-incorporated-review/root/calls/0005/source.json').read_text())
prepared = prepare_incorporated_e01_input(
    data_root=Path('/absolute/new-source-root'), predecessor_source=original)
```

原归档成员和新保存文件 SHA/字节数见 `e01-incorporated-real-input.json`。当前交付是可复用的真实完整输入及纯后处理接口，历史公司 E01 默认执行仍为 V1；新目标模型执行为 0，年度结果未创建，没有为旧未决 item 补信用。后续仍需把显式后继规则接到同一公司模型消费者，并在有效用途/调用条件下核对完整年度内容。本次不默认申请或执行下一轮。

后继纯汇总summarize_incorporated_answer先执行新来源引用检查，再将“供应材料不能判断”显式适配到既有confirmed_count的全窗口规则。只要一个未决，proposed_count=None并列准确item，不能报告部分计数；全部回答完整且机械通过才给开发提议数，semantic_acceptance_proven/metric_result_created仍false。两项新增控制覆盖已确认+未决、完整计数和缺答拒绝；与原回归共31项0.013s零skip（e01-incorporated-summary-tests.log）。完整保存请求字节/计量不变、无新模型或年度结果，不把此汇总接到旧V1/旧Run补信用。
