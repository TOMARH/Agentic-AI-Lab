param(
    [string]$TraceId = "",
    [string]$SpanId = ""
)

$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "send_traced_message.py"
python $scriptPath $TraceId $SpanId
