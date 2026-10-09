# 7d1202b D01 两坐标与390读取视图限定独立审阅

结论：**NEEDS_FIX（1项P2，限于新读取器的证据身份接线）**。已提交的两份D01映射实际正确；缺口是正常读取入口仍能给不属于该坐标或Run的有效对象授予“内容和机械收据已验证”状态。本结论不否定此前两个精确保存结果的内容核对或机械收据，不审全部PR，也不授予390整体或生产信用。

- 补丁：`7d1202b06f426ed3fc479c7be4f075327267971e`。
- 增量base：`a31342deb658bc7b1b0b65b5307eb24be4f55e51`。
- UTC开始：`2026-10-02T22:51:49.987910+00:00`。
- UTC结束：`2026-10-02T22:56:54.366510+00:00`。
- 实际工具调用：**16**（outer 6次functions.exec + nested 9次exec_command + 1次collaboration.send_message）；普通消息**3**（开工告知、一次父方进展消息、最终报告），问题0，最终报告1。

## P2：读取器验证对象自身的ID，未共同绑定公司、期间、Run、Result和收据

位置：`current_view.py:41–54`及`119–129`。`validate_record`确认原生Result和收据各自的内容ID；现有条件同时比较了若干数值/质量字段，却没有核对原生Result的company_id/metric_id/期间与行的坐标和期间，也没有将行的run_id、所选Result ID和收据与已哈希固定的`mechanical-corrected-summary.json`条目共同核对。`content_review_result_id`只是delta中另一个自报字符串；证明文件哈希一致并不检查它与具体条目之间的关系。

有限反例均仅在内存中改delta，由正常`load_current_view()`读取，其他证明文件和哈希检查保持；未改仓库产品文件、未伪造对象哈希、未重跑安装验证：

1. Paramount条目的原生Result、行和Run不变，只把`mechanical_receipt`及`mechanical_receipt_id`换为Marriott的真实PASSED收据。读取入口接受并标为`SAVED_SCOPE_CONTENT_AND_MECHANICAL_RECEIPT_VALIDATED`。
2. Paramount的新Result与收据不变，只把行的run_id换为原390里的旧Run `run:ordinary-integrated:3db326b2b92a7d79b139bd291b19a38e5b8c89e1143b8df6905f0b50fff904b3`。入口仍接受并授同一状态。
3. Paramount坐标和前驱保留，换入Marriott的真实原生Result、对应ID/收据和显示字段。入口仍接受，输出的Paramount坐标选中Marriott Result `sha256:99c76e50d0fb19cd6116a80350a6f1ca38924b5731e812695484d28381b348f8`，原生company_id明确仍为`marriott_international`。

因此，八项现有测试通过不证明本入口完整执行了README声称的具体证据接线。最小修复是在正常读取入口使用已固定哈希的机械汇总，逐条绑定公司、精确Result ID、Run ID、收据，以及原生Result的主体/指标/日期；不需要重新执行原安装验证或扩建登记系统。将上述三个短反例加入拒错验证即可。

## 已完成的限定正向核对

- 两个已提交D01条目各自的原生正文，与原attempt的records.jsonl中精确Result逐字段相同；主体、D01、FY2025起止日期、manifest目标期间、Run ID、Result ID、机械汇总和嵌入收据均实际一致。
- Paramount选定`sha256:6795449bafa12651099b226e569ad3b2882f72a89cd317adb559c8096058afdd`，Marriott选定`sha256:99c76e50d0fb19cd6116a80350a6f1ca38924b5731e812695484d28381b348f8`。各38项文字的独立原件阅读身份来自已保存conclusion.md；本次没有再次逐字审阅76条标题。
- `build_delta.py`只读检查通过`PASS_TWO_COORDINATE_NATIVE_PROOF_BINDING`；未执行validate_run或长链。两份原安装收据只读取机械报告与汇总，原件阅读和机械执行的责任边界清楚。
- 已注册defects数组与base逐字段完全相同（当前数组28条、28个不同Result身份、20个坐标；历史19坐标/27旧Result的说明未当作当前全数组计数）。两个旧D01错误身份仍在数组里。release列表非空时旧错误仍扣留的现有反例通过。
- 正常视图正好390行、390个唯一坐标，坐标集合与原索引完全相同。17个当前选中错误身份的坐标逐个与登记相符且value为null；不是全部剩余问题数。
- 相对原索引，367行逐字段不变；其他23行为4个既有有限差异、2个D01替换和17个错误身份扣留，未把其他坐标新授信用。
- Marriott C04后继没有明确新Run时显示run_id=null，未继承旧Run；Southwest C04和两个D04均只使用其delta明确给出的新Run。其scope保持`PRIOR_BOUNDED_DELTA_SCOPE_ONLY`。
- 原390及两个prior delta的实际SHA-256与input-bytes.json逐项一致。显示统计明示all390_acceptance=false、full_current_head_reexecution=false、production_authorized=false；两个恢复不算完整39项公司或新业务调用。

## 操作及短测日志

1. functions.exec + exec_command（累计2）：读取UTC开始、status、固定HEAD和增量stat；轻量检索memory登记只发现旧历史D01/UI条目，本结论未采用它们。
2. functions.exec + 2个exec_command（累计5）：固定SHA读取新四文件和缺陷登记diff；只读实时Issue28，确认本次仍属于既有390准备范围。未向Issue/PR发表评论。
3. functions.exec + exec_command（累计7）：读取本次delta、指定三份D01内容/机械材料、原390引用及两个prior delta，不重读未变长材料。
4. functions.exec + 2个exec_command（累计10）：短单测和三项内存反例。
5. collaboration.send_message（累计11）：向父方报告上述接线缺口，没有外部消息。
6. functions.exec + 2个exec_command（累计14）：只读build_delta检查；从固定SHA装入读取器，核对390集合、defect原数组、原字节摘要、两份实际完整绑定。
7. functions.exec + exec_command（累计16）：只写本文件并核对落盘，未改产品代码。

授权短测：
```text
/private/tmp/issue28-tokenizers-venv/bin/python -B -m unittest -q test_current_view
Ran 8 tests in 0.074s
OK
```

只读生成绑定核对：
```text
/private/tmp/issue28-tokenizers-venv/bin/python -B build_delta.py
PASS_TWO_COORDINATE_NATIVE_PROOF_BINDING
parent_bytes_retained=true
new_calls=[0,0,0]
```

独立反例：
```text
valid_other_company_receipt: ACCEPTED（应拒绝）
new_D01_result_with_old_Run: ACCEPTED（应拒绝）
other_company_native_result: ACCEPTED（应拒绝）
三个输出均为SAVED_SCOPE_CONTENT_AND_MECHANICAL_RECEIPT_VALIDATED
```

独立集合与身份核对：
```text
DENOMINATOR 390 390 390 390; KEY_SET_UNCHANGED=True
REGISTER_DEFECT_ARRAY_UNCHANGED=True
WITHHELD_SELECTED=17; EXACT_SELECTED_DEFECT_ID_MATCH=True
UNTOUCHED_ROWS_EXACT_BYTES_SEMANTICS=367
PRIOR_INPUT_HASH checks: 3/3 True
COMMITTED_D01_ACTUAL_BINDINGS: company/metric/period/run/result/receipt/native_body 全True（两坐标）
FIXED_HEAD=7d1202b06f426ed3fc479c7be4f075327267971e
```

未覆盖：任意新来源、新版式、其他D01内容正确性、390全量重执行、全部PR、CI、provider/SEC业务执行、生产采纳。本次未spawn、commit/push、发业务请求、重跑长材料/全fast或触碰#47/#54现场及账本。开工已有execution-state.json本地修改，本审阅未修改它。
