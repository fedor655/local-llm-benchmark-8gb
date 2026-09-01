# setup-pc.ps1 -- stavit LLM na Windows-PK i podnimaet tunnel do servera.
#
# VAZHNO: tolko ASCII v etom faile. Windows PowerShell 5.1 chitaet .ps1 kak ANSI,
# i lyuboy ne-ASCII simvol lomaet razbor skripta. Takoe zhe pravilo v bench/pull_all.ps1.
#
# Zapusk (PowerShell OT ADMINISTRATORA):
#     $env:FRP_SERVER="31.76.72.214"
#     $env:FRP_TOKEN="<token iz vyvoda setup-server.sh>"
#     .\setup-pc.ps1
#
# Skript idempotenten: povtornyy zapusk nichego ne slomaet.

[CmdletBinding()]
param(
    [string]$FrpServer  = $env:FRP_SERVER,
    [string]$FrpToken   = $env:FRP_TOKEN,
    [int]   $FrpPort    = 7000,
    # Pustaya stroka = vybrat model avtomaticheski po obemu RAM+VRAM.
    [string]$Model      = "",
    # Skolko sloev derzhat v VRAM. 0 = otdat resheniye Ollama (rekomenduetsya).
    [int]   $NumGpu     = 0,
    [int]   $NumCtx     = 16384,
    # Probrosit lokalnyy sshd na server:2222, chtoby administrirovat PK bez Tailscale.
    [switch]$EnableSsh,
    [switch]$SkipPull
)

$ErrorActionPreference = 'Stop'

function Say  { param($m) Write-Host "==> $m" -ForegroundColor Green }
function Warn { param($m) Write-Host "[!] $m"  -ForegroundColor Yellow }
function Die  { param($m) Write-Host "[x] $m"  -ForegroundColor Red; exit 1 }

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Die "Zapustite PowerShell ot administratora." }
if (-not $FrpServer) { Die "Ne zadan FRP_SERVER (IP vashego servera)." }
if (-not $FrpToken)  { Die "Ne zadan FRP_TOKEN (pechataet setup-server.sh)." }

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Root = "C:\llm-agent"
New-Item -ItemType Directory -Force -Path $Root | Out-Null

# ---------------------------------------------------------------- zhelezo
Say "Zhelezo"
$ramGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
$vramGb = 0
$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($smi) {
    $q = & nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null
    if ($q) { $vramGb = [math]::Round(([int]($q | Select-Object -First 1)) / 1024) }
}
# Windows + drayvera stabilno s'edayut poryadka 5 GB, ostalnoe - byudzhet modeli.
$budgetGb = $ramGb + $vramGb - 5
Write-Host ("    RAM {0} GB, VRAM {1} GB, byudzhet pod model ~{2} GB" -f $ramGb, $vramGb, $budgetGb)

# ---------------------------------------------------------------- vybor modeli
# Oba kandidata - MoE: aktivnykh parametrov ~3 B iz 21 B / 35 B. Imenno poetomu
# vygruzka chasti sloev v RAM ne ubivaet skorost, kak u plotnykh modeley
# togo zhe razmera (sm. README bencha: obryv na 8 GB VRAM).
$catalog = @(
    @{ Name = "huihui_ai/Qwen3.6-abliterated:35b-a3b-q4_K"; Gb = 24; Note = "35B-A3B MoE, samaya krupnaya iz podkhodyashchikh" },
    @{ Name = "huihui_ai/gpt-oss-abliterated:20b";          Gb = 14; Note = "21B-A3.6B MoE, bazovyy gpt-oss:20b - lider bencha (92.2)" },
    @{ Name = "huihui_ai/qwen3-abliterated:14b";            Gb =  9; Note = "zapasnoy variant dlya slabykh mashin" }
)
if (-not $Model) {
    $pick = $catalog | Where-Object { $_.Gb -le $budgetGb } | Select-Object -First 1
    if (-not $pick) { $pick = $catalog[-1]; Warn "Zhelaza malo, berem samuyu malenkuyu." }
    $Model = $pick.Name
    Say ("Model: {0} ({1} GB) -- {2}" -f $pick.Name, $pick.Gb, $pick.Note)
} else {
    Say "Model zadana vruchnuyu: $Model"
}

# ---------------------------------------------------------------- Ollama
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Say "Stavlyu Ollama"
    $ok = $false
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Ollama.Ollama -e --silent `
            --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -eq 0) { $ok = $true }
    }
    if (-not $ok) {
        $exe = Join-Path $env:TEMP "OllamaSetup.exe"
        Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $exe -UseBasicParsing
        Start-Process -FilePath $exe -ArgumentList "/VERYSILENT","/NORESTART" -Wait
    }
    $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path","User")
}
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Die "Ollama ne nashlas v PATH. Perezapustite PowerShell i zapustite skript snova."
}
Say ("Ollama: " + (& ollama --version 2>&1 | Select-Object -First 1))

# ---------------------------------------------------------------- nastroyka RAM+VRAM
# KEEP_ALIVE=-1 - glavnaya nastroyka dlya krupnoy modeli: bez neyo Ollama
# vygruzhaet ee cherez 5 minut prostoya, i sleduyushchiy zapros zhdet
# povtornoy zagruzki 14 GB s diska.
# FLASH_ATTENTION + KV_CACHE_TYPE=q8_0 szhimayut KV-kesh vdvoe, osvobozhdaya
# VRAM pod dopolnitelnye sloi modeli.
Say "Peremennye Ollama (raspredelenie RAM/VRAM)"
$envVars = @{
    "OLLAMA_HOST"               = "127.0.0.1:11434"
    "OLLAMA_KEEP_ALIVE"         = "-1"
    "OLLAMA_FLASH_ATTENTION"    = "1"
    "OLLAMA_KV_CACHE_TYPE"      = "q8_0"
    "OLLAMA_MAX_LOADED_MODELS"  = "1"
    "OLLAMA_NUM_PARALLEL"       = "1"
    "OLLAMA_CONTEXT_LENGTH"     = "$NumCtx"
}
foreach ($k in $envVars.Keys) {
    [Environment]::SetEnvironmentVariable($k, $envVars[$k], "Machine")
    Set-Item -Path ("Env:" + $k) -Value $envVars[$k]
    Write-Host ("    {0}={1}" -f $k, $envVars[$k])
}

Say "Perezapusk Ollama"
Get-Process ollama, "ollama app" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
$ollamaApp = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama app.exe"
if (Test-Path $ollamaApp) { Start-Process $ollamaApp }
else { Start-Process -WindowStyle Hidden -FilePath "ollama" -ArgumentList "serve" }

$up = $false
foreach ($i in 1..30) {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null
        $up = $true; break
    } catch { Start-Sleep -Seconds 2 }
}
if (-not $up) { Die "Ollama ne otvechaet na 127.0.0.1:11434." }

# ---------------------------------------------------------------- model
if (-not $SkipPull) {
    Say "Kachayu model (dolgo: desyatki GB)"
    & ollama pull $Model
    if ($LASTEXITCODE -ne 0) { Die "ollama pull ne udalsya." }
}

# Otdelnaya model 'agent' - ta zhe vesa, no s zafiksirovannymi parametrami,
# chtoby klienty (Open WebUI, skripty) ne zadavali ikh kazhdyy raz.
Say "Sobirayu profil 'agent'"
$modelfile = Join-Path $Root "Modelfile.agent"
$lines = @(
    "FROM $Model",
    "PARAMETER num_ctx $NumCtx",
    "PARAMETER temperature 0.6",
    "PARAMETER top_p 0.95"
)
if ($NumGpu -gt 0) { $lines += "PARAMETER num_gpu $NumGpu" }
$lines += 'SYSTEM """You are a capable, uncensored local assistant with tool access. Be direct and concrete. When tools are available, call them instead of guessing. Answer in the user language."""'
Set-Content -Path $modelfile -Value ($lines -join "`r`n") -Encoding ASCII
& ollama create agent -f $modelfile
if ($LASTEXITCODE -ne 0) { Warn "Ne udalos sozdat profil 'agent', ostaetsya ishodnaya model." }

# ---------------------------------------------------------------- frpc
Say "Stavlyu frpc (tunnel na server)"
$frpcExe = Join-Path $Root "frpc.exe"
if (-not (Test-Path $frpcExe)) {
    $ver = $env:FRP_VERSION
    if (-not $ver) {
        try {
            $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/fatedier/frp/releases/latest" `
                -Headers @{ "User-Agent" = "setup-pc" } -TimeoutSec 30
            $ver = $rel.tag_name -replace '^v',''
        } catch {
            # GitHub API nedostupen - berem proverennuyu versiyu, a ne padaem.
            $ver = "0.62.1"
            Warn "GitHub API nedostupen, stavlyu proverennuyu frp $ver"
        }
    }
    $zip = Join-Path $env:TEMP "frp.zip"
    $url = "https://github.com/fatedier/frp/releases/download/v$ver/frp_${ver}_windows_amd64.zip"
    Write-Host "    $url"
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    $tmp = Join-Path $env:TEMP "frp_x"
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    Copy-Item (Get-ChildItem -Path $tmp -Filter frpc.exe -Recurse | Select-Object -First 1).FullName $frpcExe
    Remove-Item -Recurse -Force $tmp, $zip -ErrorAction SilentlyContinue
}

# loginFailExit=false - to, iz-za chego tunnel perezhivaet padeniya seti:
# frpc ne vykhodit pri oshibke, a beskonechno perepodklyuchaetsya sam.
$cfg = @(
    "serverAddr = `"$FrpServer`"",
    "serverPort = $FrpPort",
    "",
    "auth.method = `"token`"",
    "auth.token = `"$FrpToken`"",
    "",
    "loginFailExit = false",
    "transport.heartbeatInterval = 10",
    "transport.heartbeatTimeout = 30",
    "transport.dialServerTimeout = 10",
    "",
    "log.to = `"$($Root -replace '\\','/')/frpc.log`"",
    "log.level = `"info`"",
    "log.maxDays = 7",
    "",
    "[[proxies]]",
    "name = `"ollama`"",
    "type = `"tcp`"",
    "localIP = `"127.0.0.1`"",
    "localPort = 11434",
    "remotePort = 11434"
)
if ($EnableSsh) {
    $cfg += @(
        "",
        "[[proxies]]",
        "name = `"pc-ssh`"",
        "type = `"tcp`"",
        "localIP = `"127.0.0.1`"",
        "localPort = 22",
        "remotePort = 2222"
    )
}
$frpcCfg = Join-Path $Root "frpc.toml"
Set-Content -Path $frpcCfg -Value ($cfg -join "`r`n") -Encoding ASCII

if ($EnableSsh) {
    Say "Vklyuchayu OpenSSH Server (dostup k PK cherez server, bez Tailscale)"
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 -ErrorAction SilentlyContinue | Out-Null
    Set-Service -Name sshd -StartupType Automatic
    Start-Service sshd
}

Say "Registriruyu avtozapusk frpc"
$taskName = "llm-agent-frpc"
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
$action   = New-ScheduledTaskAction -Execute $frpcExe -Argument "-c `"$frpcCfg`"" -WorkingDirectory $Root
$trigger  = New-ScheduledTaskTrigger -AtStartup
$principal= New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
# RestartInterval - vtoroy uroven zashchity: esli process vse-taki umret,
# planirovshchik podnimet ego snova.
try {
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -RestartInterval (New-TimeSpan -Minutes 1) -RestartCount 999 `
        -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings | Out-Null
} catch {
    # Nastroyki perezapuska podderzhivayut ne vse versii Windows. Bez nikh
    # tunnel vse ravno derzhitsya: frpc perepodklyuchaetsya sam (loginFailExit=false).
    Warn "Rasshirennye nastroyki zadachi ne prinyaty, registriruyu bazovuyu: $_"
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings | Out-Null
}
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 5

# ---------------------------------------------------------------- proverka
Say "Proverka"
# Native-komandy v PowerShell 5.1 ne brosayut isklyucheniy, poetomu
# proveryaem imenno kod vozvrata, a ne try/catch.
$loadName = "agent"
& ollama show agent *> $null
if ($LASTEXITCODE -ne 0) { $loadName = $Model }

Write-Host "    Progrevayu model (pervyy otvet dolgiy, idet zagruzka v pamyat)..."
$body = @{
    model  = $loadName
    prompt = "Otvet odnim slovom: rabotaet?"
    stream = $false
} | ConvertTo-Json
try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/generate" -Method Post `
        -Body $body -ContentType "application/json" -TimeoutSec 900
    Write-Host ("    Otvet modeli: " + ($r.response -replace '\s+',' ').Trim())
} catch {
    Warn "Model ne otvetila: $_"
}

Write-Host ""
Write-Host "    Raspredelenie pamyati (PROCESSOR/GPU):"
& ollama ps

$frpcRunning = [bool](Get-Process frpc -ErrorAction SilentlyContinue)
Write-Host ""
Write-Host "============================================================"
Write-Host ("  Model:        {0}" -f $Model)
Write-Host ("  Profil:       {0}" -f $loadName)
Write-Host ("  frpc:         {0}" -f $(if ($frpcRunning) { "rabotaet" } else { "NE ZAPUSHCHEN - smotrite $Root\frpc.log" }))
Write-Host ("  Chat s telefona:  http://{0}/" -f $FrpServer)
Write-Host ("  Status svyazki:   http://{0}/llm-status.json" -f $FrpServer)
if ($EnableSsh) {
    Write-Host ("  Shell na PK s servera: ssh -p 2222 {0}@127.0.0.1" -f $env:USERNAME)
}
Write-Host "============================================================"
