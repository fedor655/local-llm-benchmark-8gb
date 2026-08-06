# -*- coding: utf-8 -*-
"""
Набор задач для бенчмарка локальных LLM.

Категории:
  code_py  - задача на Python, проверяется исполнением unit-тестов
  code_js  - задача на JavaScript (node), проверяется исполнением
  exact    - короткий ответ, проверяется по строке "ОТВЕТ: X"
  json_out - модель должна вернуть валидный JSON нужной формы
  custom   - проверка своей функцией
"""

CODE_SYS = (
    "Ты опытный программист. Отвечай кодом. "
    "Верни РОВНО ОДИН блок кода в тройных обратных кавычках и ничего больше. "
    "Не пиши тестов, не пиши примеров использования, не пиши объяснений."
)

EXACT_SYS = (
    "Отвечай кратко. В САМОЙ ПОСЛЕДНЕЙ строке ответа обязательно напиши результат "
    "в формате:\nОТВЕТ: <значение>\nБез пояснений после этой строки."
)

# ----------------------------------------------------------------------------
# КОД: PYTHON
# ----------------------------------------------------------------------------

CODING = [
    dict(
        id="py_two_sum",
        kind="code_py",
        weight=1.0,
        level="easy",
        system=CODE_SYS,
        prompt=(
            "Напиши функцию `two_sum(nums: list[int], target: int) -> tuple[int, int] | None`.\n"
            "Она возвращает кортеж индексов (i, j), i < j, таких что nums[i] + nums[j] == target.\n"
            "Если пары нет — вернуть None. Сложность O(n) по времени.\n"
            "Если подходящих пар несколько — вернуть ту, у которой меньше i, а при равных i — меньше j."
        ),
        test=r'''
assert two_sum([2,7,11,15], 9) == (0,1)
assert two_sum([3,2,4], 6) == (1,2)
assert two_sum([3,3], 6) == (0,1)
assert two_sum([1,2,3], 100) is None
assert two_sum([], 0) is None
assert two_sum([0,0,0], 0) == (0,1)
assert two_sum([-3,4,3,90], 0) == (0,2)
big = list(range(200000))
assert two_sum(big, 399997) == (199998, 199999)
''',
    ),
    dict(
        id="py_merge_intervals",
        kind="code_py",
        weight=1.0,
        level="easy",
        system=CODE_SYS,
        prompt=(
            "Напиши функцию `merge_intervals(intervals: list[list[int]]) -> list[list[int]]`.\n"
            "Она объединяет пересекающиеся и соприкасающиеся отрезки и возвращает их "
            "отсортированными по левой границе. Например [[1,3],[2,6],[8,10],[15,18]] -> "
            "[[1,6],[8,10],[15,18]]. Отрезки [1,4] и [4,5] считаются соприкасающимися и "
            "объединяются в [1,5]. Входной список менять нельзя."
        ),
        test=r'''
assert merge_intervals([[1,3],[2,6],[8,10],[15,18]]) == [[1,6],[8,10],[15,18]]
assert merge_intervals([[1,4],[4,5]]) == [[1,5]]
assert merge_intervals([]) == []
assert merge_intervals([[5,7]]) == [[5,7]]
assert merge_intervals([[1,10],[2,3],[4,5]]) == [[1,10]]
assert merge_intervals([[8,10],[1,3]]) == [[1,3],[8,10]]
src = [[3,4],[1,2]]
merge_intervals(src)
assert src == [[3,4],[1,2]], "входной список изменён"
assert merge_intervals([[1,4],[0,4]]) == [[0,4]]
assert merge_intervals([[1,4],[0,0]]) == [[0,0],[1,4]]
''',
    ),
    dict(
        id="py_roman",
        kind="code_py",
        weight=1.0,
        level="medium",
        system=CODE_SYS,
        prompt=(
            "Напиши две функции:\n"
            "`int_to_roman(n: int) -> str` — переводит целое число 1..3999 в римскую запись;\n"
            "`roman_to_int(s: str) -> int` — обратная операция.\n"
            "Обе должны корректно работать с вычитательной формой (IV, IX, XL, XC, CD, CM)."
        ),
        test=r'''
assert int_to_roman(1) == "I"
assert int_to_roman(4) == "IV"
assert int_to_roman(9) == "IX"
assert int_to_roman(14) == "XIV"
assert int_to_roman(40) == "XL"
assert int_to_roman(1994) == "MCMXCIV"
assert int_to_roman(3999) == "MMMCMXCIX"
assert roman_to_int("MCMXCIV") == 1994
assert roman_to_int("LVIII") == 58
for n in range(1, 4000):
    assert roman_to_int(int_to_roman(n)) == n, n
''',
    ),
    dict(
        id="py_wildcard",
        kind="code_py",
        weight=1.5,
        level="hard",
        system=CODE_SYS,
        prompt=(
            "Напиши функцию `is_match(s: str, p: str) -> bool` — сопоставление строки с "
            "шаблоном, где:\n"
            "  '?' совпадает ровно с одним любым символом,\n"
            "  '*' совпадает с любой последовательностью символов, в том числе пустой.\n"
            "Шаблон должен покрывать строку целиком. Решение должно работать за полиномиальное "
            "время (не экспоненциальный перебор) и не падать на строках длиной несколько тысяч "
            "символов."
        ),
        test=r'''
assert is_match("aa", "a") is False
assert is_match("aa", "*") is True
assert is_match("cb", "?a") is False
assert is_match("adceb", "*a*b") is True
assert is_match("acdcb", "a*c?b") is False
assert is_match("", "") is True
assert is_match("", "*") is True
assert is_match("", "?") is False
assert is_match("abc", "a?c") is True
assert is_match("abcdef", "a*f") is True
assert is_match("abcdef", "a*e") is False
assert is_match("mississippi", "m??*ss*?i*pi") is False
import time
s = "a" * 3000
p = "*a*" * 30 + "a"
t0 = time.time()
assert is_match(s, p) is True
assert time.time() - t0 < 8, "слишком медленно (экспоненциальный алгоритм)"
''',
    ),
    dict(
        id="py_topo_sort",
        kind="code_py",
        weight=1.0,
        level="medium",
        system=CODE_SYS,
        prompt=(
            "Напиши функцию `topo_sort(n: int, edges: list[tuple[int, int]]) -> list[int] | None`.\n"
            "Вершины пронумерованы 0..n-1, ребро (a, b) означает 'a должно идти до b'.\n"
            "Функция возвращает любой корректный порядок топологической сортировки, "
            "а если в графе есть цикл — None."
        ),
        test=r'''
def check(n, edges, res):
    assert res is not None
    assert sorted(res) == list(range(n)), res
    pos = {v: i for i, v in enumerate(res)}
    for a, b in edges:
        assert pos[a] < pos[b], (a, b, res)

e = [(0,1),(0,2),(1,3),(2,3)]
check(4, e, topo_sort(4, e))
e2 = []
check(3, e2, topo_sort(3, e2))
assert topo_sort(2, [(0,1),(1,0)]) is None
assert topo_sort(1, [(0,0)]) is None
e3 = [(5,2),(5,0),(4,0),(4,1),(2,3),(3,1)]
check(6, e3, topo_sort(6, e3))
n = 2000
e4 = [(i, i+1) for i in range(n-1)]
check(n, e4, topo_sort(n, e4))
''',
    ),
    dict(
        id="py_lru",
        kind="code_py",
        weight=1.0,
        level="medium",
        system=CODE_SYS,
        prompt=(
            "Напиши класс `LRUCache` с конструктором `__init__(self, capacity: int)` и методами:\n"
            "  `get(self, key) -> int` — вернуть значение или -1, если ключа нет;\n"
            "  `put(self, key, value) -> None` — записать значение, вытеснив наименее "
            "недавно использованный элемент при переполнении.\n"
            "Обе операции должны работать за O(1) в среднем. Обращение через get и перезапись "
            "через put считаются использованием элемента."
        ),
        test=r'''
c = LRUCache(2)
c.put(1, 1); c.put(2, 2)
assert c.get(1) == 1
c.put(3, 3)
assert c.get(2) == -1
c.put(4, 4)
assert c.get(1) == -1
assert c.get(3) == 3
assert c.get(4) == 4
c2 = LRUCache(1)
c2.put(1, 10); c2.put(2, 20)
assert c2.get(1) == -1 and c2.get(2) == 20
c3 = LRUCache(2)
c3.put(1, 1); c3.put(2, 2); c3.put(1, 100)
c3.put(3, 3)
assert c3.get(2) == -1
assert c3.get(1) == 100
import time
c4 = LRUCache(1000)
t0 = time.time()
for i in range(200000):
    c4.put(i, i)
    c4.get(i - 500)
assert time.time() - t0 < 8, "слишком медленно, вероятно не O(1)"
''',
    ),
    dict(
        id="py_parse_config",
        kind="code_py",
        weight=1.25,
        level="medium",
        system=CODE_SYS,
        prompt=(
            "Напиши функцию `parse_config(text: str) -> dict`, разбирающую INI-подобный конфиг.\n"
            "Правила:\n"
            "  - строки вида `[секция]` начинают новую секцию;\n"
            "  - строки вида `ключ = значение` добавляются в текущую секцию;\n"
            "  - пары до первой секции попадают в секцию с именем `''` (пустая строка);\n"
            "  - пустые строки и строки, начинающиеся с `#` или `;` (после обрезки пробелов), игнорируются;\n"
            "  - пробелы вокруг имени секции, ключа и значения обрезаются;\n"
            "  - значение разбирается по типам: `true`/`false` в любом регистре -> bool, "
            "целое число -> int, число с точкой -> float, иначе -> str;\n"
            "  - если значение обёрнуто в двойные кавычки, кавычки снимаются и значение "
            "всегда остаётся строкой без разбора типа;\n"
            "  - в значении может встречаться знак `=`, делить нужно только по первому;\n"
            "  - при повторе ключа побеждает последнее значение;\n"
            "  - секция попадает в результат, даже если она пустая, а секция `''` "
            "создаётся только если до первой секции реально были пары.\n"
            "Результат: словарь {имя_секции: {ключ: значение}}."
        ),
        test=r'''
t = """
name = app
debug = TRUE

[db]
host = localhost
port = 5432
ratio = 0.75
; comment
# another
url = postgres://a=b
label = "42"
label2 =    hello world
port = 5433
"""
r = parse_config(t)
assert r[""] == {"name": "app", "debug": True}, r.get("")
d = r["db"]
assert d["host"] == "localhost"
assert d["port"] == 5433
assert d["ratio"] == 0.75 and isinstance(d["ratio"], float)
assert d["url"] == "postgres://a=b"
assert d["label"] == "42" and isinstance(d["label"], str)
assert d["label2"] == "hello world"
assert parse_config("") == {}
r2 = parse_config("[empty]")
assert r2 == {"empty": {}}, r2
r3 = parse_config("x = false")
assert r3[""]["x"] is False
r4 = parse_config("n = -17")
assert r4[""]["n"] == -17
''',
    ),
    dict(
        id="py_spiral",
        kind="code_py",
        weight=1.0,
        level="medium",
        system=CODE_SYS,
        prompt=(
            "Напиши функцию `spiral_order(matrix: list[list[int]]) -> list[int]`, "
            "возвращающую элементы прямоугольной матрицы в порядке обхода по спирали "
            "по часовой стрелке, начиная с верхнего левого угла. "
            "Пустая матрица даёт пустой список."
        ),
        test=r'''
assert spiral_order([[1,2,3],[4,5,6],[7,8,9]]) == [1,2,3,6,9,8,7,4,5]
assert spiral_order([[1,2,3,4],[5,6,7,8],[9,10,11,12]]) == [1,2,3,4,8,12,11,10,9,5,6,7]
assert spiral_order([]) == []
assert spiral_order([[]]) == []
assert spiral_order([[7]]) == [7]
assert spiral_order([[1],[2],[3]]) == [1,2,3]
assert spiral_order([[1,2,3]]) == [1,2,3]
assert spiral_order([[1,2],[3,4]]) == [1,2,4,3]
''',
    ),
    dict(
        id="py_fix_bug",
        kind="code_py",
        weight=1.25,
        level="medium",
        system=CODE_SYS,
        prompt=(
            "В коде ниже есть баги. Верни исправленную версию функции целиком "
            "(имя и сигнатуру не менять).\n\n"
            "```python\n"
            "def search_range(nums, target):\n"
            "    # Возвращает (первый_индекс, последний_индекс) вхождения target\n"
            "    # в отсортированном по возрастанию списке nums, либо (-1, -1).\n"
            "    lo, hi = 0, len(nums)\n"
            "    while lo < hi:\n"
            "        mid = (lo + hi) / 2\n"
            "        if nums[mid] < target:\n"
            "            lo = mid\n"
            "        else:\n"
            "            hi = mid\n"
            "    first = lo\n"
            "    lo, hi = 0, len(nums)\n"
            "    while lo < hi:\n"
            "        mid = (lo + hi) // 2\n"
            "        if nums[mid] <= target:\n"
            "            lo = mid + 1\n"
            "        else:\n"
            "            hi = mid\n"
            "    last = lo\n"
            "    return (first, last)\n"
            "```"
        ),
        test=r'''
assert search_range([5,7,7,8,8,10], 8) == (3, 4)
assert search_range([5,7,7,8,8,10], 6) == (-1, -1)
assert search_range([], 0) == (-1, -1)
assert search_range([1], 1) == (0, 0)
assert search_range([2,2,2,2], 2) == (0, 3)
assert search_range([1,2,3], 3) == (2, 2)
assert search_range([1,2,3], 1) == (0, 0)
assert search_range([1,1,2], 2) == (2, 2)
assert search_range([1,3,5], 4) == (-1, -1)
import time
big = [0]*100000 + [1]*100000
t0 = time.time()
assert search_range(big, 1) == (100000, 199999)
assert time.time() - t0 < 5
''',
    ),
    dict(
        id="py_csv_group",
        kind="code_py",
        weight=1.25,
        level="hard",
        system=CODE_SYS,
        prompt=(
            "Напиши функцию `top_by_group(csv_text: str, group_col: str, value_col: str, k: int) "
            "-> list[tuple[str, float]]`.\n"
            "На вход — текст CSV с заголовком в первой строке (разделитель — запятая, "
            "кавычек и экранирования нет). Нужно:\n"
            "  - сгруппировать строки по колонке group_col;\n"
            "  - в каждой группе просуммировать числовые значения из колонки value_col;\n"
            "  - строки, где значение в value_col пустое или не парсится как число, пропустить, "
            "но саму группу не терять, если в ней есть хоть одна валидная строка;\n"
            "  - вернуть k групп с наибольшей суммой, отсортированных по убыванию суммы, "
            "а при равных суммах — по имени группы по алфавиту (по возрастанию);\n"
            "  - если групп меньше k, вернуть все.\n"
            "Пустые строки в конце файла игнорировать."
        ),
        test=r'''
csv1 = """dept,name,amount
eng,a,100
eng,b,50.5
sales,c,200
sales,d,
hr,e,x
eng,f,10

"""
r = top_by_group(csv1, "dept", "amount", 2)
assert len(r) == 2
assert r[0][0] == "sales" and abs(r[0][1] - 200) < 1e-9, r
assert r[1][0] == "eng" and abs(r[1][1] - 160.5) < 1e-9, r
r2 = top_by_group(csv1, "dept", "amount", 10)
assert [g for g, _ in r2] == ["sales", "eng"], r2
csv2 = """g,v
b,5
a,5
c,1
"""
r3 = top_by_group(csv2, "g", "v", 3)
assert [g for g, _ in r3] == ["a", "b", "c"], r3
assert top_by_group("g,v\n", "g", "v", 3) == []
csv3 = """g,v
a,-5
b,-1
"""
assert [g for g, _ in top_by_group(csv3, "g", "v", 1)] == ["b"]
''',
    ),
]

CODING_JS = [
    dict(
        id="js_deep_equal",
        kind="code_js",
        weight=1.0,
        level="medium",
        system=CODE_SYS,
        prompt=(
            "Напиши на JavaScript функцию `deepEqual(a, b)`, возвращающую true, если два "
            "значения структурно равны. Требования:\n"
            "  - примитивы сравниваются строго, но NaN равен NaN, а +0 не равен -0;\n"
            "  - массивы равны при равной длине и поэлементном равенстве;\n"
            "  - обычные объекты равны при одинаковом наборе собственных ключей и равных значениях;\n"
            "  - массив никогда не равен обычному объекту;\n"
            "  - null не равен пустому объекту;\n"
            "  - Date сравниваются по значению времени.\n"
            "Объяви функцию в глобальной области, экспорт не нужен."
        ),
        test=r'''
function ok(c, m) { if (!c) { console.error("FAIL: " + m); process.exit(1); } }
ok(deepEqual(1, 1), "1==1");
ok(!deepEqual(1, "1"), "1 vs '1'");
ok(deepEqual(NaN, NaN), "NaN");
ok(!deepEqual(0, -0), "+0 vs -0");
ok(deepEqual([1,2,[3]], [1,2,[3]]), "nested arr");
ok(!deepEqual([1,2], [1,2,3]), "len");
ok(deepEqual({a:1,b:{c:2}}, {b:{c:2},a:1}), "obj order");
ok(!deepEqual({a:1}, {a:1,b:2}), "extra key");
ok(!deepEqual([], {}), "arr vs obj");
ok(!deepEqual(null, {}), "null vs obj");
ok(deepEqual(null, null), "null null");
ok(deepEqual(new Date(1000), new Date(1000)), "date eq");
ok(!deepEqual(new Date(1000), new Date(2000)), "date neq");
ok(deepEqual({}, {}), "empty obj");
ok(!deepEqual(undefined, null), "undef vs null");
console.log("OK");
''',
    ),
    dict(
        id="js_query_string",
        kind="code_js",
        weight=1.0,
        level="medium",
        system=CODE_SYS,
        prompt=(
            "Напиши на JavaScript функцию `parseQuery(qs)`, разбирающую query-строку в объект.\n"
            "Требования:\n"
            "  - ведущий символ '?' если есть — отбрасывается;\n"
            "  - пары разделены '&', ключ и значение — первым '=';\n"
            "  - ключ и значение декодируются через decodeURIComponent, '+' означает пробел;\n"
            "  - ключ без '=' даёт значение пустой строки;\n"
            "  - если ключ встречается несколько раз, значение становится массивом "
            "в порядке появления;\n"
            "  - пустые сегменты между '&' игнорируются;\n"
            "  - пустая строка даёт пустой объект.\n"
            "Объяви функцию в глобальной области."
        ),
        test=r'''
function ok(c, m) { if (!c) { console.error("FAIL: " + m); process.exit(1); } }
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
ok(eq(parseQuery(""), {}), "empty");
ok(eq(parseQuery("?a=1&b=2"), {a:"1", b:"2"}), "basic: " + JSON.stringify(parseQuery("?a=1&b=2")));
ok(eq(parseQuery("a=1&a=2&a=3"), {a:["1","2","3"]}), "repeat");
ok(eq(parseQuery("a"), {a:""}), "no eq");
ok(eq(parseQuery("a=hello+world"), {a:"hello world"}), "plus");
ok(eq(parseQuery("a=%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82"), {a:"привет"}), "utf8");
ok(eq(parseQuery("a=1&&b=2"), {a:"1", b:"2"}), "empty seg");
ok(eq(parseQuery("a=x=y"), {a:"x=y"}), "eq in value");
ok(eq(parseQuery("a%20b=1"), {"a b":"1"}), "encoded key");
console.log("OK");
''',
    ),
]

# ----------------------------------------------------------------------------
# ЛОГИКА / МАТЕМАТИКА / ЗНАНИЯ
# ----------------------------------------------------------------------------

REASONING = [
    dict(id="r_letters", kind="exact", weight=1.0, system=EXACT_SYS,
         prompt="Сколько раз буква «р» встречается в слове «программирование»?",
         answers=["3"]),
    dict(id="r_floats", kind="exact", weight=1.0, system=EXACT_SYS,
         prompt="Какое число больше: 9.11 или 9.9? Напиши само число.",
         answers=["9.9", "9,9"]),
    dict(id="r_weekday", kind="exact", weight=1.0, system=EXACT_SYS,
         prompt="Сегодня вторник. Какой день недели будет ровно через 100 дней? "
                "Ответь одним словом.",
         answers=["четверг"]),
    dict(id="r_siblings", kind="exact", weight=1.0, system=EXACT_SYS,
         prompt="У Марии четыре брата и три сестры. Сколько сестёр у брата Марии? "
                "Ответь числом.",
         answers=["4"]),
    dict(id="r_machines", kind="exact", weight=1.0, system=EXACT_SYS,
         prompt="5 станков делают 5 деталей за 5 минут. Сколько минут понадобится "
                "100 станкам, чтобы сделать 100 деталей? Ответь числом.",
         answers=["5"]),
    dict(id="r_word_problem", kind="exact", weight=1.25, system=EXACT_SYS,
         prompt="В магазине яблоки стоят 80 руб/кг, груши — 120 руб/кг. Покупатель взял "
                "смесь из яблок и груш общим весом 5 кг и заплатил 480 рублей. "
                "Сколько килограммов груш он купил? Ответь числом.",
         answers=["2", "2.0", "2,0"]),
    dict(id="r_bigo", kind="exact", weight=1.0, system=EXACT_SYS,
         prompt="Какова асимптотическая сложность по времени этого кода в худшем случае?\n\n"
                "```python\n"
                "def f(a):\n"
                "    n = len(a)\n"
                "    total = 0\n"
                "    for i in range(n):\n"
                "        j = 1\n"
                "        while j < n:\n"
                "            total += a[i] * j\n"
                "            j *= 2\n"
                "    return total\n"
                "```\n"
                "Ответь в форме O(...) без пробелов, используя n.",
         answers=["o(nlogn)", "o(n*logn)", "o(nlog n)", "o(n log n)", "o(n·logn)",
                  "o(nlog2n)", "o(n*log(n))", "o(nlog(n))"]),
    dict(id="r_bits", kind="exact", weight=1.0, system=EXACT_SYS,
         prompt="Чему равно значение выражения на Python: `(0b1011 << 2) ^ 0xF`? "
                "Ответь десятичным числом.",
         answers=["35"]),  # 11<<2 = 44 = 0b101100; 44 ^ 0b001111 = 0b100011 = 35
    dict(id="r_seq", kind="exact", weight=1.0, system=EXACT_SYS,
         prompt="Продолжи последовательность: 1, 11, 21, 1211, 111221, ... "
                "Какое число идёт следующим? Ответь числом без пробелов.",
         answers=["312211"]),
    dict(id="r_mod", kind="exact", weight=1.25, system=EXACT_SYS,
         prompt="Чему равен остаток от деления 7^100 на 13? Ответь числом.",
         answers=["9"]),
    dict(id="r_trap", kind="exact", weight=1.0, system=EXACT_SYS,
         prompt="Бита и мяч вместе стоят 1100 рублей. Бита дороже мяча на 1000 рублей. "
                "Сколько рублей стоит мяч? Ответь числом.",
         answers=["50"]),
    dict(id="r_sql", kind="exact", weight=1.0, system=EXACT_SYS,
         prompt="Есть таблица orders(id, user_id, amount, status). Нужно вывести user_id "
                "пользователей, у которых суммарная amount по строкам со status='paid' "
                "больше 1000. Какое ключевое слово SQL используется для фильтрации по "
                "результату агрегатной функции? Ответь одним словом.",
         answers=["having"]),
]

# ----------------------------------------------------------------------------
# СЛЕДОВАНИЕ ИНСТРУКЦИЯМ
# ----------------------------------------------------------------------------

INSTRUCTION = [
    dict(id="i_json", kind="json_out", weight=1.0,
         system="Ты возвращаешь только валидный JSON, без пояснений и без markdown-разметки.",
         prompt=("Верни JSON-объект с полями:\n"
                 '  "name" — строка "тест",\n'
                 '  "count" — число 7,\n'
                 '  "tags" — массив из ровно трёх строк: "a", "b", "c",\n'
                 '  "nested" — объект с единственным полем "ok" со значением true.\n'
                 "Никакого текста кроме JSON."),
         check_json=dict(name="тест", count=7, tags=["a", "b", "c"],
                         nested=dict(ok=True))),
    dict(id="i_exact_words", kind="custom", weight=1.0, checker="exact_five_words",
         system="Ты строго следуешь формальным требованиям к ответу.",
         prompt=("Опиши, что делает язык программирования Python, РОВНО пятью словами. "
                 "Никаких знаков препинания, никаких кавычек, только пять слов через пробел "
                 "и ничего больше.")),
    dict(id="i_one_word", kind="custom", weight=1.0, checker="single_upper_word",
         system="Ты строго следуешь формальным требованиям к ответу.",
         prompt=("Какой протокол используется для передачи гипертекста в интернете? "
                 "Ответь ОДНИМ словом ЗАГЛАВНЫМИ БУКВАМИ, без точки и без каких-либо "
                 "других символов.")),
    dict(id="i_no_word", kind="custom", weight=1.0, checker="no_letter_a",
         system="Ты строго следуешь формальным требованиям к ответу.",
         prompt=("Напиши одно предложение о море на русском языке, в котором нет "
                 "ни одной буквы «а». Длина — не менее 5 слов. "
                 "Выведи только само предложение.")),
]

# ----------------------------------------------------------------------------
# РУССКИЙ ЯЗЫК
# ----------------------------------------------------------------------------

RUSSIAN = [
    dict(id="ru_capital", kind="exact", weight=1.0, system=EXACT_SYS,
         prompt="Назови столицу Австралии. Ответь одним словом.",
         answers=["канберра"]),
    dict(id="ru_case", kind="exact", weight=1.0, system=EXACT_SYS,
         prompt="Поставь слово «дерево» в родительный падеж множественного числа. "
                "Ответь одним словом.",
         answers=["деревьев"]),
    dict(id="ru_code_comment", kind="code_py", weight=1.0, level="medium",
         system=CODE_SYS,
         prompt=("Напиши функцию `нормализовать_телефон(s: str) -> str | None`.\n"
                 "Она принимает российский номер телефона в произвольном виде "
                 "(например '+7 (912) 345-67-89', '8-912-345-67-89', '89123456789') "
                 "и возвращает его в каноническом виде '+79123456789'.\n"
                 "Если из строки нельзя получить корректный российский номер "
                 "(11 цифр, начинающихся с 7 или 8, либо 10 цифр без кода страны) — "
                 "вернуть None.\n"
                 "У функции должна быть докстрока на русском языке."),
         test=r'''
f = нормализовать_телефон
assert f("+7 (912) 345-67-89") == "+79123456789"
assert f("8-912-345-67-89") == "+79123456789"
assert f("89123456789") == "+79123456789"
assert f("79123456789") == "+79123456789"
assert f("9123456789") == "+79123456789"
assert f("123") is None
assert f("") is None
assert f("+7 912 345 67 8912") is None
assert f("абв") is None
doc = (f.__doc__ or "")
assert any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in doc), "нет русской докстроки"
''',
         ),
]

# ----------------------------------------------------------------------------
# ДЛИННЫЙ КОНТЕКСТ
# ----------------------------------------------------------------------------

def _haystack():
    """Собирает ~4000 токенов текста-наполнителя с фактом внутри."""
    filler = (
        "Система сборки проекта опирается на кэш артефактов, который инвалидируется "
        "по хэшу входных файлов. Планировщик задач распределяет работу между воркерами "
        "с учётом приоритета очереди. Логи агрегируются в едином хранилище и ротируются "
        "раз в сутки. Метрики собираются пулл-моделью с интервалом пятнадцать секунд. "
    )
    # ~70 параграфов ≈ 4800 токенов: с запасом влезает в num_ctx=8192 вместе
    # с вопросом, иначе иголку срезает при усечении промпта.
    parts = []
    for i in range(70):
        parts.append(f"Параграф {i}. " + filler)
        if i == 42:
            parts.append(
                "ВАЖНО: секретный код доступа к стенду нагрузочного тестирования — "
                "QX-4417-ZULU. Он меняется раз в квартал. "
            )
    return "\n".join(parts)


LONGCTX = [
    dict(id="lc_needle", kind="exact", weight=1.0, system=EXACT_SYS,
         prompt=("Ниже приведён документ. Прочитай его и ответь на вопрос.\n\n"
                 "=== ДОКУМЕНТ ===\n" + _haystack() + "\n=== КОНЕЦ ДОКУМЕНТА ===\n\n"
                 "Вопрос: какой секретный код доступа к стенду нагрузочного тестирования "
                 "указан в документе?"),
         answers=["qx-4417-zulu"]),
]


ALL_TASKS = CODING + CODING_JS + REASONING + INSTRUCTION + RUSSIAN + LONGCTX

CATEGORY_OF = {}
for t in CODING + CODING_JS:
    CATEGORY_OF[t["id"]] = "code"
for t in REASONING:
    CATEGORY_OF[t["id"]] = "reasoning"
for t in INSTRUCTION:
    CATEGORY_OF[t["id"]] = "instruction"
for t in RUSSIAN:
    CATEGORY_OF[t["id"]] = "russian"
for t in LONGCTX:
    CATEGORY_OF[t["id"]] = "longctx"

CATEGORY_WEIGHTS = {
    "code": 0.50,
    "reasoning": 0.25,
    "instruction": 0.10,
    "russian": 0.10,
    "longctx": 0.05,
}
