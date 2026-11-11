"""T02 instance adapter for the shared registered FAST/SLOW accumulation loop."""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'experiments/grow_up_harness_v2'))
import grow
from harness import artifact_v2 as A,t02_generator as G,t02_episode as E
from harness.agent import check_source
from experiments.t0_agent_v1.common import sha,relative,source_hashes


class Run(grow.Run):
    def boundary(self):return 'MuJoCo simulation; T02 three-cup collection, sampled planar object poses'

    def positive_description(self):return self.config.get('positive_reference','visual_engineering')+' on the exact sampled initial; independently verified'

    def tree_path(self):
        return ROOT/'experiments/grow_up_harness_v2/artifacts_v2/task_tree_v2.json'

    def source(self):return G.SOURCE

    def generate_tasks(self,settings):
        if 'reuse' in settings:
            # Already-registered tasks, chosen by an earlier outcome; the reason is recorded, not hidden.
            source=json.loads((ROOT/settings['reuse']['registration']).read_text())['generated']
            wanted=settings['reuse']['task_ids']
            tasks=[t for t in source['tasks'] if t['task_id'] in wanted]
            if [t['task_id'] for t in tasks]!=wanted:raise ValueError(f'registered tasks not found: {wanted}')
            return {**source,'tasks':tasks,'count':len(tasks),'outcome_filter':settings['reuse']['reason'],
                    'reused_from':settings['reuse']['registration']}
        # Train and held-out seeds must differ; both sets are sampled before physics.
        directory=self.output/f"samples_{settings['seed']}";directory.mkdir(exist_ok=False)
        return G.generate(**settings,output=directory)

    def proposer_system(self):
        return grow.L.PROPOSER_SYSTEM.replace('LEFT arm.','LEFT arm and waist pitch.')+'''
T02 goal is THREE cups in the marked tray. The public observation supplies estimated cup_bottoms_m
and tray axes from head RGB-D, plus left arm/hand and waist_pitch_joint proprioception.
The same bounded outlet permits waist_pitch_joint; each command still has at most 14 joint targets.
Use the tray axes to allocate distinct slots; keep already placed cups clear. No object ground truth
is available. Contract task params are only object_count and hold_s; target estimates are observed.
A composite reply may also carry "new_leaves": [{"name": snake_case, "summary": str, "task_node": tree id,
"pre": [str], "post": [str], "source": str}] (at most 3). Refer to one in "ir" as {"use": "new:<name>", ...}.
New leaves declare the same params as the task (object_count, hold_s) and must bind them. They enter the
library only if the whole composite then succeeds under the independent evaluator.
'''+(('\nHUMAN DIAGNOSIS (from offline analysis of earlier episodes; a hint, not a guarantee):\n'
       +self.config['human_diagnosis']+'\n') if self.config.get('human_diagnosis') else '')

    def critic_system(self):
        return '''You diagnose why a T02 three-cup collection attempt failed. Reply with ONE JSON object:
{"failure_class": one of %s, "explanation": str, "advice": str}.
facts.cups gives, per cup, its final tray-frame position, footprint margin (>= 0.001 m needed),
floor support, hand contact, and how far it moved and how hard the hand touched it after it was
released. advice is one or two concrete code changes for the next attempt.''' % list(grow.L.FAILURE_CLASSES)


    def episode(self,folder,task,**kwargs):
        self.plan['positive_reference']=self.config.get('positive_reference','visual_engineering')
        result=E.Episode(folder,self.plan,self.config['caps'],task).run(task['public'],**kwargs)
        self.counts['physical_episodes']+=1
        self.counts['worker_calls']+=result['worker_calls'];self.counts['commands']+=result['commands']
        self.counts['simulation_s']+=result['simulation_seconds']
        if kwargs['mode']=='engineering':self.observation=json.loads((folder/'public_initial.json').read_text())
        print(json.dumps({'episode':grow.rel(folder),'success':result['success'],'label':result['facts']['rule_label']}),flush=True)
        return result

    def candidates(self,store,task):
        # FAST runs only artifacts whose effect is the whole task; per-cup leaves are parts, not candidates.
        goal=set(G.FAMILY['contract']['post']);rows=[]
        for ref in store.refs():
            artifact=store.load(ref)
            if (artifact.scope.task_family==G.FAMILY['task_family'] and goal<=set(artifact.contract.post)
                    and set(artifact.contract.params)<=set(task['public'])):
                stats=store.stats(ref);rows.append((-stats['successes'],stats['uses']-stats['successes'],ref))
        return [r for *_,r in sorted(rows)]

    def library_view(self,store,task):
        # Whole-task candidates first, then their parts with code, so a proposer can replace one part.
        if store is None:return []
        whole=self.candidates(store,task);parts=[r for r in store.refs() if r not in whole]
        view=[]
        for ref in (whole+parts)[:self.config['per_task']['library_shown']]:
            entry={'ref':ref,'kind':store.load(ref).kind,'skill':store.skill(ref)}
            if entry['kind']=='leaf':entry['code']=store.code(ref)
            view.append(entry)
        return view

    def before_store_add(self,store,data):
        # Only after an independent success: store the composite's new leaves, then the composite itself.
        for leaf,source in self.pending:
            store.put_source(source);store.add(leaf)

    def artifact_data(self,decision,task,store):
        self.pending=[]
        if isinstance(decision,dict) and decision.get('new_leaves') is not None:
            return self._with_new_leaves(decision,task,store)
        return self._plain(decision,task,store)

    def _plain(self,decision,task,store):
        if decision.get('kind')=='composite' and store is not None:
            for step in decision.get('ir') or []:
                if isinstance(step,dict) and isinstance(step.get('use'),str) and step['use'] not in store.refs():
                    raise ValueError(f"composite step uses {step['use']!r}, which is not in the library; "
                                     "reference an existing ref, or define it in new_leaves and use new:<name>")
        data,code=super().artifact_data(decision,task,store)
        data['scope']['initial_sha256']=[task['private']['initial_sha256']]
        if data['kind']=='composite':code=store.preview_code(data)
        return data,code

    def _with_new_leaves(self,decision,task,store):
        """Compile a composite whose new leaves live in a throwaway copy of the store; nothing is stored yet."""
        new=decision['new_leaves']
        if decision.get('kind')!='composite' or store is None:raise ValueError('new_leaves needs a composite reply and a library')
        if not isinstance(new,list) or not 1<=len(new)<=3:raise ValueError('new_leaves must be a list of 1-3 leaves')
        root=Path(tempfile.mkdtemp(prefix='preview_',dir=self.output))
        try:
            shutil.copytree(store.root,root/'store',ignore=shutil.ignore_patterns('snapshots','projections'))
            preview=A.Store(root/'store',store.tree);names={};pending=[]
            for item in new:
                if not isinstance(item,dict) or not isinstance(item.get('source'),str):raise ValueError('each new leaf needs a string source')
                label=item.get('name')
                try:check_source(item['source'])
                except grow.L.AgentSchemaError as error:raise ValueError(f'new leaf {label!r}: {error}') from None
                leaf={'schema':A.SCHEMA,'kind':'leaf','name':label,'task_node':item.get('task_node'),
                      'summary':item.get('summary') or '',
                      'contract':{'pre':item.get('pre') or [],'post':item.get('post') or [],
                                  'params':G.FAMILY['contract']['params'],'failure_codes':G.FAMILY['contract']['failure_codes']},
                      'scope':{'task_family':G.FAMILY['task_family'],'initial_sha256':[task['private']['initial_sha256']],
                               'plant_sha256':self.generated['plant']['sha256']},
                      'provenance':{'author':self.proposer.model,'parents':[],'created_on':task['task_id'],
                                    'note':'inline leaf of a composite reply'},
                      'implementation':{'language':'python','source_sha256':preview.put_source(item['source'])}}
                try:names['new:'+str(label)]=preview.add(leaf)
                except (ValueError,KeyError,TypeError) as error:raise ValueError(f'new leaf {label!r}: {error}') from None
                pending.append((leaf,item['source']))
            ir=[{**step,'use':names.get(step.get('use'),step.get('use'))} if isinstance(step,dict) else step
                for step in decision.get('ir') or []]
            data,code=self._plain({k:v for k,v in decision.items() if k!='new_leaves'}|{'ir':ir},task,preview)
        finally:
            shutil.rmtree(root)
        self.pending=pending
        return data,code

    def execute(self):
        extra=[Path(__file__),Path(G.__file__),Path(E.__file__),Path(E.verify.__code__.co_filename),
               ROOT/'experiments/t0_agent_v1/tray_tools.py',G.SOURCE/'physics_events.json',
               *sorted(G.SOURCE.glob('cup_attempt_*/actions.json'))]
        grow.L.write_new(self.output/'adapter_registration.json',{
            'task':'T02','boundary':'simulation','whole_task':'three simultaneously supported, released, stable cups',
            'positive_control':self.positive_description(),
            'negative_wait_s':2.,'private_joint_configuration':'original robot joints retained; object free qpos sampled',
            'evaluator':'t02-three-cup-strict-v1; original tray verifier plus unchanged 0.051 s gap bound',
            'sampling_radius_units':'metres, object planar jitter; not reach joint radians',
            'human_diagnosis_in_proposer_prompt':self.config.get('human_diagnosis'),
            'column_if_agent_solves':'agent success with human diagnostic hints' if self.config.get('human_diagnosis') else 'agent success',
            'dependencies':{**source_hashes(),**{relative(p):sha(p) for p in extra}}})
        return super().execute()


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();config=json.loads(args.config.read_text())
    args.output=args.output.resolve()
    if config.get('frontier_stage'):raise ValueError('T02 uses its own complete-task generator, not the reach frontier')
    if config['controls']['positive']!='all':raise ValueError('T02 requires a positive control for every task')
    # v2 caps: the fastest legal replay of the qualified targets needs 193.35 s and 1270 commands (runs/t02_worker_budget_20261107_001);
    # wall hit 1308 s at 184 simulated s (runs/t02_worker_dev_20261107_001).
    # Loosening approved 2026-11-07; v3 adds headroom for a slower authored retreat.
    if config['caps']['simulation_s']>300 or config['caps']['commands']>2200 or config['caps']['wall_s']>2700:
        raise ValueError('T02 caps exceed this registration')
    args.output.mkdir(parents=True,exist_ok=False)
    grow.L.write_new(args.output/'config.json',config)
    run=Run(config,args.output)
    try:
        summary=run.execute()
    except grow.LLMError as error:
        run.rows.close()
        summary={'status':'gateway_stopped','gateway_error':str(error),'counts':run.counts,
                 'completed_tasks':[json.loads(line) for line in (args.output/'tasks.jsonl').read_text().splitlines()],
                 'boundary':'incomplete run; unvisited tasks are not failures'}
        grow.L.write_new(args.output/'summary.json',summary)
    print(json.dumps(summary,indent=1),flush=True)
if __name__=='__main__':main()
