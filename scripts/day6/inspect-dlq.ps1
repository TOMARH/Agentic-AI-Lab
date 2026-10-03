param(
    [string]$ResourceGroupName = "rg-ai-azure-integration-lab",
    [string]$NamespaceName = "sb-ai-int-likwmn7js4ffw",
    [string]$QueueName = "integration-events"
)

$ErrorActionPreference = "Stop"

Write-Host "=== Inspecting Service Bus Queue & DLQ Metrics ===" -ForegroundColor Cyan
Write-Host "Resource Group: $ResourceGroupName"
Write-Host "Namespace:      $NamespaceName"
Write-Host "Queue:          $QueueName"
Write-Host ""

# Fetch queue runtime metrics
$queue = az servicebus queue show `
    --resource-group $ResourceGroupName `
    --namespace-name $NamespaceName `
    --name $QueueName `
    --output json | ConvertFrom-Json

$activeCount =$queue.countDetails.activeMessageCount
$deadLetterCount =$queue.countDetails.deadLetterMessageCount
$totalCount =$queue.messageCount

Write-Host "Active Messages:      $activeCount" -ForegroundColor Green
Write-Host "Dead-Letter Messages: $deadLetterCount" -ForegroundColor $(if ($deadLetterCount -gt 0) { "Red" } else { "Green" })
Write-Host "Total Message Count:  $totalCount"
Write-Host ""

if ($deadLetterCount -gt 0) {
    Write-Host "Dead-lettered messages detected. Checking DLQ subqueue properties..." -ForegroundColor Yellow
} else {
    Write-Host "DLQ is clean (0 dead-lettered messages)." -ForegroundColor Green
}