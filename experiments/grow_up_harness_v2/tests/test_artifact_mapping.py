import json
import unittest
from pathlib import Path
from harness import artifact_mapping as M


class MappingTests(unittest.TestCase):
    def test_native_views_preserve_historically_successful_bytes(self):
        config=json.loads((M.ROOT/'experiments/grow_up_harness_v2/configs/artifact_mapping_repair_20261110.json').read_text())
        for family in ('T01','T02'):
            view=M.project(family,config[family])
            historical=json.loads((M.ROOT/config[family]['historical_success']).read_text())
            self.assertEqual(view.manifest['code_sha256'],historical['source_sha256'])
            task={'object_count':1 if family=='T01' else 3,'hold_s':1.0}
            self.assertEqual(view.resolve({'artifact_ref':view.ref,'params':task},task),view.code)
            self.assertIn(view.ref,view.card)
            if family=='T01':
                self.assertIn('Cartesian/waist',view.card)
                self.assertNotIn('Commands may ONLY be',view.card)

    def test_generated_source_wrong_ref_and_wrong_bindings_are_rejected(self):
        v=M.Views('T01','a@123','code','card',{'code_sha256':M.digest_text('code')})
        task={'object_count':1,'hold_s':1.0}
        for call in [{'source':'code'}, {'artifact_ref':'wrong','params':task},
                     {'artifact_ref':v.ref,'params':{'object_count':True,'hold_s':1.0}},
                     {'artifact_ref':v.ref,'params':{'object_count':1,'hold_s':2.0}}]:
            with self.assertRaises(ValueError):v.resolve(call,task)

    def test_stale_code_binding_cannot_execute(self):
        v=M.Views('T01','a@123','changed','card',{'code_sha256':M.digest_text('old')})
        with self.assertRaisesRegex(ValueError,'bound code differs'):
            v.resolve({'artifact_ref':v.ref,'params':{'object_count':1,'hold_s':1.0}}, {'object_count':1,'hold_s':1.0})


    def runner(self):
        import importlib.util
        path=M.ROOT/'experiments/grow_up_harness_v2/calibration/mapping_holdout.py'
        spec=importlib.util.spec_from_file_location('mapping_boundary_test',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_changed_initial_is_rejected_before_simulation(self):
        import tempfile,hashlib
        from unittest.mock import patch
        m=self.runner()
        with tempfile.TemporaryDirectory() as directory,patch.object(m,'ROOT',Path(directory)):
            p=Path(directory)/'initial.npz';p.write_bytes(b'original')
            task={'private':{'initial_source':'initial.npz','initial_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}}
            m.check_initial(task)
            p.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'registered initial changed'):m.check_initial(task)

    def test_rejected_invocation_is_not_a_physical_evaluation(self):
        import tempfile,hashlib
        from unittest.mock import patch
        m=self.runner()
        with tempfile.TemporaryDirectory() as directory,patch.object(m,'ROOT',Path(directory)):
            root=Path(directory);initial=root/'initial.npz';initial.write_bytes(b'saved initial')
            task={'task_id':'case','public':{'object_count':1,'hold_s':1.0},'private':{'initial_source':'initial.npz','initial_sha256':hashlib.sha256(initial.read_bytes()).hexdigest()}}
            exports=root/'exports/T01';exports.mkdir(parents=True);(exports/'code.py').write_text('frozen')
            (root/'config.json').write_text(json.dumps({'T01':{'caps':{}}}))
            (root/'registration.json').write_text(json.dumps({'dependencies':{},'tasks':{'T01':{'tasks':[task]}}}))
            (root/'store_frozen.json').write_text(json.dumps({'files':m.inventory(root/'exports')}))
            results=[False,True]
            def simulated_episode(self,mode,source=None):
                self.output.mkdir(parents=True);(self.output/'public_initial.json').write_text('{}')
                return {'success':results.pop(0),'mode':mode,'commands':1,'worker_calls':0,'simulation_seconds':.2}
            with patch.object(m,'load_key'),patch.object(m,'select_skill',return_value=None),patch.object(m.T1.Episode,'__init__',lambda self,path,*a:setattr(self,'output',path)),patch.object(m.T1.Episode,'run',simulated_episode):
                summary=m.run(root,'T01')
            self.assertEqual(summary['status'],'invocation_rejected')
            self.assertEqual(summary['arms']['skill']['evaluated'],0)
            self.assertEqual(summary['counts']['physical_episodes'],2)
