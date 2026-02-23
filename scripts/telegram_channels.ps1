param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ArgsList
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }

& $python (Join-Path $projectRoot 'telegram_parser_skill.py') channels @ArgsList
exit $LASTEXITCODE
