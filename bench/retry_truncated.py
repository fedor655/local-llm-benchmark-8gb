# -*- coding: utf-8 -*-
"""Добор: перепрогон задач, оборванных лимитом токенов.

«Думающие» модели (qwen3, deepseek-r1) упираются в num_predict и обрываются
посреди рассуждения — это артефакт бенчмарка, а не их неспособность. Здесь
такие задачи прогоняются заново с большим бюджетом, результат вписывается
обратно в json с пометкой retried.

Запуск: python retry_truncated.py [--models m1 m2 ...]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench  # noqa: E402
from tasks import ALL_TASKS  # noqa: E402

BIG_PREDICT = 12288
BIG_CTX = 16384


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=[])
    args = ap.parse_args()

    by_id = {t["id"]: t for t in ALL_TASKS}
    files = sorted(f for f in os.listdir(bench.RESULTS) if f.endswith(".json"))
    total_retried = 0

    for fn in files:
        path = os.path.join(bench.RESULTS, fn)
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if not d.get("tasks"):
            continue
        model = d["model"]
        if args.models and model not in args.models:
            continue

        stuck = [r for r in d["tasks"] if r.get("truncated")]
        if not stuck:
            continue

        print(f"\n=== {model}: добор {len(stuck)} задач "
              f"(бюджет {BIG_PREDICT} токенов) ===", flush=True)
        rawdir = os.path.join(bench.RAW, bench.safe_name(model))
        os.makedirs(rawdir, exist_ok=True)

        for rec in stuck:
            t = by_id[rec["id"]]
            r = bench.chat(model, t["system"], t["prompt"],
                           BIG_PREDICT, num_ctx=BIG_CTX)
            if r.get("error"):
                print(f"  [ERR ] {rec['id']}: {r['error'][:80]}", flush=True)
                continue

            content = r["content"]
            with open(os.path.join(rawdir, rec["id"] + ".retry.txt"),
                      "w", encoding="utf-8") as f:
                if r.get("thinking"):
                    f.write("<<<THINKING>>>\n" + r["thinking"] +
                            "\n<<<END THINKING>>>\n\n")
                f.write(content)

            kind = t["kind"]
            if kind == "code_py":
                ok, detail = bench.run_snippet(
                    bench.extract_code(content, "py"), t["test"], "py")
            elif kind == "code_js":
                ok, detail = bench.run_snippet(
                    bench.extract_code(content, "js"), t["test"], "js")
            elif kind == "exact":
                ok = bench.match_exact(bench.extract_answer(content), t["answers"])
                detail = "ok" if ok else "неверный ответ"
            elif kind == "json_out":
                ok, detail = bench.check_json_out(content, t["check_json"])
            elif kind == "custom":
                ok, detail = bench.CHECKERS[t["checker"]](content)
            else:
                ok, detail = False, "неизвестный тип"

            was = rec["passed"]
            rec["passed"] = bool(ok)
            rec["detail"] = detail
            rec["wall_s"] = round(r.get("wall", 0.0), 2)
            rec["tok_s"] = round(r.get("tok_s", 0.0), 2)
            rec["out_tokens"] = r.get("eval_count", 0)
            rec["truncated"] = r.get("done_reason") == "length"
            rec["retried"] = True
            total_retried += 1

            mark = "PASS" if ok else "FAIL"
            change = "" if was == ok else ("  <== СТАЛО ЛУЧШЕ" if ok else "")
            trunc = " [снова обрыв]" if rec["truncated"] else ""
            print(f"  [{mark}] {rec['id']:<20} {rec['wall_s']:>6.1f}с "
                  f"{rec['out_tokens']:>5} ток{trunc}{change}", flush=True)

        bench.unload(model)
        new = bench.summarize(model, d["tasks"], d.get("load_s", 0.0),
                              d.get("total_wall_min", 0.0) * 60)
        new["retry_pass"] = True
        with open(path, "w", encoding="utf-8") as f:
            json.dump(new, f, ensure_ascii=False, indent=2)
        print(f"  ИТОГ {model}: было {d['total_score']:.1f} -> "
              f"стало {new['total_score']:.1f} "
              f"(код {new['by_category']['code']['pct']:.0f}%)", flush=True)

    print(f"\nвсего перепрогнано задач: {total_retried}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
