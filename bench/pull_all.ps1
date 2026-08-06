$ErrorActionPreference = 'Continue'
# ВАЖНО: только ASCII в этом файле. Windows PowerShell 5.1 читает .ps1 как ANSI,
# и любой кириллический литерал ломает парсер (см. историю: два падения подряд).
#
# Robust download queue: several passes with retries, because the link keeps
# breaking (TLS handshake timeout, stalled parts). Model list comes from the
# ollama API, not from log parsing.
$base = Split-Path $PSScriptRoot -Parent
$logDir = Join-Path $base 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$log  = Join-Path $logDir 'pull.log'
$raw  = Join-Path $logDir 'pull_raw.txt'
$flag = Join-Path $logDir 'pulls_complete.flag'

if (Test-Path $flag) { Remove-Item $flag -Force }

# Order = priority: lighter and more promising models first.
$models = @(
  'deepseek-r1:8b',
  'mistral:7b',
  'qwen2.5-coder:14b',
  'gemma3:12b',
  'phi4:14b',
  'deepseek-coder-v2:16b',
  'mistral-nemo:12b',
  'granite3.3:8b',
  'codegemma:7b',
  'gpt-oss:20b'
)

function Write-Log($msg) {
  $line = "[$((Get-Date).ToString('HH:mm:ss'))] $msg"
  Write-Output $line
  try { Add-Content -Path $log -Value $line -Encoding utf8 -ErrorAction Stop } catch {}
}

function Get-Installed {
  try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 30
    return @($r.models | ForEach-Object { $_.name })
  } catch {
    return @()
  }
}

# Wait for a live server (it may still be restarting).
for ($i = 0; $i -lt 60; $i++) {
  try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 10 | Out-Null; break }
  catch { Start-Sleep -Seconds 5 }
}

for ($pass = 1; $pass -le 3; $pass++) {
  $have = Get-Installed
  $todo = @($models | Where-Object { $have -notcontains $_ })
  if ($todo.Count -eq 0) { Write-Log "pass ${pass}: nothing left"; break }
  Write-Log "pass ${pass}: remaining $($todo.Count) - $($todo -join ', ')"
  foreach ($m in $todo) {
    $t0 = Get-Date
    Write-Log "START $m (pass $pass)"
    & ollama pull $m *>> $raw
    $ok = $LASTEXITCODE
    $sec = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
    Write-Log "DONE  $m exit=$ok in ${sec}s"
  }
}

$have = Get-Installed
$missing = @($models | Where-Object { $have -notcontains $_ })
if ($missing.Count -gt 0) { Write-Log "MISSING: $($missing -join ', ')" }
Write-Log 'ALL PULLS FINISHED'
Set-Content -Path $flag -Value 'done' -Encoding utf8
