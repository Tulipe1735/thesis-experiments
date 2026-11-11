import unittest
from harness.frontier import author_gate, generate

class FrontierGateTests(unittest.TestCase):
    def test_only_capability_failure_and_empty_library_open(self):
        self.assertTrue(author_gate(True, [], 0, attempted_all=True)['open'])
        self.assertTrue(author_gate(True, [{'success':False,'label':'ORIENTATION'}],1,attempted_all=True)['open'])
        for label in ('INTERFACE','WORKER_ERROR','UNSAFE','BUDGET',None):
            self.assertFalse(author_gate(True,[{'success':False,'label':label}],1,attempted_all=True)['open'])
        self.assertFalse(author_gate(True,[{'success':False,'label':'NOT_HELD','evidence_status':'insufficient_sampling'}],1,attempted_all=True)['open'])
        self.assertFalse(author_gate(False,[],0,attempted_all=True)['open'])
        self.assertFalse(author_gate(True,[{'success':True}],1,attempted_all=True)['open'])
        self.assertFalse(author_gate(True,[],1,attempted_all=False)['open'])

    def test_unregistered_physics_stages_cannot_be_silently_run_as_reach(self):
        for stage in ('obstacle','pregrasp','lift'):
            with self.assertRaisesRegex(ValueError,'closed'):
                generate(stage,seed=1,count=1,radius_rad=.3)

class WorkerFaultGateTests(unittest.TestCase):
    def test_worker_exception_types_never_open_authorship(self):
        from harness.grow_loop import rule_label
        for error in ('WorkerError','WorkerOutputLimit','WorkerInputLimit','IsolationError'):
            facts={'execution_error':{'type':error,'message':'worker failed'},'guard':None,
                   'unsafe_frames':0,'final_position_error_m':.1,'final_orientation_error_rad':0.}
            label=rule_label({'verified_local_success':False},facts)
            self.assertEqual(label,'WORKER_ERROR')
            self.assertFalse(author_gate(True,[{'success':False,'label':label}],1,attempted_all=True)['open'])

class FrontierRunTests(unittest.TestCase):
    def test_task_orders_controls_and_reuse_before_authoring(self):
        import importlib.util
        import io
        import tempfile
        from pathlib import Path
        from unittest.mock import MagicMock
        root=Path(__file__).resolve().parents[3]
        spec=importlib.util.spec_from_file_location('frontier_grow',root/'experiments/grow_up_harness_v2/calibration/grow.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        cases=[(True,[],0,True),
               (True,[{'success':True,'label':None}],1,False),
               (True,[{'success':False,'label':'ORIENTATION'}],1,True),
               (True,[{'success':False,'label':'NOT_REACHED','execution_error':{'type':'UnknownFailure'}}],1,False),
               (True,[{'success':False,'label':'BUDGET'}],1,False),
               (False,[],0,False)]
        for positive,attempts,size,opens in cases:
            with self.subTest(positive=positive,attempts=attempts),tempfile.TemporaryDirectory() as tmp:
                runner=module.Run.__new__(module.Run)
                runner.config={'frontier_stage':'tight_pose','controls':{'positive':'all'}}
                runner.output=Path(tmp);runner.counts={'proposer_calls':0,'physical_episodes':0}
                runner.rows=io.StringIO();events=[]
                runner.episode=lambda *a,**kw: events.append('positive') or {'success':positive}
                runner.fast=lambda *a,**kw: events.append('fast') or attempts
                runner.candidates=lambda *a:list(range(size))
                runner.slow=lambda *a,**kw: events.append('slow') or {'solved':False,'attempts':[]}
                runner.task('train',{'task_id':'test','private':{'palm_travel_m':.1,'sampled_arm_q':{}}},MagicMock(),learn=True,scratch=False)
                self.assertEqual('slow' in events,opens)
                self.assertEqual(events[0],'positive')
                if opens:self.assertEqual(events,['positive','fast','slow'])
