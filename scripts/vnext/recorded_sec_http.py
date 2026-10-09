"""Recorded HTTP replies through the normal SEC persistence path, no sockets."""
from http.client import HTTPException
from pathlib import Path
import hashlib
from sec_http import SecHttpClient, FetchResult, parse_request_log_rows


class RecordedSecHttpClient(SecHttpClient):
    def __init__(self, *, recorded_root, **kwargs):
        super().__init__(**kwargs)
        self.recorded_root=Path(recorded_root).resolve()

    def reply(self, *, url):
        rows=parse_request_log_rows(text=(self.recorded_root/'evidence/requests_log.csv').read_text())
        matches=[r for r in rows if r['source_url']==url]
        if not matches:raise ValueError('RECORDED_HTTP_REPLY_MISSING:'+url)
        row=matches[-1]
        path=(self.recorded_root/row['repo_relative_path']).resolve()
        if self.recorded_root not in path.parents:raise ValueError('RECORDED_HTTP_PATH_OUTSIDE_SOURCE')
        raw=path.read_bytes()
        if len(raw)!=int(row['content_length']) or hashlib.sha256(raw).hexdigest()!=row['content_sha256']:
            raise ValueError('RECORDED_HTTP_SOURCE_BYTES_CHANGED')
        return int(row['status_code']),raw,{},row['error']

    def _fetch_once(self, *, url, purpose, local_path, attempt):
        # Override only obtaining an HTTP reply. Native immutable body/header
        # persistence and request logging remain in the original client.
        try:
            status,body,headers,error=self.reply(url=url)
        except (HTTPException,OSError) as failure:
            result=FetchResult(url=url,status_code=0,local_path='',sha256='',content_length=0,headers_path='',error=str(failure))
        else:
            result=self._persist_result(url=url,status_code=status,body=body,headers=headers,local_path=local_path,error=error)
        self._append_log_row(result=result,purpose=purpose,attempt=attempt)
        return result
