# Локальные ИИ-агенты для написания кода — обзор

Что реально можно натравить на локальную модель (Ollama/vLLM) для кодинга, и
почему одни связки работают, а другие зависают. Обзор + **наши живые находки**
с этого проекта.

## Ландшафт (все open-source, работают с локальными моделями)

| Инструмент | Форм-фактор | Как правит код | Автономность |
|---|---|---|---|
| **Aider** | CLI (git) | SEARCH/REPLACE-диффы | полу-авто (`--yes`) |
| **Cline** | VS Code | XML-теги инструментов | Plan/Act, разрешения |
| **Roo Code** / **Kilo Code** | VS Code | форки Cline, больше фич | автономнее |
| **Continue** | VS Code / JetBrains | autocomplete + chat + agent | настраиваемо |
| **OpenHands** | веб-UI + Docker | function-calling (JSON) | полностью автономный |
| **Goose** (Block) | CLI/desktop | MCP-инструменты | кросс-инструментальный |
| **OpenCode** (SST) | терминал | provider-agnostic | автономный |
| **Tabby** / **Twinny** | self-host / VS Code | autocomplete + chat | ассистент |

## Главная практическая проблема: формат tool-call

Агенты используют **разные форматы вызова инструментов**, и локальные модели держат
их по-разному:

| Формат | Кто использует | Локальные модели |
|---|---|---|
| **SEARCH/REPLACE-дифф** | Aider | держат лучше всего (код-тюнинг = дисциплина диффов) |
| **OpenAI JSON tool-calls** | Continue, часть OpenHands | нормально у coder-моделей |
| **Anthropic-XML теги** | Cline | капризно: Cline жёстко привязан к XML, и модель, шлющая JSON, **зависает в цикле** |
| **MCP JSON-RPC** | Goose | требует надёжного structured-output |

**Известный баг** ([cline#10843](https://github.com/cline/cline/issues/10843)):
локальный Qwen2.5-Coder шлёт валидный JSON, а Cline ждёт XML → бесконечный цикл.
Лечится принудительным выравниванием на XML.

## Какие локальные модели тянут агентов

- **Qwen3-Coder-30B-A3B** — ~**96% корректных tool-call**, 256K контекст, агентный
  тюнинг. Практический порог «надёжного агента».
- **Qwen2.5-Coder 32B/14B/7B** — рабочие, стоковые версии держат формат.
- **Аблитерированные** версии — **хуже** по дисциплине инструментов (наш замер ниже).

## Наши живые находки (этот проект)

Проверено на RTX 3070 (локально) и аренде RTX 4090:

1. **Размер решает.** 7B-abliterated как агент **не выдал ни одного** валидного шага
   протокола; 30B — держит. (см. `stage1-local-findings.md`)
2. **Aider — самый прощающий.** SEARCH/REPLACE-формат съедает даже просевшую модель;
   обе 30B-модели прошли задачи **4/4** с проверкой исполнением.
3. **OpenHands — мощный, но строгий.** Требует поле `security_risk` в каждом
   `execute_bash`; аблитерированная 30B его **стабильно забывала** (десяток ошибок),
   переусердствовала на «привет» (построила Flask-app). На медленном сетевом томе
   рантайм ещё и висел — чинилось патчем плагинов (см. `server-agents-research`).
4. **Цена аблитерации — в дисциплине, не в уме.** Балл на 32 задачах: сток =
   abliterated (83.5/100). Ломается именно строгий tool-calling.

## Рекомендации по кейсам

- **Быстрый старт / прогоны / максимальная совместимость с локалью** → **Aider**
  (`aider --model ollama_chat/qwen3-coder`). Прощает формат.
- **Интерактив в IDE** → **Cline/Roo** (но сверь, что модель шлёт нужный формат;
  бери **стоковый** coder, не abliterated).
- **Полная автономия + песочница** → **OpenHands** (нужна сильная модель 30B+ и
  терпимость к строгому протоколу).
- **Приватность прежде всего** → **Continue + Ollama** или Aider локально: код не
  покидает машину.

**Общий вывод:** для локального агента бери **coder-модель 30B+** (Qwen3-Coder),
**сток, не abliterated**, и **прощающий формат** (Aider SEARCH/REPLACE). Строгие
JSON/XML-протоколы (Cline/OpenHands) требуют самой дисциплинированной модели.

## Источники
- [9 self-hostable coding agents (Security Boulevard)](https://securityboulevard.com/2026/06/9-open-source-ai-coding-agents-worth-self-hosting/)
- [Open-source coding agents (OpenHands blog)](https://www.openhands.dev/blog/open-source-ai-coding-agents)
- [Open-source assistants ranked, local-model support (Morph)](https://www.morphllm.com/ai-coding-assistant-open-source)
- [Best local models for tool calling 2026 (PromptQuorum)](https://www.promptquorum.com/power-local-llm/best-local-models-tool-calling-2026)
- [Cline #10843 — local model tool-format loop](https://github.com/cline/cline/issues/10843)
