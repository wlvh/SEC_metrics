"""OFFLINE SecureGPT probe tests with synthetic SDKs; not connectivity evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import probe_securegpt as probe  # noqa: E402

sdk = probe.sdk


class MessageFormatTests(unittest.TestCase):
    def test_string_content_becomes_text_parts(self):
        self.assertEqual(sdk.securegpt_messages([{'role': 'user', 'content': 'hi'}]),
                         [{'role': 'user', 'content': [{'type': 'text', 'text': 'hi'}]}])

    def test_text_parts_pass_through_unchanged(self):
        parts = [{'type': 'text', 'text': 'a'}, {'type': 'text', 'text': 'b'}]
        self.assertEqual(sdk.securegpt_messages([{'role': 'system', 'content': parts}])[0]['content'], parts)

    def test_non_text_or_malformed_messages_are_rejected_not_dropped(self):
        for messages in ([], [{'role': 'user', 'content': [{'type': 'image_url', 'image_url': 'x'}]}],
                         [{'role': 'user', 'content': [{'type': 'text', 'text': 'a'}, {'type': 'file'}]}],
                         [{'role': 'user', 'content': 'a', 'name': 'extra'}],
                         [{'role': 'user', 'content': []}], [{'role': '', 'content': 'a'}]):
            with self.subTest(messages=messages), self.assertRaises(ValueError):
                sdk.securegpt_messages(messages)


class ResponseTests(unittest.TestCase):
    def setUp(self):
        self.request = probe.challenge()
        self.answer = {'nonce': self.request['nonce'], 'sum': self.request['a'] + self.request['b']}
        self.text = json.dumps(self.answer)

    def test_string(self):
        self.assertEqual(probe.validate(self.text, self.request), self.answer)

    def test_dict(self):
        self.assertEqual(probe.validate(self.answer, self.request), self.answer)

    def test_choices_and_text_blocks(self):
        raw = {'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant',
               'content': [{'type': 'text', 'text': self.text}]}}]}
        self.assertEqual(probe.validate(raw, self.request), self.answer)

    def test_explicit_path(self):
        self.assertEqual(probe.validate({'data': {'answer': self.text}}, self.request, 'data.answer'), self.answer)

    def test_error_message_not_success(self):
        with self.assertRaisesRegex(ValueError, 'SDK_ERROR'):
            probe.validate({'error': 'unauthorized', 'text': self.text}, self.request)

    def test_old_response_wrong_nonce(self):
        with self.assertRaisesRegex(ValueError, 'NONCE'):
            probe.validate({**self.answer, 'nonce': 'old-run'}, self.request)

    def test_wrong_sum_and_non_integer(self):
        for number in [str(self.answer['sum']), self.answer['sum'] + 1, True]:
            with self.subTest(number=number), self.assertRaisesRegex(ValueError, 'SUM'):
                probe.validate({**self.answer, 'sum': number}, self.request)

    def test_arbitrary_text_is_not_pass(self):
        for raw in ['hello', '', {'text': 'permission denied'}, {'message': 'HTTP 200'}]:
            with self.subTest(raw=raw), self.assertRaises((ValueError, TypeError)):
                probe.validate(raw, self.request)

    def test_truncation_is_not_pass(self):
        with self.assertRaisesRegex(ValueError, 'INCOMPLETE'):
            probe.validate({'choices': [{'finish_reason': 'length', 'message': {'content': self.text}}]}, self.request)

    def test_no_markdown_repair(self):
        with self.assertRaises(ValueError):
            probe.validate('```json\n'+self.text+'\n```', self.request)

    def test_response_object_with_text_body_is_kept_for_offline_reading(self):
        text = self.text

        class TextResponse:
            def raise_for_status(self):
                return None

            def json(self):
                raise ValueError('not JSON')

            @property
            def text(self):
                return text

        self.assertEqual(sdk.normalize_response(TextResponse()), self.text)
        self.assertEqual(probe.validate(sdk.normalize_response(TextResponse()), self.request), self.answer)


FAKE_SDK = '''
import json,os,re,sys,time
from pathlib import Path
class SecureGPT:
    def __init__(self,env):
        if env != 'dev': raise ValueError('test environment')
    def request(self,payload):
        p=Path(os.environ['TEST_MARKER']); p.write_text(p.read_text()+'1' if p.exists() else '1')
        assert set(payload)=={'messages'}
        assert set(payload['messages'][0])=={'role','content'}
        block=payload['messages'][0]['content'][0]
        assert block['type']=='text'
        print('SDK_PRIVATE_DIAGNOSTIC_FOR_TEST')
        prompt=block['text']
        nonce=re.search(r'"([0-9a-f]{24})"',prompt).group(1)
        a,b=map(int,re.search(r'整数(\\d+)加(\\d+)',prompt).groups())
        mode=os.environ.get('TEST_MODE','success')
        if mode=='sleep': time.sleep(15)
        if mode=='error': raise RuntimeError('SDK private error detail')
        if mode=='exit': sys.exit(2)
        if mode=='unknown': return {'data':{'answer':json.dumps({'nonce':nonce,'sum':a+b})}}
        return {'choices':[{'finish_reason':'stop','message':{'role':'assistant',
            'content':json.dumps({'nonce':nonce,'sum':a+b})}}]}
'''


class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sdk = self.root/'sdk'
        (self.sdk/'utils').mkdir(parents=True)
        (self.sdk/'utils/__init__.py').write_text('')
        (self.sdk/'utils/secure_gpt.py').write_text(FAKE_SDK)
        self.marker = self.root/'calls.txt'
        self.env = {**os.environ, 'TEST_MARKER': str(self.marker), 'SEC_INTERNAL_TEXT_PATH': '',
                    'SEC_WORKSPACE_URL': '', 'SEC_ENV': 'dev', 'SEC_INTERNAL_SDK_ROOT': ''}
        self.program = str(Path(probe.__file__).resolve())

    def run_probe(self, extra=(), mode='success', sdk_root=True):
        command = [sys.executable, self.program, '--env', 'dev',
                   *(['--sdk-root', str(self.sdk)] if sdk_root else []),
                   '--output-dir', str(self.root/'output'), *extra]
        return subprocess.run(command, env={**self.env, 'TEST_MODE': mode}, capture_output=True,
                              text=True, timeout=10)

    def test_one_request_verified_and_private_logs(self):
        process = self.run_probe()
        self.assertEqual(process.returncode, 0, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report['status'], 'PASS')
        self.assertTrue(report['sdk_returned'])
        self.assertEqual(self.marker.read_text(), '1')
        self.assertNotIn('SDK_PRIVATE_DIAGNOSTIC_FOR_TEST', process.stdout+process.stderr)
        self.assertIn('SDK_PRIVATE_DIAGNOSTIC_FOR_TEST', (self.root/'output/sdk.stdout.log').read_text())
        self.assertEqual(oct((self.root/'output').stat().st_mode & 0o777), oct(0o700))

    def test_timeout_no_retry(self):
        process = self.run_probe(['--timeout-seconds', '0.8'], mode='sleep')
        self.assertEqual(process.returncode, 124, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report['status'], 'TIMEOUT')
        self.assertEqual(report['remote_outcome'], 'UNKNOWN_DO_NOT_AUTOMATICALLY_RETRY')
        self.assertEqual(self.marker.read_text(), '1')

    def test_request_failure_no_retry(self):
        process = self.run_probe(mode='error')
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertEqual(json.loads(process.stdout)['status'], 'REQUEST_ERROR_REMOTE_OUTCOME_UNKNOWN')
        self.assertNotIn('SDK private error detail', process.stdout)
        self.assertEqual(self.marker.read_text(), '1')

    def test_sdk_exit_inside_request_is_a_final_unknown_outcome(self):
        process = self.run_probe(mode='exit')
        self.assertEqual(process.returncode, 1, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report['status'], 'WORKER_EXIT_FAILED')
        self.assertEqual(report['remote_outcome'], 'UNKNOWN_DO_NOT_AUTOMATICALLY_RETRY')
        self.assertEqual(report['worker_exit_code'], 2)
        self.assertEqual(self.marker.read_text(), '1')

    def test_unknown_response_then_offline_path_recheck(self):
        first = self.run_probe(mode='unknown')
        self.assertEqual(first.returncode, 2, first.stderr)
        second = subprocess.run([sys.executable, self.program, '--replay-dir', str(self.root/'output'),
                                 '--text-path', 'data.answer'], capture_output=True, text=True,
                                env=self.env, timeout=10)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout)['status'], 'PASS_SAVED_RESPONSE')
        self.assertEqual(self.marker.read_text(), '1')

    def test_missing_sdk_no_request(self):
        process = self.run_probe(['--sdk-root', str(self.root/'missing')])
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertEqual(json.loads(process.stdout)['status'], 'INITIALIZATION_FAILED')
        self.assertFalse(self.marker.exists())

    def test_sdk_not_installed_is_initialization_failure(self):
        process = self.run_probe(sdk_root=False)
        self.assertEqual(process.returncode, 1, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report['status'], 'INITIALIZATION_FAILED')
        self.assertEqual(report['sdk_request_invocations'], 0)
        self.assertFalse(self.marker.exists())

    def test_existing_output_no_second_call(self):
        self.assertEqual(self.run_probe().returncode, 0)
        self.assertEqual(self.run_probe().returncode, 2)
        self.assertEqual(self.marker.read_text(), '1')

    def test_bootstrap_sequence_no_spark(self):
        (self.sdk/'config.py').write_text('''
import os
def get_main_config(path,env,flag):
    assert env=='dev' and flag is True
    os.environ['BOOTSTRAP_STAGE']='1'
''')
        (self.sdk/'utils/config_utils.py').write_text('''
import os
def load_config(config,field):
    assert os.environ['BOOTSTRAP_STAGE']=='1'
    os.environ['BOOTSTRAP_STAGE']='2'
    return {'environment':{'test-workspace.invalid':'dev'}}
''')
        (self.sdk/'utils/setup_utils.py').write_text('''
import os
def set_env_vars(ws,env):
    assert os.environ['BOOTSTRAP_STAGE']=='2'
    assert ws=='test-workspace.invalid' and env=='dev'
''')
        process = self.run_probe(['--bootstrap', '--workspace-url', 'https://test-workspace.invalid/'])
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(self.marker.read_text(), '1')

    def test_mismatched_workspace_no_request(self):
        (self.sdk/'config.py').write_text('def get_main_config(*a): pass\n')
        (self.sdk/'utils/config_utils.py').write_text(
            "def load_config(**kw): return {'environment':{'test-workspace.invalid':'prod'}}\n")
        process = self.run_probe(['--bootstrap', '--workspace-url', 'test-workspace.invalid'])
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertFalse(self.marker.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
