import tempfile
import unittest
from pathlib import Path
import numpy as np
from harness import t02_generator as G

class T02SampleTests(unittest.TestCase):
    def test_seed_saves_actual_object_state_without_public_truth(self):
        with tempfile.TemporaryDirectory(dir=G.ROOT) as tmp:
            a=Path(tmp)/'a';b=Path(tmp)/'b';a.mkdir();b.mkdir()
            x=G.generate(94001,1,.002,output=a);y=G.generate(94001,1,.002,output=b)
            t=x['tasks'][0];u=y['tasks'][0]
            self.assertEqual(t['private']['object_free_qpos'],u['private']['object_free_qpos'])
            self.assertNotIn('object_free_qpos',t['public'])
            self.assertEqual(len(t['private']['object_free_qpos']),3)
            self.assertTrue((G.ROOT/t['private']['initial_source']).exists())
            with np.load(G.ROOT/t['private']['initial_source'],allow_pickle=False) as s:
                self.assertIn('mujoco_integration_state',s.files)
            self.assertEqual(t['public']['object_count'],3)
