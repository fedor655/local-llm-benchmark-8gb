# -*- coding: utf-8 -*-
"""Прогоняет бенчмарк по моделям по мере их появления в ollama.

Завершается, когда pull.log сообщил об окончании загрузки и все модели
из ollama list уже посчитаны.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench  # noqa: E402
from tasks import ALL_TASKS  # noqa: E402

BASE = bench.BASE
PULL_LOG = os.path.join(BASE, "logs", "pull.log")
# Флаг ставит pull2.ps1 в самом конце — после основной очереди И догоняющей.
# Ориентироваться на строку в pull.log нельзя: основной скрипт пишет её раньше,
# и драйвер вышел бы, не дождавшись догоняющих моделей.
PULL_FLAG = os.path.join(BASE, "logs", "pulls_complete.flag")
POLL_S = 90


def pulls_done():
    return os.path.exists(PULL_FLAG)


def main():
    os.makedirs(bench.RESULTS, exist_ok=True)
    os.makedirs(bench.RAW, exist_ok=True)
    seen_idle = 0
    while True:
        models = [n for n, _ in bench.list_local_models()]
        pending = [
            m for m in models
            if not os.path.exists(
                os.path.join(bench.RESULTS, bench.safe_name(m) + ".json"))
        ]
        if pending:
            seen_idle = 0
            for m in pending:
                print(f"\n>>> старт {m} ({time.strftime('%H:%M:%S')})", flush=True)
                try:
                    bench.run_model(m, ALL_TASKS)
                except Exception as e:  # noqa: BLE001
                    print(f"!! сбой на {m}: {type(e).__name__}: {e}", flush=True)
                    # чтобы не зациклиться на битой модели
                    with open(os.path.join(bench.RESULTS,
                                           bench.safe_name(m) + ".json"),
                              "w", encoding="utf-8") as f:
                        f.write('{"model": %r, "error": %r, "tasks": []}'
                                % (m, f"{type(e).__name__}: {e}"))
            continue

        if pulls_done():
            print("\nвсё посчитано, загрузки завершены — выход", flush=True)
            return 0

        seen_idle += 1
        if seen_idle % 10 == 1:
            print(f"[{time.strftime('%H:%M:%S')}] жду новые модели "
                  f"(посчитано {len(models)})", flush=True)
        time.sleep(POLL_S)


if __name__ == "__main__":
    sys.exit(main())
