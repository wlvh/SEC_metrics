# a5a3ceba 限定独立复核

**结论：NEEDS_FIX（P2，单次一条 SEC 请求的新增年报续接无法前进）。** 仅审阅 `a5a3cebaa8d640821c0054eba1973992f597608c` 相对 `fd1f18933e134262bf04e887c012adf1320d2a1b` 的指定增量；前两轮混合模式审阅结论按原范围承接，没有重审旧代码或重跑长材料测试。

`normal_source_requirements.py` 从已验证的本公司 submissions 原件选择当期 10-K/10-K/A，并先声明主文件 URL；新增 `_c04_declared_annual_url` 只接受同 CIK 的已验证 submissions 清单。首次混合 C04 调用若在刷新 submissions 后发现该年报主文件尚未保存，`prepare_case` 的确切 `SAVED_SOURCE_MISSING:<年报URL>` 可由第 343–348 行识别，且只会把角色恰为 `current_annual_primary`、状态为 `MISSING_SAVED_SOURCE` 的该 URL 交给来源模式。非 C04 角色、其他 URL 和其他错误不会走此入口。获取器在真实申领前仍重新发现公司来源、核对官方 URL 与账本，并以 `source_only_c04=True` 记录；本次测试只模拟了捕获，没有证明新财年实际原件或后续 Run。

**阻断发生在下一轮。** 前次 submissions 获取成功后，`_resume_one_c04_source` 第 207–220 行现可识别同一缺件错误，并以已验证的 submissions 和前次 SEC 槽、报告、C04 尝试及重建待办作续接预检。第 337–348 行随后把待取项缩成该年报 URL。但只要传入 `resume_from`，第 358–367 行又无条件调用 `prepare_case`，并要求完整 `source_proofs`。年报仍未保存时，这里再次抛出同一个 `SAVED_SOURCE_MISSING:<年报URL>`；它被登记为 `CAPTURE` 错误，`session.capture` 根本未到达。因此 `max_sec_requests=1` 的合法两轮路径会停在已发现的年报 URL 前。建议在续接捕获前复用同样严格的缺件判断，同时保留前次报告、已验证来源角色、待办 URL、账本和获取器的重验；补一条 submissions 刷新后引出新年报、随后 `resume_from` 实际捕获年报的两轮测试。

`resume-repro.log` 以受控的已认证续接返回值代替昂贵的前次真实录制，保留本次协调器的后续控制流：已验证 submissions 和确切缺失年报被发现，`prepare_case` 抛出该缺件错误，结果为 `captures=0`、`capture_mock_called=False`、`CAPTURE` 错误及录制账本 `[0,0,0]`。这项短复现不声称完成前次报告的端到端认证；认证检查由已读代码及前轮保存的两轮日志界定。现有新增三项短测试本次重跑通过，但其捕获正向只有 `resume_from=None`，所以没有覆盖阻断分支；见 `short-tests.log`。

`identity.log` 独立加载当前 V14 Requirement，核对本提交及父提交、模块字节绑定、closure、execution authority，并逐项核对当前 refresh/provider/SEC 三份收据的 48/91/48 个证据哈希，全部一致。V13 父规则未在本提交改变，旧 C04-only 和默认路线的代码条件未变；这不能替代新的两轮正向验收。保存的 365.477 秒混合两轮与 330.682 秒 C04-only 日志只按其原提交范围读取，本轮未重跑。真实新增 provider/paid/SEC 调用 **0/0/0**；未改原账本、父任务未提交的 `execution-state.json`、生产状态、#47/PR52，也未提交或推送。

本次共 **25 次 `functions.exec` 编排、43 次其内工具调用**（包含写入本结论及一次最终只读核验），低于约定上限。
