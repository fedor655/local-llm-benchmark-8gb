# -*- coding: utf-8 -*-
"""
Тот же бенчмарк, но по бесплатным облачным моделям (OpenAI-совместимый API).

Логика задач, исполнение кода и подсчёт баллов берутся из bench.py без
изменений — заменяется только транспорт. Это гарантирует, что облачные
результаты сравнимы с локальными: те же 32 задачи, те же проверки.

Запуск:
    python bench/cloud.py --models groq/openai/gpt-oss-120b cerebras/gpt-oss-120b
    python bench/cloud.py --list

Ключи берутся из переменных окружения GROQ_API_KEY, CEREBRAS_API_KEY,
OPENROUTER_API_KEY либо из файла, указанного в BENCH_ENV_FILE.

Отличие от локального прогона, важное при чтении цифр: tok/s здесь —
сквозная пропускная способность, включая сеть и очередь провайдера,
а не чистая скорость генерации, которую отдаёт Ollama. Значения занижены
относительно локальных и сравнивать их напрямую нельзя. Сравнимы:
баллы, доля решённых задач и время ожидания ответа.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench  # noqa: E402
from tasks import ALL_TASKS  # noqa: E402

# provider -> (base_url, env-переменная с ключом)
PROVIDERS = {
    "groq":       ("https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY"),
    "cerebras":   ("https://api.cerebras.ai/v1/chat/completions",     "CEREBRAS_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions",   "OPENROUTER_API_KEY"),
}

HTTP_TIMEOUT = int(os.environ.get("BENCH_HTTP_TIMEOUT", "600"))
# Пауза между запросами: бесплатные тиры считают запросы в минуту,
# без неё прогон упирается в 429 на середине и портит результат.
THROTTLE_S = float(os.environ.get("BENCH_THROTTLE_S", "2"))


def load_env_file():
    """Подхватывает ключи из .env-файла, если он указан."""
    path = os.environ.get("BENCH_ENV_FILE")
    if not path or not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def split_spec(spec):
    """'groq/openai/gpt-oss-120b' -> ('groq', 'openai/gpt-oss-120b')"""
    provider, _, model = spec.partition("/")
    if provider not in PROVIDERS:
        raise ValueError(
            f"неизвестный провайдер {provider!r}; известные: "
            + ", ".join(sorted(PROVIDERS))
        )
    if not model:
        raise ValueError(f"в {spec!r} не указана модель после провайдера")
    return provider, model


RETRY_AFTER_RE = re.compile(r"try again in ([\d.]+)(ms|s)", re.IGNORECASE)
MAX_429_RETRIES = int(os.environ.get("BENCH_MAX_429_RETRIES", "6"))


def _retry_delay(headers, body, attempt):
    """Сколько ждать после 429. Провайдеры сообщают это по-разному:
    Groq кладёт срок в текст сообщения, остальные — в заголовок Retry-After.
    Если не сказано ничего, растём экспоненциально."""
    if headers is not None:
        for h in ("retry-after", "x-ratelimit-reset-requests"):
            v = headers.get(h)
            if v:
                try:
                    return min(float(str(v).rstrip("s")), 120.0)
                except ValueError:
                    pass
    m = RETRY_AFTER_RE.search(body or "")
    if m:
        val = float(m.group(1))
        return min(val / 1000.0 if m.group(2).lower() == "ms" else val, 120.0)
    return min(5.0 * (2 ** attempt), 120.0)


def cloud_chat(model_spec, system, prompt, num_predict, num_ctx=None,
               keep_alive=None):
    """Замена bench.chat с тем же контрактом возврата.

    Бесплатные тиры отдают 429 постоянно, поэтому ожидание лимита встроено
    сюда: без него прогон обрывается на середине и результат нельзя сравнивать
    с локальным, где такого ограничения нет. Время ожидания лимита НЕ попадает
    в wall — иначе цифры измеряли бы щедрость тарифа, а не скорость модели.
    """
    provider, model = split_spec(model_spec)
    url, keyvar = PROVIDERS[provider]
    key = os.environ.get(keyvar, "")
    if not key:
        return {"error": f"нет ключа: переменная {keyvar} не задана", "wall": 0.0}

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": num_predict,
        "temperature": bench.GEN_OPTIONS["temperature"],
        "top_p": bench.GEN_OPTIONS["top_p"],
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")

    waited_total = 0.0
    for attempt in range(MAX_429_RETRIES + 1):
        req = urllib.request.Request(url, data=data, headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            # Без явного User-Agent часть провайдеров отдаёт 403 от Cloudflare.
            "User-Agent": "local-llm-benchmark/1.0",
        })
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                r = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            # 413 у Groq — это тоже лимит (TPM), а не «слишком большой запрос».
            is_limit = e.code == 429 or (
                e.code == 413 and "rate_limit" in body)
            if is_limit and attempt < MAX_429_RETRIES:
                delay = _retry_delay(getattr(e, "headers", None), body, attempt)
                print(f"      лимит {e.code}, жду {delay:.0f}с "
                      f"(попытка {attempt + 1}/{MAX_429_RETRIES})", flush=True)
                time.sleep(delay)
                waited_total += delay
                continue
            return {"error": f"HTTP {e.code}: {body[:400]}",
                    "wall": time.time() - t0}
        except Exception as e:  # noqa: BLE001
            return {"error": f"{type(e).__name__}: {e}", "wall": time.time() - t0}
    else:
        return {"error": f"лимит не отпустил за {MAX_429_RETRIES} попыток",
                "wall": 0.0}

    wall = time.time() - t0
    choices = r.get("choices") or []
    if not choices:
        return {"error": f"пустой ответ провайдера: {json.dumps(r)[:300]}",
                "wall": wall}
    msg = choices[0].get("message") or {}
    content = msg.get("content") or ""
    # Некоторые модели отдают рассуждения отдельным полем, а не в <think>.
    thinking = msg.get("reasoning") or msg.get("reasoning_content") or ""
    usage = r.get("usage") or {}
    out_tok = usage.get("completion_tokens", 0) or 0
    in_tok = usage.get("prompt_tokens", 0) or 0

    return {
        "content": content,
        "thinking": thinking,
        "wall": wall,
        "eval_count": out_tok,
        "prompt_eval_count": in_tok,
        # Чистой скорости генерации облако не сообщает: делим на полное время.
        "eval_duration_s": wall,
        "prompt_eval_duration_s": 0.0,
        "load_duration_s": 0.0,
        "tok_s": (out_tok / wall) if wall > 0 else 0.0,
        "done_reason": choices[0].get("finish_reason", ""),
        "rate_limit_wait_s": round(waited_total, 1),
    }


def throttled_chat(*a, **kw):
    r = cloud_chat(*a, **kw)
    if THROTTLE_S > 0:
        time.sleep(THROTTLE_S)
    return r


def main():
    load_env_file()
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=[],
                    help="спецификации вида provider/model-id")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--only", nargs="*", default=[], help="ID задач")
    ap.add_argument("--list", action="store_true",
                    help="показать провайдеров и наличие ключей")
    args = ap.parse_args()

    if args.list:
        print("провайдер     ключ    endpoint")
        for name, (url, keyvar) in sorted(PROVIDERS.items()):
            mark = "есть" if os.environ.get(keyvar) else "НЕТ "
            print(f"{name:<13} {mark}    {url}")
        return 0

    if not args.models:
        print("укажи --models, например: groq/openai/gpt-oss-120b")
        return 1

    os.makedirs(bench.RESULTS, exist_ok=True)
    os.makedirs(bench.RAW, exist_ok=True)

    # Подмена транспорта: всё остальное в bench.py работает как есть.
    bench.chat = throttled_chat
    bench.unload = lambda model: None

    tasks = ALL_TASKS
    if args.only:
        tasks = [t for t in ALL_TASKS if t["id"] in set(args.only)]

    print(f"моделей: {len(args.models)}, задач: {len(tasks)}, "
          f"пауза между запросами: {THROTTLE_S}с")
    for spec in args.models:
        done = os.path.join(bench.RESULTS, bench.safe_name(spec) + ".json")
        if args.resume and os.path.exists(done):
            print(f"пропуск (уже есть): {spec}")
            continue
        try:
            split_spec(spec)
        except ValueError as e:
            print(f"!! {e}")
            continue
        try:
            bench.run_model(spec, tasks)
        except KeyboardInterrupt:
            print("прервано пользователем")
            return 130
        except Exception as e:  # noqa: BLE001
            print(f"!! сбой на {spec}: {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
