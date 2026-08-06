# -*- coding: utf-8 -*-
"""Проверка самого бенчмарка: эталонные решения обязаны проходить все тесты,
а заведомо неверные — падать. Если это не так, задача сформулирована криво.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import run_snippet, match_exact, check_json_out, CHECKERS  # noqa: E402
from tasks import ALL_TASKS  # noqa: E402

REF = {}

REF["py_two_sum"] = '''
def two_sum(nums, target):
    seen = {}
    for j, v in enumerate(nums):
        need = target - v
        if need in seen:
            return (seen[need], j)
        if v not in seen:
            seen[v] = j
    return None
'''

REF["py_merge_intervals"] = '''
def merge_intervals(intervals):
    out = []
    for a, b in sorted((list(x) for x in intervals), key=lambda x: (x[0], x[1])):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out
'''

REF["py_roman"] = '''
_VALS = [(1000,"M"),(900,"CM"),(500,"D"),(400,"CD"),(100,"C"),(90,"XC"),
         (50,"L"),(40,"XL"),(10,"X"),(9,"IX"),(5,"V"),(4,"IV"),(1,"I")]

def int_to_roman(n):
    out = []
    for v, s in _VALS:
        while n >= v:
            out.append(s); n -= v
    return "".join(out)

def roman_to_int(s):
    m = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}
    total = 0
    for i, ch in enumerate(s):
        if i + 1 < len(s) and m[ch] < m[s[i+1]]:
            total -= m[ch]
        else:
            total += m[ch]
    return total
'''

REF["py_wildcard"] = '''
def is_match(s, p):
    n, m = len(s), len(p)
    dp = [False] * (m + 1)
    dp[0] = True
    for j in range(1, m + 1):
        dp[j] = dp[j-1] and p[j-1] == "*"
    for i in range(1, n + 1):
        prev = dp[0]
        dp[0] = False
        for j in range(1, m + 1):
            cur = dp[j]
            if p[j-1] == "*":
                dp[j] = dp[j] or dp[j-1]
            elif p[j-1] == "?" or p[j-1] == s[i-1]:
                dp[j] = prev
            else:
                dp[j] = False
            prev = cur
    return dp[m]
'''

REF["py_topo_sort"] = '''
from collections import deque

def topo_sort(n, edges):
    adj = [[] for _ in range(n)]
    deg = [0] * n
    for a, b in edges:
        adj[a].append(b); deg[b] += 1
    q = deque(i for i in range(n) if deg[i] == 0)
    out = []
    while q:
        v = q.popleft(); out.append(v)
        for w in adj[v]:
            deg[w] -= 1
            if deg[w] == 0:
                q.append(w)
    return out if len(out) == n else None
'''

REF["py_lru"] = '''
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity):
        self.cap = capacity
        self.d = OrderedDict()
    def get(self, key):
        if key not in self.d:
            return -1
        self.d.move_to_end(key)
        return self.d[key]
    def put(self, key, value):
        if key in self.d:
            self.d.move_to_end(key)
        self.d[key] = value
        if len(self.d) > self.cap:
            self.d.popitem(last=False)
'''

REF["py_parse_config"] = '''
def _coerce(v):
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        return v[1:-1]
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v

def parse_config(text):
    res = {}
    cur = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1].strip()
            res.setdefault(cur, {})
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        sec = cur if cur is not None else ""
        res.setdefault(sec, {})[k.strip()] = _coerce(v.strip())
    return res
'''

REF["py_spiral"] = '''
def spiral_order(matrix):
    if not matrix or not matrix[0]:
        return []
    top, bot = 0, len(matrix) - 1
    left, right = 0, len(matrix[0]) - 1
    out = []
    while top <= bot and left <= right:
        for c in range(left, right + 1):
            out.append(matrix[top][c])
        top += 1
        for r in range(top, bot + 1):
            out.append(matrix[r][right])
        right -= 1
        if top <= bot:
            for c in range(right, left - 1, -1):
                out.append(matrix[bot][c])
            bot -= 1
        if left <= right:
            for r in range(bot, top - 1, -1):
                out.append(matrix[r][left])
            left += 1
    return out
'''

REF["py_fix_bug"] = '''
def search_range(nums, target):
    lo, hi = 0, len(nums)
    while lo < hi:
        mid = (lo + hi) // 2
        if nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    first = lo
    lo, hi = 0, len(nums)
    while lo < hi:
        mid = (lo + hi) // 2
        if nums[mid] <= target:
            lo = mid + 1
        else:
            hi = mid
    last = lo - 1
    if first > last:
        return (-1, -1)
    return (first, last)
'''

REF["py_csv_group"] = '''
def top_by_group(csv_text, group_col, value_col, k):
    lines = [l for l in csv_text.splitlines() if l.strip()]
    if not lines:
        return []
    header = lines[0].split(",")
    gi = header.index(group_col)
    vi = header.index(value_col)
    sums = {}
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) <= max(gi, vi):
            continue
        try:
            val = float(parts[vi])
        except ValueError:
            continue
        sums[parts[gi]] = sums.get(parts[gi], 0.0) + val
    ordered = sorted(sums.items(), key=lambda kv: (-kv[1], kv[0]))
    return ordered[:k]
'''

REF["ru_code_comment"] = '''
import re

def нормализовать_телефон(s):
    """Приводит российский номер телефона к виду +7XXXXXXXXXX.

    Возвращает None, если строка не похожа на корректный номер.
    """
    d = re.sub(r"\\D", "", s or "")
    if len(d) == 11 and d[0] in "78":
        return "+7" + d[1:]
    if len(d) == 10:
        return "+7" + d
    return None
'''

REF["js_deep_equal"] = '''
function deepEqual(a, b) {
  if (Object.is(a, b)) return true;
  if (typeof a !== "object" || typeof b !== "object") return false;
  if (a === null || b === null) return false;
  const aDate = a instanceof Date, bDate = b instanceof Date;
  if (aDate || bDate) return aDate && bDate && a.getTime() === b.getTime();
  const aArr = Array.isArray(a), bArr = Array.isArray(b);
  if (aArr !== bArr) return false;
  if (aArr) {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) if (!deepEqual(a[i], b[i])) return false;
    return true;
  }
  const ka = Object.keys(a), kb = Object.keys(b);
  if (ka.length !== kb.length) return false;
  for (const k of ka) {
    if (!Object.prototype.hasOwnProperty.call(b, k)) return false;
    if (!deepEqual(a[k], b[k])) return false;
  }
  return true;
}
'''

REF["js_query_string"] = '''
function parseQuery(qs) {
  const out = {};
  if (!qs) return out;
  if (qs[0] === "?") qs = qs.slice(1);
  if (!qs) return out;
  for (const seg of qs.split("&")) {
    if (!seg) continue;
    const i = seg.indexOf("=");
    const rawK = i === -1 ? seg : seg.slice(0, i);
    const rawV = i === -1 ? "" : seg.slice(i + 1);
    const dec = (x) => decodeURIComponent(x.replace(/\\+/g, " "));
    const k = dec(rawK), v = dec(rawV);
    if (!(k in out)) out[k] = v;
    else if (Array.isArray(out[k])) out[k].push(v);
    else out[k] = [out[k], v];
  }
  return out;
}
'''

# Заведомо неверные решения — они ОБЯЗАНЫ падать, иначе тест ничего не проверяет.
BAD = {
    "py_two_sum": "def two_sum(nums, target):\n    return (0, 1)\n",
    "py_wildcard": "def is_match(s, p):\n    return s == p\n",
    "py_fix_bug": "def search_range(nums, target):\n    return (0, 0)\n",
    "py_parse_config": "def parse_config(text):\n    return {}\n",
    "py_csv_group": "def top_by_group(a, b, c, k):\n    return []\n",
    "js_deep_equal": "function deepEqual(a, b) { return true; }\n",
    "js_query_string": "function parseQuery(q) { return {}; }\n",
}


def main():
    tasks = {t["id"]: t for t in ALL_TASKS}
    fails = 0

    print("--- эталонные решения (должны проходить) ---")
    for tid, code in REF.items():
        t = tasks[tid]
        lang = "py" if t["kind"] == "code_py" else "js"
        ok, detail = run_snippet(code, t["test"], lang)
        print(f"  {'OK  ' if ok else 'СБОЙ'} {tid}" + ("" if ok else f"  <- {detail}"))
        if not ok:
            fails += 1

    print("--- заведомо неверные (должны падать) ---")
    for tid, code in BAD.items():
        t = tasks[tid]
        lang = "py" if t["kind"] == "code_py" else "js"
        ok, detail = run_snippet(code, t["test"], lang)
        print(f"  {'СБОЙ' if ok else 'OK  '} {tid}" +
              ("  <- тест пропустил мусор!" if ok else ""))
        if ok:
            fails += 1

    print("--- проверки не-кодовых задач ---")
    # match_exact: правильный ответ проходит, близкий неверный — нет
    cases = [
        (["3"], "ОТВЕТ: 3", True), (["3"], "13", False), (["3"], "ОТВЕТ: 3.", True),
        (["9.9"], "9.9", True), (["9.9"], "9.11", False),
        (["четверг"], "Четверг", True), (["четверг"], "среда", False),
        (["qx-4417-zulu"], "код — QX-4417-ZULU", True),
        (["qx-4417-zulu"], "QAZ", False),
        (["канберра"], "Канберра", True), (["канберра"], "Сидней", False),
        (["having"], "HAVING", True),
        (["o(nlogn)"], "O(n log n)", False),  # проверяем, что вариант учтён в answers
    ]
    for answers, got, want in cases:
        got_ok = match_exact(got, answers)
        mark = "OK  " if got_ok == want else "СБОЙ"
        if got_ok != want:
            fails += 1
        print(f"  {mark} match_exact({got!r}, {answers}) = {got_ok}, ждали {want}")

    t = tasks["i_json"]
    ok, _ = check_json_out('```json\n{"name":"тест","count":7,"tags":["a","b","c"],'
                           '"nested":{"ok":true}}\n```', t["check_json"])
    print(f"  {'OK  ' if ok else 'СБОЙ'} i_json эталон")
    fails += 0 if ok else 1

    checks = [
        ("exact_five_words", "язык программирования для быстрой разработки", True),
        ("exact_five_words", "Python это язык.", False),
        ("single_upper_word", "HTTP", True),
        ("single_upper_word", "http", False),
        ("no_letter_a", "Море сегодня будет очень тихим", True),
        ("no_letter_a", "Море красивое и большое сегодня", False),
    ]
    for name, text, want in checks:
        got_ok, det = CHECKERS[name](text)
        mark = "OK  " if got_ok == want else "СБОЙ"
        if got_ok != want:
            fails += 1
        print(f"  {mark} {name}({text[:35]!r}) = {got_ok} ({det})")

    print(f"\nпроблем: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
