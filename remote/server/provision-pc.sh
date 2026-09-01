#!/usr/bin/env bash
# Ставит LLM на удалённый ПК, к которому нет физического доступа.
# Запускается НА СЕРВЕРЕ, ходит на ПК через Tailscale.
#
# Работает строго заходами: на каждую команду - новый коннект и выход.
# Никаких длинных сессий, поэтому обрыв Tailscale роняет одну команду,
# а не всю установку; повторный запуск продолжает с того же места.
#
#   ./provision-pc.sh recon      # только посмотреть ОС и железо, ничего не менять
#   ./provision-pc.sh install    # поставить модель и туннель
#
# Обязательные переменные:
#   PC_HOST      имя или IP ПК в тайлнете (например pc-home или 100.x.y.z)
#   PC_USER      пользователь на ПК
#
# Необязательные:
#   TS_AUTHKEY   ключ Tailscale - если сервер ещё не в тайлнете
#   PC_PASS      пароль ПК (тогда нужен sshpass; лучше ключ или Tailscale SSH)
#   FRP_TOKEN    по умолчанию читается из /etc/frp/token
#   MODEL        перебить автовыбор модели
set -euo pipefail

MODE="${1:-}"
case "$MODE" in
  recon|install) ;;
  *) echo "Использование: $0 recon|install"; exit 2 ;;
esac

: "${PC_HOST:?Задайте PC_HOST - имя ПК в тайлнете}"
: "${PC_USER:?Задайте PC_USER - пользователь на ПК}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRP_TOKEN="${FRP_TOKEN:-$(cat /etc/frp/token 2>/dev/null || true)}"

log()  { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[x] %s\033[0m\n' "$*" >&2; exit 1; }

# Один заход = одна команда. ControlMaster выключен намеренно: залипшее
# соединение к ПК через тайлнет - главный источник зависаний.
SSH_BASE=(
  -o ConnectTimeout=15
  -o ServerAliveInterval=5
  -o ServerAliveCountMax=3
  -o ControlMaster=no
  -o ControlPath=none
  -o StrictHostKeyChecking=accept-new
  -o LogLevel=ERROR
)
SSH_BIN=(ssh)
SCP_BIN=(scp)
if [ -n "${PC_PASS:-}" ]; then
  command -v sshpass >/dev/null 2>&1 || die "PC_PASS задан, но нет sshpass: apt-get install -y sshpass"
  SSH_BIN=(sshpass -p "$PC_PASS" ssh)
  SCP_BIN=(sshpass -p "$PC_PASS" scp)
  # BatchMode здесь ставить нельзя: он запрещает парольный ввод, через
  # который и работает sshpass.
  SSH_BASE+=(-o PreferredAuthentications=password -o PubkeyAuthentication=no)
else
  SSH_BASE+=(-o BatchMode=yes)
fi

# rex <секунды> <команда> - один заход, жёсткий потолок по времени.
rex() {
  local t="$1"; shift
  timeout --signal=INT --kill-after=10 "$t" \
    "${SSH_BIN[@]}" -n "${SSH_BASE[@]}" "${PC_USER}@${PC_HOST}" -- "$@"
}

# ---------------------------------------------------------------- тайлнет
if ! command -v tailscale >/dev/null 2>&1; then
  if [ -n "${TS_AUTHKEY:-}" ]; then
    log "Ставлю Tailscale на сервер"
    curl -fsSL https://tailscale.com/install.sh | sh
  else
    die "На сервере нет Tailscale. Дайте TS_AUTHKEY, либо подключите сервер к тайлнету заранее."
  fi
fi

if ! tailscale status >/dev/null 2>&1; then
  [ -n "${TS_AUTHKEY:-}" ] || die "Сервер не в тайлнете. Нужен TS_AUTHKEY."
  log "Подключаю сервер к тайлнету"
  # --accept-dns=false и --accept-routes=false принципиальны: без них
  # Tailscale перепишет резолвер и маршруты сервера, и сервер потеряет
  # связь ровно так же, как терялась она у вас.
  tailscale up --authkey "$TS_AUTHKEY" \
    --accept-dns=false --accept-routes=false --hostname="llm-relay"
fi
log "Тайлнет: $(tailscale ip -4 2>/dev/null | head -1)"

# ---------------------------------------------------------------- связь с ПК
log "Проверяю связь с ${PC_HOST}"
if ! timeout 20 tailscale ping -c 2 --timeout 5s "$PC_HOST" >/dev/null 2>&1; then
  warn "tailscale ping не прошёл - ПК может спать или быть не в сети"
fi

# ---------------------------------------------------------------- какая ОС
log "Определяю ОС"
PC_OS=""
if UNAME="$(rex 30 'uname -s' 2>/dev/null)"; then
  case "$UNAME" in
    Linux*)  PC_OS=linux ;;
    Darwin*) PC_OS=macos ;;
  esac
fi
if [ -z "$PC_OS" ]; then
  if rex 40 'powershell -NoProfile -Command exit' >/dev/null 2>&1; then
    PC_OS=windows
  fi
fi
[ -n "$PC_OS" ] || die "Не удалось определить ОС ПК. Проверьте, что SSH на ПК работает: ssh ${PC_USER}@${PC_HOST}"
log "ОС: $PC_OS"

# ---------------------------------------------------------------- железо
log "Снимаю характеристики"
case "$PC_OS" in
  linux)
    SPECS="$(rex 60 'echo "--- CPU"; lscpu | grep -E "^Model name|^CPU\(s\):" ; \
      echo "--- RAM"; free -g | awk "/^Mem:/{print \$2\" GB\"}"; \
      echo "--- GPU"; (nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || echo "нет nvidia-smi"); \
      echo "--- DISK"; df -BG --output=avail / | tail -1; \
      echo "--- OLLAMA"; (ollama --version 2>/dev/null || echo "не установлена")' )" || SPECS="(не удалось)"
    ;;
  macos)
    SPECS="$(rex 60 'sysctl -n machdep.cpu.brand_string; echo "RAM: $(( $(sysctl -n hw.memsize) / 1073741824 )) GB"; \
      system_profiler SPDisplaysDataType | grep -E "Chipset|VRAM" ; \
      (ollama --version 2>/dev/null || echo "ollama не установлена")' )" || SPECS="(не удалось)"
    ;;
  windows)
    # Только ASCII и -EncodedCommand: команда едет через cmd.exe на Windows,
    # где и вложенные кавычки, и кириллица в кодовой странице консоли
    # превращаются в кашу. base64 от UTF-16LE снимает оба вопроса разом.
    PS_SPECS='$ErrorActionPreference="SilentlyContinue";
      $cs=Get-CimInstance Win32_ComputerSystem;
      $cpu=Get-CimInstance Win32_Processor | Select-Object -First 1;
      Write-Output ("CPU:  " + $cpu.Name);
      Write-Output ("RAM:  " + [math]::Round($cs.TotalPhysicalMemory/1GB) + " GB");
      $smi=Get-Command nvidia-smi -ErrorAction SilentlyContinue;
      if ($smi) { Write-Output ("GPU:  " + (nvidia-smi --query-gpu=name,memory.total --format=csv,noheader)) }
      else { Get-CimInstance Win32_VideoController | ForEach-Object { Write-Output ("GPU:  " + $_.Name + " (no nvidia-smi)") } }
      Write-Output ("DISK: " + [math]::Round((Get-PSDrive C).Free/1GB) + " GB free on C:");
      Write-Output ("OS:   " + (Get-CimInstance Win32_OperatingSystem).Caption);
      Write-Output ("ADMIN: " + ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator));
      $o=Get-Command ollama -ErrorAction SilentlyContinue;
      if ($o) { Write-Output ("OLLAMA: " + (ollama --version)) } else { Write-Output "OLLAMA: not installed" }'
    ENC="$(printf '%s' "$PS_SPECS" | iconv -f UTF-8 -t UTF-16LE | base64 -w0)"
    SPECS="$(rex 90 "powershell -NoProfile -EncodedCommand ${ENC}")" || SPECS="(не удалось)"
    ;;
esac

echo
echo "============================================================"
echo "  ПК: ${PC_HOST}   ОС: ${PC_OS}"
echo "------------------------------------------------------------"
echo "$SPECS"
echo "============================================================"

if [ "$MODE" = "recon" ]; then
  echo
  echo "Это была только разведка, на ПК ничего не менялось."
  echo "Установка:  PC_HOST=$PC_HOST PC_USER=$PC_USER $0 install"
  exit 0
fi

# ---------------------------------------------------------------- установка
[ -n "$FRP_TOKEN" ] || die "Нет FRP_TOKEN и пустой /etc/frp/token. Сначала запустите setup-server.sh."
SERVER_TS_IP="$(tailscale ip -4 2>/dev/null | head -1)"
SERVER_ADDR="${FRP_SERVER:-$SERVER_TS_IP}"
[ -n "$SERVER_ADDR" ] || die "Не определил адрес сервера для frpc. Задайте FRP_SERVER."

case "$PC_OS" in
  windows)
    log "Заливаю setup-pc.ps1 на ПК"
    [ -f "$HERE/../pc/setup-pc.ps1" ] || die "Не нашёл ../pc/setup-pc.ps1 рядом со скриптом."
    timeout 120 "${SCP_BIN[@]}" "${SSH_BASE[@]}" \
      "$HERE/../pc/setup-pc.ps1" "${PC_USER}@${PC_HOST}:setup-pc.ps1"

    log "Запускаю установку на ПК (долго: качается модель)"
    warn "Скрипту на ПК нужны права администратора."
    MODEL_ARG=""
    [ -n "${MODEL:-}" ] && MODEL_ARG=" -Model '${MODEL}'"
    # Потолок 4 часа: скачивание 14-24 ГБ по домашнему каналу - это надолго.
    rex 14400 "powershell -NoProfile -ExecutionPolicy Bypass -File setup-pc.ps1 -FrpServer '${SERVER_ADDR}' -FrpToken '${FRP_TOKEN}' -EnableSsh${MODEL_ARG}"
    ;;
  linux|macos)
    die "ПК на ${PC_OS}: bootstrap для этой ОС пока не написан. Скажите - допишу, он короче windows-варианта."
    ;;
esac

log "Готово. Проверка:"
echo "  bash $HERE/../tools/healthcheck.sh"
