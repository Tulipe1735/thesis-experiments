"""Validate code execution and callable-skill dispatch from one frozen artifact."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'experiments/grow_up_harness_v2'
sys.path[:0] = [str(ROOT), str(PACKAGE), str(PACKAGE / 'calibration')]
from harness import artifact_mapping as M, grow_loop as L, t01_episode as T1, t02_episode as T2
from harness.llm import Client, LLMError, LLMReplyError


def read(path): return json.loads(Path(path).read_text())
def rel(path): return str(Path(path).resolve().relative_to(ROOT))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def inventory(folder):
    return {str(p.relative_to(folder)): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def load_key():
    for line in (ROOT / '.env').read_text().splitlines():
        key, sep, value = line.partition('=')
        if sep and key.strip().removeprefix('export ') == 'OPENCODE_API_KEY':
            values = shlex.split(value, comments=True)
            if len(values) != 1 or not values[0]:
                raise ValueError('OPENCODE_API_KEY must be one nonempty value')
            os.environ['OPENCODE_API_KEY'] = values[0]
            return
    raise ValueError('OPENCODE_API_KEY missing from root .env')


def account_model_call(counts, folder):
    for path in folder.rglob('model/metadata.json'):
        meta = read(path)
        counts['llm_wall_s'] += meta['wall_seconds']
        usage = meta.get('usage')
        if usage is not None:
            for key in ('prompt_tokens', 'completion_tokens'):
                counts[key] += usage.get(key, 0) or 0



def prepare(config_path, output):
    config = read(config_path)
    if config['skill_execution'] != 'artifact_call':
        raise ValueError('this runner validates artifact calls; controller-resynthesis configs are archived')
    output.mkdir(parents=True, exist_ok=False)
    L.write_new(output / 'config.json', config)
    tasks, bindings, dependencies = {}, {}, [Path(__file__), Path(M.__file__), Path(T1.__file__),
        Path(T2.__file__), Path(L.__file__), PACKAGE / 'harness/llm.py', PACKAGE / 'harness/artifact.py',
        PACKAGE / 'harness/artifact_v2.py', ROOT / 'experiments/t0_agent_v1/tray_verify.py',
        ROOT / 'experiments/t0_agent_v1/runtime.py', ROOT / 'grasp_optimization/pantry_robot.py',
        ROOT / 'experiments/grow_up_v2/isolation/worker.py', ROOT / 'experiments/cordis_t01/worker.py', config_path]
    for family in config['active_families']:
        spec = config[family]
        views = M.project(family, spec)
        prior = read(ROOT / spec['initial']['registration'])
        for key in spec['initial']['keys']: prior = prior[key]
        task = copy.deepcopy(next(t for t in prior['tasks'] if t['task_id'] == spec['initial']['task_id']))
        original = ROOT / task['private']['initial_source']
        if sha(original) != task['private']['initial_sha256']:
            raise ValueError('registered initial bytes changed')
        sample = output / f'samples_{family}' / (task['task_id'] + '.npz')
        sample.parent.mkdir(); shutil.copyfile(original, sample)
        task['private']['initial_source'] = rel(sample)
        tasks[family] = {**prior, 'tasks': [task], 'count': 1,
                         'selection': 'known historical success for mapping repair; not unseen generalization'}
        export = output / 'exports' / family; export.mkdir(parents=True)
        (export / 'code.py').write_text(views.code)
        (export / 'skill.md').write_text(views.card)
        L.write_new(export / 'manifest.json', views.manifest)
        bindings[family] = views.manifest
        old = read(ROOT / spec['historical_success'])
        if not old['success'] or old['source_sha256'] != views.manifest['code_sha256']:
            raise ValueError(f'{family}: projection differs from the historically successful code; fix mapping before physics')
        dependencies.extend([ROOT / prior['plant']['path'], original, sample, ROOT / spec['historical_success']])
        if family == 'T01': dependencies.append(ROOT / spec['artifact'])
        else:
            dependencies.append(ROOT / spec['geometry'])
            dependencies.extend((ROOT / spec['store'] / 'artifacts').glob('*.yaml'))
            dependencies.extend((ROOT / spec['store'] / 'sources').glob('*.py'))
    L.write_new(output / 'registration.json', {
        'date': config['date'], 'boundary': 'simulation', 'status': 'registered_before_physics',
        'tasks': tasks, 'bindings': bindings, 'skill_execution': 'artifact_call',
        'baselines': {'negative': 'wait-only, success voids batch',
                      'positive_and_code': 'historically successful artifact code, independently rechecked; failure skips skill',
                      'original_failure': config['original_failure'],
                      'treatment': 'model selects exact skill binding; runtime invokes the same frozen code and native interface'},
        'prediction': config['prediction'], 'falsification': config['falsification'],
        'dependencies': {rel(p): sha(p) for p in dependencies}})
    L.write_new(output / 'store_frozen.json', {'files': inventory(output / 'exports')})
    return {'registered': list(tasks), 'artifact_refs': {f: m['artifact_ref'] for f,m in bindings.items()}}


def select_skill(output, family, task, observation, config, counts):
    views = M.project(family, config[family])
    exported = read(output / 'exports' / family / 'manifest.json')
    if views.manifest != exported: raise ValueError('artifact views differ from registered export')
    packet = {'task': task['public'], 'observation': observation,
        'codex_diagnosis': {'author': 'Codex', 'task': 'Select and invoke the existing successful artifact skill.',
          'failure_facts': config['original_failure'], 'available_leaves': [views.card],
          'repair_scope': 'The prior mapping replaced skill invocation with controller resynthesis and changed its interface. '
                          'Preserve the existing implementation and native interface. Return only its invocation binding; '
                          'do not generate source, joint trajectories or another diagnosis.',
          'output_schema': {'artifact_ref': views.ref, 'params': {k: task['public'][k] for k in ('object_count','hold_s')}}}}
    folder = output / family / task['task_id'] / 'skill'
    folder.mkdir()
    for attempt in range(1, 3):
        record = folder / f'proposal_{attempt:02d}'
        counts['proposer_calls'] += 1
        try:
            decision, meta = Client(**config['model']).chat(
                'You select an existing callable artifact skill. Reply with one JSON object containing only '
                'artifact_ref and params. Do not generate a controller or change any implementation.',
                json.dumps(packet, ensure_ascii=False), record / 'model')
            source = views.resolve(decision, task['public'])
            L.write_new(folder / 'invocation.json', decision)
            L.write_new(folder / 'binding.json', {**exported, 'resolved_code_sha256': M.digest_text(source),
                         'same_code_as_direct_projection': source == (output/'exports'/family/'code.py').read_text()})
            return source
        except (LLMReplyError, ValueError) as error:
            L.write_new(record / 'rejection.json', {'error': str(error)})
            counts['gate_rejections'] += 1
            if attempt == 2: return None
            packet['format_feedback'] = {'error': str(error), 'instruction': 'Correct this exact field error; one retry only.'}
        finally:
            account_model_call(counts, record)


def check_initial(task):
    path = ROOT / task['private']['initial_source']
    if sha(path) != task['private']['initial_sha256']:
        raise ValueError('registered initial changed: ' + str(path))


def run(output, family):
    config, registration = read(output/'config.json'), read(output/'registration.json')
    if inventory(output/'exports') != read(output/'store_frozen.json')['files']: raise ValueError('frozen export changed')
    if any(sha(ROOT/p) != h for p,h in registration['dependencies'].items()): raise ValueError('registered dependency changed')
    generated = registration['tasks'][family]; task = generated['tasks'][0]
    group = output/family; group.mkdir(exist_ok=False)
    folder = group/task['task_id']; folder.mkdir()
    counts = {'proposer_calls':0, 'critic_calls':0, 'gate_rejections':0, 'physical_episodes':0,
              'commands':0, 'worker_calls':0, 'simulation_s':0., 'llm_wall_s':0., 'prompt_tokens':0, 'completion_tokens':0}
    def episode(path, mode, source=None):
        check_initial(task)
        if family=='T01': result = T1.Episode(path, generated, config[family]['caps'], task).run(mode=mode,source=source)
        else:
            plan = {'plant':generated['plant'], 'body_geometry':read(ROOT/config[family]['geometry'])}
            result = T2.Episode(path,plan,config[family]['caps'],task).run(task['public'],mode=mode,source=source,
                                   task_input={k:task['public'][k] for k in ('object_count','hold_s')})
        counts['physical_episodes']+=1
        for key in ('commands','worker_calls'):counts[key]+=result[key]
        counts['simulation_s']+=result['simulation_seconds']
        print(json.dumps({'family':family,'arm':path.name,'success':result['success']}),flush=True)
        return result
    negative = episode(folder/'negative','wait')
    arms={};error=None;status='complete'
    if negative['success']:status='void'
    else:
        source=(output/'exports'/family/'code.py').read_text()
        arms['code']=episode(folder/'code','worker',source)
        if not arms['code']['success']:status='positive_failed'
        else:
            load_key()
            try:
                selected=select_skill(output,family,task,read(folder/'code/public_initial.json'),config,counts)
                if selected is not None:arms['skill']=episode(folder/'skill/execution','worker',selected)
                else:
                    arms['skill']={'success':False,'stage':'invocation_rejected','physical_episodes':0}
                    status='invocation_rejected'
            except LLMError as exc:
                status='gateway_stopped';error=str(exc)
    unchanged=inventory(output/'exports')==read(output/'store_frozen.json')['files']
    row={'task_id':task['task_id'],'initial_sha256':task['private']['initial_sha256'],'negative':negative,'arms':arms}
    L.write_new(group/'tasks.json',[row])
    summary={'family':family,'status':status if unchanged else 'void','registered_tasks':1,'counts':counts,
             'gateway_error':error,'exports_unchanged':unchanged,'skill_execution':'artifact_call',
             'arms':{arm:{'successes':int(r['success']),'evaluated':int('mode' in r),'stage':r.get('stage','physical')} for arm,r in arms.items()},
             'claim_ceiling':'same-artifact view binding on a known successful simulation initial; not controller learning or a library-benefit comparison'}
    L.write_new(group/'summary.json',summary)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run'])
    p.add_argument('--config',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--family',choices=['T01','T02'])
    a=p.parse_args();print(json.dumps(prepare(a.config,a.output.resolve()) if a.action=='prepare' else run(a.output.resolve(),a.family),indent=1),flush=True)
if __name__=='__main__':main()
