param(
    [string]$TenantId = $env:APIM_TENANT_ID,
    [string]$Audience = $env:APIM_AUDIENCE,
    [string]$AzureCliPath = 'C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd',
    [string]$SubscriptionId
)

$ErrorActionPreference = 'Stop'

# Both CLI calls share the acquisition clock and redirect CLI output for validation.
function Invoke-AzureCli([string]$CliArguments) {
    $script:failure = 'process_start_failed: Unable to start Azure CLI.'
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = "$env:SystemRoot\System32\cmd.exe"
    $start.Arguments = '/d /s /c ""{0}" {1}"' -f $AzureCliPath, $CliArguments
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    # shortcut: PowerShell 5.1 descendants can delay caller EOF; revisit launch isolation if the installed CLI reproduces this.
    $start.RedirectStandardInput = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.WorkingDirectory = if ($env:USERPROFILE -match '\A[A-Za-z]:\\' -and [IO.Directory]::Exists($env:USERPROFILE)) { $env:USERPROFILE } else { $env:SystemRoot }
    $process = New-Object Diagnostics.Process
    $started = $false
    try {
        $process.StartInfo = $start
        $script:failure = 'azure_cli_timeout: Azure CLI exceeded the 15s acquisition budget.'
        if ($acquisition.ElapsedMilliseconds -ge 15000) { throw $failure }
        $script:failure = 'process_start_failed: Unable to start Azure CLI.'
        if (-not $process.Start()) { throw $failure }
        $started = $true
        $script:failure = 'stream_read_failed: Unable to complete reading Azure CLI output.'
        $process.StandardInput.Close()
        # shortcut: ReadToEndAsync buffers all CLI output; use capped readers if untrusted output must be supported.
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $script:failure = 'azure_cli_timeout: Azure CLI exceeded the 15s acquisition budget.'
        $remaining = 15000 - $acquisition.ElapsedMilliseconds
        if ($remaining -le 0 -or -not $process.WaitForExit([int]$remaining)) { throw $failure }
        $remaining = 15000 - $acquisition.ElapsedMilliseconds
        if ($remaining -le 0) { throw $failure }
        $script:failure = 'stream_read_failed: Unable to complete reading Azure CLI output.'
        # Even the unused stream must finish; a descendant may keep either private pipe open.
        if (-not [Threading.Tasks.Task]::WaitAll([Threading.Tasks.Task[]]@($stdout, $stderr), [int][Math]::Min(2000, $remaining))) {
            if ($remaining -lt 2000 -or $acquisition.ElapsedMilliseconds -ge 15000) {
                $script:failure = 'azure_cli_timeout: Azure CLI exceeded the 15s acquisition budget.'
            }
            throw $failure
        }
        $script:failure = 'azure_cli_timeout: Azure CLI exceeded the 15s acquisition budget.'
        if ($acquisition.ElapsedMilliseconds -ge 15000) { throw $failure }
        if ($process.ExitCode -ne 0) {
            $cliError = $stderr.Result
            $script:failure = 'azure_cli_failed: Azure CLI exited with code {0}.' -f $process.ExitCode
            if ([regex]::IsMatch($cliError, '\bAADSTS530036\b')) {
                $script:failure = 'conditional_access_auth_flow: AADSTS530036: Conditional Access rejected refresh-token reuse under authentication-flows checks. Review the matched policy and Original transfer method; another login may not resolve this.'
            }
            throw $failure
        }
        $script:failure = 'internal_error: Unable to acquire access token.'
        return $stdout.Result
    } finally {
        try {
            if ($started -and -not $process.HasExited) {
                # Kill only this invocation's still-live CLI tree, with a separate bounded cleanup tail.
                $killer = New-Object Diagnostics.Process
                try {
                    $killer.StartInfo.FileName = "$env:SystemRoot\System32\taskkill.exe"
                    $killer.StartInfo.Arguments = '/F /T /PID {0}' -f $process.Id
                    $killer.StartInfo.UseShellExecute = $false
                    $killer.StartInfo.CreateNoWindow = $true
                    $killer.StartInfo.RedirectStandardOutput = $true
                    $killer.StartInfo.RedirectStandardError = $true
                    if (-not $killer.Start()) { throw $failure }
                    $null = $killer.StandardOutput.ReadToEndAsync()
                    $null = $killer.StandardError.ReadToEndAsync()
                    if (-not $killer.WaitForExit(2000)) {
                        $killer.Kill()
                        $null = $killer.WaitForExit(1000)
                    }
                    if (-not $process.WaitForExit(1000)) { throw $failure }
                } finally {
                    $killer.Dispose()
                }
            }
        } catch {
            $script:failure = 'cleanup_failed: Unable to stop the Azure CLI process tree.'
            throw $failure
        } finally {
            $process.Dispose()
        }
    }
}

$failure = 'internal_error: Unable to acquire access token.'
try {
    # These values are passed through cmd.exe; reject shell metacharacters before constructing its command line.
    $uuidPattern = '\A[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\z'
    $failure = 'configuration_invalid: TenantId must be a canonical UUID.'
    if ($TenantId -notmatch $uuidPattern) { throw $failure }
    $failure = 'configuration_invalid: Audience must be a supported api:// or https:// resource.'
    if ($Audience -notmatch '\A(?:api|https)://[A-Za-z0-9._~:/-]+\z') { throw $failure }
    $pinned = $PSBoundParameters.ContainsKey('SubscriptionId')
    $failure = 'configuration_invalid: SubscriptionId must be a canonical UUID when supplied.'
    if ($pinned -and $SubscriptionId -notmatch $uuidPattern) { throw $failure }
    $failure = 'configuration_invalid: AzureCliPath must be a supported absolute .cmd path.'
    if ($AzureCliPath -notmatch '\A[A-Za-z]:\\[A-Za-z0-9._\\ -]+\.cmd\z') { throw $failure }
    $failure = 'azure_cli_not_found: Install native Azure CLI at the configured path.'
    if (-not [IO.File]::Exists($AzureCliPath)) { throw $failure }

    $acquisition = [Diagnostics.Stopwatch]::StartNew()
    $selector = '--tenant {0}' -f $TenantId
    if ($pinned) {
        $metadataQuery = '{id:id,tenantId:tenantId,accountType:user.type,environmentName:environmentName,state:state}'
        $metadataText = Invoke-AzureCli ('account show --subscription {0} --query "{1}" --output json --only-show-errors' -f $SubscriptionId, $metadataQuery)
        $failure = 'subscription_metadata_invalid: Cached subscription metadata did not match the required user, tenant, cloud, and state.'
        # Reject arrays before ConvertFrom-Json can unwrap a singleton array on Windows PowerShell.
        if ($metadataText -notmatch '\A\s*\{') { throw $failure }
        $metadata = ConvertFrom-Json -InputObject $metadataText
        if ($metadata -isnot [pscustomobject]) { throw $failure }
        foreach ($field in @('id', 'tenantId', 'accountType', 'environmentName', 'state')) {
            if ($metadata.$field -isnot [string] -or [string]::IsNullOrWhiteSpace($metadata.$field)) { throw $failure }
        }
        if ($metadata.id -ine $SubscriptionId -or $metadata.tenantId -ine $TenantId -or
            $metadata.accountType -cne 'user' -or $metadata.environmentName -cne 'AzureCloud' -or
            $metadata.state -cne 'Enabled') { throw $failure }
        $selector = '--subscription {0}' -f $SubscriptionId
    }
    $token = (Invoke-AzureCli ('account get-access-token {0} --resource {1} --query accessToken --output tsv' -f $selector, $Audience)) -creplace '\r?\n\z', ''
    $failure = 'invalid_token_output: Azure CLI did not return one valid raw token.'
    if ($token -ceq 'null' -or -not [regex]::IsMatch($token, '\A[!-~]{1,65536}\z')) { throw $failure }
    $failure = 'internal_error: Unable to acquire access token.'
    [Console]::Out.WriteLine($token)
    exit 0
} catch {
    [Console]::Error.WriteLine($failure)
    exit 1
}
