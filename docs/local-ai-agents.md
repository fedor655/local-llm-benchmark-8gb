# Локальные ИИ-агенты

От «модель отвечает в чате» к «модель как агент»: читает и правит код, вызывает
инструменты, гоняет задачи сама. Ветка — про запуск агентной модели без цензуры
в три этапа по нарастанию мощности.

## Модель

**`huihui-ai/Huihui-Qwen3-Coder-30B-A3B-Instruct-abliterated`**
— аблитерированная версия Qwen3-Coder-30B-A3B.

- 30,5B параметров, **3B активных** (MoE) → быстрая генерация при «знаниях» 30B.
- 256K контекст, сильный tool-calling (в стоке), заточен под «читай-правь-запускай».
- Вес BF16 ≈ 57 ГБ; GGUF-кванты для дешёвого старта есть у `mradermacher`.

**Нюанс аблитерации:** снятие отказов может просаживать именно tool-calling и
структурированный вывод — то, на чём держится агент. Поэтому на обкатке сравниваем
с **стоковым** `Qwen/Qwen3-Coder-30B-A3B-Instruct`: для обычного кода сток почти не
отказывает и держит инструменты надёжнее. Аблитерированную берём, только если отказы
реально мешают (security / эксплойты для CTF / пентест).

## Агент-клиент: Aider

Aider правит код через простой diff-формат, а не через жёсткий протокол функций —
поэтому **прощает** просевший после аблитерации tool-calling. Легко цепляется и к
Ollama, и к vLLM (меняется один флаг). Хорош для воспроизводимых прогонов — ложится
на ту же логику, что и бенчмарк.

Cline / Roo (VS Code) — вторым, когда подтвердим, что tool-calling держится: UX богаче,
автономнее, но строже к протоколу инструментов.

## Три этапа

> **Этап 1 пройден.** Результаты и грабли — в
> [stage1-local-findings.md](stage1-local-findings.md): 7B пишет корректный код,
> но протокол инструментов не держит; вызывать модель только по HTTP API,
> клиент — готовый фреймворк, не самоделка.

### Этап 0 — превью локально (0 ₽)
30B в 8 ГБ не влезет, но **7B-abliterated-кодер влезет** — пощупать поведение.
```bash
ollama pull hf.co/bartowski/Qwen2.5-Coder-7B-Instruct-abliterated-GGUF:Q4_K_M
pip install aider-chat
aider --model ollama_chat/hf.co/bartowski/Qwen2.5-Coder-7B-Instruct-abliterated-GGUF:Q4_K_M
```

### Этап 1 — обкатка на RTX 5090 32GB (~120 ₽/ч)
GGUF Q4 (~18 ГБ) через Ollama. Проверить, что модель отвечает, привязать Aider,
погонять tool-calling и пару реальных задач. Пара часов ≈ ~300 ₽.
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull hf.co/mradermacher/Huihui-Qwen3-Coder-30B-A3B-Instruct-abliterated-i1-GGUF:Q4_K_M
aider --model ollama_chat/<tag>          # эндпоинт http://localhost:11434
```

### Этап 2 — максимум на A100 80GB / H100 (~190–320 ₽/ч)
Полные веса BF16 (57 ГБ) через **vLLM**, OpenAI-совместимый эндпоинт, длинный
контекст, параллельность. Код агента не меняется — только `base_url`.
```bash
pip install vllm
vllm serve huihui-ai/Huihui-Qwen3-Coder-30B-A3B-Instruct-abliterated \
  --max-model-len 32768 --port 8000
aider --openai-api-base http://<server>:8000/v1 --openai-api-key dummy \
  --model openai/huihui-ai/Huihui-Qwen3-Coder-30B-A3B-Instruct-abliterated
```
H200/H100 нужны только при переходе на 80B-abliterated
(`bartowski/huihui-ai_Qwen3-Coder-Next-abliterated`). Для 30B хватает A100.

## Стоимость (immers.cloud / Intelion, руб/час)

| GPU | Точность | Цена/ч | 5000 ₽ хватит на |
|---|---|---|---|
| RTX 5090 32GB | GGUF Q4 | ~120 | ~40 ч |
| A100 80GB | BF16 | ~190 | ~26 ч |
| H100 80GB | BF16 | ~320 | ~15 ч |

## Что мерить у агента (в отличие от чат-бенчмарка)

- **Доля решённых задач** end-to-end (правка проходит тесты) — SWE-bench-логика.
- **Надёжность tool-calling** — как часто ломается формат правки / вызов инструмента.
- **Сток vs abliterated** на одних задачах — цена аблитерации для агентного режима.
