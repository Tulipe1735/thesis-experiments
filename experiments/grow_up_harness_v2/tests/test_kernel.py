import io
import unittest
from pathlib import Path

import mujoco

from harness import kernel as K

XML = '<mujoco><worldbody><body><freejoint/><geom size=".1"/></body></worldbody></mujoco>'


class StagesTest(unittest.TestCase):
    def test_chain_flattens_tools_in_order_with_both_preflights(self):
        tp01, tp04 = K.stages('TP01'), K.stages('TP04')
        self.assertEqual(tp01[:2], [('locate', 'locate'), ('grasp', 'preflight')])
        self.assertEqual([s for _, s in tp01].count('preflight'), 2)
        self.assertEqual(tp04[:len(tp01)], tp01)
        self.assertEqual(tp04[-1], ('place', 'release_and_retreat'))
        self.assertEqual(len(tp04), sum(len(K.TOOLS[t]) for t in K.CHAINS['TP04']))

    def test_only_the_first_stage_of_each_tool_opens_it(self):
        chain = K.stages('TP04')
        opened = [stage for k, (_, stage) in enumerate(chain) if K.starts_tool(chain, k)]
        self.assertEqual(opened, ['locate', 'preflight', 'transfer'])
        self.assertFalse(K.starts_tool(chain, chain.index(('grasp', 'prepare')) + 1))


class FreezeTest(unittest.TestCase):
    def roundtrip(self, value, links, out, live, new_out):
        stream = io.BytesIO()
        K._Freezer(stream, links, out).dump(value)
        return K._Thawer(io.BytesIO(stream.getvalue()), live, new_out).load()

    def test_links_rebind_paths_move_and_sharing_survives(self):
        model = mujoco.MjModel.from_xml_string(XML)
        old, new = mujoco.MjData(model), mujoco.MjData(model)
        shared = [1, 2]
        value = {'data': old, 'model': model, 'a': shared, 'b': shared, 'none': None,
                 'folder': Path('/run/source/tools'), 'memory': Path('/repo/memory.json')}
        back = self.roundtrip(value, {'data': old, 'model': model, 'renderer': None}, Path('/run/source'),
                              {'data': new, 'model': model}, Path('/run/resume'))
        self.assertIs(back['data'], new)
        self.assertIs(back['model'], model)
        self.assertIs(back['a'], back['b'])
        self.assertIsNone(back['none'])
        self.assertEqual(back['folder'], Path('/run/resume/tools'))
        self.assertEqual(back['memory'], Path('/repo/memory.json'))

    def test_unlinked_mujoco_object_is_refused(self):
        model = mujoco.MjModel.from_xml_string(XML)
        with self.assertRaisesRegex(TypeError, 'unlinked MuJoCo object'):
            K._Freezer(io.BytesIO(), {'model': model}, Path('/run')).dump({'extra': mujoco.MjData(model)})


if __name__ == '__main__':
    unittest.main()
