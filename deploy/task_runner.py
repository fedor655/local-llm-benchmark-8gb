import json, subprocess, os

MODEL = os.environ.get('MODEL', 'coder-abliterated')
AIDER = os.path.expanduser('~/.local/bin/aider')
tasks = json.load(open('/tmp/gittasks.json', encoding='utf-8'))
env = dict(os.environ, OLLAMA_API_BASE='http://127.0.0.1:11434',
           PYTHONUTF8='1', PYTHONIOENCODING='utf-8')

print(f'=== агент: Aider + {MODEL} | задач: {len(tasks)} ===')
passed = 0
for t in tasks:
    tid = t['id']
    d = f'/tmp/task_{tid}'
    subprocess.run(['rm', '-rf', d]); os.makedirs(d)
    subprocess.run(['git', 'init', '-q'], cwd=d)
    subprocess.run(['git', 'config', 'user.email', 'x@x.x'], cwd=d)
    subprocess.run(['git', 'config', 'user.name', 'x'], cwd=d)
    open(f'{d}/solution.py', 'w').close()
    msg = t['prompt'] + '\n\nPut the solution in solution.py. Code only.'
    try:
        subprocess.run(
            [AIDER, '--model', f'ollama_chat/{MODEL}', '--yes-always',
             '--no-auto-commits', '--no-auto-lint', '--no-check-update',
             '--no-show-release-notes', '--no-analytics', '--no-show-model-warnings',
             '--message', msg, 'solution.py'],
            cwd=d, env=env, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        print(f'{tid:22} TIMEOUT (агент думал >5 мин)'); continue
    code = open(f'{d}/solution.py', encoding='utf-8', errors='replace').read()
    if not code.strip():
        print(f'{tid:22} FAIL — агент не записал код'); continue
    testsrc = code + '\n' + t['test'] + '\nprint("__PASS__")'
    tr = subprocess.run(['python3', '-c', testsrc], cwd=d,
                        capture_output=True, text=True, timeout=30)
    ok = '__PASS__' in tr.stdout and tr.returncode == 0
    if ok:
        passed += 1
        print(f'{tid:22} PASS  (тест пройден исполнением)')
    else:
        err = (tr.stderr.strip().splitlines() or ['no output'])[-1]
        print(f'{tid:22} FAIL  ({err[:80]})')
print(f'=== ИТОГ {MODEL}: {passed}/{len(tasks)} прошли ===')
