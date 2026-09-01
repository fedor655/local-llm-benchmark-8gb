#!/usr/bin/env bash
# Ставит на VPS точку входа для телефона: frps (туннель с ПК) + Open WebUI + nginx.
# Идемпотентен: можно запускать повторно, ничего не сломает.
#
#   bash setup-server.sh
#
# Переменные окружения:
#   FRP_VERSION   версия frp (по умолчанию берётся последняя с GitHub)
#   FRP_TOKEN     токен канала frp (по умолчанию генерируется и сохраняется)
#   WEBUI_TAG     тег образа Open WebUI (по умолчанию 0.11)
set -euo pipefail

FRP_BIND_PORT=7000
OLLAMA_TUNNEL_PORT=11434   # сюда frp приведёт Ollama с ПК, слушает только 127.0.0.1
PC_SSH_TUNNEL_PORT=2222    # сюда frp приведёт sshd с ПК, слушает только 127.0.0.1
WEBUI_PORT=3000
WEBUI_TAG="${WEBUI_TAG:-0.11}"

log()  { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[x] %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Запускать от root."

# ---------------------------------------------------------------- пакеты
log "Базовые пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl ca-certificates nginx jq openssl tar >/dev/null

# ---------------------------------------------------------------- docker
if ! command -v docker >/dev/null 2>&1; then
  # Docker при установке выставляет политику цепочки FORWARD в DROP.
  # Если сервер что-то маршрутизирует - VPN-шлюз, WireGuard, OpenVPN,
  # проброс для домашней сети - транзитный трафик после этого умирает,
  # и со стороны это выглядит как "интернет вдруг стал еле работать".
  # Запоминаем политику до установки и возвращаем, если Docker её сменил.
  FWD_BEFORE="$(iptables -S FORWARD 2>/dev/null | head -1 || true)"
  log "Ставлю Docker"
  curl -fsSL https://get.docker.com | sh
  FWD_AFTER="$(iptables -S FORWARD 2>/dev/null | head -1 || true)"
  if [ "$FWD_BEFORE" = "-P FORWARD ACCEPT" ] && [ "$FWD_AFTER" = "-P FORWARD DROP" ]; then
    warn "Docker сменил политику FORWARD на DROP - возвращаю ACCEPT,"
    warn "иначе сломается любая маршрутизация через этот сервер (VPN и прочее)."
    iptables -P FORWARD ACCEPT
  fi
else
  log "Docker уже стоит: $(docker --version)"
fi
systemctl enable --now docker >/dev/null 2>&1 || true

# ---------------------------------------------------------------- токен frp
mkdir -p /etc/frp
if [ -n "${FRP_TOKEN:-}" ]; then
  printf '%s' "$FRP_TOKEN" > /etc/frp/token
elif [ ! -s /etc/frp/token ]; then
  # Токен генерирует скрипт, запоминать его не нужно: он печатается в конце,
  # чтобы вставить в команду на ПК. Без него любой, кто найдёт порт 7000,
  # пробросит через ваш сервер что угодно.
  openssl rand -hex 16 > /etc/frp/token
fi
chmod 600 /etc/frp/token
FRP_TOKEN="$(cat /etc/frp/token)"

# ---------------------------------------------------------------- frps
if [ ! -x /usr/local/bin/frps ]; then
  log "Ставлю frps"
  if [ -z "${FRP_VERSION:-}" ]; then
    FRP_VERSION="$(curl -fsSL https://api.github.com/repos/fatedier/frp/releases/latest \
      | jq -r '.tag_name' | sed 's/^v//')" || true
  fi
  # Если GitHub API недоступен - берём проверенную версию, а не падаем.
  if [ -z "${FRP_VERSION:-}" ] || [ "$FRP_VERSION" = "null" ]; then
    FRP_VERSION=0.62.1
    log "GitHub API недоступен, ставлю проверенную frp ${FRP_VERSION}"
  fi
  tmp="$(mktemp -d)"
  curl -fsSL -o "$tmp/frp.tgz" \
    "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_amd64.tar.gz"
  tar -xzf "$tmp/frp.tgz" -C "$tmp"
  install -m755 "$tmp"/frp_*/frps /usr/local/bin/frps
  rm -rf "$tmp"
fi
log "frps: $(/usr/local/bin/frps --version 2>/dev/null || echo '?')"

cat > /etc/frp/frps.toml <<EOF
bindPort = ${FRP_BIND_PORT}

# Ключевая строка: порты, которые ПК пробрасывает сюда, поднимаются только
# на локальном интерфейсе. Наружу их отдаёт nginx, а не frp.
proxyBindAddr = "127.0.0.1"

auth.method = "token"
auth.token = "${FRP_TOKEN}"

allowPorts = [
  { start = ${OLLAMA_TUNNEL_PORT}, end = ${OLLAMA_TUNNEL_PORT} },
  { start = ${PC_SSH_TUNNEL_PORT}, end = ${PC_SSH_TUNNEL_PORT} },
]

log.to = "/var/log/frps.log"
log.level = "info"
log.maxDays = 7
EOF
chmod 600 /etc/frp/frps.toml

cat > /etc/systemd/system/frps.service <<'EOF'
[Unit]
Description=frp server (tunnel endpoint for the LLM PC)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/frps -c /etc/frp/frps.toml
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable frps >/dev/null 2>&1
systemctl restart frps

# ---------------------------------------------------------------- Open WebUI
log "Open WebUI"
# --network=host здесь не для удобства, а по необходимости: frps поднимает
# туннель к Ollama строго на 127.0.0.1 сервера, и контейнер в bridge-сети
# до него не достучится ни через host-gateway, ни как-либо ещё.
# HOST=127.0.0.1 при этом не даёт Open WebUI вылезти наружу мимо nginx.
docker rm -f open-webui >/dev/null 2>&1 || true
docker run -d \
  --name open-webui \
  --restart unless-stopped \
  --network=host \
  -e HOST=127.0.0.1 \
  -e PORT=${WEBUI_PORT} \
  -e OLLAMA_BASE_URL="http://127.0.0.1:${OLLAMA_TUNNEL_PORT}" \
  -e WEBUI_AUTH=False \
  -e ENABLE_SIGNUP=False \
  -v open-webui:/app/backend/data \
  "openwebui/open-webui:${WEBUI_TAG}" >/dev/null

# ---------------------------------------------------------------- nginx
log "nginx"
cat > /etc/nginx/sites-available/llm <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 100m;

    # Долгий ответ модели с выгрузкой в RAM - это норма. Таймауты щедрые,
    # иначе nginx рвёт стрим на середине генерации.
    proxy_read_timeout    900s;
    proxy_send_timeout    900s;
    proxy_connect_timeout 30s;
    proxy_buffering       off;

    # Чат с телефона
    location / {
        proxy_pass http://127.0.0.1:${WEBUI_PORT};
        proxy_http_version 1.1;
        proxy_set_header Upgrade    \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host       \$host;
        proxy_set_header X-Real-IP  \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Прямой API модели: OpenAI-совместимый /ollama/v1/chat/completions
    # и родной /ollama/api/*. Отсюда её дёргают агенты и скрипты.
    location /ollama/ {
        proxy_pass http://127.0.0.1:${OLLAMA_TUNNEL_PORT}/;
        proxy_http_version 1.1;
        proxy_set_header Host       localhost;
        proxy_set_header Connection "";
    }

    # Состояние связки, чтобы проверять снаружи без захода на сервер
    location = /llm-status.json {
        default_type application/json;
        alias /var/www/html/llm-status.json;
        add_header Cache-Control "no-store";
    }
}
EOF

# Не удаляем, а отодвигаем: если на сервере был свой сайт на 80 порту,
# он должен восстанавливаться одной командой, а не заново писаться.
if [ -e /etc/nginx/sites-enabled/default ]; then
  mv -f /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default.disabled-by-llm-setup
  warn "Прежний сайт по умолчанию отключён, копия: /etc/nginx/sites-available/default.disabled-by-llm-setup"
fi
ln -sfn /etc/nginx/sites-available/llm /etc/nginx/sites-enabled/llm
nginx -t
systemctl reload nginx

# ---------------------------------------------------------------- статус
cat > /usr/local/bin/llm-status <<'EOF'
#!/usr/bin/env bash
# Собирает состояние связки в /var/www/html/llm-status.json
out=/var/www/html/llm-status.json
mkdir -p /var/www/html
tags="$(curl -fsS --max-time 8 http://127.0.0.1:11434/api/tags 2>/dev/null || true)"
ps_json="$(curl -fsS --max-time 8 http://127.0.0.1:11434/api/ps 2>/dev/null || true)"
tunnel_up=false
[ -n "$tags" ] && tunnel_up=true
models='[]'
loaded='[]'
[ -n "$tags" ]    && models="$(printf '%s' "$tags"    | jq -c '[.models[]?.name]' 2>/dev/null || echo '[]')"
[ -n "$ps_json" ] && loaded="$(printf '%s' "$ps_json" | jq -c '[.models[]? | {name, size, size_vram}]' 2>/dev/null || echo '[]')"
jq -n \
  --arg ts "$(date -Is)" \
  --argjson tunnel "$tunnel_up" \
  --arg frps "$(systemctl is-active frps)" \
  --arg webui "$(docker inspect -f '{{.State.Status}}' open-webui 2>/dev/null || echo missing)" \
  --argjson models "$models" \
  --argjson loaded "$loaded" \
  '{checked_at:$ts, pc_tunnel_up:$tunnel, frps:$frps, open_webui:$webui, models:$models, loaded:$loaded}' \
  > "$out"
EOF
chmod 755 /usr/local/bin/llm-status

cat > /etc/systemd/system/llm-status.service <<'EOF'
[Unit]
Description=Publish LLM link status as JSON
[Service]
Type=oneshot
ExecStart=/usr/local/bin/llm-status
EOF
cat > /etc/systemd/system/llm-status.timer <<'EOF'
[Unit]
Description=Refresh LLM link status every minute
[Timer]
OnBootSec=30s
OnUnitActiveSec=60s
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now llm-status.timer >/dev/null 2>&1
/usr/local/bin/llm-status || true

# ---------------------------------------------------------------- firewall
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
  log "Открываю порты в ufw"
  ufw allow 80/tcp                >/dev/null
  ufw allow ${FRP_BIND_PORT}/tcp  >/dev/null
fi

# -------------------------------------------------- контроль: что торчит наружу
log "Проверяю, что наружу открыто только то, что задумано"
sleep 5
if command -v ss >/dev/null 2>&1; then
  for port in "${WEBUI_PORT}" "${OLLAMA_TUNNEL_PORT}" "${PC_SSH_TUNNEL_PORT}"; do
    if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "^(0\.0\.0\.0|\*|\[::\]):${port}$"; then
      printf '\033[1;33m[!] порт %s слушает на всех интерфейсах, а должен только на 127.0.0.1\033[0m\n' "$port"
    fi
  done
fi

# ---------------------------------------------------------------- итог
IP="$(curl -fsS --max-time 8 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')"
cat <<EOF

============================================================
  Сервер готов.

  Чат с телефона:   http://${IP}/
  API для агентов:  http://${IP}/ollama/v1/chat/completions
  Статус связки:    http://${IP}/llm-status.json

  Дальше на ПК, в PowerShell от администратора:

      \$env:FRP_SERVER="${IP}"
      \$env:FRP_TOKEN="${FRP_TOKEN}"
      .\setup-pc.ps1

  pc_tunnel_up в статусе станет true, как только ПК подключится.
============================================================
EOF
