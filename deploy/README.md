# Развёртывание сервера с агентом (сохранённая конфигурация)

Воспроизводит стенд, собранный на RTX 4090: **Ollama + 30B-кодер (abliterated и
stock) + Aider + OpenHands (пропатченный)**. Всё в одном скрипте — под переезд на
H100.

## Быстрый старт

```bash
# на свежем сервере (Ubuntu 22.04/24.04 + CUDA), под пользователем ubuntu:
chmod +x setup.sh
./setup.sh                 # 24GB-карта (Q4_K_M)
QUANT=Q6_K ./setup.sh      # 80GB-карта (H100) — квант получше
```

Что ставит: Ollama (слушает 0.0.0.0), обе модели, Docker, ufw (наружу только SSH +
Jupyter), Aider, OpenHands на `127.0.0.1:3000` + патч рантайма.

Доступ к UI (с ноутбука):
```bash
ssh -i <key> -N -L 3000:localhost:3000 ubuntu@<server-ip>
# затем http://localhost:3000
```

## Переезд на H100 80GB — что поменять

**1. Квант — можно жирнее (больше качества).** 30B-A3B помещается целиком:

| Квант | Размер | 24GB | 80GB (H100) |
|---|---|---|---|
| Q4_K_M | ~17 ГБ | ✅ | ✅ |
| Q6_K | ~23 ГБ | впритык | ✅ **(рекоменд.)** |
| Q8_0 | ~32 ГБ | ❌ | ✅ |
| BF16 (полные веса) | ~57 ГБ | ❌ | ✅ (через vLLM) |

Просто: `QUANT=Q6_K ./setup.sh`.
Для **Q8_0** поменяй в `setup.sh` репозитории с `-i1-GGUF` на `-GGUF` (у static-
сборок есть Q8_0), у i1 его может не быть.

**2. Максимум качества — vLLM + BF16** (вместо Ollama), полные веса:
```bash
pip install vllm
vllm serve huihui-ai/Huihui-Qwen3-Coder-30B-A3B-Instruct-abliterated \
  --max-model-len 32768 --port 11434 --served-model-name coder-abliterated
```
Эндпоинт OpenAI-совместимый — Aider/OpenHands цепляются без изменений. Даёт выше
throughput и параллельность; на H100 имеет смысл.

**3. Патч OpenHands (шаг 7) на H100, скорее всего, НЕ нужен.** Зависание рантайма
было из-за **медленного сетевого тома** (инициализация jupyter/vscode не
завершалась). На быстром локальном NVMe H100 плагины поднимутся сами. Патч
безвреден (просто убирает vscode/jupyter-оверхед) — оставь, если не нужен
VS Code/IPython внутри песочницы; убери шаг 7, если нужны.

## Модели

- `coder-abliterated` — `Huihui-Qwen3-Coder-30B-A3B-Instruct-abliterated` (без цензуры)
- `coder-stock` — `Qwen3-Coder-30B-A3B-Instruct` (сток)

Сравнение: в OpenHands **Settings → LLM → Custom Model** меняешь
`openai/coder-abliterated` ↔ `openai/coder-stock`. В Aider — флаг `--model`.

## Прогон бенчмарка через агента

`task_runner.py` (в корне при тесте) гоняет задачи из `bench/tasks.py` через Aider
и проверяет unit-тестами:
```bash
MODEL=coder-abliterated python3 task_runner.py
MODEL=coder-stock       python3 task_runner.py
```

## Замечания и выводы
Подробности отладки и findings — в
[`docs/server-agents-research.md`](../docs/server-agents-research.md).
Ключевое: канал к модели — **HTTP API**, не TTY; агент-клиент — **готовый
фреймворк**, не самоделка; на строгом tool-calling видна цена аблитерации.
