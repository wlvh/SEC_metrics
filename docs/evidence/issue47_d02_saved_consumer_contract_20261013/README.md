# D02 保存回答的实际消费者接缝

历史侧向公共模型输入输出实现负责人提供原 Ford FY2025 call0009，供既有公司入口消费。此记录只读取保存材料并核对现有 H1 后处理；没有模型、SEC 请求或新 Run。不是新模型试验、审查包或独立调用器。

## 可取得输入

完整请求、实际 provider body、HTTP 原响应、assistant bytes、Source 与终态均来自 PR52 保留提交 `bcc0c0bc0293ba6b6ffc58b1f4e9034dbb52a786` 的 `evidence/issue47_model_calls/9a368413797ddef1/model-ledger.tar.gz`。逐成员路径、字节数、SHA256及原参数见 [ford.json](ford.json)。只读 tar 成员，不解包到执行账本，也不重新 start/run。

主干 `tests/fixtures/d02_saved_quote_failures.json` 是 H1 引用回归的投影，只保回答涉及的块。它不是完整模型请求：Ford 在该投影中没有块，原请求实际有 b1812 一块。公共接口必须消费完整 semantic-request，不能用回归投影重建新问题。

在含该保留 Git 对象的 checkout，用实际 Python 环境和 `PYTHONPATH=scripts:tools:.` 运行以下只读核对；代码只使用标准库和已有合同模块，不安装公司、取源或写结果：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 - <<'PY'
import io,json,subprocess,tarfile
from vnext import legal_review_contract as contract
old='bcc0c0bc0293ba6b6ffc58b1f4e9034dbb52a786'
path='evidence/issue47_model_calls/9a368413797ddef1/model-ledger.tar.gz'
archive=subprocess.check_output(['git','show',old+':'+path])
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:
    def read(name): return tar.extractfile('root/calls/0009/'+name).read()
    request=json.loads(read('semantic-request.json'))
    source=json.loads(read('source.json'))
    answer=read('wire/assistant-output.bin')
    response=json.loads(read('wire/raw-response.bin'))
    provider=json.loads(read('invocation_control/requests/07aff1fb87b2834ecae8603033856901c338c69002e797973b37ee4ba9e7b047.bin'))
assert source['request']==request
assert provider['messages']==contract.provider_messages(request)
assert response['choices'][0]['message']['content'].encode('utf-8')==answer
decisions,added=contract.validate_answer(request=request,raw_output=answer)
print(json.dumps({'company':request['company_id'],'period_end':request['period_end'],
    'input_blocks':len(request['blocks']),
    'item8_subreview':contract.reviewed_blocks(request=request,decisions=decisions,added=added),
    'new_calls':[0,0,0]}))
PY
```

实际结果：完整 source.request 等于 semantic-request；两条 provider messages 等于原请求按现有合同生成的消息；原响应 message.content 与 assistant bytes 完全相同。HTTP200、原终态 SUCCEEDED、该原调用计数 `[1,1,0]`；usage963输入/13输出，计费金额未报告。以上原执行归属保留，不给当前核对新增调用或接受信用。

## 后处理与完整指标边界

现有 `legal_review_contract.validate_answer(request=原完整请求, raw_output=原assistant字节)` 返回 decisions、added；`reviewed_blocks` 返回 Item8新增块、扣留原因和未决块。该函数保持 V1 引用20–300字符合同，不裁答、不改请求，不判断完整诉讼业务内容。

Ford 的原答是 `{"decisions":[],"also_in_scope":[]}`，原 must_decide 为空，机械处理结果是 `([], null, [])`。这仅说明 Item8 子审阅没有新增块。原完整 D02 Result 还含 Item3、既已纳入的附注诉讼/保修内容；17765字符，完整值 SHA256、Result ID与 records.jsonl 路径见 JSON。不能将子答写成完整 D02 零值、无诉讼、N/A 或新完整接受。

原 Run 绑定的 SourceReference 包含本请求的 source_reference_id。请求指定 Ford/CIK37996、报告日2025-12-31；原完整 Result 是2025-01-01至2025-12-31。source_proofs 仍列当时真实申报、文档、body/headers和 request-attempt，不能仅凭 company_id 或回答文本相同复用到别的来源或期间。

## 剩余接线与负例

公共负责人维护同一保存回答解析/保存入口，本方维护历史选期、原件准备及既有纯后处理。当前 D04 保存回答路线及旧 native_assessment_replay 类型没有证明支持 D02，不能直接借用后声称公司链完成。下一消费者必须将完整请求、匹配原答、来源/期间和完整 D02 汇总一起接到公共入口，再验证新任务处理、同输入零计算、独立 results/CSV；本记录尚未完成这三项新公司验收。

沿用已经 main 的 H1 正反材料：12原答4合同通过/8拒绝，14条真实过长引文仍是长度失败；合同通过也不保证法律语义正确。Marriott 两年旧格式通过但漏自保，Enphase旧位置仍有业务缺陷，不能把所有格式通过回答当正确参考。旧回答、失败、Run、35次真实批次和调用预算均保持；此交接不恢复失败机会或开启第三轮方法试验。

## 主干真实原件准备增量

在实际 main `731f8fd1` 的 `d02_text_results_v3.prepare_business_text_sources` 上，只取原 Run 的 SourceReference/RawBlob 元数据和已保存原件，不读旧业务值作为操作数。Ford FY2025 全文4176块准备2.570秒，文档身份与原请求相同。该原件的 Item8 范围是 `[1812,1813)`、一块；其完整原文及 must_decide 集重建出的请求与原 call0009 逐字段完全一致，provider_messages 也完全相同，当前 H1 可消费原答。见 [main-source.json](main-source.json)。这仅验证该单块实例，不提供通用 Item8 pool 实现，也不通过删块让新请求匹配旧回答。

主干完整源候选有53块，原完整结果选择45块：所有原45块的文本、所属节、文档/来源身份与字节跨度均保持，没有缺失。多出的8块是已定位的重复公司名称、财务附注页眉及 Note24 Continued 标题，具体原文/跨度在JSON；它们不是8个新增诉讼事实。这是后继完整文本汇总要处理的真实展示范围差异，不用原答案手动裁剪来源或改签旧结果。只读原件准备不是新公司结果、首算/复跑/CSV验收。

复现源准备：先按前文读取原call0009，恢复原件根，设 `SEC_HISTORY_SOURCE_ROOT` 为实际 `source-inputs`。以下命令不安装公司或访问网络；只用旧Run的来源元数据，不读其金额或文本结果作为处理输入：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 - <<'PY_SOURCE'
import hashlib,json,os,subprocess
from pathlib import Path
from vnext import d02_text_results_v3 as core
from vnext.canonical import content_hash
from vnext.legal_review_contract import review_request
from vnext.text_business_candidates import _substantive
old='bcc0c0bc0293ba6b6ffc58b1f4e9034dbb52a786'
record='docs/evidence/issue47_history/model-live-round-9a368413/d02/ford_motor_company-d02-2025-12-31/run-ford_motor_company-d02-2025-12-31-D02/records.jsonl'
rows=[json.loads(line) for line in subprocess.check_output(['git','show',old+':'+record]).splitlines()]
ref=next(r for r in rows if r['record_type']=='SOURCE_REFERENCE' and r['source_role']=='target_primary')
blob=next(r for r in rows if r['record_type']=='RAW_BLOB' and r['raw_asset_id']==ref['raw_asset_id'])
root=Path(os.environ['SEC_HISTORY_SOURCE_ROOT'])
sha=blob['raw_asset_id'].split(':')[1]
raw=(root/'evidence/request_attempts'/sha[:2]/sha/ref['document_name']).read_bytes()
assert 'sha256:'+hashlib.sha256(raw).hexdigest()==blob['raw_asset_id']
inventory=json.loads((root/'evidence/request_attempts/2e/2e312b9a7c22fc6b22a4c68dc2b2924274426be1e672178d40428ff655fcae53/CIK0000037996.json').read_text())
recent=inventory['filings']['recent'];index=recent['accessionNumber'].index(ref['accession'])
filing={k:v[index] for k,v in recent.items()}
target={'company_id':'ford_motor_company','entity':'37996','accession':ref['accession'],
    'period_start':'2025-01-01','period_end':'2025-12-31','scope':core.SCOPES['D02']}
target['scope_key']=content_hash(value=target['scope'])
p=core.prepare_business_text_sources(metric_id='D02',target=target,source_references=[ref],
    raw_blobs={blob['raw_asset_id']:blob},raw_bytes_by_id={blob['raw_asset_id']:raw},
    source_filings={ref['source_reference_id']:filing})
doc=p['documents'][ref['source_reference_id']];proposal=p['proposals'][ref['source_reference_id']]
scope=next(s for s in proposal['checked_ranges'] if s['section_id']=='ITEM_8')
assert scope['end_block_exclusive']-scope['start_block']==1
pool=[i for i in range(scope['start_block'],scope['end_block_exclusive']) if _substantive(doc,doc['blocks'][i])]
keyword=[r['block_index'] for r in proposal['D02']['candidates'] if r['section_id']=='ITEM_8']
request=review_request(company_id=target['company_id'],target_cik=target['entity'],
    period_end=target['period_end'],document=doc,pool=pool,keyword_admitted=keyword)
assert request['request_id']=='sha256:7f0d2be204ae60689397a55ac102ec07f3ad0923c57ab00db59060abd9fe8908'
print(json.dumps({'source_document':doc['text_document_id'],'request_id':request['request_id'],
    'source_candidates':len(proposal['D02']['candidates']),'new_calls':[0,0,0]}))
PY_SOURCE
```

源准备与完整原request/provider比对已分别实际运行；主干核心文件与main731相同。没有新模型试验、注册、旧Run修改或普通保存器。公共负责人按此实例接保存回答入口；其他多块原件仍按既有边界读取和未决分别推进。
