# -*- coding: utf-8 -*-
"""
Бенчмарк локальных LLM через Ollama HTTP API.

Запуск:
    python bench.py --models qwen3:8b qwen2.5-coder:7b
    python bench.py --all            # все модели из `ollama list`
    python bench.py --all --resume   # пропустить уже посчитанные

Результаты: results/<model>.json + results/raw/<model>/<task>.txt
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tasks import ALL_TASKS, CATEGORY_OF, CATEGORY_WEIGHTS  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(BASE, "results")
RAW = os.path.join(RESULTS, "raw")
API = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
if not API.startswith("http"):
    API = "http://" + API

# Параметры генерации — одинаковые для всех моделей ради честности сравнения.
GEN_OPTIONS = {
    "temperature": 0.2,
    "top_p": 0.9,
    "seed": 42,
    "num_ctx": 8192,
}
# Лимит подобран так, чтобы «думающие» модели (qwen3, deepseek-r1) успевали
# закончить рассуждение и выдать ответ: при 2560 их обрывало на середине <think>,
# и это выглядело как провал задачи, хотя виноват был бенчмарк.
NUM_PREDICT = {
    "code_py": 6144,
    "code_js": 6144,
    "exact": 4096,
    "json_out": 2048,
    "custom": 2048,
}
# Сек на один запрос: Ollama иногда виснет наглухо, и длинный таймаут съедал бы
# часы впустую. Для заведомо медленных моделей поднимается через переменную
# окружения BENCH_HTTP_TIMEOUT, чтобы не путать «модель думает» с «сервер умер».
HTTP_TIMEOUT = int(os.environ.get("BENCH_HTTP_TIMEOUT", "600"))
MAX_CONSEC_ERRORS = int(os.environ.get("BENCH_MAX_ERRORS", "3"))
EXEC_TIMEOUT = 30           # сек на исполнение сгенерированного кода

# Паттерны, при которых сгенерированный код НЕ исполняется (считается провалом).
DANGEROUS = [
    r"\bshutil\b", r"\bsubprocess\b", r"\bos\.system\b", r"\bos\.remove\b",
    r"\bos\.rmdir\b", r"\bos\.unlink\b", r"\bos\.popen\b", r"\bsocket\b",
    r"\burllib\b", r"\brequests\b", r"\bhttpx\b", r"\bctypes\b", r"\bwinreg\b",
    r"\bopen\s*\([^)]*['\"][wax]", r"\b__import__\s*\(\s*['\"]os",
    r"\bchild_process\b", r"\brequire\s*\(\s*['\"]fs['\"]",
    r"\bfetch\s*\(", r"\bprocess\.exit\s*\(\s*0\s*\)\s*;?\s*$",
]
DANGEROUS_RE = re.compile("|".join(DANGEROUS), re.MULTILINE)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def api_post(path, payload, timeout=HTTP_TIMEOUT):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_get(path, timeout=30):
    with urllib.request.urlopen(API + path, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def chat(model, system, prompt, num_predict, num_ctx=None, keep_alive="10m"):
    opts = dict(GEN_OPTIONS)
    opts["num_predict"] = num_predict
    if num_ctx:
        opts["num_ctx"] = num_ctx
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": opts,
        "keep_alive": keep_alive,
    }
    # BENCH_THINK=0 гасит режим рассуждений у моделей, которые его поддерживают,
    # чтобы сравнить цену «думания» в качестве и в секундах ожидания.
    if os.environ.get("BENCH_THINK") == "0":
        payload["think"] = False
    t0 = time.time()
    try:
        r = api_post("/api/chat", payload)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        return {"error": f"HTTP {e.code}: {body}", "wall": time.time() - t0}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}", "wall": time.time() - t0}

    wall = time.time() - t0
    msg = r.get("message", {}) or {}
    content = msg.get("content", "") or ""
    thinking = msg.get("thinking", "") or ""
    eval_count = r.get("eval_count", 0) or 0
    eval_dur = r.get("eval_duration", 0) or 0
    return {
        "content": content,
        "thinking": thinking,
        "wall": wall,
        "eval_count": eval_count,
        "prompt_eval_count": r.get("prompt_eval_count", 0) or 0,
        "eval_duration_s": eval_dur / 1e9 if eval_dur else 0.0,
        "prompt_eval_duration_s": (r.get("prompt_eval_duration", 0) or 0) / 1e9,
        "load_duration_s": (r.get("load_duration", 0) or 0) / 1e9,
        "tok_s": (eval_count / (eval_dur / 1e9)) if eval_dur else 0.0,
        "done_reason": r.get("done_reason", ""),
    }


def unload(model):
    try:
        api_post("/api/chat", {"model": model, "messages": [], "keep_alive": 0},
                 timeout=120)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Разбор ответа
# ---------------------------------------------------------------------------

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
THINK_OPEN_RE = re.compile(r"<think>.*\Z", re.DOTALL | re.IGNORECASE)
FENCE_RE = re.compile(r"```[ \t]*([a-zA-Z0-9_+-]*)[ \t]*\r?\n(.*?)```", re.DOTALL)


def strip_think(text):
    text = THINK_RE.sub("", text)
    text = THINK_OPEN_RE.sub("", text)  # незакрытый блок (обрыв по лимиту токенов)
    return text.strip()


def _unwrap_quotes(code):
    """Некоторые модели оборачивают код не в ```, а в \"\"\" или '''.
    Тогда файл превращается в строковый литерал и ничего не определяет."""
    c = code.strip()
    for q in ('"""', "'''"):
        if c.startswith(q) and c.endswith(q) and len(c) > 2 * len(q):
            c = c[len(q):-len(q)].strip()
            break
    return c


OPEN_FENCE_RE = re.compile(r"```[ \t]*[a-zA-Z0-9_+-]*[ \t]*\r?\n", re.MULTILINE)


def extract_code(text, lang):
    """Достаёт код из markdown-блоков; если блоков нет — берёт текст целиком."""
    body = strip_think(text)
    blocks = FENCE_RE.findall(body)
    if not blocks:
        # Ответ мог оборваться по лимиту токенов до закрывающих ```.
        # Тогда парных блоков нет, но код после последней открывающей ``` есть.
        opens = list(OPEN_FENCE_RE.finditer(body))
        if opens:
            return _unwrap_quotes(body[opens[-1].end():])
        return _unwrap_quotes(body)
    want = {"py": ("python", "py", "python3"), "js": ("javascript", "js", "node")}[lang]
    typed = [b for tag, b in blocks if tag.lower() in want]
    untagged = [b for tag, b in blocks if not tag]
    pool = typed or untagged or [max((b for _, b in blocks), key=len)]
    return _unwrap_quotes(_join_definition_blocks(pool, lang))


DEF_MARKERS = {
    "py": ("def ", "class "),
    "js": ("function ", "class ", "const ", "let ", "var "),
}


def _join_definition_blocks(blocks, lang):
    """Решение может быть разнесено по нескольким блокам (например, две функции).
    Склеиваем только блоки с определениями, отбрасывая примеры использования:
    чужой assert из демонстрации уронил бы корректное решение."""
    if len(blocks) == 1:
        return blocks[0].strip()
    markers = DEF_MARKERS[lang]
    defs = [
        b for b in blocks
        if any(m in b for m in markers)
        and "assert " not in b
        and "__main__" not in b
    ]
    if not defs:
        return max(blocks, key=len).strip()
    return "\n\n".join(b.strip() for b in defs)


ANSWER_RE = re.compile(r"ОТВЕТ\s*[:：]\s*(.+)", re.IGNORECASE)


def extract_answer(text):
    body = strip_think(text)
    matches = ANSWER_RE.findall(body)
    if matches:
        return matches[-1].strip()
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def norm_answer(s):
    s = s.strip().strip("*_`\"'.,!?;:()[]{} \t")
    s = s.replace("ё", "е").replace("Ё", "Е")
    return s.lower().strip()


WORDCHAR = "0-9a-zA-Zа-яА-Я"


def match_exact(got, answers):
    """Сначала точное совпадение, затем поиск ответа как отдельного токена
    внутри короткой финальной строки (модель могла обрамить его словами)."""
    gotn = norm_answer(got)
    expected = [norm_answer(a) for a in answers]
    if any(gotn == e for e in expected):
        return True
    if len(gotn) > 120:
        return False
    for e in expected:
        if not e:
            continue
        pat = rf"(?<![{WORDCHAR}]){re.escape(e)}(?![{WORDCHAR}])"
        if re.search(pat, gotn):
            return True
    return False


# ---------------------------------------------------------------------------
# Исполнение кода
# ---------------------------------------------------------------------------

def run_snippet(code, test_code, lang):
    """Возвращает (passed: bool, detail: str)."""
    if not code.strip():
        return False, "пустой ответ"
    if DANGEROUS_RE.search(code):
        m = DANGEROUS_RE.search(code)
        return False, f"код заблокирован фильтром безопасности: {m.group(0)!r}"

    suffix = ".py" if lang == "py" else ".js"
    header = "# -*- coding: utf-8 -*-\nimport sys\nsys.setrecursionlimit(30000)\n" \
        if lang == "py" else ""
    # Маркер комментария обязан соответствовать языку: '#' внутри .js — SyntaxError.
    sep = "\n\n# ---- tests ----\n" if lang == "py" else "\n\n// ---- tests ----\n"
    full = header + code + sep + test_code + \
        ("\nprint('OK')\n" if lang == "py" else "\n")

    tmpdir = tempfile.mkdtemp(prefix="llmbench_")
    path = os.path.join(tmpdir, "solution" + suffix)
    with open(path, "w", encoding="utf-8") as f:
        f.write(full)

    cmd = [sys.executable, path] if lang == "py" else ["node", path]
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=EXEC_TIMEOUT,
                           cwd=tmpdir, env=env)
    except subprocess.TimeoutExpired:
        return False, f"таймаут исполнения >{EXEC_TIMEOUT}с"
    except Exception as e:  # noqa: BLE001
        return False, f"не удалось запустить: {e}"

    if p.returncode == 0:
        return True, "ok"
    err = (p.stderr or b"").decode("utf-8", "replace").strip()
    out = (p.stdout or b"").decode("utf-8", "replace").strip()
    tail = (err or out).splitlines()
    detail = " | ".join(tail[-3:])[:400] if tail else f"exit={p.returncode}"
    return False, detail


# ---------------------------------------------------------------------------
# Кастомные проверки
# ---------------------------------------------------------------------------

def check_exact_five_words(text):
    body = strip_think(text).strip()
    body = body.strip("`").strip()
    lines = [l for l in body.splitlines() if l.strip()]
    if not lines:
        return False, "пусто"
    line = lines[-1].strip() if len(lines) == 1 else lines[0].strip()
    if len(lines) > 1:
        return False, f"несколько строк ({len(lines)})"
    if re.search(r"[.,!?;:\"'()\[\]{}\-—]", line):
        return False, f"есть пунктуация: {line[:60]!r}"
    words = line.split()
    if len(words) != 5:
        return False, f"{len(words)} слов вместо 5: {line[:60]!r}"
    return True, "ok"


def check_single_upper_word(text):
    body = strip_think(text).strip().strip("`").strip()
    if "\n" in body.strip():
        return False, "больше одной строки"
    if not body:
        return False, "пусто"
    if body != body.upper():
        return False, f"не в верхнем регистре: {body[:40]!r}"
    if not re.fullmatch(r"[A-ZА-Я0-9]+", body):
        return False, f"лишние символы: {body[:40]!r}"
    if body not in ("HTTP", "HTTPS"):
        return False, f"неверный ответ: {body[:40]!r}"
    return True, "ok"


def check_no_letter_a(text):
    body = strip_think(text).strip().strip("`").strip()
    lines = [l for l in body.splitlines() if l.strip()]
    if not lines:
        return False, "пусто"
    if len(lines) > 1:
        return False, f"несколько строк ({len(lines)})"
    line = lines[0]
    if "а" in line.lower():
        return False, f"содержит букву 'а': {line[:70]!r}"
    words = [w for w in re.findall(r"[А-Яа-яЁё]+", line)]
    if len(words) < 5:
        return False, f"меньше 5 слов: {line[:70]!r}"
    if not re.search(r"[А-Яа-яЁё]", line):
        return False, "нет русского текста"
    return True, "ok"


CHECKERS = {
    "exact_five_words": check_exact_five_words,
    "single_upper_word": check_single_upper_word,
    "no_letter_a": check_no_letter_a,
}


def check_json_out(text, expected):
    body = strip_think(text).strip()
    blocks = FENCE_RE.findall(body)
    if blocks:
        body = max((b for _, b in blocks), key=len).strip()
    start = body.find("{")
    end = body.rfind("}")
    if start == -1 or end == -1:
        return False, "JSON не найден"
    try:
        got = json.loads(body[start:end + 1])
    except Exception as e:  # noqa: BLE001
        return False, f"невалидный JSON: {e}"
    if got != expected:
        return False, f"структура не совпала: {json.dumps(got, ensure_ascii=False)[:200]}"
    return True, "ok"


# ---------------------------------------------------------------------------
# Прогон одной модели
# ---------------------------------------------------------------------------

def safe_name(model):
    return re.sub(r"[^A-Za-z0-9._-]", "_", model)


def run_model(model, tasks, verbose=True):
    rawdir = os.path.join(RAW, safe_name(model))
    os.makedirs(rawdir, exist_ok=True)

    if verbose:
        print(f"\n=== {model} ===", flush=True)

    # Прогрев: загрузка модели в память замеряется отдельно.
    warm = chat(model, "Ты помощник.", "Скажи 'готов'.", 16)
    load_s = warm.get("load_duration_s", 0.0)
    if warm.get("error"):
        print(f"  !! модель не отвечает: {warm['error']}", flush=True)
        return {"model": model, "error": warm["error"], "tasks": []}

    records = []
    consec_errors = 0
    t_model0 = time.time()
    for t in tasks:
        kind = t["kind"]
        npred = NUM_PREDICT[kind]
        nctx = None
        if t["id"] == "lc_needle":
            # Документ ~4800 токенов: нужен запас, иначе промпт усекается
            # и иголку из него вырезает вместе с началом текста.
            npred, nctx = 2048, 12288
        r = chat(model, t["system"], t["prompt"], npred, num_ctx=nctx)

        rec = {
            "id": t["id"],
            "category": CATEGORY_OF[t["id"]],
            "weight": t.get("weight", 1.0),
            "kind": kind,
            "passed": False,
            "detail": "",
            "wall_s": round(r.get("wall", 0.0), 2),
            "tok_s": round(r.get("tok_s", 0.0), 2),
            "out_tokens": r.get("eval_count", 0),
            "in_tokens": r.get("prompt_eval_count", 0),
            "truncated": r.get("done_reason") == "length",
        }

        if r.get("error"):
            rec["detail"] = r["error"]
            records.append(rec)
            consec_errors += 1
            if verbose:
                print(f"  [ERR ] {t['id']}: {r['error'][:90]}", flush=True)
            if consec_errors >= MAX_CONSEC_ERRORS:
                print(f"  !! {consec_errors} сбоя подряд — прекращаю прогон "
                      f"{model}, остальные задачи не засчитаны", flush=True)
                for rest in tasks[tasks.index(t) + 1:]:
                    records.append({
                        "id": rest["id"], "category": CATEGORY_OF[rest["id"]],
                        "weight": rest.get("weight", 1.0), "kind": rest["kind"],
                        "passed": False, "detail": "пропущено после сбоев",
                        "wall_s": 0.0, "tok_s": 0.0, "out_tokens": 0,
                        "in_tokens": 0, "truncated": False,
                    })
                break
            continue

        consec_errors = 0
        content = r["content"]
        with open(os.path.join(rawdir, t["id"] + ".txt"), "w", encoding="utf-8") as f:
            if r.get("thinking"):
                f.write("<<<THINKING>>>\n" + r["thinking"] + "\n<<<END THINKING>>>\n\n")
            f.write(content)

        if kind == "code_py":
            code = extract_code(content, "py")
            ok, detail = run_snippet(code, t["test"], "py")
        elif kind == "code_js":
            code = extract_code(content, "js")
            ok, detail = run_snippet(code, t["test"], "js")
        elif kind == "exact":
            got = extract_answer(content)
            ok = match_exact(got, t["answers"])
            detail = "ok" if ok else f"получено {got[:80]!r}, ждали {t['answers'][0]!r}"
        elif kind == "json_out":
            ok, detail = check_json_out(content, t["check_json"])
        elif kind == "custom":
            ok, detail = CHECKERS[t["checker"]](content)
        else:
            ok, detail = False, "неизвестный тип задачи"

        rec["passed"] = bool(ok)
        rec["detail"] = detail
        records.append(rec)
        if verbose:
            mark = "PASS" if ok else "FAIL"
            trunc = " [обрыв]" if rec["truncated"] else ""
            print(f"  [{mark}] {t['id']:<20} {rec['wall_s']:>6.1f}с "
                  f"{rec['tok_s']:>5.1f} tok/s{trunc}"
                  f"{'' if ok else '  <- ' + str(detail)[:110]}", flush=True)

    total_wall = time.time() - t_model0
    unload(model)

    res = summarize(model, records, load_s, total_wall)
    with open(os.path.join(RESULTS, safe_name(model) + ".json"), "w",
              encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    if verbose:
        print(f"  ИТОГ {model}: {res['total_score']:.1f}/100  "
              f"код {res['by_category']['code']['pct']:.0f}%  "
              f"медиана {res['median_tok_s']:.1f} tok/s  "
              f"время {total_wall/60:.1f} мин", flush=True)
    return res


def summarize(model, records, load_s, total_wall):
    by_cat = {}
    for cat in CATEGORY_WEIGHTS:
        rs = [r for r in records if r["category"] == cat]
        wsum = sum(r["weight"] for r in rs) or 1.0
        wok = sum(r["weight"] for r in rs if r["passed"])
        by_cat[cat] = {
            "passed": sum(1 for r in rs if r["passed"]),
            "total": len(rs),
            "pct": 100.0 * wok / wsum,
        }
    total = sum(CATEGORY_WEIGHTS[c] * by_cat[c]["pct"] for c in CATEGORY_WEIGHTS)

    speeds = sorted(r["tok_s"] for r in records if r["tok_s"] > 0)
    median = speeds[len(speeds) // 2] if speeds else 0.0
    return {
        "model": model,
        "total_score": total,
        "by_category": by_cat,
        "passed": sum(1 for r in records if r["passed"]),
        "total_tasks": len(records),
        "median_tok_s": median,
        "mean_tok_s": (sum(speeds) / len(speeds)) if speeds else 0.0,
        "load_s": round(load_s, 2),
        "total_wall_min": round(total_wall / 60, 2),
        "truncated_count": sum(1 for r in records if r["truncated"]),
        "tasks": records,
    }


# ---------------------------------------------------------------------------

def list_local_models():
    try:
        data = api_get("/api/tags")
    except Exception as e:  # noqa: BLE001
        print(f"не удалось получить список моделей: {e}")
        return []
    out = []
    for m in data.get("models", []):
        out.append((m["name"], m.get("size", 0)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--only", nargs="*", default=[], help="ID задач для прогона")
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    os.makedirs(RAW, exist_ok=True)

    models = list(args.models)
    if args.all:
        models = [n for n, _ in list_local_models()]
    if not models:
        print("нечего запускать: укажи --models или --all")
        return 1

    tasks = ALL_TASKS
    if args.only:
        tasks = [t for t in ALL_TASKS if t["id"] in set(args.only)]

    print(f"моделей: {len(models)}, задач: {len(tasks)}")
    for m in models:
        done = os.path.join(RESULTS, safe_name(m) + ".json")
        if args.resume and os.path.exists(done):
            print(f"пропуск (уже есть): {m}")
            continue
        try:
            run_model(m, tasks)
        except KeyboardInterrupt:
            print("прервано пользователем")
            return 130
        except Exception as e:  # noqa: BLE001
            print(f"!! сбой на модели {m}: {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
