# D03 当前保存来源的请求组普查

此目录运行仓库现有 `prepare_regulatory_semantic_source()` 和 `requests_from_source()`，使用 `request_context_format` 的固定分组与 tokenizers 0.22.2，对 #28 十家公司保存的完整来源逐一构造D03请求。`original_sources_only()`禁止网络和旧输出/报告作为输入；脚本不会调用模型、SEC或创建原生Result。每家公司均对账请求内单元顺序与来源 `required_unit_ids`，不以关键词缩小输入。命令、每家公司完成行与错误保留在`census.log`；只有循环走完才原子写入`census.json`。脚本执行所用解释器为`/private/tmp/issue28_py314_venv/bin/python`，其`tokenizers`版本已在运行前单独检查为0.22.2。

本次实测代码根为本地提交`5dcded2a7725cb613f2dab89a1e38234b7cfa6b6`，无其它未提交生产源码差异。十家公司共448个来源单元，按实际200,000上下文与4096输出预留组成**130个请求组**，每组请求ID唯一、单元顺序与完整来源对上；十家均成功构造。逐公司组数为：Marriott 5、Southwest 9、Ford 15、Pfizer 16、JPMorgan 38、Salesforce 7、Lumen 11、Macy’s 7、Paramount 14、Enphase 8。JPMorgan的一组带一条旧`source_statement_facts`，其它组该字段为空。`census.json`逐公司保存来源ID、单元数、组数和耗时，`census.log`保留每家公司结束输出与最终130的收据。

结果只代表**当前仓库保存来源与当前代码/资源配置下的请求组织**，不是模型输出能在4096令牌内完整返回、不是语义正确或公司级验收，也不自动获得D03真实请求许可。先前条件估算的“D03首轮130”在此输入版本上得到分组证据；若一组一次、没有有效复用，单D03首轮已比现有97次provider/paid余额多33次，尚未包括B13或补验。这不是增额申请或保证追加33即可完成。若来源、分组、需求快照或必评集合改变，须重新计量。带原`source_statement_facts`的一组仍需显式后继，不能恢复已知错误的旧确定性事实信用；其它组也必须经原始响应保存、当前语义验证和完整原生链后才可能形成结果。

无新增账本调用、额度、请求机会、生产权限；#47来源与账本没有参与。
