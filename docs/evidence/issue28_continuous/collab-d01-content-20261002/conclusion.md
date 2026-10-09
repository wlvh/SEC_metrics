# D01 当前两份保存原件的内容核对（2026-10-02）

**结论：PASS_LIMITED_CONTENT。** 对固定补丁 `865d82205d6b0fa37b11ad15e7000122016c6c8a` 之后的 Paramount 与 Marriott FY2025 私有普通更新，我从两份保存的 10-K 原始字节独立核对了完整 Item 1A 内的标题及标题式段首。各 38 条候选均为该节的逐字标题或加重显示的段首，顺序、原文字节片段、候选文字及私有 Result 的换行展示一致；没有发现明显漏掉的标题，也没有发现把页码、目录链接或普通正文当标题。这个结论只给这两个**具体来源、期间和 Result 身份**的 D01 内容有限信用，不给一般新版式的自动更新、十家公司×39 指标正式验收或生产采纳信用。

| 保存的原件与目标 | 完整 Item 1A 边界（原始字节，左闭右开） | 本次私有 Result |
| --- | --- | --- |
| Paramount Skydance Corporation，CIK 2041610，FY2025，10-K `0002041610-26-000011`，`psky-20251231.htm`，原件 SHA-256 `4cf3d42c0ba1129dadd58d9c1ffdc4f35e2a81cec7bab3763e2a3bbecfea135d` | `541354:643428`，从实际 `Item 1A. Risk Factors.` 到 `Item 1B.` | `sha256:6795449bafa12651099b226e569ad3b2882f72a89cd317adb559c8096058afdd`，候选 `sha256:817401f7905528f2f403baaa065d81b4b360af37b508c2a84a7a20823f492c46` |
| Marriott International, Inc.，CIK 1048286，FY2025，10-K `0001048286-26-000007`，`mar-20251231.htm`，原件 SHA-256 `c372495ac4ad3e62399040675f490315db137e17cd9a9a4a8c10cb1d09312547` | `421133:505239`，从实际 `Item 1A. Risk Factors.` 到 `Item 1B. Unresolved Staff Comments.` | `sha256:99c76e50d0fb19cd6116a80350a6f1ca38924b5731e812695484d28381b348f8`，候选 `sha256:5e41cbfad234ed939d4c4792a7f35a427728ad406259a1dae05517acc4922662` |

上述主体、10-K 类型、年度截止日及 accession 与保存原件的 DEI 封面字段、原件 URL 和私有 Run 目标相符；截止日原件写为 December 31, 2025。两份原件的 SHA-256 由本次直接重算。原件分别位于 `/private/tmp/issue28-d01-emphasis-paramount-20261002-final/metrics/D01/attempts/2bf85d7f0f6a4cf9b43447c3e018408a/data/evidence/request_attempts/4c/4cf3d42c0ba1129dadd58d9c1ffdc4f35e2a81cec7bab3763e2a3bbecfea135d/psky-20251231.htm` 和 `/private/tmp/issue28-d01-emphasis-marriott-20261002-final/metrics/D01/attempts/5fa26e4007ef4ce1aee75cd5869d836b/data/evidence/request_attempts/c3/c372495ac4ad3e62399040675f490315db137e17cd9a9a4a8c10cb1d09312547/mar-20251231.htm`。

本次从原件逐字节切出 76 个候选片段，独立计算每片段 SHA-256，用标准 HTML 解析去标签、合并空白并按 NFC 规范化后，76/76 均与记录的片段哈希和候选文字相同。候选按原件先后排列，均位于完整 Item 1A 内；两份 `METRIC_RESULT.value` 均恰为各自 38 条标题按原序换行拼接，`text_payload.items` 的顺序与文字也一致。逐条坐标和完整标题见 [claim-byte-audit.log](claim-byte-audit.log)。

为了独立检查遗漏，我另外在两份 Item 1A 的**整个原始标记范围**扫描加粗或下划线 `span`，并把未落入候选片段的加重文字逐一看回原件。Paramount 的 43 个加重片段覆盖全部 38 条候选；未匹配的非空文字仅为起始 `Risk Factors.` 与下一节 `Item 1B.`，多出的加粗片段属于拆开的标题。Marriott 的 51 个加重片段也覆盖全部 38 条；未匹配的非空文字仅为九次带链接的页首 `Table of Contents` 和下一节 `Item 1B.`。两节内没有 `<b>`、`<strong>`、`<h1>`–`<h6>` 或带 `font-weight` 的 `div` 作为另一套明显标题标记。按当前解析器重建的完整 Item 1A 区间分别有 125、87 个块；未选块中 Paramount 无非链接加重段首，Marriott 的九个加重段首全是目录链接。完整区间的逐块位置和前文见 [source-view.log](source-view.log)。这里核对的是标题级内容，未把普通正文的风险事实逐句审定为新的指标结论。

关键边界也直接看了原件标记。Marriott 新增的 `Operational Risks`、`Development and Financing Risks`、`Technology, Information Protection, and Privacy Risks`、`General Risk Factors` 都是各自独立的下划线标题 `span`，字重 400，位于后续风险段落之前；它们符合已批准 Spec 对 Item 1A 所有加重标题的要求。Paramount 的法律法规标题在原件中被拆为加粗 `U`、普通字重的 `.`、加粗 `S`、普通字重的 `.` 与后续加粗文字；候选的单个原始跨度确实覆盖这些标记并解码为完整的 `U.S. or foreign laws or regulations...` 标题，未把下一段正文接进来。源代码的标点桥接在这个原件上修复了旧的 `...changes in U` 截断；这不证明任意跨页或任意拆分版式都已支持。

两个私有普通更新的终态是 `CANDIDATE_READY`，其 Result 记录内部为 `publication=PUBLISHED`、`quality=EXACT`、Evidence 为 `PASS`，provider/paid/SEC 调用均为 0；对应私有 Run 的 `validation.json` 仍为 `NOT_RUN`。因此本次完成的是这两份当前原件的**标题内容独立核对**，没有把程序重放、内容正确、正式批次验收和生产发布混为一项。补丁 `865d822` 的既有 [限定独审](../collab-d01-page-boundary-20261002/independent-review-865d822/conclusion.md) 只处理已知跨页误合并及已知分页形式的拒绝；其他跨页形式、新来源和其他 D01 坐标没有在这里获得完整自动更新保证。正式 390 坐标的本方正常入口汇入、所需验证及发布权限仍按各自原有门槛处理。

本次只读原件和私有记录，未发网络或业务请求，未运行长测试，未改旧 Run/Result、#47 或 PR52，也未 commit/push。独立扫描的具体输入、片段和未匹配标记留在上述两份日志。
