param(
    [string] $SubscriptionId = 'e5939949-6509-48de-964b-5f1b65c34714',
    [string] $ResourceGroup = 'rg-ai-azure-integration-lab',
    [string] $WorkflowName = 'la-day3-orchestration',
    [string] $TriggerName = 'When_an_HTTP_request_is_received',
    [int] $TimeoutSeconds = 120
)

$ErrorActionPreference = 'Stop'
$base = "https://management.azure.com/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Logic/workflows/$WorkflowName"
$accountId = az account show --query id --output tsv
if ($LASTEXITCODE -ne 0 -or $accountId -ne $SubscriptionId) {
    throw 'Azure CLI is not authenticated to the expected sprint subscription.'
}

$callbackEndpoint = $base + "/triggers/$TriggerName/listCallbackUrl?api-version=2016-06-01"
$requestFile = Join-Path $env:TEMP 'day4-list-callback.json'
'{"keyType":"Primary"}' | Set-Content -LiteralPath $requestFile -Encoding utf8
$callbackJson = az rest --method post --url $callbackEndpoint --body "@$requestFile" --headers Content-Type=application/json --output json
$callbackExitCode = $LASTEXITCODE
Remove-Item -LiteralPath $requestFile -Force -ErrorAction SilentlyContinue
if ($callbackExitCode -ne 0) { throw 'Trigger callback lookup failed.' }
$callbackUrl = ($callbackJson | ConvertFrom-Json).value
if (-not $callbackUrl) { throw 'Trigger callback lookup returned no URL.' }

$startedAt = [DateTimeOffset]::UtcNow
$client = [System.Net.Http.HttpClient]::new()
$response = $client.GetAsync($callbackUrl).GetAwaiter().GetResult()
$triggerStatus = [int]$response.StatusCode
$response.Dispose()
$client.Dispose()
if ($triggerStatus -ne 202) {
    throw "Logic App trigger returned HTTP $triggerStatus; expected 202."
}

$runsUrl = $base + '/runs?api-version=2016-06-01'
$deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
$run = $null
while ([DateTimeOffset]::UtcNow -lt $deadline) {
    $runsJson = az rest --method get --url $runsUrl --output json
    if ($LASTEXITCODE -ne 0) { throw 'Run-history lookup failed.' }
    $runs = ($runsJson | ConvertFrom-Json).value
    $run = $runs |
        Where-Object { [DateTimeOffset]$_.properties.startTime -ge $startedAt } |
        Sort-Object { [DateTimeOffset]$_.properties.startTime } -Descending |
        Select-Object -First 1
    if ($run -and $run.properties.status -in @('Succeeded', 'Failed', 'Cancelled', 'TimedOut')) {
        break
    }
    Start-Sleep -Seconds 5
}
if (-not $run) { throw 'No workflow run appeared before the timeout.' }

$actionsUrl = $base + "/runs/$($run.name)/actions?api-version=2016-06-01"
$actionsJson = az rest --method get --url $actionsUrl --output json
if ($LASTEXITCODE -ne 0) { throw 'Run action status lookup failed.' }
$actions = ($actionsJson | ConvertFrom-Json).value

[pscustomobject]@{
    triggerHttpStatus = $triggerStatus
    workflowRun = $run.properties.status
    functionHttpAction = ($actions | Where-Object name -eq 'HTTP').properties.status
    serviceBusSendAction = ($actions | Where-Object name -eq 'Send_ServiceBus_Message').properties.status
    failureScope = ($actions | Where-Object name -eq 'Handle_Function_Failure').properties.status
    startedAt = $run.properties.startTime
}
