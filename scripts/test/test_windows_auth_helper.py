import os
from pathlib import Path
import subprocess
import tempfile
import unittest


HELPER = Path(__file__).resolve().parents[1] / 'auth' / 'apim-user-token-helper.windows.cmd'
SCRIPT = HELPER.with_suffix('.ps1')
TENANT = '11111111-1111-1111-1111-111111111111'
AUDIENCE = 'api://test-gateway'


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell and cmd.exe required')
class WindowsAuthHelperTests(unittest.TestCase):
    def test_native_cli_explicit_tenant_redacted_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_az = root / 'fake az.cmd'
            args_file = root / 'args.txt'
            fake_az.write_text('@echo off\r\n'
                               'echo %* > "%FAKE_ARGS_FILE%"\r\n'
                               'echo sensitive-stderr 1>&2\r\n'
                               'if "%FAKE_SLEEP%"=="1" ping -n 35 127.0.0.1 >nul\r\n'
                               'if "%FAKE_MULTILINE%"=="1" echo second-line\r\n'
                               'if not "%FAKE_OUTPUT%"=="" echo %FAKE_OUTPUT%\r\n'
                               'exit /b %FAKE_STATUS%\r\n', encoding='ascii')
            env = {**os.environ, 'FAKE_ARGS_FILE': str(args_file), 'FAKE_STATUS': '0',
                   'FAKE_OUTPUT': 'token-1', 'FAKE_SLEEP': '0', 'FAKE_MULTILINE': '0'}

            def invoke(**overrides):
                return subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                       '-File', str(SCRIPT), '-TenantId', TENANT, '-Audience', AUDIENCE,
                                       '-AzureCliPath', str(fake_az)], env={**env, **overrides},
                                      capture_output=True, text=True, timeout=45, cwd=root)

            for token in ('token-1', 'token-2'):
                result = invoke(FAKE_OUTPUT=token)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), token)
                self.assertEqual(result.stderr, '')
            self.assertEqual(args_file.read_text().strip(),
                             f'account get-access-token --tenant {TENANT} --resource {AUDIENCE} --query accessToken --output tsv')
            for output, status in [('', '0'), ('null', '0'), ('bad token', '0'), ('token', '1')]:
                with self.subTest(output=output, status=status):
                    result = invoke(FAKE_OUTPUT=output, FAKE_STATUS=status)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, '')
                    self.assertEqual(result.stderr.strip(), 'Unable to acquire access token')
            for overrides in ({'FAKE_MULTILINE': '1'}, {'FAKE_OUTPUT': 'token-1\tbad'}):
                result = invoke(**overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertEqual(result.stderr.strip(), 'Unable to acquire access token')
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                     '-File', str(SCRIPT), '-TenantId', TENANT, '-Audience', 'api://gateway&whoami',
                                     '-AzureCliPath', str(fake_az)], env=env, capture_output=True,
                                    text=True, cwd=root)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertEqual(result.stderr.strip(), 'Unable to acquire access token')
            result = subprocess.run([str(HELPER)], env={**env, 'APIM_TENANT_ID': '', 'APIM_AUDIENCE': ''},
                                    capture_output=True, text=True, cwd=root)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertEqual(result.stderr.strip(), 'Unable to acquire access token')
            result = invoke(FAKE_SLEEP='1')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertEqual(result.stderr.strip(), 'Unable to acquire access token')


if __name__ == '__main__':
    unittest.main()
