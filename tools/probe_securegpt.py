#!/usr/bin/env python3
"""SecureGPT connectivity probe: one SDK request, strict answer check, no fallback.

Sends one random nonce and two small integers through scripts/securegpt_sdk.py
and passes only when the assistant returns strict JSON with that nonce and the
correct sum. A connectivity/usability check, not a financial-metric check.

The SDK and credentials come from the corporate image. The run directory may
hold SDK diagnostics: keep it inside the internal network, never commit it.
The timeout stops the local worker, not the remote server or SDK retries.
Operator guide: docs/securegpt_probe.md.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT/'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT/'scripts'))
import securegpt_sdk as sdk  # noqa: E402


def save(path: Path, value: Any) -> None:
    """Write private JSON; replacement is local output, never a source mutation."""
    temp = path.with_name('.' + path.name + '.tmp')
    with temp.open('w', encoding='utf-8') as stream:
        os.chmod(temp, 0o600)
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    temp.replace(path)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def challenge() -> dict:
    nonce = secrets.token_hex(12)
    a, b = secrets.randbelow(900) + 100, secrets.randbelow(900) + 100
    prompt = (f'这是连通性测试，不是财报数据。不要使用工具。只返回一个严格JSON对象，'
              f'恰好包含nonce和sum两个字段，不要Markdown或其他文字。'
              f'nonce为字符串"{nonce}"；sum为整数{a}加{b}的计算结果。')
    return {'nonce': nonce, 'a': a, 'b': b,
            'messages': [{'role': 'user', 'content': prompt}]}


def validate(raw: Any, request: dict, text_path: str | None = None) -> dict:
    if isinstance(raw, dict) and set(raw) == {'nonce', 'sum'}:
        answer = raw  # Some SDKs decode the assistant JSON before returning it.
    else:
        content = sdk.assistant_content(raw, text_path=text_path)
        answer = json.loads(content) if isinstance(content, str) else content
    if not isinstance(answer, dict) or set(answer) != {'nonce', 'sum'}:
        raise ValueError('JSON_FIELDS_MISMATCH')
    if answer['nonce'] != request['nonce']:
        raise ValueError('NONCE_MISMATCH')
    if type(answer['sum']) is not int or answer['sum'] != request['a'] + request['b']:
        raise ValueError('SUM_MISMATCH')
    return answer


def worker(root: Path) -> int:
    settings, request = load(root/'settings.json'), load(root/'request.json')
    report = {'status': 'INITIALIZING', 'provider': 'securegpt', 'mode': 'internal',
              'environment': settings['env'], 'sdk_request_invocations': 0,
              'sdk_returned': False, 'sdk_internal_retries': 'NOT_INSPECTED',
              'business_metric_tested': False}
    save(root/'summary.json', report)
    phase = 'INITIALIZATION'
    try:
        if settings['sdk_root']:
            sdk_path = Path(settings['sdk_root']).resolve(strict=True)
            if not sdk_path.is_dir():
                raise ValueError('SDK root must be a directory')
            sys.path.insert(0, str(sdk_path))
            os.chdir(sdk_path)
        if settings['bootstrap']:
            sdk.bootstrap(env=settings['env'], workspace_url=settings['workspace_url'] or '',
                          config_file=settings['config_file'])
        if settings['init_adls']:
            sdk.initialize_adls()
        client = sdk.open_client(env=settings['env'])
        phase = 'REQUEST'
        report.update(status='CALL_STARTED', sdk_request_invocations=1)
        save(root/'summary.json', report)
        raw = sdk.send(client=client, messages=request['messages'])
        report.update(sdk_returned=True, response_type=type(raw).__name__)
        save(root/'summary.json', report)
        phase = 'RESPONSE'
        normalized = sdk.normalize_response(raw)
        save(root/'response.json', normalized)
        phase = 'VALIDATION'
        answer = validate(normalized, request, settings['text_path'])
        save(root/'answer.json', answer)
        report.update(status='PASS', assistant_output_verified=True)
        code = 0
    except Exception as error:
        report.update(status={
            'INITIALIZATION': 'INITIALIZATION_FAILED',
            'REQUEST': 'REQUEST_ERROR_REMOTE_OUTCOME_UNKNOWN',
            'RESPONSE': 'RESPONSE_RECEIVED_UNPARSED_OR_ERROR',
            'VALIDATION': 'RESPONSE_RECEIVED_CONTRACT_FAILED',
        }[phase], assistant_output_verified=False, error_type=type(error).__name__)
        # SDK exceptions may contain private endpoints/tokens; keep them local.
        save(root/'failure.json', {'phase': phase, 'type': type(error).__name__, 'message': str(error)})
        code = 2 if phase in {'RESPONSE', 'VALIDATION'} else 1
    save(root/'summary.json', report)
    return code


FINAL_STATUSES = {'PASS', 'INITIALIZATION_FAILED', 'REQUEST_ERROR_REMOTE_OUTCOME_UNKNOWN',
                  'RESPONSE_RECEIVED_UNPARSED_OR_ERROR', 'RESPONSE_RECEIVED_CONTRACT_FAILED',
                  'TIMEOUT', 'INTERRUPTED'}


def remote_outcome(report: dict) -> str:
    if report.get('sdk_returned'):
        return 'SDK_RETURNED_POSTPROCESSING_INCOMPLETE'
    if report.get('sdk_request_invocations'):
        return 'UNKNOWN_DO_NOT_AUTOMATICALLY_RETRY'
    return 'NO_REQUEST_INVOCATION_OBSERVED'


def emit(report: dict) -> None:
    # Never put raw SDK replies, headers, credentials, or captured SDK logs in stdout.
    print(json.dumps(report, ensure_ascii=False), flush=True)


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', choices=sdk.ENVIRONMENTS, default=os.getenv('SEC_ENV'))
    parser.add_argument('--sdk-root', default=os.getenv('SEC_INTERNAL_SDK_ROOT'))
    parser.add_argument('--workspace-url', default=os.getenv('SEC_WORKSPACE_URL'))
    parser.add_argument('--config-file', default=os.getenv('SEC_INTERNAL_CONFIG', 'config/main_config.cfg'))
    parser.add_argument('--bootstrap', action='store_true')
    parser.add_argument('--init-adls', action='store_true')
    parser.add_argument('--text-path', default=os.getenv('SEC_INTERNAL_TEXT_PATH'))
    parser.add_argument('--timeout-seconds', type=float, default=180)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--replay-dir', type=Path, help='Check a saved response only; makes no SDK request')
    parser.add_argument('--_worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args._worker:
        return worker(args._worker.resolve())
    if args.replay_dir:
        try:
            root = args.replay_dir.resolve()
            validate(load(root/'response.json'), load(root/'request.json'), args.text_path)
            emit({'status': 'PASS_SAVED_RESPONSE', 'new_sdk_request_invocations': 0,
                  'live_connectivity_retested': False})
            return 0
        except Exception as error:
            emit({'status': 'SAVED_RESPONSE_CHECK_FAILED', 'error_type': type(error).__name__,
                  'new_sdk_request_invocations': 0})
            return 2
    if args.env not in sdk.ENVIRONMENTS or args.output_dir is None:
        parser.error('Supply explicit --env (or SEC_ENV) and --output-dir')
    if not 0 < args.timeout_seconds <= 3600:
        parser.error('--timeout-seconds must be > 0 and <= 3600')
    if args.bootstrap and not args.workspace_url:
        parser.error('--bootstrap requires --workspace-url (or SEC_WORKSPACE_URL)')
    root = args.output_dir.expanduser().resolve()
    if root.exists():
        parser.error('Use a new output directory; existing runs are not overwritten/retried')
    root.mkdir(parents=True, mode=0o700)
    settings = {k: getattr(args, k) for k in (
        'env', 'sdk_root', 'workspace_url', 'config_file', 'bootstrap', 'init_adls', 'text_path')}
    if settings['sdk_root']:
        settings['sdk_root'] = str(Path(settings['sdk_root']).expanduser().resolve())
    save(root/'settings.json', settings)
    save(root/'request.json', challenge())
    started = time.monotonic()
    command = [sys.executable, str(Path(__file__).resolve()), '--_worker', str(root)]
    with (root/'sdk.stdout.log').open('wb') as stdout, (root/'sdk.stderr.log').open('wb') as stderr:
        os.chmod(root/'sdk.stdout.log', 0o600)
        os.chmod(root/'sdk.stderr.log', 0o600)
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            code = child.wait(timeout=args.timeout_seconds)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
            # POSIX process group: do not leave a hung worker behind after local timeout.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
            report = load(root/'summary.json') if (root/'summary.json').is_file() else {}
            is_timeout = isinstance(error, subprocess.TimeoutExpired)
            report.update(status='TIMEOUT' if is_timeout else 'INTERRUPTED',
                          remote_outcome=remote_outcome(report), assistant_output_verified=False)
            save(root/'summary.json', report)
            code = 124 if is_timeout else 130
    report = load(root/'summary.json') if (root/'summary.json').is_file() else {'status': 'WORKER_FAILED'}
    if report.get('status') not in FINAL_STATUSES or (code != 0 and report.get('status') == 'PASS'):
        # The worker died outside its own handler (e.g. SDK sys.exit, OOM kill).
        report.update(status='WORKER_EXIT_FAILED', remote_outcome=remote_outcome(report),
                      assistant_output_verified=False, worker_exit_code=code)
        code = 1
    report.update(elapsed_seconds=round(time.monotonic()-started, 3), exit_code=code,
                  output_dir=str(root))
    save(root/'summary.json', report)
    emit(report)
    return code if code in {0, 1, 2, 124, 130} else 1


if __name__ == '__main__':
    raise SystemExit(cli())
