# 0af0f717 D03 material timing: scoped independent review

**结论：NEEDS_FIX（历史包创建者身份的断言）；性能修复本身未发现来源认证或请求匹配退化。** 审阅精确补丁 `0af0f717333a82ab104440859564e17077020e69`，父提交 `85a2c56b3fff996dcbaab1dabdf383a4df6e39a7`。范围仅为两个实现文件、两个定向测试及本目录计时/旧包材料；未修改实现或执行真实调用。

## 需要处理的发现

**P2：白名单内的模块哈希可以互换，重新计算包 ID 后仍会被接受。** `d03_recorded_response_store.py:113-123` 只要求 `module_sha256` 为当前或历史两个 SHA 之一，`packet_id` 则是同一可修改包正文的内容哈希。把一个合法新包的模块 SHA 改为历史值 `89e46c2b...`，再用现有 `content_hash` 重算 `packet_id`，其五个文件、来源、请求、响应和审核结果均无需改变；后续检查仍会通过。反向替换也同理。`test_d03_recorded_response_store.py:75-90` 只检验全零未知 SHA 和 `LIVE` credit，未覆盖两个获准 SHA 互换。故现有实现能拒绝未知哈希和信用升级，却不能证明“任意哈希篡改均拒绝”或仅凭 SHA 证明旧创建者身份。建议把历史兼容绑定到受信的确切旧包身份，或把断言收窄为实际可证明的边界，并加入白名单内替换的反例。这个缺口只涉及离线包来源身份；返回值仍固定为零调用、无原生 Result/Run、无生产授权。

**并发文件修改的既有边界：** 冷读先在 `d03_recorded_response_store.py:124-129` 检查文件大小和 SHA，再在 `:130-134` 重新打开并解析。若另一个写入者在两次读取之间替换 `source.json` 或 `checked.json` 为语义相同但字节不同的 JSON，后续内容比较可通过，而实际解析的字节不再是刚才校验的字节。这不是本补丁引入的退化，也没有发现能藉此获得真实调用或原生信用；若验收要求并发写入下的精确字节完整性，应在同一次读取的字节上完成哈希和解析。

## 已核对的边界

- 记录在 `record_offline_response()` 内复制输入，然后经 `validate_candidate_response()` → `candidate_request()` → `_authenticated_original()`，从当前保存来源重建并核对来源和原始请求；之后只序列化复制件。调用者的源或请求在验证期间改变会触发 `D03_RECORDED_PACKET_INPUT_MUTATED`。冷读从盘上重新调用同一认证链，并比较保存的候选请求及审核结果；两次操作之间没有沿用先前认证结论。
- 默认 `validate_candidate_response()` 仍返回审核字典；可选开关仅在验证成功后追加返回已认证请求。显式请求仍必须等于重建请求，响应仍按已认证请求的 ID 检查。本人运行 `PYTHONPATH=scripts python3 -m unittest -q tests.vnext.test_regulatory_fact_review`：2 项通过，60.149 秒。未重跑完整大材料测试。
- 历史模块 SHA `89e46c2b...` 与 `c009ec97b9ac229c8202d1bd001bd1ea366d0c7d` 及父提交中的保存模块原字节 SHA 一致。保存日志报告旧包 ID `sha256:4bac51a935deadda11f456ba39f6976647fe2d5cd05fe194f89fbc7ef7ce02d6` 在禁网独立进程冷读通过，原响应 1350 字节、两项 unresolved、零调用、无原生结果；本人只核对日志与旧模块哈希，未重新冷读旧包。
- `before.log` 与 `after.log` 的同一材料测试分别为 116.660 秒、6 次来源重建和 80.409 秒、4 次来源重建；记录阶段 37.655→19.055 秒，实质冷读 36.909→18.686 秒。来源重建时间是包含在阶段时间中的分段计时，不可与总耗时相加。`final-material-tests.log` 报两项包测试通过，80.510 秒。这些只支持本地重复认证减少和本地运行改善；新 head 的远端 CI、D03 业务结论、真实 provider 响应及生产采纳均未核验。

工具调用：11 次 `functions.exec`、27 个内层工具调用（含一次 `write_stdin` 和本报告写入/核对/更正）；低于 80 次上限。没有调用 #47/PR52、没有真实业务请求、没有提交或推送。当前工作区中其他路径的已有改动未处理。
