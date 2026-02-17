$ErrorActionPreference = 'Stop'
$project = 'D:\work\TG_Parser'
$profilePath = $PROFILE.CurrentUserCurrentHost

if (-not (Test-Path (Split-Path -Parent $profilePath))) {
  New-Item -ItemType Directory -Path (Split-Path -Parent $profilePath) -Force | Out-Null
}
if (-not (Test-Path $profilePath)) {
  New-Item -ItemType File -Path $profilePath -Force | Out-Null
}

$block = @"
# TG_Parser aliases
function telegram_parse { & '$project\telegram_parse.ps1' @args }
function telegram_channels { & '$project\telegram_channels.ps1' @args }
Set-Alias tgparse telegram_parse
Set-Alias tgch telegram_channels
"@

$content = Get-Content $profilePath -Raw
if ($content -notmatch 'TG_Parser aliases') {
  Add-Content -Path $profilePath -Value "`n$block`n"
  Write-Host "Aliases added to $profilePath"
} else {
  Write-Host "Aliases already present in $profilePath"
}

Write-Host 'Run: . $PROFILE to reload aliases in current shell.'
