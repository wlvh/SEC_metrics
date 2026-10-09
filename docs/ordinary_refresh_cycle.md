# 有限普通来源刷新与更新

`tools/vnext_ordinary_refresh.py`是普通更新的新协调入口。一次选定公司、指标、历史目录和每轮请求上限后，程序从申报元数据发现URL与后续依赖，使用已有`SecAcquisitionSession.capture`获取，再调用原`ordinary_update_cycle.run_company`处理逐指标历史。无需逐份填URL、单元格或答案；它不启动后台常驻任务或定时调度。

```bash
python3 tools/vnext_ordinary_refresh.py --state-root /absolute/update-history --max-sec-requests 10 --output /absolute/new/check.json
```

可以用`--company`缩小公司范围，`--metric`限制计算和历史更新；来源发现仍复用原有39项完整依赖图，不另定义一套按指标来源规则，所有取得动作受本轮请求上限约束。默认仍展示配置中的十家公司和39项指标。现有普通历史控制器支持38项，D03明确返回`UPDATE_NOT_IMPLEMENTED / ORDINARY_UPDATE_ROUTE_NOT_WIRED`。其他模块的原生结果开发不因此失效，也不能把其更新接线缺口写成财报缺失。

## 一轮做什么

1. 核对原生获取会话、来源目录、累计总账及安全的历史目录。
2. 在同一获取会话的数据根读取当前元数据；各公司轮流取得一份待处理来源，再按新元数据重建依赖。主文件或目录出现后，新依赖自动进入下一轮。
3. 每轮每个URL最多尝试一次，新增SEC尝试不超过配置上限；原成功原件直接复用。已保存请求清单中该URL的最后一次失败不会被自动重抽。
4. 取得多少来源就准确报告多少。HTTP失败或一家公司的发现失败不会抹掉其他公司的来源；仍调用现有逐指标更新器，让无依赖指标完成。
5. 新输入、重复输入、失败保留、恢复和历史读取继续由同一普通更新历史控制器处理。完整成功候选的期间和原生结果保持其原义。

`REFRESH_INCOMPLETE`列明本轮未取得的依赖、保留失败的URL与来源限制。即使已保存输入本身可以计算为`UPDATES_READY`，也不能据此把未完成刷新的一轮整体标成当前更新完成。来源读取损坏、解析不支持和真实获取失败继续分别保留其原因。

自身调用数从本协调返回的原生收据求和，累计总账前后差额单列，避免把其他并发执行算到本协调名下。LIVE获取未返回且额外槽无法归属时，调用数显示UNKNOWN/null并报告`CALL_ACCOUNTING_UNRESOLVED`，不会写为0或刷新完成。

`--max-sec-requests 0`只检查并处理已经保存的输入，不授予当前SEC新鲜性。每轮请求上限是运行资源配置，不是逐文档审批队列；它不能越过固定累计240/240/80、零自动重试或原暂停边界。

## 执行绑定与证据

LIVE入口须同时通过新协调器当前字节绑定、自己的完整离线更新接线证据以及原SEC获取器的全部门禁。未绑定的新文件或失配证据不能靠非空参数启动真实获取。`--max-provider-requests`默认0；显式有限额度下，仅从未尝试的D04原生请求可进入既有执行器，B13真实执行保持暂停。相同原成功先按原收据和当前来源复验；旧失败不换格式重试，跨新来源保留部分旧组的复用仍未实现并明确拒绝。仅来源获取、单请求成功或记录响应不能代替完整指标结果。

recorded材料测试使用独立临时总账、真实保存原件作为明确记录响应，并禁用网络、DNS与HTTP：

```bash
ORDINARY_REFRESH_MATERIAL_ROOT=/absolute/new/material PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_ordinary_refresh_cycle_material
```

当前材料选择JPM/Pfizer及B01，不重启Marriott试点。获取证据、原生结果、更新历史、390验收和正式生产信用分别解释；没有正式发布、active切换或长期运行权限。

## 当前增量及限制

`capacity_update_input`把运行规则目录和来源目录分开；原件、身份和获取记录仍从显式来源根验证，规则由当前执行绑定提供。schema2登记附原始完整来源快照，当前等价检查只允许获取记录/实现身份变化，数量、单位、期间、原文、所需请求、提示或输出合同变化均不借用旧执行信用。原样成功继续参与完整公司—指标任务。

新年报已经取得而同accession Company Facts尚未更新时，来源发现保留财年校验的具体未决并允许继续取得CF，不能把中间缺项当作完整输入。一次新provider请求终态与异常回读按同一ordinal只累计一次；无法归属时停止受影响provider并报告UNKNOWN。

实际JPM A08 FY2025完成10次SEC刷新与候选历史；同一固定实现重复触发为零调用。新B13/D04共享历史的完整recorded生命周期通过，后续当前绑定与真实成功复用另验。证据见`docs/evidence/issue28_continuous/registered-native-update/`，不重启Marriott旧试点。
<!-- capability-anchor: CAPABILITY.ordinary_refresh_native_draft -->


同一次原生更新可以复用已构造的完全相同请求字节：最多两份完整输入、64MiB，退出调用即清空；每次核对当前规则和分词状态。它不复用来源真实性、原收据或模型含义检查，也不更改分组、200000上限或调用数量。少见非普通JSON类型走原构造器，不能因编码器类型转换命中别的输入。
