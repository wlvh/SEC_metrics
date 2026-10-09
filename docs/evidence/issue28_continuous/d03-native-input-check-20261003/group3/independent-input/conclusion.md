一次独立输入核对已完成；response.log 仅创建一次，保留原始 JSON。原答包含 2 条有限判断：Supplement0 原位置 24 的税务确认政策属于 OTHER_MEANING；原位置 36 的笼统法律程序属于 UNRESOLVED。责任范围当前参与结论为 UNRESOLVED，没有把共享正文中的案件另算为本组案件，也没有推断全公司无调查。

固定开发 SHA：2a711128de8fc301054ff4cfac5f7dea6aeba81e。

输入字节 SHA256：1f4eff8257d1c289e31c1180a9c67249249274ead900d78311fffd4c3faaa972（866455 bytes）。请求体 SHA256：a6573132e7f5902d40ebd593da5612d9c28cc9d47fe81edded3f249c14aa2385（683843 bytes）。请求体 user 内容解析后与 input.json 完全相同；系统消息及原类别保持原样。本次未发请求。

实际读取范围：NativeFacts4 全部 182 facts、NativeFacts5 全部 188 facts、Supplement0 全部 41 外层对象及其全部嵌套内容；1965 条完整共享正文、visible_columns 和全部 visible_unit_bounds；149 contexts、3 units、1 namespace environment、7 XML style attributes；全部原生属性、原 fact.ordinal 及 objects 零基位置。事实 ordinal 的完整非排序列表保存在 input-restoration.log 和 local-reference-validation.log，不能以行号或顺序号替代。NativeFacts4/5 的财务表、会计政策、分部及交易披露没有形成新的 D03 调查事实。原生行使用经逐行可逆验证的显示方式，重复字段由原属性和已完整读取的 namespace dictionary 还原；XML 全文按原打包表示读取，全部样式值已读取并还原。此前工具输出截断处另行完整补读，未把截断当覆盖。

恢复核对：三个 payload 的 bytes 和 SHA256 全部匹配；正确的 canonical content_hash 重算三个 unit_id 全部匹配；41 个外层 XML hash 及全部嵌套 XML 相对切片 hash 匹配。初次用普通序列化直接探测 unit_id 的比较不是正确算法，已在日志明确记录，不作为真实性异常；随后使用导入的直接 canonical helper 核对。两条判断的责任单位引用和正文辅助引用均在原索引位置存在。没有运行长测试。

局限：税务政策的假设性检查不能等同实际监管调查。Note 6 的真实税务审计是共享上下文，其中的调查/执法联系没有在本组政策段建立。会计政策所说的笼统法律程序也没有证明监管机关、被调查主体或调查联系。共享正文中其他明确案件由其原责任单位负责；本组不产生公司合并结论。未读父参考、旧响应、同族结论或其他请求原生材料。未创建 Candidate/Review/Run，也未授 DeepSeek、人工、公司或生产信用。

工具与消息：最终预定 32 次 functions.exec、35 次嵌套 exec_command，保守合计 67 次工具调用；2 条普通消息（开工说明及最终报告），0 问题，1 次抽取、1 次原答写入。没有 spawn、commit/push、真实模型/SEC/账户/生产请求、其他工作树/账本/运行根操作或打包。

时间：首个可核对记录为 2026-10-03T15:23:27.087876+00:00；原答写入为 2026-10-03T15:36:11.921361+00:00，已记录区间耗时 764.833 秒。初期读取及一次导入失败早于该计时起点，未记录精确起始壁钟，因此该数是全程耗时下界，不能冒充完整任务秒数；最终核对时间另见 execution-accounting.log。本次未触及 80 次工具、90 分钟或 3 条普通消息上限。

原答 SHA256：77731e3adbf3abdd72d8d3d98526f3e89ed0c7504b4c3694ad10789c203d782f。

最终只读核对完成：2026-10-03T15:37:13.225131+00:00，记录区间实际耗时 826.137 秒；最终 Git SHA、两份输入 SHA 和原答 SHA 均未变。实际工具调用为 32 次外层 + 35 次嵌套 = 67 次；普通消息合计 2 条。
