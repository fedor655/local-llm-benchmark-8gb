$ErrorActionPreference = 'Continue'
# ASCII ONLY in this file. Windows PowerShell 5.1 reads .ps1 as ANSI,
# and any Cyrillic literal breaks the parser (same lesson as pull_all.ps1).
#
# Uncensored / abliterated model set for the benchmark.
# Pulled straight from Hugging Face GGUF repos via Ollama's hf.co/ shortcut.
#
# Purpose: run the SAME 32 tasks as the base models to measure the QUALITY
# COST of abliteration -- does surgically removing the refusal direction make
# the model dumber (worse code, more hallucinations, weaker instructions)?
#
# Pairing (base already in the main benchmark  ->  abliterated twin here):
#   llama3.1:8b        ->  llama31-abliterated       (already registered locally)
#   qwen2.5-coder:7b   ->  qwen2.5-coder-7b-ablit
#   qwen2.5-coder:14b  ->  qwen2.5-coder-14b-ablit
#   (heavy, optional)  ->  qwen3-coder-30b-a3b-ablit (MoE, 3B active, CPU offload)

$base = Split-Path $PSScriptRoot -Parent
$logDir = Join-Path $base 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$log = Join-Path $logDir 'pull_uncensored.log'

function Write-Log($msg) {
  $line = "[$((Get-Date).ToString('HH:mm:ss'))] $msg"
  Write-Output $line
  try { Add-Content -Path $log -Value $line -Encoding utf8 -ErrorAction Stop } catch {}
}

# name = short ollama tag the driver will enumerate; src = hf.co GGUF ref (Q4_K_M).
$models = @(
  @{ name = 'qwen2.5-coder-7b-ablit';  src = 'hf.co/bartowski/Qwen2.5-Coder-7B-Instruct-abliterated-GGUF:Q4_K_M' },
  @{ name = 'qwen2.5-coder-14b-ablit'; src = 'hf.co/bartowski/Qwen2.5-Coder-14B-Instruct-abliterated-GGUF:Q4_K_M' }
  # Heavy (MoE ~18 GB Q4, only 3B active -> runs with CPU offload like gpt-oss:20b):
  # @{ name = 'qwen3-coder-30b-a3b-ablit'; src = 'hf.co/mradermacher/Huihui-Qwen3-Coder-30B-A3B-Instruct-abliterated-i1-GGUF:Q4_K_M' }
)

# NOTE: llama31-abliterated is already registered in Ollama on this machine
# (Meta-Llama-3.1-8B-Instruct abliterated, Q4). Its base twin llama3.1:8b is
# already benchmarked on main, so that pair needs no pull.

foreach ($m in $models) {
  Write-Log ("pull " + $m.name + "  <-  " + $m.src)
  ollama pull $m.src 2>&1 | ForEach-Object { Write-Log $_ }
  # Re-tag under the short name so results files are clean (driver reads ollama list):
  ollama cp $m.src $m.name 2>&1 | ForEach-Object { Write-Log $_ }
}
Write-Log 'done'
