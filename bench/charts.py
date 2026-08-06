# -*- coding: utf-8 -*-
"""Графики для README. Рендерит каждый в светлом и тёмном варианте.

Палитра — валидированная (см. скилл dataviz): для категориальных шкал взяты
первые три слота, они проходят проверку по всем парам в обоих режимах.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench  # noqa: E402
from tasks import ALL_TASKS, CATEGORY_OF  # noqa: E402

OUT = os.path.join(bench.BASE, "charts")
os.makedirs(OUT, exist_ok=True)

THEME = {
    "light": dict(
        surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
        grid="#e1e0d9", axis="#c3c2b7",
        series=["#2a78d6", "#eb6834", "#1baf7a"],
        seq=["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf",
             "#184f95", "#0d366b"],
    ),
    "dark": dict(
        surface="#1a1a19", ink="#ffffff", ink2="#c3c2b7", muted="#898781",
        grid="#2c2c2a", axis="#383835",
        series=["#3987e5", "#d95926", "#199e70"],
        seq=["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf",
             "#184f95", "#0d366b"],
    ),
}

CAT_ORDER = ["code", "reasoning", "instruction", "russian", "longctx"]
CAT_RU = {"code": "Код", "reasoning": "Логика", "instruction": "Инструкции",
          "russian": "Русский", "longctx": "Контекст"}

plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans", "sans-serif"]


def load():
    out = []
    for fn in sorted(os.listdir(bench.RESULTS)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(bench.RESULTS, fn), encoding="utf-8") as f:
            try:
                d = json.load(f)
            except Exception:  # noqa: BLE001
                continue
        if d.get("tasks") and len(d["tasks"]) == len(ALL_TASKS):
            code = [r for r in d["tasks"] if CATEGORY_OF[r["id"]] == "code"]
            d["_code_wait"] = sum(r["wall_s"] for r in code) / len(code)
            out.append(d)
    out.sort(key=lambda d: -d["total_score"])
    return out


def sizes_gb():
    try:
        return {n: s / 1e9 for n, s in bench.list_local_models()}
    except Exception:  # noqa: BLE001
        return {}


def frame(ax, t, xlabel=None, ylabel=None, title=None, sub=None):
    ax.set_facecolor(t["surface"])
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(t["axis"])
        ax.spines[s].set_linewidth(1.0)
    ax.tick_params(colors=t["muted"], labelsize=10, length=0)
    if title:
        ax.set_title(title, color=t["ink"], fontsize=15, fontweight="600",
                     loc="left", pad=26 if sub else 10)
    if sub:
        # Смещение строго в пунктах: в долях осей на высоком графике
        # подзаголовок наезжает на заголовок.
        ax.annotate(sub, (0, 1), xycoords="axes fraction",
                    textcoords="offset points", xytext=(0, 7),
                    color=t["ink2"], fontsize=10.5, va="bottom", ha="left")
    if xlabel:
        ax.set_xlabel(xlabel, color=t["ink2"], fontsize=10.5, labelpad=8)
    if ylabel:
        ax.set_ylabel(ylabel, color=t["ink2"], fontsize=10.5, labelpad=8)


def rbar(ax, y, width, height, color, r=0.22):
    """Горизонтальный столбец со скруглёнными концами."""
    r = min(r, height / 2, max(width, 1e-9) / 2)
    p = FancyBboxPatch(
        (0, y - height / 2 + r), max(width - 2 * r, 1e-9), height - 2 * r,
        boxstyle=f"round,pad={r},rounding_size={r}",
        linewidth=0, facecolor=color, mutation_aspect=1,
    )
    ax.add_patch(p)


def save(fig, name, t):
    fig.patch.set_facecolor(t["surface"])
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor=t["surface"])
    plt.close(fig)
    print("  ", os.path.basename(path))


# ---------------------------------------------------------------------------

def chart_ranking(data, mode):
    t = THEME[mode]
    fig, ax = plt.subplots(figsize=(9.5, 7.2))
    names = [d["model"] for d in data][::-1]
    vals = [d["total_score"] for d in data][::-1]

    ax.xaxis.grid(True, color=t["grid"], linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for i, v in enumerate(vals):
        rbar(ax, i, v, 0.58, t["series"][0])
        ax.text(v + 1.2, i, f"{v:.1f}", va="center", ha="left",
                color=t["ink"], fontsize=10, fontweight="600")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, color=t["ink"], fontsize=10.5)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.7, len(names) - 0.3)
    frame(ax, t, xlabel="Итоговый балл из 100",
          title="Общий зачёт: 16 локальных моделей",
          sub="код 50 % · логика 25 % · инструкции 10 % · русский 10 % · контекст 5 %")
    save(fig, f"ranking-{mode}.png", t)


def chart_tradeoff(data, mode, sz):
    t = THEME[mode]
    fig, ax = plt.subplots(figsize=(10, 6.8))

    def group(d):
        g = sz.get(d["model"], 0)
        if g <= 6.0:
            return 0
        return 1 if g <= 9.5 else 2

    labels = ["влезает в 8 ГБ VRAM", "на грани (7–9 ГБ)", "не влезает (>9 ГБ)"]
    ax.grid(True, color=t["grid"], linewidth=1, zorder=0)
    ax.set_axisbelow(True)

    pts = sorted(data, key=lambda d: -d["total_score"])
    for gi in (0, 1, 2):
        xs = [d["_code_wait"] for d in pts if group(d) == gi]
        ys = [d["by_category"]["code"]["pct"] for d in pts if group(d) == gi]
        if xs:
            ax.scatter(xs, ys, s=140, color=t["series"][gi], zorder=3,
                       edgecolors=t["surface"], linewidths=2, label=labels[gi])

    ax.set_xscale("log")
    ax.set_xlim(2.6, 330)
    ax.set_xticks([5, 10, 25, 50, 100, 200])
    ax.set_xticklabels(["5 с", "10 с", "25 с", "50 с", "100 с", "200 с"])
    ax.set_ylim(0, 114)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(["0 %", "25 %", "50 %", "75 %", "100 %"])
    frame(ax, t, xlabel="Среднее ожидание кодового ответа (шкала логарифмическая)",
          ylabel="Решено кодовых задач",
          title="Главный компромисс: качество кода против времени ожидания",
          sub="левый верхний угол — идеал: умно и быстро")
    leg = ax.legend(loc="lower right", frameon=False, fontsize=10)
    for txt in leg.get_texts():
        txt.set_color(t["ink2"])

    # Подписи 16 точек неизбежно налезают друг на друга при размещении
    # «строго сверху»: перебираем позиции вокруг точки и берём первую,
    # которая никого не задевает и не вылезает за область графика.
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    cands = [(0, 12, "center", "bottom"), (0, -13, "center", "top"),
             (11, 0, "left", "center"), (-11, 0, "right", "center"),
             (0, 22, "center", "bottom"), (0, -23, "center", "top"),
             (11, 11, "left", "bottom"), (-11, 11, "right", "bottom"),
             (11, -11, "left", "top"), (-11, -11, "right", "top")]
    placed = [leg.get_window_extent(rend)]
    axbb = ax.get_window_extent(rend)
    # Сами маркеры тоже занимают место: без этого подпись садится на чужую точку.
    for d in pts:
        px, py = ax.transData.transform(
            (d["_code_wait"], d["by_category"]["code"]["pct"]))
        placed.append(matplotlib.transforms.Bbox.from_bounds(
            px - 9, py - 9, 18, 18))
    for d in pts:
        xy = (d["_code_wait"], d["by_category"]["code"]["pct"])
        for dx, dy, ha, va in cands:
            ann = ax.annotate(d["model"], xy, textcoords="offset points",
                              xytext=(dx, dy), ha=ha, va=va, fontsize=8.8,
                              color=t["ink2"], zorder=4)
            bb = ann.get_window_extent(rend).expanded(1.06, 1.25)
            if axbb.containsx(bb.x0) and axbb.containsx(bb.x1) \
                    and axbb.containsy(bb.y0) and axbb.containsy(bb.y1) \
                    and not any(bb.overlaps(p) for p in placed):
                placed.append(bb)
                break
            ann.remove()
        else:
            ann = ax.annotate(d["model"], xy, textcoords="offset points",
                              xytext=(0, 12), ha="center", va="bottom",
                              fontsize=8.8, color=t["ink2"], zorder=4)
            placed.append(ann.get_window_extent(rend))
    save(fig, f"tradeoff-{mode}.png", t)


def chart_heatmap(data, mode):
    t = THEME[mode]
    cmap = LinearSegmentedColormap.from_list("seq", t["seq"])
    fig, ax = plt.subplots(figsize=(8.2, 7.6))
    grid = [[d["by_category"][c]["pct"] for c in CAT_ORDER] for d in data]
    ax.imshow(grid, cmap=cmap, vmin=0, vmax=100, aspect="auto")

    for i, row in enumerate(grid):
        for j, v in enumerate(row):
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=9.5,
                    fontweight="600",
                    color="#ffffff" if v >= 55 else "#0b0b0b")
    ax.set_xticks(range(len(CAT_ORDER)))
    ax.set_xticklabels([CAT_RU[c] for c in CAT_ORDER], color=t["ink"],
                       fontsize=10.5)
    ax.set_yticks(range(len(data)))
    ax.set_yticklabels([d["model"] for d in data], color=t["ink"], fontsize=10)
    ax.tick_params(colors=t["muted"], length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([x - 0.5 for x in range(1, len(CAT_ORDER))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(data))], minor=True)
    ax.grid(which="minor", color=t["surface"], linewidth=2)
    ax.tick_params(which="minor", length=0)
    ax.set_title("Сильные и слабые стороны по категориям", color=t["ink"],
                 fontsize=15, fontweight="600", loc="left", pad=26)
    ax.annotate("процент решённых задач в каждой категории", (0, 1),
                xycoords="axes fraction", textcoords="offset points",
                xytext=(0, 7), color=t["ink2"], fontsize=10.5,
                va="bottom", ha="left")
    save(fig, f"categories-{mode}.png", t)


def chart_tasks(data, mode):
    t = THEME[mode]
    n = len(data)
    rows = []
    for task in ALL_TASKS:
        tid = task["id"]
        sol = sum(1 for d in data for r in d["tasks"]
                  if r["id"] == tid and r["passed"])
        rows.append((tid, CAT_RU[CATEGORY_OF[tid]], sol))
    rows.sort(key=lambda r: r[2])

    fig, ax = plt.subplots(figsize=(9.5, 10))
    ax.xaxis.grid(True, color=t["grid"], linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for i, (tid, cat, sol) in enumerate(rows):
        rbar(ax, i, sol, 0.6, t["series"][0], r=0.18)
        ax.text(sol + 0.18, i, str(sol), va="center", ha="left",
                color=t["ink"], fontsize=9.5, fontweight="600")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([f"{tid}  ·  {cat}" for tid, cat, _ in rows],
                       color=t["ink"], fontsize=9.5)
    ax.set_xlim(0, n + 1.2)
    ax.set_ylim(-0.7, len(rows) - 0.3)
    ax.set_xticks(range(0, n + 1, 4))
    frame(ax, t, xlabel=f"Сколько моделей из {n} решили задачу",
          title="Сложность задач",
          sub="снизу — то, на чём модели ломаются чаще всего")
    save(fig, f"tasks-{mode}.png", t)


def main():
    data = load()
    sz = sizes_gb()
    print(f"моделей: {len(data)}")
    for mode in ("light", "dark"):
        print(f"--- {mode} ---")
        chart_ranking(data, mode)
        chart_tradeoff(data, mode, sz)
        chart_heatmap(data, mode)
        chart_tasks(data, mode)
    print(f"\nготово: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
