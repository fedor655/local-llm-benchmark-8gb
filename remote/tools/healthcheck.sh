#!/usr/bin/env bash
# Сквозная проверка связки телефон -> сервер -> ПК -> модель.
# Нужен только curl: запускается с ноутбука, с сервера, из CI - откуда угодно.
#
#   ./healthcheck.sh                 # проверить всё
#   LLM_SERVER=1.2.3.4 ./healthcheck.sh
#
# Код возврата: 0 - связка живая, 1 - что-то отвалилось.

SERVER="${LLM_SERVER:-31.76.72.214}"
BASE="http://${SERVER}"
FAIL=0

ok()   { printf '  \033[1;32m[ok]\033[0m   %s\n' "$*"; }
bad()  { printf '  \033[1;31m[FAIL]\033[0m %s\n' "$*"; FAIL=1; }
info() { printf '  \033[2m       %s\033[0m\n' "$*"; }
head_() { printf '\n\033[1m%s\033[0m\n' "$*"; }

head_ "1. Сервер отвечает"
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$BASE/" || echo 000)"
case "$code" in
  200|302|401) ok "nginx на $SERVER отдаёт $code" ;;
  000)         bad "нет ответа от $SERVER:80 (сервер лежит или порт закрыт)" ;;
  *)           bad "nginx вернул $code" ;;
esac

head_ "2. Состояние по данным сервера"
status="$(curl -fsS --max-time 15 "$BASE/llm-status.json" 2>/dev/null || true)"
if [ -z "$status" ]; then
  bad "/llm-status.json недоступен (setup-server.sh не отработал?)"
else
  echo "$status" | (command -v jq >/dev/null && jq . || cat) | sed 's/^/       /'
  get() { printf '%s' "$status" | sed -n "s/.*\"$1\":[[:space:]]*\"\{0,1\}\([^,\"}]*\).*/\1/p" | head -1; }
  [ "$(get frps)" = "active" ]      && ok "frps работает"        || bad "frps: $(get frps)"
  [ "$(get open_webui)" = "running" ] && ok "Open WebUI работает" || bad "Open WebUI: $(get open_webui)"
  if [ "$(get pc_tunnel_up)" = "true" ]; then
    ok "туннель с ПК поднят"
  else
    bad "туннель с ПК не поднят - ПК выключен, или frpc не запущен, или не сошёлся токен"
    info "на ПК: Get-Process frpc; Get-Content C:\\llm-agent\\frpc.log -Tail 30"
  fi
fi

head_ "3. API модели снаружи"
tags="$(curl -fsS --max-time 20 "$BASE/ollama/api/tags" 2>/dev/null || true)"
if [ -n "$tags" ]; then
  ok "/ollama/api/tags отвечает"
  printf '%s' "$tags" | grep -o '"name":"[^"]*"' | sed 's/"name":"/       модель: /; s/"$//'
else
  bad "/ollama/api/tags не отвечает"
fi

head_ "4. Модель реально отвечает (может занять минуты при выгрузке в RAM)"
t0=$(date +%s)
resp="$(curl -fsS --max-time 900 "$BASE/ollama/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"agent","messages":[{"role":"user","content":"Ответь одним словом: работает?"}],"stream":false}' \
  2>/dev/null || true)"
t1=$(date +%s)
if [ -n "$resp" ]; then
  ok "ответ получен за $((t1-t0)) с"
  printf '%s' "$resp" | grep -o '"content":"[^"]*"' | head -1 | sed 's/^/       /'
else
  bad "модель не ответила через /ollama/v1/chat/completions"
  info "проверьте, что профиль 'agent' создан: rexec.sh pc 'ollama list'"
fi

head_ "5. Вызов инструментов (агентский режим)"
tool_resp="$(curl -fsS --max-time 900 "$BASE/ollama/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"agent","stream":false,
       "messages":[{"role":"user","content":"Какая погода в Москве? Используй инструмент."}],
       "tools":[{"type":"function","function":{"name":"get_weather",
         "description":"Текущая погода в городе",
         "parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}}]}' \
  2>/dev/null || true)"
if printf '%s' "$tool_resp" | grep -q 'tool_calls'; then
  ok "модель вызывает инструменты - агентом работать может"
  printf '%s' "$tool_resp" | grep -o '"arguments":"[^"]*"' | head -1 | sed 's/^/       /'
else
  bad "tool_calls в ответе нет - агентский режим не подтверждён"
  info "не все модели умеют вызывать инструменты; gpt-oss и Qwen3 умеют"
fi

echo
if [ "$FAIL" -eq 0 ]; then
  printf '\033[1;32mСвязка работает целиком.\033[0m\n'
else
  printf '\033[1;31mЕсть проблемы - смотрите [FAIL] выше.\033[0m\n'
fi
exit "$FAIL"
