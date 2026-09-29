param(
    [string]$TenantId = $env:APIM_TENANT_ID,
    [string]$Audience = $env:APIM_AUDIENCE,
    [string]$AzureCliPath = 'C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd'
)

$failure = 'Unable to acquire access token'
try {
    # These values are passed through cmd.exe; reject shell metacharacters before constructing its command line.
    if ($TenantId -notmatch '\A[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\z' -or
        $Audience -notmatch '\A(?:api|https)://[A-Za-z0-9._~:/-]+\z' -or
        $AzureCliPath -notmatch '\A[A-Za-z]:\\[A-Za-z0-9._\\ -]+\.cmd\z') { throw $failure }
    if (-not [IO.File]::Exists($AzureCliPath)) { throw $failure }

    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = "$env:SystemRoot\System32\cmd.exe"
    $start.Arguments = '/d /s /c ""{0}" account get-access-token --tenant {1} --resource {2} --query accessToken --output tsv"' -f $AzureCliPath, $TenantId, $Audience
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardInput = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.WorkingDirectory = if ($env:USERPROFILE -match '\A[A-Za-z]:\\' -and [IO.Directory]::Exists($env:USERPROFILE)) { $env:USERPROFILE } else { $env:SystemRoot }
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    try {
        if (-not $process.Start()) { throw $failure }
        $process.StandardInput.Close()
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(15000)) {
            & "$env:SystemRoot\System32\taskkill.exe" /F /T /PID $process.Id > $null 2>&1
            throw $failure
        }
        if ($process.ExitCode -ne 0) { throw $failure }
        if (-not $stdout.Wait(2000)) { throw $failure }
        $token = $stdout.Result -creplace '\r?\n\z', ''
        if ($token -ceq 'null' -or -not [regex]::IsMatch($token, '\A[!-~]{1,65536}\z')) { throw $failure }
        [Console]::Out.WriteLine($token)
    } finally {
        $process.Dispose()
    }
} catch {
    [Console]::Error.WriteLine($failure)
    exit 1
}
