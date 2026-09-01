#!/usr/bin/env bash
# Одна команда - одно подключение - выход. Ничего не висит между вызовами.
#
# Задача, ради которой это написано: любая долгоживущая сессия к ПК рвётся
# (особенно через Tailscale) и утаскивает за собой того, кто её открыл.
# Поэтому здесь принципиально нет интерактивного режима, нет ControlMaster
# и нет переиспользования соединения: каждый вызов - новый короткий коннект,
# жёсткий потолок по времени и гарантированный выход.
#
#   ./rexec.sh server 'systemctl status frps'
#   ./rexec.sh pc     'ollama ps'
#   ./rexec.sh pc     'nvidia-smi' --timeout 120
#
# Переменные окружения:
#   LLM_SERVER    IP сервера            (по умолчанию 31.76.72.214)
#   LLM_SRV_USER  пользователь сервера  (по умолчанию root)
#   LLM_PC_USER   пользователь на ПК    (по умолчанию совпадает с $USER)
#   LLM_PC_PORT   порт ПК на сервере    (по умолчанию 2222, его открывает frp)
set -euo pipefail

SERVER="${LLM_SERVER:-31.76.72.214}"
SRV_USER="${LLM_SRV_USER:-root}"
PC_USER="${LLM_PC_USER:-$USER}"
PC_PORT="${LLM_PC_PORT:-2222}"
TIMEOUT=60

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
}

TARGET="${1:-}"; shift || usage
[ -n "$TARGET" ] || usage
CMD="${1:-}"; shift || true
[ -n "$CMD" ] || usage

while [ $# -gt 0 ]; do
  case "$1" in
    --timeout) TIMEOUT="$2"; shift 2 ;;
    *) echo "Неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
done

# Общие для всех вызовов опции. ServerAlive* даёт быстрый детект обрыва,
# ControlMaster=no + ControlPath=none запрещают залипание соединения,
# -n отвязывает stdin, чтобы вызов не мог зависнуть в ожидании ввода.
COMMON_OPTS=(
  -o BatchMode=yes
  -o ConnectTimeout=15
  -o ServerAliveInterval=5
  -o ServerAliveCountMax=3
  -o ControlMaster=no
  -o ControlPath=none
  -o StrictHostKeyChecking=accept-new
  -o LogLevel=ERROR
)
# -n только для внешнего вызова: в ProxyCommand он бы задушил канал -W,
# который как раз ходит через stdin/stdout процесса-прыжка.
SSH_OPTS=(-n "${COMMON_OPTS[@]}")

case "$TARGET" in
  server)
    exec timeout --signal=INT --kill-after=10 "$TIMEOUT" \
      ssh "${SSH_OPTS[@]}" "${SRV_USER}@${SERVER}" -- "$CMD"
    ;;
  pc)
    # Через сервер: frp приводит sshd с ПК на 127.0.0.1:2222 сервера.
    # Соединение инициирует ПК, поэтому проброс работает и за NAT, и без
    # Tailscale, и не зависит от белого IP на домашнем роутере.
    exec timeout --signal=INT --kill-after=10 "$TIMEOUT" \
      ssh "${SSH_OPTS[@]}" \
        -o ProxyCommand="ssh ${COMMON_OPTS[*]} -W %h:%p ${SRV_USER}@${SERVER}" \
        -p "$PC_PORT" "${PC_USER}@127.0.0.1" -- "$CMD"
    ;;
  *)
    echo "Первый аргумент: server или pc" >&2
    exit 2
    ;;
esac
