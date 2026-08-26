# -*- coding: utf-8 -*-
"""Графики к разделу про FreeToken: цена памяти и аренда против апгрейда.

Не зависит от результатов бенчмарка — только числа из открытых источников,
собранные в августе 2026. Тема, рамка и сохранение переиспользуются из
charts.py, чтобы новые картинки не выбивались из остальных.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from charts import THEME, frame, save  # noqa: E402

# Курс ЦБ РФ на 20.08.2026. Все рублёвые оценки в разделе считаны по нему.
USD_RUB = 85.13

# Комплект 32 ГБ (2×16) DDR4-3200 SO-DIMM, розница в долларах.
# Источники перечислены в README, раздел «Цена вопроса».
RAM_POINTS = [
    ("Начало\n2024", 67),
    ("Окт\n2025", 75),
    ("Янв\n2026", 165),
    ("Фев\n2026", 195),
    ("Авг\n2026", 297),
]

# Апгрейд ноутбука до 64 ГБ: комплект 2×32 ГБ SO-DIMM (~$700) плюс
# российская наценка 15–20 % за курс и логистику.
UPGRADE_RUB = 65_000

# Аренда почасово, vast.ai / Runpod, август 2026.
RENT = [
    ("RTX 4090, 24 ГБ", 0.35),
    ("RTX 3090, 24 ГБ", 0.20),
]


def chart_ram_price(mode):
    t = THEME[mode]
    fig, ax = plt.subplots(figsize=(9.5, 5.6))

    labels = [p[0] for p in RAM_POINTS]
    vals = [p[1] for p in RAM_POINTS]
    x = range(len(vals))

    ax.yaxis.grid(True, color=t["grid"], linewidth=1, zorder=0)
    ax.set_axisbelow(True)

    ax.plot(x, vals, color=t["series"][0], linewidth=2.4, zorder=3,
            solid_capstyle="round")
    ax.scatter(x, vals, s=90, color=t["series"][0], zorder=4,
               edgecolors=t["surface"], linewidths=2)

    for i, v in enumerate(vals):
        ax.annotate(f"${v}", (i, v), textcoords="offset points",
                    xytext=(0, 14), ha="center", color=t["ink"],
                    fontsize=11, fontweight="600")

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, color=t["ink2"], fontsize=10.5)
    ax.set_ylim(0, max(vals) * 1.28)
    ax.set_xlim(-0.45, len(vals) - 0.55)

    frame(ax, t, ylabel="Цена комплекта, $",
          title="Комплект 32 ГБ DDR4-3200 SO-DIMM подорожал в 4.4 раза",
          sub="весь скачок пришёлся на переброс мощностей DRAM на HBM для ИИ-ускорителей")
    save(fig, f"ram-price-{mode}.png", t)


def chart_rent_vs_buy(mode):
    t = THEME[mode]
    fig, ax = plt.subplots(figsize=(9.5, 5.8))

    hours = list(range(0, 4001, 50))
    ax.yaxis.grid(True, color=t["grid"], linewidth=1, zorder=0)
    ax.set_axisbelow(True)

    ax.axhline(UPGRADE_RUB, color=t["ink2"], linewidth=1.8, linestyle=(0, (5, 4)),
               zorder=3)
    ax.annotate(f"апгрейд ноутбука до 64 ГБ ≈ {UPGRADE_RUB // 1000} 000 ₽",
                (80, UPGRADE_RUB), textcoords="offset points",
                xytext=(0, 10), ha="left", color=t["ink2"], fontsize=10.5)

    # Подпись 4090 идёт влево-вверх от своей линии — сверху пусто. Подпись
    # 3090 приходится уводить ВНИЗ: над ней проходит линия 4090, и при верхнем
    # выносе текст оказывался перечёркнут. Точки окупаемости разведены по
    # разные стороны пунктира, иначе сталкиваются с подписями рядов.
    LABEL = [(2600, (-12, 24), "right"), (2900, (0, -22), "left")]
    BE_OFFSET = [(-10, 12), (-10, -24)]

    for i, (name, usd_h) in enumerate(RENT):
        rub_h = usd_h * USD_RUB
        ax.plot(hours, [h * rub_h for h in hours], color=t["series"][i],
                linewidth=2.4, zorder=4, solid_capstyle="round")

        be = UPGRADE_RUB / rub_h
        if be <= hours[-1]:
            ax.scatter([be], [UPGRADE_RUB], s=90, color=t["series"][i],
                       zorder=5, edgecolors=t["surface"], linewidths=2)
            ax.annotate(f"{round(be / 10) * 10:.0f} ч", (be, UPGRADE_RUB),
                        textcoords="offset points", xytext=BE_OFFSET[i],
                        ha="right", color=t["ink"], fontsize=10.5,
                        fontweight="600")

        lx, loff, lha = LABEL[i]
        ax.annotate(f"{name} · {rub_h:.0f} ₽/ч", (lx, lx * rub_h),
                    textcoords="offset points", xytext=loff, ha=lha,
                    color=t["series"][i], fontsize=10.5, fontweight="600")

    ax.set_xlim(0, 4300)
    ax.set_ylim(0, 130_000)
    ax.set_yticks(range(0, 130_001, 25_000))
    ax.set_yticklabels([f"{v // 1000} 000 ₽" if v else "0"
                        for v in range(0, 130_001, 25_000)])

    frame(ax, t, xlabel="Часов работы",
          title="За цену апгрейда памяти — 2200 часов аренды RTX 4090",
          sub="и арендованная 4090 мощнее, чем 3070 с доложенной памятью")
    save(fig, f"rent-vs-buy-{mode}.png", t)


def main():
    for mode in ("light", "dark"):
        print(f"--- {mode} ---")
        chart_ram_price(mode)
        chart_rent_vs_buy(mode)
    print("\nготово")
    return 0


if __name__ == "__main__":
    sys.exit(main())
