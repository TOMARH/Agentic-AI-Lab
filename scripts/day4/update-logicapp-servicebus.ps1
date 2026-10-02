param(
    [string] $NamespaceName,
    [string] $QueueName = 'integration-events',
    [string] $SubscriptionId = 'e5939949-6509-48de-964b-5f1b65c34714',
    [string] $ResourceGroup = 'rg-ai-azure-integration-lab',
    [string] $WorkflowName = 'la-day3-orchestration',
    [string] $IdentityName = 'uami-agentic-ai-lab-logicapp',
    [switch] $RemoveSenderAction
)

$ErrorActionPreference = 'Stop'
if (-not $RemoveSenderAction -and [string]::IsNullOrWhiteSpace($NamespaceName)) {
    throw 'NamespaceName is required unless RemoveSenderAction is set.'
}
$identityPath = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/$IdentityName"
$workflowPath = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Logic/workflows/$WorkflowName"
$uri = 'https://management.azure.com' + $workflowPath + '?api-version=2019-05-01'

$accountId = az account show --query id --output tsv
if ($LASTEXITCODE -ne 0 -or $accountId -ne $SubscriptionId) {
    throw 'Azure CLI is not authenticated to the expected sprint subscription.'
}

$workflowJson = az rest --method get --url $uri --output json
if ($LASTEXITCODE -ne 0) { throw 'Could not read the existing Logic App workflow.' }
$workflow = $workflowJson | ConvertFrom-Json -AsHashtable
$definition = $workflow.properties.definition
$actions = $definition.actions
if (-not $actions.Contains('HTTP')) {
    throw 'Expected existing Function HTTP action was not found; no update was made.'
}

if ($RemoveSenderAction) {
    if ($actions.Contains('Send_ServiceBus_Message')) {
        $actions.Remove('Send_ServiceBus_Message') | Out-Null
    }
} else {
    $actions['Send_ServiceBus_Message'] = @{
        type = 'Http'
        inputs = @{
            method = 'POST'
            uri = "https://$NamespaceName.servicebus.windows.net/$QueueName/messages?timeout=60"
            headers = @{ 'Content-Type' = 'application/json' }
            body = @{ eventId = '@workflow().run.name'; eventType = 'day4-integration-event' }
            authentication = @{
                type = 'ManagedServiceIdentity'
                audience = 'https://servicebus.azure.net/'
                identity = $identityPath
            }
        }
        runAfter = @{ HTTP = @('Succeeded') }
    }
}

$body = @{
    location = $workflow.location
    identity = $workflow.identity
    tags = $workflow.tags
    properties = @{
        definition = $definition
        parameters = $workflow.properties.parameters
        state = 'Enabled'
    }
} | ConvertTo-Json -Depth 100 -Compress

$bodyFile = Join-Path $env:TEMP 'day4-logic-workflow-update.json'
$body | Set-Content -LiteralPath $bodyFile -Encoding utf8
$updatedJson = az rest --method put --url $uri --body "@$bodyFile" --headers Content-Type=application/json --output json
$restExitCode = $LASTEXITCODE
Remove-Item -LiteralPath $bodyFile -Force -ErrorAction SilentlyContinue
if ($restExitCode -ne 0) { throw 'Logic App update failed.' }
$updated = $updatedJson | ConvertFrom-Json

[pscustomobject]@{
    workflow = $WorkflowName
    state = $updated.properties.state
    action = if ($RemoveSenderAction) { 'Send_ServiceBus_Message removed' } else { 'Send_ServiceBus_Message configured' }
    queue = if ($RemoveSenderAction) { $null } else { $QueueName }
}
