# -*- coding: utf-8 -*-
"""Собирает результаты в итоговый markdown-отчёт."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench  # noqa: E402
from tasks import ALL_TASKS, CATEGORY_OF  # noqa: E402

RESULTS = bench.RESULTS
OUT = os.path.join(bench.BASE, "results", "REPORT.md")

CAT_TITLE = {
    "code": "Код",
    "reasoning": "Логика",
    "instruction": "Инстр.",
    "russian": "Рус.",
    "longctx": "Контекст",
}


def load():
    """Возвращает (полные прогоны, неполные). Модель с неполным набором задач
    нельзя ставить в общий рейтинг: её итоговый балл считается по категориям,
    и отсутствующие категории обнулили бы его без всякой связи с качеством."""
    full, partial = [], []
    for fn in sorted(os.listdir(RESULTS)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(RESULTS, fn), encoding="utf-8") as f:
            try:
                d = json.load(f)
            except Exception:  # noqa: BLE001
                continue
        if not d.get("tasks"):
            continue
        real = [r for r in d["tasks"] if r["detail"] != "пропущено после сбоев"]
        if len(real) < len(ALL_TASKS):
            d["_done_tasks"] = len(real)
            partial.append(d)
        else:
            full.append(d)
    return full, partial


def sizes():
    try:
        return {n: s for n, s in bench.list_local_models()}
    except Exception:  # noqa: BLE001
        return {}


def main():
    data, partial = load()
    if not data:
        print("нет результатов")
        return 1
    data.sort(key=lambda d: -d["total_score"])
    sz = sizes()

    L = []
    L.append("# Бенчмарк локальных LLM\n")
    L.append(f"Моделей протестировано: **{len(data)}**, задач на модель: "
             f"**{len(ALL_TASKS)}**.\n")

    L.append("\n## Сводная таблица\n")
    L.append("| # | Модель | Размер | **Балл** | Код | Логика | Инстр. | Рус. | "
             "Контекст | tok/s | Загрузка | Время прогона |")
    L.append("|---|--------|--------|----------|-----|--------|--------|------|"
             "----------|-------|----------|---------------|")
    for i, d in enumerate(data, 1):
        c = d["by_category"]
        gb = sz.get(d["model"], 0) / 1e9
        L.append(
            f"| {i} | `{d['model']}` | {gb:.1f} ГБ | **{d['total_score']:.1f}** | "
            f"{c['code']['pct']:.0f}% | {c['reasoning']['pct']:.0f}% | "
            f"{c['instruction']['pct']:.0f}% | {c['russian']['pct']:.0f}% | "
            f"{c['longctx']['pct']:.0f}% | {d['median_tok_s']:.1f} | "
            f"{d['load_s']:.1f}с | {d['total_wall_min']:.1f} мин |"
        )

    if partial:
        L.append("\n## Неполные прогоны (вне общего рейтинга)\n")
        L.append("| Модель | Задач пройдено | Решено | Код | tok/s |")
        L.append("|--------|----------------|--------|-----|-------|")
        for d in partial:
            c = d["by_category"]
            L.append(f"| `{d['model']}` | {d['_done_tasks']} из {len(ALL_TASKS)} | "
                     f"{d['passed']} | {c['code']['pct']:.0f}% | "
                     f"{d['median_tok_s']:.1f} |")

    L.append("\n## Кодовые задачи по отдельности\n")
    code_tasks = [t["id"] for t in ALL_TASKS if CATEGORY_OF[t["id"]] == "code"]
    short = {tid: tid.replace("py_", "").replace("js_", "js:") for tid in code_tasks}
    L.append("| Модель | " + " | ".join(short[t] for t in code_tasks) + " | Итого |")
    L.append("|---" * (len(code_tasks) + 2) + "|")
    for d in data:
        by = {r["id"]: r for r in d["tasks"]}
        cells = []
        for tid in code_tasks:
            r = by.get(tid)
            cells.append("+" if r and r["passed"] else ".")
        n = sum(1 for c in cells if c == "+")
        L.append(f"| `{d['model']}` | " + " | ".join(cells) +
                 f" | {n}/{len(code_tasks)} |")

    L.append("\n## Сложность задач (сколько моделей справилось)\n")
    L.append("| Задача | Категория | Решили |")
    L.append("|--------|-----------|--------|")
    for t in ALL_TASKS:
        tid = t["id"]
        ok = sum(1 for d in data
                 for r in d["tasks"] if r["id"] == tid and r["passed"])
        L.append(f"| `{tid}` | {CAT_TITLE[CATEGORY_OF[tid]]} | {ok}/{len(data)} |")

    L.append("\n## Скорость и реальная цена ответа\n")
    L.append("На практике решает не tok/s, а сколько ждать готовый ответ: "
             "«думающая» модель может быть быстрой по токенам и всё равно "
             "заставлять ждать минутами, потому что токенов она порождает тысячи.\n")
    L.append("| Модель | Медиана tok/s | Ср. время кодового ответа | "
             "Ср. длина ответа | Обрывов по лимиту | Добор |")
    L.append("|--------|---------------|---------------------------|"
             "------------------|-------------------|-------|")
    for d in data:
        code = [r for r in d["tasks"] if CATEGORY_OF[r["id"]] == "code"]
        avg_w = sum(r["wall_s"] for r in code) / len(code) if code else 0
        avg_t = sum(r["out_tokens"] for r in code) / len(code) if code else 0
        retried = sum(1 for r in d["tasks"] if r.get("retried"))
        L.append(f"| `{d['model']}` | {d['median_tok_s']:.1f} | {avg_w:.0f}с | "
                 f"{avg_t:.0f} ток | {d['truncated_count']} | "
                 f"{('да, ' + str(retried)) if retried else '—'} |")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n>>> записано в {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
