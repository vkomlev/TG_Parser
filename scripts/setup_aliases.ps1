$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path
$profilePath = $PROFILE.CurrentUserCurrentHost

if (-not (Test-Path (Split-Path -Parent $profilePath))) {
  New-Item -ItemType Directory -Path (Split-Path -Parent $profilePath) -Force | Out-Null
}
if (-not (Test-Path $profilePath)) {
  New-Item -ItemType File -Path $profilePath -Force | Out-Null
}

$parseScript = Join-Path $projectRoot 'scripts\telegram_parse.ps1'
$channelsScript = Join-Path $projectRoot 'scripts\telegram_channels.ps1'
$block = @"
# TG_Parser aliases
function telegram_parse { & '$parseScript' @args }
function telegram_channels { & '$channelsScript' @args }
Set-Alias tgparse telegram_parse
Set-Alias tgch telegram_channels
"@

$content = Get-Content $profilePath -Raw
if ($null -eq $content) { $content = '' }

# Обновить существующий блок или добавить новый (для пользователей со старыми путями в профиле)
$pattern = '(?s)# TG_Parser aliases\r?\n.*?Set-Alias tgch telegram_channels\r?\n?'
if ($content -match $pattern) {
  $newContent = $content -replace $pattern, ($block.TrimEnd() + "`n")
  Set-Content -Path $profilePath -Value $newContent -NoNewline -Encoding UTF8
  Write-Host "Aliases updated in $profilePath"
} else {
  Add-Content -Path $profilePath -Value "`n$block`n"
  Write-Host "Aliases added to $profilePath"
}

Write-Host 'Run: . $PROFILE to reload aliases in current shell.'
