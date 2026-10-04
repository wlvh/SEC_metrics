# Pinned DeepSeek V4.1 tokenizer

`tokenizer.json.gz` is a deterministic gzip copy of the official tokenizer at
revision `dba1be0a40aa45a94ad051997016db3960a90277`:
https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/tree/dba1be0a40aa45a94ad051997016db3960a90277

The original 6,367,257 bytes have SHA256
`c90dfa01249db1be4245780a052ede752e1361c612ac6d08e2bdada7d599476b`.
The compressed 1,868,514 bytes have SHA256
`d0a53c1a5e7f998a5f42b4f428888da70ed47ad33eb2a8afe32294f39f17ef5a`.
The original upstream MIT license is included.

The local formatter implements only the exact two-text-message, JSON-object,
non-thinking Chat Completions subset of upstream `encoding/encoding.py`
(SHA256 `502bdaec8a3fd88ebc24c4721a7038fbe42f2063c664638127056107920035c1`).
It includes the system message, full user content, response-format hint,
beginning marker, role markers, and assistant generation suffix. The count
adds the configured 4,096 output tokens to the complete input count and tests
the unchanged 200,000 context ceiling. Unsupported envelopes are rejected.

Install the bound local engine with
`python3 -m pip install --no-deps --require-hashes -r requirements-continuous-context.txt`.
The file pins the Linux x86-64 CI and macOS arm64 wheels; no Hub client,
model download, model inference, or account access is needed. Missing or
different engine versions can only produce a conservative
rendered-prompt byte count; reference grouping requires the exact engine and
fails explicitly when it is unavailable. Provider-reported usage remains the
actual observation; this file provides neither execution nor result credit.
