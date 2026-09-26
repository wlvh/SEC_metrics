# 8115b114 C04 来源续接差异独立审阅

审阅对象：`8115b114b1de73627aece35c26ee3417e7f66846` 相对 `ab584906d341ab42eb1155490f865e472acd8e48` 的新增差异；仅限委托指定路径和现行收据。**结论：NEEDS_FIX_P2；第二条真实 SEC GET 暂不执行。** 第 193 槽和当前 Marriott/C04 的 Company Facts 目标本身有正向证据，阻断原因是续接所依赖的前次报告待刷新集合未被认证。

## P2：可改写的待刷新集合被当作前次报告的授权范围

`ordinary_refresh_cycle.py:158-166` 只检查 `deferred_source_urls` 是非空、无重复的字符串列表；它既不与前次报告的已承诺摘要比较，也不从第 193 槽后的已验证来源状态重建并逐项比较。`ordinary_refresh_cycle.py:242-244` 随后把这个列表作为下一 URL 的许可集合。报告位于可写的外部路径，原始 `real-refresh-1.json` 的 SHA-256 虽记在执行说明中，却未在运行时检查。

只读对抗验证：从真实报告复制一份临时 JSON，仅在 `deferred_source_urls` 追加前次申报清单 URL；用真实第 193 槽收据/终态、原 C04 状态和当前来源日志调用 `_resume_one_c04_source()`，返回成功，许可集合含新增 URL，真实调用为 0。原报告实际只有 Company Facts URL。现行下一 URL `https://data.sec.gov/api/xbrl/companyfacts/CIK0001048286.json` 确实在原集合及当前 C04 `source_proofs` 中；发现的是认证缺口，不能据此说目标 URL 错误。最小修复是在续接时从已验证来源状态重建前次未完成集合并与报告精确比较，或用不可变、受运行时检查的报告摘要约束它；增加“只改待刷新集合即在申领前拒绝”的负例。不能只验证报告中的 `captures[0].source_url`，因为该字段已被现有收据比对覆盖。

## 并发边界与计数

`ordinary_refresh_cycle.py:202-209` 在账本锁内取得快照后释放锁；`ordinary_refresh_cycle.py:245-249` 在获取器外比较来源日志摘要，然后 `SecAcquisitionSession.capture()` 自己重新持锁。若同账本其他进程在两段之间申领，尤其是不会改变 SEC 来源日志的 provider 槽，续接检查无法保证第 193 槽仍是紧邻前驱；若 SEC 来源在摘要检查后改变，也没有在获取器锁内复核预期摘要。当前没有第 194 槽，来源日志摘要仍为 `6c5fa272fd25936bbcdb7fd344a0b25479c8c62da3edb7ef473ddaf4a659d4cf`。这不是已观察到的并发故障，但不能把预检称为原子保证。修复上项后，第二条真实请求仍应由唯一的 #28 账本执行者在即时复查 193/来源摘要后进行；若要允许并发执行，需要把预期前驱及来源摘要的比较移到申领所持的同一把锁内。

本差异未改变 `_call_accounting()`：已有短测验证只把本次 capture 记作自身调用，并在 capture 异常且账本 SEC 增量超出已收据数量时标记 `UNKNOWN`；账本缺终态的槽仍按原规则计数并停止通道。本次没有注入续接后真实传输异常；相关计数结论限于代码与短测，不是第二条 GET 的实测结果。

## 已核对的正向边界与未覆盖范围

- 真实第 193 槽为 Marriott 的申报清单 GET，收据 `SUCCEEDED`、终态 `[0,0,1]`；原报告与槽中收据/终态相同，来源日志摘要等于收据末摘要。原 C04 最新/成功尝试及终态可续读。当前账本止于 193，累计 `[143,143,50]`。只读预检把下一 URL 判为 Marriott Company Facts，角色 `companyfacts`，它在原报告待刷新集合与当前 C04 来源证明中。
- 本次两项执行文件的实际 SHA-256/大小与 V14 `baseline_manifest.json` 一致；现行 provider、SEC、refresh 三份收据的文件摘要与 `binding-summary.json` 一致，执行 authority hash 同为 `sha256:61d4320637a5ee0dd641a61567afb8de13317b048564afb81862fa943e9de982`。离线接线记录中的 refresh 校验使用了 stubbed SEC authorizer，不代表第二次真实传输。
- `requirements/issue_28_v13/baseline_manifest.json` 在两个精确提交中的 SHA-256 同为 `f6b5cb43bbf6255b5a54d141567117d6b53444c0ee5e657e23d69db1c0d5f162`；V13 目录、C04 控制器和 SEC 获取器没有这次差异。原 C04 状态的配置/终态在真实只读预检及本次对抗调用中均通过读取。单公司、仅 C04、单次 SEC 上限和旧报告在账本推进后的拒绝有代码约束及录制证据。
- 本人执行 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_ordinary_refresh_cycle`：11 项通过。读取已提交的 108.787 秒两来源录制测试日志及真实零 GET 预检日志，没有重跑长测。此次未发 SEC/provider 请求，未操作 #47/PR52，未验证并发压力、第二条真实 GET、后续 C04 数值结论或完整 390 坐标验收。

工具使用：16 次 `functions.exec` 编排、50 次子工具调用，合计 66 次；无长测重跑或真实请求。
