# Paramount C04：四份注册变体原件及完整关系检查

固定总账第105–108次实际SEC获取均为`SUCCEEDED`，新增provider/paid/SEC为**0/0/4**；through108累计**59/59/49**，对应剩余**181/181/31**。本次只读分析、归档及还原另增**0/0/0**。这四次解决已定位的原件获取缺口；**没有生成C04原生Run，没有新增390坐标完成信用**。旧结果、旧失败、其他调用与生产状态未修改。

## 原件与实际阅读范围

| 调用 | 来源 | 申报身份及实际事项 |
| --- | --- | --- |
| 105 | `psky-20250807.htm` | 2025-10-23修订正文，39842字节；完整可见正文已读 |
| 106 | `0002041610-25-000029.hdr.sgml` | `8-K12B/A`，CIK2041610，Items7.01、9.01 |
| 107 | `d841914d8k12b.htm` | 2025-08-07原申报正文，174483字节；完整可见正文已读 |
| 108 | `0001193125-25-175046.hdr.sgml` | `8-K12B`，CIK2041610，Items1.01、1.02、2.01、2.03、3.01、3.02、3.03、5.01、5.02、5.03、5.05、7.01、9.01 |

`summary.json`逐文件列官方URL、原件SHA/字节数、原收据与终态身份、恢复路径及响应元数据SHA。原正文与头文件分别核对，两个完整事项集合一致。两份可见封面使用8-K/8-K/A，而SEC头文件使用8-K12B/8-K12B/A，双方原值都保留。原申报accession的1193125前缀不改变头文件明确的注册主体CIK2041610。

另行链接的Ex23.1、Ex99.x及其他被引用原申报没有在这四次请求中取得。本材料不声称已阅读这些附件，也不将四份文件称为39项来源全部验收。

## 以主体和事项判断，而非按词命中

1. 原申报的注册主体是Paramount Skydance Corporation（原名New Pluto Global, Inc.）。正文说明交易完成、其成为Paramount的successor issuer；Paramount Global和Skydance Media LLC在交易后分别成为其子公司。原申报还包括融资、所有权及控制、董事高管、薪酬、章程等事项。注册人、前身及被收购公司的事实不能相互替代。
2. 修订说明明确只补原申报延期提交的Item9.01财务信息，未作其他修改。其中历史审计财务报表属于Skydance Media LLC，合并备考数据明确仅为示意，并非已经发生的合并主体历史结果。
3. 修订的Exhibit23.1描述明确将Ernst & Young LLP同意关联到**Skydance Media LLC**。这是该附件的主体描述，不是任命EY为Paramount Skydance审计师的陈述。原申报PricewaterhouseCoopers出现于Paul Marinelli以前的工作履历；审计委员会任命属于董事治理，也不是外部审计师任免。
4. 两份正文与头文件均没有Item4.01，全文也未陈述Paramount更换审计师。这只是这两份申报的内容结论；不能自动扩展为全年所有申报已经覆盖，更不能单独推出C04=0。

九处关系锚点的完整文本、原件字节范围与片段SHA在`source-analysis.json`。恢复树`analysis/`还保存两个完整正文的块视图、原生DEI事实及四份完整文字视图；它们是派生阅读材料，原件才是来源。

## C04仍需完成的责任

- **获取/发现已推进：** 通用注册变体发现已经产生四个具体URL，本包证明全部实际取得，并核对了原件及头文件。原缺失报告保留历史含义。
- **接受实现尚未完成：** 当前`catalog/r5/C04_auditor_changes_v2.md`和冻结普通治理入口仍限定8-K/8-K/A。来源发现新增形式并不自动扩张旧Spec、旧六事件集合或原Run语义；后继形式与头文件接受、完整事件集合重建及原生Run仍要落地验证。
- **主体/比较事实限制保留：** 先前完整来源检查已证明当前registrant没有同CIK前期普通年报；2024比较事实属前身。本包新文件没有补出同registrant前期AuditorName。不能用收购对象EY、前身或同事务所名称拼成比较对。
- **需要明确的业务接受决定：** 先前当前年报Item9的None及连续审计陈述已有证据，但v2的否定路径仍要求同主体当前/前期AuditorName相同和完整支持形式事件集合。若要在新注册人情形以明确原文否定取代前期比较，应通过后继规则明确批准；本项未擅自采用，也未将实现缺口包装成合法披露限制。

先前源检查说明见上级`README.md`及`current.json`，按其原绑定解释；本包不重跑或重签它们。其“4个URL尚缺”段落仅代表获取前，现由本包四个成功原收据补充更新。

## 自包含归档与实际还原

- `material-index.json`将**60个逻辑文件**映射到**47个唯一内容对象**，没有`repository_path`引用。
- `material-objects.tar.xz`大小**4560292字节**，SHA256=`0078e467dd18fa1b9978c48e538e0c01366710ea5fde830a28d63f1f734bd67e`。
- `calls/0105`–`0108`保存原intent、plan、receipt、terminal、wire原文/响应元数据及四份**原字节**`execution-rules.tar.gz`，未重写压缩包。
- `source-inputs/`按原proof路径保存原件/响应元数据；`execution-evidence/`保存原捕获返回、汇总、程序、日志及发现计划；`analysis/`保存本次阅读程序和派生材料。未纳入私有凭据目录或其他调用。
- `restore_material.py`是现有real-material还原器的逐字节副本。实际使用全新外部目录、不存在的repository路径，在新进程还原全部文件；随后独立将全部恢复文件与原文件逐字节比较，核对四份终态全部证据SHA，并读回四份原runtime包的全部509个成员。没有软链接、硬链接或仓库回退。见`restore.log`、`restore-check.json`及`verify_restore.py`。

```bash
python3 restore_material.py --evidence /absolute/registration-variants-real-material --repository /absolute/unused-path --output /absolute/new-material-root
```

这是原件与原执行证据的可审查归档，不是全固定总账回放、不新增业务验收、不授正式采纳或发布权限。首次辅助HTML块定位脚本与标准库同名offset冲突造成的本地TypeError已修正；没有影响原件、SEC调用或业务结论。
