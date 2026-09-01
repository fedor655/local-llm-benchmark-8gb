#!/usr/bin/env bash
# Снимает с сервера всё, что поставил setup-server.sh, и возвращает
# исходное состояние. Запускать от root на сервере.
#
#   bash rollback-server.sh            # снять всё, Docker оставить
#   PURGE_DOCKER=1 bash rollback-server.sh   # снести и Docker тоже
#
# Docker по умолчанию не трогаем: на сервере могут крутиться чужие
# контейнеры, и удалять его вслепую опаснее, чем оставить.
set -euo pipefail

log()  { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { echo "Запускать от root." >&2; exit 1; }

log "Open WebUI"
docker rm -f open-webui >/dev/null 2>&1 || true
echo "    Том open-webui с историей чатов оставлен."
echo "    Удалить вручную: docker volume rm open-webui"

log "frps"
systemctl disable --now frps >/dev/null 2>&1 || true
rm -f /etc/systemd/system/frps.service
rm -f /usr/local/bin/frps
rm -rf /etc/frp

log "Публикация статуса"
systemctl disable --now llm-status.timer >/dev/null 2>&1 || true
rm -f /etc/systemd/system/llm-status.service /etc/systemd/system/llm-status.timer
rm -f /usr/local/bin/llm-status /var/www/html/llm-status.json
systemctl daemon-reload

log "nginx"
rm -f /etc/nginx/sites-enabled/llm /etc/nginx/sites-available/llm
if [ -e /etc/nginx/sites-available/default.disabled-by-llm-setup ]; then
  mv -f /etc/nginx/sites-available/default.disabled-by-llm-setup /etc/nginx/sites-enabled/default
  echo "    Прежний сайт по умолчанию восстановлен."
elif [ -e /etc/nginx/sites-available/default ]; then
  ln -sfn /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default
  echo "    Включён стандартный сайт nginx."
fi
if nginx -t 2>/dev/null; then
  systemctl reload nginx
else
  warn "nginx -t не проходит - проверьте конфиг вручную."
fi

log "Правила firewall"
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
  ufw delete allow 7000/tcp >/dev/null 2>&1 || true
  echo "    Правило на 7000 снято. Порт 80 оставлен - его обычно нужно держать открытым."
fi

# Главное при откате: вернуть транзитный трафик. Если сервер что-то
# маршрутизирует (VPN-шлюз и подобное), политика FORWARD в DROP от Docker
# рвёт его наглухо, и симптом - "интернет почти не работает".
log "Политика FORWARD"
CUR="$(iptables -S FORWARD 2>/dev/null | head -1 || true)"
echo "    Сейчас: ${CUR:-неизвестно}"
if [ "$CUR" = "-P FORWARD DROP" ]; then
  warn "FORWARD стоит в DROP - маршрутизация через сервер не работает."
  if [ "${PURGE_DOCKER:-0}" = "1" ] || [ "${FIX_FORWARD:-1}" = "1" ]; then
    iptables -P FORWARD ACCEPT
    echo "    Вернул ACCEPT."
    echo "    Чтобы пережило перезагрузку: apt-get install -y iptables-persistent && netfilter-persistent save"
  fi
fi

if [ "${PURGE_DOCKER:-0}" = "1" ]; then
  log "Удаляю Docker"
  systemctl disable --now docker >/dev/null 2>&1 || true
  apt-get purge -y -qq docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin >/dev/null 2>&1 || true
  apt-get autoremove -y -qq >/dev/null 2>&1 || true
  rm -f /etc/apt/sources.list.d/docker.list
  echo "    /var/lib/docker оставлен. Удалить вручную: rm -rf /var/lib/docker"
fi

log "Готово"
echo "  Проверьте: curl -sI http://127.0.0.1/ | head -1"
echo "  Если сервер маршрутизирует трафик: iptables -S FORWARD | head -1"
