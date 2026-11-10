"""Start isolated services, run browser scenarios and stop all owned processes."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request


TESTS = Path(__file__).resolve().parent
REPO = TESTS.parents[1]
STARTUP_TIMEOUT = 600


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def stop(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    return {'pid': process.pid, 'exit_code': process.returncode}


def run_suite(script, output, node):
    output.mkdir(parents=True)
    for name in ('tmp', 'logs', 'results', 'evidence'):
        (output / name).mkdir()
    api_port, web_port = free_port(), free_port()
    assert api_port != web_port
    api, origin = f'http://127.0.0.1:{api_port}', f'http://localhost:{web_port}'
    frontend = REPO / 'frontend'
    starter = output / 'start-vite.mjs'
    starter.write_text("import {pathToFileURL} from 'node:url';\n"
        + 'const {createServer}=await import(pathToFileURL(' + json.dumps(str(frontend / 'node_modules/vite/dist/node/index.js')) + ').href);\n'
        + 'const server=await createServer({root:' + json.dumps(str(frontend))
        + ',configFile:' + json.dumps(str(frontend / 'vite.config.ts'))
        + ',cacheDir:' + json.dumps(str(output / 'tmp/vite-cache'))
        + ",server:{host:'127.0.0.1',port:" + str(web_port)
        + ",strictPort:true,proxy:{'/api':{target:" + json.dumps(api)
        + ',changeOrigin:false}}}});\nawait server.listen();\n')
    env = dict(os.environ)
    env.update(PYTHONDONTWRITEBYTECODE='1', SKILLPROOF_ENV='development',
        SKILLPROOF_DB_PATH=str(output / 'tmp/test.db'), SKILLPROOF_ORIGIN=origin,
        SKILLPROOF_ALLOWED_HOSTS='localhost,127.0.0.1', SKILLPROOF_COOKIE_SECURE='0',
        TMPDIR=str(output / 'tmp'), PYTHONPATH=os.pathsep.join([str(TESTS), str(REPO / 'backend')]),
        NO_PROXY='localhost,127.0.0.1,::1', no_proxy='localhost,127.0.0.1,::1',
        SKILLPROOF_QA_ORIGIN=origin, SKILLPROOF_QA_RUN=str(output),
        SKILLPROOF_QA_RESTART_TIMEOUT=str(STARTUP_TIMEOUT + 15),
        SKILLPROOF_QA_PYTHON=sys.executable, SKILLPROOF_QA_ANSWERS=str(TESTS / 'fixtures/answers.json'))
    commands = {
        'api': [sys.executable, '-m', 'uvicorn', 'e2e_app:app', '--app-dir', str(TESTS), '--host', '127.0.0.1', '--port', str(api_port)],
        'vite': [node, str(starter)],
    }
    processes, handles, generations = {}, [], {}
    manifest = {'suite': script.name, 'origin': origin, 'api_origin': api, 'restarts': []}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def start(name, deadline=None):
        generations[name] = generations.get(name, 0) + 1
        handle = (output / 'logs' / f'{name}-{generations[name]}.txt').open('w')
        handles.append(handle)
        process = subprocess.Popen(commands[name], cwd=REPO, env=env, stdout=handle,
            stderr=subprocess.STDOUT, start_new_session=True)
        processes[name] = process
        address = api + '/api/health' if name == 'api' else origin
        if deadline is None:
            deadline = time.monotonic() + STARTUP_TIMEOUT
        while True:
            if process.poll() is not None:
                raise RuntimeError(f'{name} exited before readiness; see {handle.name}')
            try:
                with opener.open(address, timeout=1) as response:
                    assert response.status == 200
                return process.pid
            except OSError:
                if time.monotonic() > deadline:
                    raise TimeoutError(f'{name} readiness timed out')
                time.sleep(.1)

    browser = None
    try:
        for name in commands:
            start(name)
        handle = (output / 'logs/browser.txt').open('w')
        handles.append(handle)
        browser = subprocess.Popen([node, str(script)], cwd=TESTS, env=env,
            stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
        deadline, handled = time.monotonic() + 1800, 0
        while browser.poll() is None:
            if time.monotonic() > deadline:
                raise TimeoutError(f'{script.name} timed out')
            request = output / 'control-request.json'
            if request.exists():
                command = json.loads(request.read_text())
                if command['sequence'] != handled:
                    targets = ['api'] if command['target'] == 'api' else ['vite', 'api']
                    before = {name: stop(processes[name]) for name in targets}
                    ready_deadline = time.monotonic() + STARTUP_TIMEOUT
                    after = {name: start(name, ready_deadline) for name in reversed(targets)}
                    receipt = {'sequence': command['sequence'], 'target': command['target'],
                        'before': before, 'after': after, 'ready': True,
                        'at': datetime.now(timezone.utc).isoformat()}
                    manifest['restarts'].append(receipt)
                    temp = output / 'control-response.tmp'
                    temp.write_text(json.dumps(receipt))
                    temp.replace(output / 'control-response.json')
                    handled = command['sequence']
            time.sleep(.1)
        print((output / 'logs/browser.txt').read_text(), end='', flush=True)
        summary_path = output / 'results/summary.json'
        if not summary_path.exists():
            raise RuntimeError(f'{script.name}: no test summary was produced')
        summary = json.loads(summary_path.read_text())
        expected = len(re.findall(r"await check\('([^']+)'", script.read_text()))
        manifest['summary'] = summary
        if browser.returncode or expected == 0 or summary['total'] != expected or summary['pass'] != expected or summary['fail']:
            raise RuntimeError(f'{script.name}: incomplete or failing tests: {summary}; expected {expected}')
        return summary
    finally:
        if browser is not None:
            stop(browser)
        manifest['stopped'] = {name: stop(p) for name, p in processes.items()}
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        for handle in handles:
            handle.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--suite', choices=[p.stem for p in TESTS.glob('test_*.cjs')])
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    node = shutil.which('node')
    if not node:
        parser.error('Node.js is required')
    scripts = sorted(TESTS.glob('test_*.cjs')) if args.suite is None else [TESTS / f'{args.suite}.cjs']
    if not scripts:
        parser.error('No browser test suites found')
    results = []
    for script in scripts:
        print(f'Running {script.name}', flush=True)
        try:
            summary = run_suite(script, args.output / script.stem, node)
            results.append({'suite': script.name, 'status': 'pass', **summary})
        except Exception as error:
            print(str(error), file=sys.stderr, flush=True)
            results.append({'suite': script.name, 'status': 'fail', 'error': str(error)})
    (args.output / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
    return 0 if all(result['status'] == 'pass' for result in results) else 1


if __name__ == '__main__':
    sys.exit(main())
