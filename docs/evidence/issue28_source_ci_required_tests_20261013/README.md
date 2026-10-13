# Source-material CI：跳过/空套件不再算通过

回应已合 [PR246 P2 4257780287](https://github.com/wlvh/SEC_metrics/pull/246#discussion_r4257780287) 和接收方4257819216。说明承诺“不允许跳过当通过”，但材料worker原来执行 `python -m unittest -q`，跳过测试正常返回0；foundation只看该退出码，实际可能报PASSED。

先用真正的子进程小fixture复现：skipped suite在原worker返回0，`before.log`留原红。只改现有worker的启动命令，复用已交付 `tests/required_unittests.py`；其默认拒绝意外skip、空套件、错误及失败。限时/例外限时、环境、cwd、独立子进程、超时124和输出tail结构保留。没有新测试平台、skip白名单、屏蔽失败、保护设置或业务算法变更。

12个既有foundation扩展控制0.200s、全部通过：实际child pass=0，fail/skip/empty/pass+skip非0；foundation正式source-material CLI函数使用真实worker，混合pass+skip报告FAILED，不能被汇总转绿；原TimeoutExpired的124、原限时及部分stdout/stderr保持。fixtures只替选测输入和临时根，不mock worker成功。实际已有材料module `tests.vnext.test_text_results_v2` 沿新worker执行26 tests/0.323s，worker0.477s/原240秒限制/零fail-error-skip，收据 `actual-material-worker.json`。

这是本次必要函数体修改：`tools/run_fast_tests_v2._run_source_case` 的真实材料入口，仅用既有required runner取代直接unittest；不改selector清单、feature加载、workflow、fast共享准备或退休规则。新增控制放既有 `tests.test_foundation_ci`，原workflow已显式执行，不再加平行登记。旧原生快照/封存测试不因本修复恢复为新任务必跑要求；未变公司财报或全44材料未本地重跑。

实测起点actualmain e16ca316加这两文件未提交差异。main随后接PR250后再正常组合，仅小控制须重验，新head CI独立核；原26module实测仍按e16执行，不给后续27method假覆盖。提交/公开树与实际版本另说明，不声称原工作树已按最终SHA执行。

期间读取观察到 `run_foundation_ci.py` 有三份字节相同的函数定义，最后一份覆盖前两份，不是把每个测试重复执行。AST及一次共享准备控制已核；这与本次材料skip缺口无关，因此没有顺手清理或全仓重构。

开发、诊断及CI验证新增业务调用0/0/0，不Ready、合并、正式采纳、部署或active。source材料漏取/skip将真实暴露为失败，需要补环境或材料，不靠删断言换通过；仅这条运行保证已修，不证明39指标内容正确或生产完成。
