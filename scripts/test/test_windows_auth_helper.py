"""Fake CLI only. On Windows, also works with the two auth sources beside this file."""

import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


AUTH = Path(__file__).resolve().parent
if not (AUTH / 'apim-user-token-helper.windows.cmd').is_file():
    AUTH = AUTH.parent / 'auth'
HELPER = AUTH / 'apim-user-token-helper.windows.cmd'
SCRIPT = HELPER.with_suffix('.ps1')
TENANT = '11111111-1111-1111-1111-111111111111'
SUBSCRIPTION = '22222222-2222-2222-2222-222222222222'
AUDIENCE = 'api://test-gateway'
METADATA = {'id': SUBSCRIPTION, 'tenantId': TENANT, 'accountType': 'user',
            'environmentName': 'AzureCloud', 'state': 'Enabled'}
METADATA_ARGS = ['account', 'show', '--subscription', SUBSCRIPTION, '--query',
                 '{id:id,tenantId:tenantId,accountType:user.type,environmentName:environmentName,state:state}',
                 '--output', 'json', '--only-show-errors']
TOKEN_ARGS = ['account', 'get-access-token', '--subscription', SUBSCRIPTION,
              '--resource', AUDIENCE, '--query', 'accessToken', '--output', 'tsv']
CA_FAILURE = ('conditional_access_auth_flow: AADSTS530036: Conditional Access rejected refresh-token reuse under '
              'authentication-flows checks. Review the matched policy and Original transfer method; '
              'another login may not resolve this.')
STREAM_FAILURE = 'stream_read_failed: Unable to complete reading Azure CLI output.'
TIMEOUT_FAILURE = 'azure_cli_timeout: Azure CLI exceeded the 15s acquisition budget.'
METADATA_FAILURE = ('subscription_metadata_invalid: Cached subscription metadata did not match the required '
                    'user, tenant, cloud, and state.')


def creation_time(kernel, handle):
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_uint64)] * 4
    times = [ctypes.c_uint64() for _ in range(4)]
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in times)):
        raise ctypes.WinError(ctypes.get_last_error())
    return times[0].value


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell and cmd.exe required')
class WindowsAuthHelperTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='opencode-windows-auth-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.fake_az = self.root / 'fake az.cmd'
        self.args_file = self.root / 'args.txt'
        self.child_file = self.root / 'child.txt'
        self.stdout_file = self.root / 'stdout.bin'
        self.stderr_file = self.root / 'stderr.bin'
        self.metadata_file = self.root / 'metadata.json'
        self.metadata_file.write_text(json.dumps(METADATA), encoding='ascii')
        fake_cli = self.root / 'fake_cli.py'
        fake_cli.write_text('''import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time

if sys.argv[1:] == ['--child']:
    time.sleep(float(os.environ['FAKE_CHILD_SLEEP']))
    sys.exit(0)
with Path(os.environ['FAKE_ARGS_FILE']).open('a', encoding='utf-8') as args_file:
    args_file.write(json.dumps(sys.argv[1:]) + '\\n')
metadata = sys.argv[1:3] == ['account', 'show']
time.sleep(float(os.environ['FAKE_METADATA_DELAY' if metadata else 'FAKE_TOKEN_DELAY']))
os.write(2, Path(os.environ['FAKE_STDERR_FILE']).read_bytes())
os.write(1, Path(os.environ['FAKE_METADATA_FILE' if metadata else 'FAKE_STDOUT_FILE']).read_bytes())
mode = os.environ['FAKE_METADATA_MODE' if metadata else 'FAKE_MODE']
if mode != 'normal':
    child = subprocess.Popen([sys.executable, '-I', '-B', __file__, '--child'],
                             stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL if mode == 'hold_stderr' else sys.stdout,
                             stderr=subprocess.DEVNULL if mode == 'hold_stdout' else sys.stderr,
                             close_fds=False)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_uint64)] * 4
    times = [ctypes.c_uint64() for _ in range(4)]
    if not kernel.GetProcessTimes(int(child._handle), *(ctypes.byref(value) for value in times)):
        raise ctypes.WinError(ctypes.get_last_error())
    Path(os.environ['FAKE_CHILD_FILE']).write_text(f'{child.pid} {times[0].value}')
    if mode == 'sleep':
        time.sleep(60)
sys.exit(int(os.environ['FAKE_METADATA_STATUS' if metadata else 'FAKE_STATUS']))
''', encoding='ascii')
        self.fake_az.write_bytes(b'@echo off\r\n"%FAKE_PYTHON%" -I -B "%FAKE_CLI%" %*\r\nexit /b %errorlevel%\r\n')
        self.powershell = str(Path(os.environ['SystemRoot']) / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe')
        self.env = {**os.environ, 'APIM_TENANT_ID': TENANT, 'APIM_AUDIENCE': AUDIENCE,
                    'FAKE_PYTHON': sys.executable, 'FAKE_CLI': str(fake_cli),
                    'FAKE_ARGS_FILE': str(self.args_file), 'FAKE_CHILD_FILE': str(self.child_file),
                    'FAKE_STDOUT_FILE': str(self.stdout_file), 'FAKE_STDERR_FILE': str(self.stderr_file),
                    'FAKE_METADATA_FILE': str(self.metadata_file), 'FAKE_METADATA_STATUS': '0',
                    'FAKE_METADATA_DELAY': '0', 'FAKE_TOKEN_DELAY': '0', 'FAKE_METADATA_MODE': 'normal',
                    'FAKE_MODE': 'normal', 'FAKE_STATUS': '0', 'FAKE_CHILD_SLEEP': '12',
                    'FAKE_HELPER': str(SCRIPT), 'FAKE_AZ': str(self.fake_az)}
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
        self.kernel.OpenProcess.restype = ctypes.c_void_p
        self.kernel.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        self.kernel.TerminateProcess.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        self.kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
        self.addCleanup(self.finish_child)

    def start_helper(self, output=b'token-1\r\n', error=b'private-stderr', status=0,
                     env=None, explicit_inputs=True, subscription=None, wrapper=None):
        self.args_file.unlink(missing_ok=True)
        self.stdout_file.write_bytes(output)
        self.stderr_file.write_bytes(error)
        arguments = ['-TenantId', TENANT, '-Audience', AUDIENCE] if explicit_inputs else []
        if subscription is not None:
            arguments += ['-SubscriptionId', subscription]
        script = SCRIPT
        if wrapper is not None:
            script = self.root / 'wrapper.ps1'
            script.write_text('param([string]$TenantId, [string]$Audience, [string]$AzureCliPath, [string]$SubscriptionId)\n'
                              + wrapper + '\n& $env:FAKE_HELPER @PSBoundParameters\nexit $LASTEXITCODE\n', encoding='ascii')
        return subprocess.Popen([self.powershell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                 '-File', str(script), *arguments, '-AzureCliPath', str(self.fake_az)],
                                env={**self.env, 'FAKE_STATUS': str(status), **(env or {})},
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.root)

    def invoke(self, **kwargs):
        with self.start_helper(**kwargs) as process:
            try:
                output, error = process.communicate(timeout=35)
            finally:
                if process.poll() is None:
                    process.kill()
                    self.finish_child()
        return subprocess.CompletedProcess(process.args, process.returncode, output, error)

    def invoke_leaky(self, **kwargs):
        started = time.monotonic()
        with self.start_helper(**kwargs) as process:
            try:
                process.wait(timeout=25)
                elapsed = time.monotonic() - started
                self.assertTrue(self.child_running())  # The helper must not kill descendants of an exited CLI.
            finally:
                if process.poll() is None:
                    process.kill()
                self.finish_child()  # Release caller pipes only AFTER measuring helper-process exit.
            output, error = process.communicate(timeout=5)
        return subprocess.CompletedProcess(process.args, process.returncode, output, error), elapsed

    def calls(self):
        return [json.loads(line) for line in self.args_file.read_text(encoding='utf-8').splitlines()]

    def assert_failure(self, result, message):
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, message + '\n')
        self.assertLess(len(result.stderr), 512)

    def child_running(self, terminate=False):
        if not self.child_file.exists():
            return False
        pid, created = map(int, self.child_file.read_text().split())
        # Query identity and (if requested) terminate using the SAME handle, never a reopened PID.
        handle = self.kernel.OpenProcess(0x101001, False, pid)  # SYNCHRONIZE | QUERY_LIMITED_INFORMATION | TERMINATE
        if not handle:
            self.assertEqual(ctypes.get_last_error(), 87)  # Process no longer exists.
            self.child_file.unlink()
            return False
        try:
            if creation_time(self.kernel, handle) != created:
                self.child_file.unlink()  # The recorded process is gone; this PID belongs to someone else.
                return False
            status = self.kernel.WaitForSingleObject(handle, 0)
            self.assertIn(status, (0, 258))  # WAIT_OBJECT_0 or WAIT_TIMEOUT
            if status == 258:
                if not terminate:
                    return True
                if not self.kernel.TerminateProcess(handle, 1):
                    self.assertEqual(self.kernel.WaitForSingleObject(handle, 0), 0)  # May have just exited.
                self.assertEqual(self.kernel.WaitForSingleObject(handle, 2000), 0)
            self.child_file.unlink()
            return False
        finally:
            self.kernel.CloseHandle(handle)

    def finish_child(self):
        self.assertFalse(self.child_running(terminate=True))

    def test_success_ignores_noisy_stderr_and_preserves_arguments(self):
        for token in (b'token-1\r\n', b'token-2\n', b'token-3'):
            with self.subTest(token=token):
                result = self.invoke(output=token, error=b'AADSTS530036 sensitive-stderr\n' * 8192,
                                     explicit_inputs=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, token.decode().rstrip('\r\n') + '\n')
                self.assertEqual(result.stderr, '')
                self.assertEqual(self.calls(), [['account', 'get-access-token', '--tenant', TENANT,
                                                '--resource', AUDIENCE, '--query', 'accessToken', '--output', 'tsv']])

    def test_subscription_selects_only_the_verified_cached_account(self):
        result = self.invoke(subscription=SUBSCRIPTION, error=b'AADSTS530036 private-warning\n' * 8192)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'token-1\n', ''))
        self.assertEqual(self.calls(), [METADATA_ARGS, TOKEN_ARGS])
        self.assert_failure(self.invoke(subscription=SUBSCRIPTION, error=b'AADSTS530036 private-error', status=1),
                            CA_FAILURE)
        self.assertEqual(self.calls(), [METADATA_ARGS, TOKEN_ARGS])

    def test_subscription_metadata_fails_closed_before_token_request(self):
        cases = [('empty', b''), ('malformed', b'{private-invalid'), ('null', b'null'), ('array', b'[]'),
                 ('singleton-array', json.dumps([METADATA]).encode()), ('string', b'"private-metadata"'),
                 ('scalar', b'7'), ('trailing-json', json.dumps(METADATA).encode() + b' {}')]
        for field in METADATA:
            cases.append((f'missing-{field}', json.dumps({k: v for k, v in METADATA.items() if k != field}).encode()))
            for value in (None, '', ' ', 7, [], {'private': 'value'}):
                cases.append((f'invalid-{field}-{value!r}', json.dumps({**METADATA, field: value}).encode()))
        for field, value in (('id', '33333333-3333-3333-3333-333333333333'),
                             ('tenantId', '33333333-3333-3333-3333-333333333333'),
                             ('accountType', 'servicePrincipal'), ('environmentName', 'AzureUSGovernment'),
                             ('state', 'Disabled')):
            cases.append((f'wrong-{field}', json.dumps({**METADATA, field: value}).encode()))
        for name, metadata in cases:
            with self.subTest(case=name):
                self.metadata_file.write_bytes(metadata)
                self.assert_failure(self.invoke(subscription=SUBSCRIPTION), METADATA_FAILURE)
                self.assertEqual(self.calls(), [METADATA_ARGS])

    def test_subscription_metadata_cli_failure_has_no_fallback(self):
        for error, message in ((b'private-error', 'azure_cli_failed: Azure CLI exited with code 7.'),
                               (b'AADSTS530036 private-error', CA_FAILURE)):
            with self.subTest(error=error):
                self.assert_failure(self.invoke(subscription=SUBSCRIPTION, error=error,
                                                env={'FAKE_METADATA_STATUS': '7'}), message)
                self.assertEqual(self.calls(), [METADATA_ARGS])

    def test_subscription_validation_never_falls_back(self):
        for subscription in ('', 'private-subscription&whoami', '{' + SUBSCRIPTION + '}', SUBSCRIPTION + '0', ' '):
            with self.subTest(subscription=subscription):
                self.assert_failure(self.invoke(subscription=subscription),
                                    'configuration_invalid: SubscriptionId must be a canonical UUID when supplied.')
                self.assertFalse(self.args_file.exists())
        for name, message in (('APIM_TENANT_ID', 'TenantId must be a canonical UUID.'),
                              ('APIM_AUDIENCE', 'Audience must be a supported api:// or https:// resource.')):
            with self.subTest(name=name):
                self.assert_failure(self.invoke(subscription=SUBSCRIPTION, env={name: ''}, explicit_inputs=False),
                                    'configuration_invalid: ' + message)
                self.assertFalse(self.args_file.exists())

    def test_conditional_access_is_allowlisted_and_redacted(self):
        private = (b'\x1b[31mERROR:\x1b[0m AADSTS530036: secret-token user@example.invalid\r\n'
                   b'11111111-2222-3333-4444-555555555555 https://private.invalid/path?secret=fake\r\n')
        for error in (b'AADSTS530036', private, private + b'AADSTS530036\nAADSTS530036'):
            with self.subTest(error=error):
                self.assert_failure(self.invoke(output=b'token-looking-stdout\n', error=error, status=1), CA_FAILURE)

    def test_unknown_codes_and_collisions_are_generic(self):
        for error in (b'', b'private-secret user@example.invalid', b'AADSTS123456', b'AADSTS5300367',
                      b'XAADSTS530036', b'AADSTS530036_extra', b'aadsts530036'):
            with self.subTest(error=error):
                self.assert_failure(self.invoke(output=b'AADSTS530036\ntoken-looking-stdout\n', error=error, status=7),
                                    'azure_cli_failed: Azure CLI exited with code 7.')

    def test_invalid_token_output(self):
        for output in (b'', b'null\r\n', b' ', b'\r\n', b'bad token\n', b'first\nsecond\n',
                       b'token\n\n', b'token\tbad', b'token\x00bad', b'token\x1bbad', b'token\x7fbad',
                       b'x' * 65537 + b'\n'):
            with self.subTest(length=len(output), prefix=output[:20]):
                self.assert_failure(self.invoke(output=output),
                                    'invalid_token_output: Azure CLI did not return one valid raw token.')
        result = self.invoke(output=b'x' * 65536 + b'\r\n')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'x' * 65536 + '\n', ''))

    def test_configuration_and_missing_executable(self):
        for name, value, message in (
            ('APIM_TENANT_ID', '', 'TenantId must be a canonical UUID.'),
            ('APIM_TENANT_ID', 'private-tenant&whoami', 'TenantId must be a canonical UUID.'),
            ('APIM_AUDIENCE', '', 'Audience must be a supported api:// or https:// resource.'),
            ('APIM_AUDIENCE', 'api://private&whoami', 'Audience must be a supported api:// or https:// resource.'),
        ):
            with self.subTest(name=name, value=value):
                self.assert_failure(self.invoke(env={name: value}, explicit_inputs=False), 'configuration_invalid: ' + message)
        for name, message in (('APIM_TENANT_ID', 'TenantId must be a canonical UUID.'),
                              ('APIM_AUDIENCE', 'Audience must be a supported api:// or https:// resource.')):
            removed = self.env.pop(name)
            try:
                self.assert_failure(self.invoke(explicit_inputs=False), 'configuration_invalid: ' + message)
            finally:
                self.env[name] = removed
        self.fake_az.unlink()
        self.assert_failure(self.invoke(), 'azure_cli_not_found: Install native Azure CLI at the configured path.')
        self.fake_az = self.root / 'private&invalid.cmd'
        self.assert_failure(self.invoke(),
                            'configuration_invalid: AzureCliPath must be a supported absolute .cmd path.')
        self.assertFalse(self.args_file.exists())

    def test_process_start_failure_is_redacted(self):
        # Keep PowerShell bootstrap healthy; corrupt SystemRoot only at the CLI start boundary.
        wrapper = ("$line = (Select-String -Path $env:FAKE_HELPER -SimpleMatch 'if (-not $process.Start())').LineNumber\n"
                   "$null = Set-PSBreakpoint -Script $env:FAKE_HELPER -Line $line -Action {\n"
                   "    $original = $env:SystemRoot\n"
                   "    try {\n"
                   "        $env:SystemRoot = $env:FAKE_MISSING_SYSTEMROOT\n"
                   "        $process.StartInfo.FileName = \"$env:SystemRoot\\System32\\cmd.exe\"\n"
                   "    } finally { $env:SystemRoot = $original }\n}")
        self.assert_failure(self.invoke(wrapper=wrapper,
                                        env={'FAKE_MISSING_SYSTEMROOT': str(self.root / 'missing-system-root')}),
                            'process_start_failed: Unable to start Azure CLI.')
        self.assertFalse(self.args_file.exists())

    def test_launcher_remains_no_argument_and_inherits_environment(self):
        # Probe only a temporary copy; never replace the fixed-argument installed pilot launcher.
        launcher = self.root / HELPER.name
        shutil.copyfile(HELPER, launcher)
        launcher.with_suffix('.ps1').write_text(
            "if ($args.Count -ne 0) { exit 2 }\n"
            f"if ($env:APIM_TENANT_ID -ne '{TENANT}' -or $env:APIM_AUDIENCE -ne '{AUDIENCE}') {{ exit 3 }}\n"
            "[Console]::Out.WriteLine('launcher-env-ok')\n", encoding='ascii')
        result = subprocess.run([str(launcher), 'not-forwarded'], env=self.env, capture_output=True,
                                text=True, timeout=10, cwd=self.root)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'launcher-env-ok\n', ''))
        launcher.with_suffix('.ps1').write_text('& $env:FAKE_HELPER -AzureCliPath $env:FAKE_AZ\nexit $LASTEXITCODE\n',
                                               encoding='ascii')
        result = subprocess.run([str(launcher)], env={**self.env, 'APIM_TENANT_ID': '', 'APIM_AUDIENCE': ''},
                                capture_output=True, text=True, timeout=10, cwd=self.root)
        self.assert_failure(result, 'configuration_invalid: TenantId must be a canonical UUID.')

    def test_timeout_is_bounded_and_kills_own_child(self):
        started = time.monotonic()
        result = self.invoke(env={'FAKE_MODE': 'sleep', 'FAKE_CHILD_SLEEP': '60'})
        elapsed = time.monotonic() - started
        self.assert_failure(result, TIMEOUT_FAILURE)
        self.assertGreaterEqual(elapsed, 15)
        self.assertLess(elapsed, 25)
        self.assertTrue(self.child_file.exists())
        self.assertFalse(self.child_running())
        self.assertFalse(self.child_file.exists())
        self.finish_child()

    def test_inherited_pipes_have_bounded_helper_process_exit(self):
        for mode, status in (('hold_stdout', 0), ('hold_stderr', 7), ('hold_stdout', 7), ('hold_stderr', 0)):
            with self.subTest(mode=mode, status=status):
                result, elapsed = self.invoke_leaky(status=status, env={'FAKE_MODE': mode})
                self.assert_failure(result, STREAM_FAILURE)
                self.assertLess(elapsed, 10)
                self.assertFalse(self.child_file.exists())
                self.finish_child()

    @unittest.expectedFailure
    def test_known_powershell51_descendant_inheritance_delays_caller_eof(self):
        # Availability assertion only; process deadlines and diagnostics must pass in the separate tests.
        started = time.monotonic()
        self.invoke(env={'FAKE_MODE': 'hold_stdout'})
        self.assertLess(time.monotonic() - started, 10)

    def test_metadata_inherited_pipes_fail_before_token_request(self):
        for mode in ('hold_stdout', 'hold_stderr'):
            with self.subTest(mode=mode):
                result, elapsed = self.invoke_leaky(subscription=SUBSCRIPTION, env={'FAKE_METADATA_MODE': mode})
                self.assert_failure(result, STREAM_FAILURE)
                self.assertLess(elapsed, 10)
                self.assertEqual(self.calls(), [METADATA_ARGS])

    def test_subscription_metadata_and_token_share_one_budget(self):
        started = time.monotonic()
        result = self.invoke(subscription=SUBSCRIPTION,
                             env={'FAKE_METADATA_DELAY': '8', 'FAKE_TOKEN_DELAY': '9'})
        self.assert_failure(result, TIMEOUT_FAILURE)
        self.assertGreaterEqual(time.monotonic() - started, 15)
        self.assertLess(time.monotonic() - started, 25)
        self.assertEqual(self.calls(), [METADATA_ARGS, TOKEN_ARGS])

    def test_exhausted_budget_does_not_start_token(self):
        wrapper = ("$line = (Select-String -Path $env:FAKE_HELPER -SimpleMatch \"`$selector = '--subscription\").LineNumber\n"
                   '$null = Set-PSBreakpoint -Script $env:FAKE_HELPER -Line $line -Action { Start-Sleep -Seconds 16 }')
        self.assert_failure(self.invoke(subscription=SUBSCRIPTION, wrapper=wrapper), TIMEOUT_FAILURE)
        self.assertEqual(self.calls(), [METADATA_ARGS])

    def test_stream_completion_uses_remaining_shared_budget(self):
        budget_file = self.root / 'budget.txt'
        # Inject only after the token process exits; prove the short stream-wait branch, not wall time.
        wrapper = r'''
$lines = @(Select-String -Path $env:FAKE_HELPER -SimpleMatch '$remaining = 15000 - $acquisition.ElapsedMilliseconds')
if ($lines.Count -ne 2) { throw 'Expected two remaining-budget calculations.' }
$null = Set-PSBreakpoint -Script $env:FAKE_HELPER -Line $lines[1].LineNumber -Action {
    if ($CliArguments.StartsWith('account get-access-token ') -and $started -and $process.HasExited) {
        (Get-Variable acquisition).Value = [pscustomobject]@{ElapsedMilliseconds = 14500}
    }
}
$line = (Select-String -Path $env:FAKE_HELPER -SimpleMatch 'if ($remaining -lt 2000 -or $acquisition.ElapsedMilliseconds -ge 15000)').LineNumber
$null = Set-PSBreakpoint -Script $env:FAKE_HELPER -Line ($line + 1) -Action {
    [IO.File]::WriteAllText($env:FAKE_BUDGET_FILE, ('{0} {1} {2} {3}' -f $remaining, $acquisition.ElapsedMilliseconds, $started, $process.HasExited))
}
'''
        result, elapsed = self.invoke_leaky(
            subscription=SUBSCRIPTION, wrapper=wrapper,
            env={'FAKE_MODE': 'hold_stderr', 'FAKE_BUDGET_FILE': str(budget_file)})
        self.assert_failure(result, TIMEOUT_FAILURE)
        self.assertEqual(budget_file.read_text().split(), ['500', '14500', 'True', 'True'])
        self.assertLess(elapsed, 10)
        self.assertEqual(self.calls(), [METADATA_ARGS, TOKEN_ARGS])

    def test_fixture_cleanup_rejects_reused_pid_and_is_idempotent(self):
        guard = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'import time; time.sleep(60)'],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            created = creation_time(self.kernel, int(guard._handle))
            self.child_file.write_text(f'{guard.pid} {created + 1}')
            self.finish_child()
            self.finish_child()
            self.assertFalse(self.child_file.exists())
            self.assertIsNone(guard.poll())
        finally:
            if guard.poll() is None:
                guard.terminate()  # Popen retains this known process handle.
            guard.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
