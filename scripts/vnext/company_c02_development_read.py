"""Replay pending C02 in the explicitly pinned creator, without network."""
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch


def main():
    runtime, work, source, company = sys.argv[1:]
    runtime = Path(runtime)
    from company_worker_guard import install_worker_guards
    install_worker_guards(runtime)
    sys.path[:0] = [str(runtime), str(runtime/'scripts')]
    from vnext.company_c02_development import replay_review
    with patch.object(socket.socket, 'connect', side_effect=ValueError('COMPANY_C02_REVIEW_NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo', side_effect=ValueError('COMPANY_C02_REVIEW_DNS_FORBIDDEN')):
        receipt, out = replay_review(work=Path(work), source=Path(source), company_id=company)
    print(json.dumps({'review_id': receipt['review_id'],
        'source_sha256': out['processing']['source_sha256'],
        'facts_and_unresolved': out['processing']['model_facts_and_unresolved'],
        'source_filing': out['processing']['source_filing'], 'status': 'REVIEW_REQUIRED',
        'semantic_acceptance': False, 'business_metric_completed': False}))


if __name__ == '__main__':
    main()
