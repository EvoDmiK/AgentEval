#!/usr/bin/env python3
"""A-H evaluation through real LangChain runnable autologging.

Install: uv venv --python 3.12 .venv-eval && uv pip install --python
  .venv-eval/bin/python -r requirements-eval.txt
Smoke (no agent/model calls): .venv-eval/bin/python scripts/extended_runner.py
  --smoke --curl-transport --outdir runs/extended-20261012/instrumentation-smoke
Evaluation: --dataset PATH --ids A01,F01 --agents openclaw,hermes --memory off
G only: --ids G01 --memory on --step-callback module:function

Coordinator owns memory configuration/reset. Callback(event, record) may inspect
storage or wait for extraction; return JSON is local-only. Events: before_step,
after_step, after_item. Explicit corrections use seed_prompts_json objects with
phase='correction', prompt='...'; string entries are seed steps. Every invocation
is a fresh session. Never resumes Hermes conversation via --resume.

Outer autolog traces measure the CLI runnable, not the native model/tools inside
the external process. Native telemetry now targets experiment 45 alongside outer traces and is not
inferred from stdout. No synthetic model/token metrics are emitted.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from eval_settings import TRACKING_URI
from run_eval import QA_PROMPT, ERR_PROMPT, build_units, clean_answer


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else
                          json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def append(path, record):
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def write_manifest(path, value):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


def read_records(path):
    if not path.exists():
        return []
    # Fail on a torn/corrupt journal rather than discard an attempt.
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def agent_artifacts(mlflow, out, agent, attempts, events, manifest_path):
    """Publish agent-only snapshots; the complete local journal remains append-only."""
    result_path = out/f'results-{agent}.jsonl'
    for source, target in [(attempts, result_path), (events, out/f'events-{agent}.jsonl')]:
        rows = [r for r in read_records(source)
                if r.get('agent') == agent or r.get('key', '').startswith(agent + '/')]
        temporary = target.with_suffix('.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
        temporary.replace(target)
        mlflow.log_artifact(str(target))
    mlflow.log_artifact(str(manifest_path))
    return result_path


@contextlib.contextmanager
def tracking_transport(remote, use_curl):
    """SDK/autolog remain real; optional localhost bridge changes HTTP transport only.

    Cloud endpoint rejects some Python HTTP clients; existing publishers use curl.
    Bind loopback with a random path token; forward only to the configured origin.
    Headers and payload use stdin/temp files, never credential-bearing argv.
    """
    if not use_curl:
        yield remote
        return
    parsed = urlsplit(remote)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.query:
        raise ValueError('curl transport needs an HTTP(S) tracking origin')
    token = uuid.uuid4().hex

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def forward(self):
            prefix = '/' + token
            if not self.path.startswith(prefix + '/'):
                self.send_error(404)
                return
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            with tempfile.TemporaryDirectory(prefix='eval-http-') as directory:
                base = Path(directory)
                payload, output, headers = base/'body', base/'output', base/'headers'
                payload.write_bytes(body)
                config = ''.join('header = ' + json.dumps(k + ': ' + v) + '\n'
                                 for k, v in self.headers.items()
                                 if k.lower() not in {'host', 'connection', 'content-length', 'accept-encoding'})
                command = ['curl', '-sS', '--max-time', '120', '--config', '-',
                           '-X', self.command, '-D', str(headers), '-o', str(output),
                           '-w', '%{http_code}', remote.rstrip('/') + self.path[len(prefix):]]
                if body:
                    command[1:1] = ['--data-binary', '@' + str(payload)]
                result = subprocess.run(command, input=config, text=True, capture_output=True)
                if result.returncode:
                    self.send_error(502, 'upstream curl transport failure')
                    return
                content = output.read_bytes()
                self.send_response(int(result.stdout))
                # Last HTTP header block (curl may receive CONNECT/100 responses).
                block = headers.read_text().strip().split('\n\n')[-1]
                for line in block.splitlines()[1:]:
                    key, sep, value = line.partition(':')
                    if sep and key.lower() in {'content-type', 'location'}:
                        self.send_header(key, value.strip())
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = forward

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/{token}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def load_plan(path, ids, all_items):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    required = {'문항ID', '유형', '출처 문서', '질문/지시', '정답',
                '정답 근거(위치·원문)', '채점 옵션', '제시 자료', '비고'}
    if not rows or not required.issubset(rows[0]):
        raise ValueError('dataset must retain original Korean nine columns')
    qids = [r['문항ID'] for r in rows]
    if len(qids) != len(set(qids)):
        raise ValueError('duplicate item IDs')
    if any(not q or q[0] not in 'ABCDEFGH' for q in qids):
        raise ValueError('only A-H item IDs supported')
    if not all_items and not ids.issubset(set(qids)):
        raise ValueError(f'unknown IDs: {sorted(ids-set(qids))}')
    selected = rows if all_items else [r for r in rows if r['문항ID'] in ids]
    units = []
    # Preserve original E document grouping and prompt semantics.
    for unit in build_units([r for r in rows if r['문항ID'].startswith('E')],
                            None if all_items else ids):
        units.append({**unit, 'category': 'E', 'steps': [{'phase': 'answer', 'prompt': unit['prompt']}],
                      'row': next(r for r in rows if r['문항ID'] in unit['members'])})
    for row in selected:
        item = row['문항ID']
        if item.startswith('E'):
            continue
        steps = []
        category = item[0]
        if category == 'G':
            seeds = json.loads(row.get('seed_prompts_json') or '[]')
            if not isinstance(seeds, list) or not seeds:
                raise ValueError(f'{item}: G requires nonempty seed_prompts_json')
            phases = json.loads(row.get('seed_phases_json') or '[]')
            if not isinstance(phases, list) or (phases and len(phases) != len(seeds)):
                raise ValueError(f'{item}: seed_phases_json must match seed count')
            for n, seed in enumerate(seeds, 1):
                phase, prompt = ('seed', seed) if isinstance(seed, str) else (seed['phase'], seed['prompt'])
                if phases:
                    phase = phases[n-1]
                if phase not in {'seed', 'correction'} or not isinstance(prompt, str) or not prompt.strip():
                    raise ValueError(f'{item}: invalid seed/correction step')
                steps.append({'phase': f'{phase}-{n}', 'prompt': prompt})
            prompt = row['질문/지시']
        elif category in 'ABCD':
            prompt = QA_PROMPT.format(q=row['질문/지시'])
        else:
            prompt = row['질문/지시']
        if not (category == 'G' and row.get('audit_kind') == 'storage_audit'):
            steps.append({'phase': 'recall' if category == 'G' else 'answer', 'prompt': prompt})
        units.append({'unit': item, 'members': [item], 'category': category, 'steps': steps, 'row': row})
    return sorted(units, key=lambda u: u['unit'])


def external_agent(record, options):
    """Actual CLI execution inside a RunnableLambda; structured errors are results."""
    prompt, sid, agent = record['prompt'], record['session'], record['agent']
    if options.smoke:
        command = [sys.executable, '-c',
                   'import sys; print("instrumentation subprocess: " + sys.argv[1]); sys.exit(int(sys.argv[2]))',
                   prompt, str(options.smoke_exit)]
        execution = 'deterministic-local-subprocess (no agent/model call)'
    elif agent == 'openclaw':
        command = ['docker', 'exec', options.openclaw_container, 'node', 'dist/index.js',
                   'agent', '--agent', 'eval', '--session-id', sid, '--message', prompt]
        execution = 'existing-docker-exec'
    elif options.hermes_container:
        command = ['docker', 'exec', '-e', 'HERMES_SESSION_ID=' + sid,
                   options.hermes_container, 'hermes', 'chat', '-Q', '-q', prompt]
        execution = 'existing-docker-exec (fresh chat, no --resume)'
    else:
        command = ['sh', str(ROOT/'hermes-docker/run-hermes.sh'), 'chat', '-Q', '-q', prompt]
        execution = 'run-hermes.sh -> docker run --rm isolated profile (fresh chat)'
    start, clock = dt.datetime.now(dt.timezone.utc).isoformat(), time.monotonic()
    try:
        child = subprocess.run(command, capture_output=True, text=True, timeout=options.timeout,
                               env={**os.environ, 'HERMES_SESSION_ID': sid})
        stdout, stderr, code = child.stdout, child.stderr, child.returncode
        error = None if code == 0 else 'nonzero_exit'
    except subprocess.TimeoutExpired as exc:
        def decode(value):
            return value.decode(errors='replace') if isinstance(value, bytes) else value or ''
        stdout, stderr, code, error = decode(exc.stdout), decode(exc.stderr), 124, 'timeout'
    except OSError as exc:
        stdout, stderr, code, error = '', str(exc), 127, type(exc).__name__
    return {**record, 'start': start, 'end': dt.datetime.now(dt.timezone.utc).isoformat(),
            'wall_s': time.monotonic()-clock, 'stdout': stdout, 'stderr': stderr, 'exit': code,
            'error': error, 'answer': clean_answer(agent, stdout), 'execution': execution,
            'command': command, 'native_trace_id': None, 'native_tokens': None,
            'native_session_id': sid if agent == 'openclaw' and not options.smoke else None}


def invoke_callback(callback, event, record, path):
    if callback:
        try:
            result = callback(event, dict(record))
            status = 'ok'
        except Exception as exc:
            result, status = {'error': repr(exc)}, 'audit_error'
        append(path, {'event': event, 'attempt_id': record['attempt_id'], 'key': record['key'],
                      'time': dt.datetime.now(dt.timezone.utc).isoformat(), 'status': status, 'result': result})
        return status
    return 'not_configured'


def verify_trace(mlflow, client, trace_id, record, run_id, attempts):
    if not trace_id:
        raise RuntimeError('autolog produced no trace ID')
    mlflow.flush_trace_async_logging()
    trace = client.get_trace(trace_id)
    request = json.loads(trace.data.request) if isinstance(trace.data.request, str) else trace.data.request
    response = json.loads(trace.data.response) if isinstance(trace.data.response, str) else trace.data.response
    if request != record['trace_input']:
        raise RuntimeError('remote trace input differs from invocation')
    expected = record['trace_output']
    if response != expected:
        raise RuntimeError('remote trace output differs from actual subprocess result')
    spans = trace.data.spans
    if not spans or not any(s.name == 'external_agent_cli' for s in spans):
        raise RuntimeError('remote autolog external_agent_cli span missing')
    run = client.get_run(run_id)
    if run.data.params.get('agent') != record['agent']:
        raise RuntimeError('remote run agent parameter mismatch')
    local = attempts.read_bytes()
    if any(row['agent'] != record['agent'] for row in read_records(attempts)):
        raise RuntimeError('result artifact contains a different agent')
    with tempfile.TemporaryDirectory(prefix='eval-readback-') as directory:
        downloaded = Path(client.download_artifacts(run_id, attempts.name, directory))
        if downloaded.read_bytes() != local:
            raise RuntimeError('remote attempts artifact differs from local journal')
    if not run.inputs.dataset_inputs:
        raise RuntimeError('remote dataset input linkage missing')
    if trace.info.trace_metadata.get('mlflow.sourceRun') != run_id:
        raise RuntimeError('remote autolog trace source run mismatch')
    return {'trace_id': trace_id, 'run_id': run_id, 'agent': record['agent'], 'span_names': [s.name for s in spans],
            'request_verified': True, 'stdout_verified': True, 'result_artifact': attempts.name,
            'result_artifact_sha256': digest(local), 'artifact_agent_verified': True,
            'run_agent_verified': True, 'source_run_verified': True, 'dataset_input_verified': True,
            'native_llm_tokens': 'unknown (not fabricated)'}


def execute(options):
    import mlflow
    import mlflow.langchain
    import pandas as pd
    from mlflow import MlflowClient
    from langchain_core.runnables import RunnableLambda

    out = Path(options.outdir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    attempts, events = out/'attempts.jsonl', out/'attempt-events.jsonl'
    callback_path = out/'callbacks-private.jsonl'
    callback = None
    if options.step_callback:
        module, function = options.step_callback.rsplit(':', 1)
        callback = getattr(importlib.import_module(module), function)
    if options.smoke:
        plan = [{'unit': 'SMOKE', 'members': ['SMOKE'], 'category': 'smoke', 'row': {},
                 'steps': [{'phase': 'instrumentation', 'prompt': 'actual stdout readback proof'}]}]
        source_bytes = json.dumps(plan).encode()
        source = 'deterministic instrumentation smoke; no evaluation dataset'
    else:
        path = Path(options.dataset).resolve()
        plan = load_plan(path, set(filter(None, options.ids.split(','))), options.all)
        source_bytes, source = path.read_bytes(), str(path)
        categories = {u['category'] for u in plan}
        if 'G' in categories and (options.memory != 'on' or len(categories) != 1):
            raise ValueError('G must be selected separately with --memory on; coordinator owns configuration')
        if 'G' not in categories and options.memory != 'off':
            raise ValueError('A-F/H require --memory off')
    agents = options.agents.split(',')
    if not agents or any(a not in {'openclaw', 'hermes'} for a in agents) or len(set(agents)) != len(agents):
        raise ValueError('--agents must contain distinct openclaw/hermes')
    identity = {'dataset_sha256': digest(source_bytes), 'plan_sha256': digest(plan), 'agents': agents,
                'reps': options.reps, 'memory': options.memory, 'smoke': options.smoke,
                'smoke_exit': options.smoke_exit, 'step_callback': options.step_callback,
                'openclaw_container': options.openclaw_container, 'hermes_container': options.hermes_container,
                'tracking_uri': options.tracking_uri, 'experiment_id': options.experiment_id}
    identity['dataset_id'], identity['dataset_version'] = options.dataset_id, options.dataset_version
    if not identity['dataset_version']:
        identity['dataset_version'] = 'sha256:' + identity['dataset_sha256']
    manifest_path = out/'manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest['identity'] != identity:
            raise ValueError('outdir belongs to a different dataset/plan/configuration; choose a new outdir')
    else:
        manifest = {'identity': identity, 'evaluation_id': uuid.uuid4().hex, 'runs': {}}
        write_manifest(manifest_path, manifest)
    prior = read_records(attempts)
    finalized = {r['attempt_id'] for r in prior}
    for event in read_records(events):
        if event['event'] == 'started' and event['attempt_id'] not in finalized:
            # A crash may have launched an agent. Do not silently rerun an uncertain call.
            interrupted = {k: v for k, v in event.items() if k != 'event'}
            interrupted.update(exit=126, success=False, error='interrupted_execution_unknown',
                               stdout='', stderr='', answer='', trace_id=None)
            append(attempts, interrupted)
            prior.append(interrupted)
            finalized.add(event['attempt_id'])
    # Every finalized attempt, including a failed CLI, is settled. Retry only explicitly.
    done = {r['key'] for r in prior if not options.retry_errors or r['success']}
    chain = RunnableLambda(lambda record: external_agent(record, options), name='external_agent_cli')
    with tracking_transport(options.tracking_uri, options.curl_transport) as uri:
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(experiment_id=options.experiment_id)
        mlflow.langchain.autolog(log_traces=True, silent=False)
        client = MlflowClient()
        experiment = client.get_experiment(options.experiment_id)
        if options.experiment_id == '45' and experiment.name != 'compare-summary':
            raise ValueError('experiment 45 must be compare-summary')
        dataset = mlflow.data.from_pandas(pd.DataFrame([
            {'unit': u['unit'], 'category': u['category'], 'phase': s['phase'], 'prompt': s['prompt']}
            for u in plan for s in u['steps']]), source=source,
            name='extended-A-H-' + identity['dataset_sha256'][:12], digest=identity['plan_sha256'][:16])
        proofs = []
        for agent in agents:
            key = f"extended/{manifest['evaluation_id']}/{agent}"
            run_id = manifest['runs'].get(agent)
            if not run_id:
                matches = client.search_runs([options.experiment_id], f"tags.compare_key = '{key}'")
                if matches:
                    run_id = matches[0].info.run_id
            with mlflow.start_run(run_id=run_id, run_name=f"{'instrumentation-smoke' if options.smoke else 'extended-A-H'} · {agent}",
                                  experiment_id=options.experiment_id,
                                  tags={'compare_key': key, 'evaluation_id': manifest['evaluation_id'],
                                        'instrumentation': 'mlflow.langchain.autolog external runnable',
                                        'trace_scope': 'outer CLI chain; native inner traces separate',
                                        'evaluation_methods': 'outcome; trajectory_and_tool_use; component_level',
                                        'evaluation_type': 'instrumentation_smoke' if options.smoke else 'extended_A_H'}) as run:
                run_id = run.info.run_id
                manifest['runs'][agent] = run_id
                write_manifest(manifest_path, manifest)
                mlflow.log_params({'agent': agent, 'dataset_sha256': identity['dataset_sha256'],
                                   'plan_sha256': identity['plan_sha256'], 'dataset_version': identity['dataset_version'],
                                   'dataset_id': options.dataset_id or 'not_published',
                                   'memory': options.memory, 'repetitions': options.reps})
                if not client.get_run(run_id).inputs.dataset_inputs:
                    mlflow.log_input(dataset, context='evaluation')
                # Resume pending telemetry verification without executing the external agent again.
                verified = {r['trace_id'] for r in read_records(out/'readback.jsonl')}
                for previous in [r for r in prior if r['agent'] == agent and r.get('trace_id') not in verified
                                 and r.get('trace_id')]:
                    result_path = agent_artifacts(mlflow, out, agent, attempts, events, manifest_path)
                    proof = verify_trace(mlflow, client, previous['trace_id'], previous, run_id, result_path)
                    append(out/'readback.jsonl', proof)
                    proofs.append(proof)
                audit_events = {e['attempt_id']: e for e in read_records(events)
                                if e['event'] in {'audited', 'audit_retried'}}
                for previous in [r for r in prior if r['agent'] == agent and r.get('trace_id') and callback]:
                    event = audit_events.get(previous['attempt_id'])
                    if event and 'audit_error' not in (event['before_status'], event['after_status'], event['item_status']):
                        continue
                    if event and event['before_status'] == 'audit_error':
                        raise RuntimeError('prior pre-execution audit failed; its historical state cannot be reconstructed')
                    status = invoke_callback(callback, 'after_step', previous, callback_path)
                    terminal = previous.get('is_final_step', previous['phase'] in {'answer', 'recall', 'instrumentation'})
                    item_status = invoke_callback(callback, 'after_item', previous, callback_path) if terminal else 'not_applicable'
                    append(events, {'event': 'audit_retried', 'key': previous['key'], 'attempt_id': previous['attempt_id'],
                                    'before_status': 'not_repeated', 'after_status': status, 'item_status': item_status})
                    if 'audit_error' in (status, item_status):
                        raise RuntimeError('resumed callback audit failed; external agent was not rerun')
                for rep in range(1, options.reps+1):
                    for unit in plan:
                        failed_dependency = False
                        for step in unit['steps']:
                            attempt_key = f'{agent}/{unit["unit"]}/{rep}/{step["phase"]}'
                            existing = [r for r in prior if r['key'] == attempt_key]
                            if attempt_key in done:
                                if existing and not existing[-1]['success']:
                                    failed_dependency = True
                                continue
                            if failed_dependency:
                                print(f'blocked dependent phase: {attempt_key}', flush=True)
                                break
                            record = {'key': attempt_key, 'attempt_id': uuid.uuid4().hex,
                                      'attempt': len(existing)+1, 'agent': agent, 'unit': unit['unit'],
                                      'item': unit['members'][0], 'members': unit['members'],
                                      'item_id': unit['members'][0],
                                      'category': unit['category'], 'repetition': rep, 'rep': rep,
                                      'phase': step['phase'], 'prompt': step['prompt'], 'memory': options.memory,
                                      'is_final_step': step == unit['steps'][-1],
                                      'session': 'extended-' + uuid.uuid4().hex,
                                      'session_semantics': ('exact CLI --session-id' if agent == 'openclaw' else
                                                            'fresh chat process; UUID is outer correlation; native ID unknown'),
                                      'dataset_sha256': identity['dataset_sha256'], 'run_id': run_id,
                                      'plan_sha256': identity['plan_sha256'], 'dataset_version': identity['dataset_version'],
                                      'dataset_id': options.dataset_id,
                                      'audit_kind': unit['row'].get('audit_kind', ''),
                                      'as_of': unit['row'].get('as_of', ''), 'evidence_ref': unit['row'].get('evidence_ref', '')}
                            append(events, {'event': 'started', **record})
                            before_status = 'not_configured'
                            try:
                                before_status = invoke_callback(callback, 'before_step', record, callback_path)
                                result = chain.invoke(record, config={'metadata': {
                                    'agent': agent, 'category': unit['category'], 'item': record['item'],
                                    'repetition': rep, 'session': record['session'], 'phase': record['phase'],
                                    'dataset_sha256': identity['dataset_sha256'], 'attempt_id': record['attempt_id']}})
                                trace_id = mlflow.get_last_active_trace_id()
                                result['success'] = result['exit'] == 0 and bool(result['answer'].strip())
                                result['trace_id'] = trace_id
                                # Keep trace output snapshot separate; autolog output predates our bookkeeping.
                                trace_output = {k: v for k, v in result.items() if k not in {'success', 'trace_id'}}
                                result['trace_input'], result['trace_output'] = record, trace_output
                            except Exception as exc:
                                result = {**record, 'exit': 125, 'success': False, 'error': repr(exc),
                                          'stdout': '', 'stderr': '', 'answer': '', 'trace_id': None}
                            append(attempts, result)
                            prior.append(result)
                            done.add(attempt_key)
                            append(events, {'event': 'finished', 'key': attempt_key, 'attempt_id': record['attempt_id'],
                                            'success': result['success'], 'exit': result['exit']})
                            audit_status = invoke_callback(callback, 'after_step', result, callback_path)
                            if step == unit['steps'][-1]:
                                item_audit_status = invoke_callback(callback, 'after_item', result, callback_path)
                            else:
                                item_audit_status = 'not_applicable'
                            append(events, {'event': 'audited', 'key': attempt_key, 'attempt_id': record['attempt_id'],
                                            'before_status': before_status, 'after_status': audit_status,
                                            'item_status': item_audit_status})
                            result_path = agent_artifacts(mlflow, out, agent, attempts, events, manifest_path)
                            mlflow.log_metrics({'attempt_exit': result['exit'],
                                                'attempt_success': int(result['success'])}, step=len(prior))
                            if 'wall_s' in result:
                                mlflow.log_metric('wall_s', result['wall_s'], step=len(prior))
                            if result.get('trace_id'):
                                proof = verify_trace(mlflow, client, result['trace_id'], result, run_id, result_path)
                                append(out/'readback.jsonl', proof)
                                proofs.append(proof)
                            else:
                                raise RuntimeError('attempt preserved but autolog trace unavailable; see attempts journal')
                            print(f'{attempt_key}: exit={result["exit"]} trace={result["trace_id"]}', flush=True)
                            if not result['success']:
                                failed_dependency = True
                            if 'audit_error' in (before_status, audit_status, item_audit_status):
                                raise RuntimeError('storage callback audit failed; CLI answer preserved separately; see callbacks-private.jsonl')
                selected = [r for r in prior if r['agent'] == agent]
                mlflow.log_metrics({'attempt_count': len(selected), 'successful_attempt_count': sum(r['success'] for r in selected),
                                    'failed_attempt_count': sum(not r['success'] for r in selected)})
                agent_artifacts(mlflow, out, agent, attempts, events, manifest_path)
                proof_path = out/f'readback-{agent}.jsonl'
                proof_path.write_text(''.join(json.dumps(p)+'\n' for p in read_records(out/'readback.jsonl')
                                             if p['run_id'] == run_id))
                mlflow.log_artifact(str(proof_path))
        mlflow.flush_trace_async_logging()
    return manifest, prior, proofs


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dataset', default=str(ROOT/'datasets/base/1_문항표.csv'))
    parser.add_argument('--dataset-version', default='', help='defaults to full CSV SHA-256 version')
    parser.add_argument('--dataset-id', default='', help='persistent EvaluationDataset ID, published by coordinator')
    parser.add_argument('--ids', default='')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--agents', default='openclaw,hermes')
    parser.add_argument('--reps', type=int, default=1)
    parser.add_argument('--outdir', required=True)
    parser.add_argument('--memory', choices=['on', 'off'], default='off')
    parser.add_argument('--step-callback', default='')
    parser.add_argument('--tracking-uri', default=TRACKING_URI)
    parser.add_argument('--experiment-id', default='45')
    parser.add_argument('--curl-transport', action='store_true')
    parser.add_argument('--retry-errors', action='store_true', help='explicitly append new attempts for finalized errors')
    parser.add_argument('--timeout', type=float, default=900)
    parser.add_argument('--openclaw-container', default='openclaw-cli')
    parser.add_argument('--hermes-container', default='', help='existing Hermes container; otherwise isolated run-hermes.sh')
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--smoke-exit', type=int, default=0)
    args = parser.parse_args()
    if args.reps < 1 or args.timeout <= 0:
        parser.error('positive reps and timeout required')
    if not args.smoke and not (args.all or args.ids):
        parser.error('give --ids or --all')
    directory = Path(args.outdir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    with (directory/'.runner.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('another runner owns this outdir')
        manifest, records, proofs = execute(args)
    print(json.dumps({'runs': manifest['runs'], 'attempts': len(records), 'new_verified_traces': len(proofs)}))
    by_key = {}
    for record in records:
        by_key.setdefault(record['key'], []).append(record)
    return 1 if any(not any(r['success'] for r in history) for history in by_key.values()) else 0


if __name__ == '__main__':
    sys.exit(main())
