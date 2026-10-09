# D03 开发审阅 CLI 保存与读取增量独审

结论：**PASS_LIMITED_DELTA**。本次未发现该显式开发 CLI 必须修复后才能交付的缺陷。结论只覆盖保存、原生输入重读及权限边界；它不认可 D03 语义、公司结果、真实 DeepSeek 执行或生产采纳。

## 确切范围

检查提交 `f5db8911a47ef1b6e08551f7a2946ec5734e68ee`，比较基线 `2ab895d45b5051f415e07c62f87e74179afd086d`；开始、结束 HEAD 相同。仅复核 `tools/vnext_d03_model_review.py`、`tests/vnext/test_d03_model_review_cli.py` 及 fast runner 追加的一行 selector。工作树三项产品字节与提交和父 `binding-impact.json` 一致，摘要见 `identity.json`。

未变 mapper 的既有有限独审复用 `d03-model-native-mapping-20261004/independent-review/conclusion.md`（对象 `ccb0c5e65cda6150b66bc07081ba0b7329bb152d`），未重做其全部引用/语义边界探针。本轮检查 mapper SHA256 为 `72fa2fb42c145f2a0a2c85106ebc8f7d9db5a23350183afd21d57c0240187ee1`，与既有证据和基线完全相同。

读取了实际 AGENTS.md、相关架构/能力/行为/测试/发布边界、Issue #28 实时正文及第5.8节；服务器 updatedAt `2026-10-03T18:15:44Z`，原读入正文保存于 `issue28-read.json`。GitHub治理元数据读取不属于 SEC/provider 业务调用。现有自检和 README 只作定位入口。

## 独立执行与判断

1. 必需短命令 `PYTHONPATH=scripts:tools /private/tmp/issue28-tokenizers-venv/bin/python -m unittest tests.vnext.test_d03_model_review_cli` 独立通过：4项、0.165秒，见 `unit-test.log`。这些是合成输入测试，不是业务语义验收。
2. 新进程实际调用 CLI `read`，socket/subprocess 禁用，重新读取真实 Marriott 原来源和六组已存 request/response、四原生记录、完整 context 与 display。4.155秒通过；外部 Candidate `sha256:92dcda707632a0fbf661cd0704661e70ec5b8391bd6519fcb5cb55a3040b0cec` 与 ReviewUnit `sha256:7d4d085ed67f317e6f2e78a11be1751fd1b60f1cfe4d5096942ebc4154e2e705` 完全相同。私有原包17个文件前后摘要相同。只导入 CLI 并写本目录日志，没有执行会写父摘要的原 `cold.py`。见 `actual-cold-read.log`。
3. 另执行46项有意义的 CLI 探针：36项拒绝、8项正向控制、2项下述范围观察，0.341秒。全程禁网/禁子进程，临时合成输入与输出仅在新建 `/private/tmp` 根，结束自动清理。见 `independent-probes.log`。
4. 在7个不可变写入位置分别中断：每次最终 `records.jsonl` 均不存在，CLI读取失败；同一输入恢复保留所有先写字节并重建同一 PENDING 记录集。完整输入/来源/请求校验在首次写入前发生；最终记录最后写入。沿用原不可变 writer 的完整临时 inode、no-overwrite hardlink 和锁，未扩建存储机制。
5. 错来源摘要、重复JSON键、非法manifest/row、空请求、request或response改字节、重签manifest试图替换旧包、后部wire/record冲突均拒绝；已存在字节不覆盖。外部 Candidate/ReviewUnit错误拒绝；包内文件/目录symlink、额外symlink及输出root alias拒绝，代码根、真实账本根、已有active publication根和相对根均拒绝。
6. 新CLI只调用已审mapper，manifest摘要与真实wire字节逐项核对，完整来源仍从既有来源准入路径认证；读取仍要求外部原生身份，重建后精确比较记录/context/display。保存和读取输出均为 ReviewUnit `PENDING`，Candidate `REVIEW_REQUIRED`，scope为空，SYSTEM disabled；Result/Run/provider attempt/production全部false，调用为0/0/0。没有用Evidence机械PASS授予语义信用。
7. 基线、检查提交和当前工作树确认 mapper/Spec、普通默认入口、旧D03验证器、Review、不可变writer、真实调用配置均未变，V13/V14 authority目录无改动。runner只追加新selector，产品调用搜索未发现正常生产路由接入。见 `protected-paths.log`。

## 读取范围的明确限制

新保存的 `development-input.json` 是保存时的来源定位附件，**CLI read 不验证这个附件本身**。探针实际删除它或将其公司/来源摘要改成伪值，原生重读仍返回原公司与同一 PENDING 身份。其原因是read复用原mapper，从metadata和实际保存wires重建来源与原生记录；附件不属于那四项记录的身份。

本次把它视为 README 已声明“outside the unchanged four native records”的范围限制，而非原生输入错误接受：改变附件不能改变已验证的来源、响应、公司身份或获得信用。因此不能将本结论扩大为“全部17文件或manifest历史定位均由read认证”，下游若要用附件证明输入定位历史，应另核附件摘要。原生真实输入与外部身份绑定仍通过。

没有执行全fast、390、其他公司/修订多文档、业务正反例/人工语义、真实工厂增加身份后的资源核对、DeepSeek/live、生产更新或正式采纳；旧mapper完整独审和其他selector证据只按未变范围复用。没有完整公司新增成功。

## 资源与现场

开始UTC `2026-10-03T18:48:29Z`，完成UTC `2026-10-03T18:55:08.068737+00:00`，墙钟6.65分钟；保守最终工具计数43（9次functions.exec包装＋34次内嵌工具），普通消息2，无问题/子代理，未接近80工具或90分钟上限。见 `review-accounting.log`。

只向本独审目录写日志和这一份结论；没有产品或父证据/私有原包修改，没有commit/push、provider/SEC/account调用、#47/PR52操作、长测试或archive/tar。开始已有 `execution-state.json` 修改，未接触它。记忆仅提醒有限验证不能升级为广泛验收（MEMORY.md:440–446）；本次事实均按当前提交、代码及执行核验。
