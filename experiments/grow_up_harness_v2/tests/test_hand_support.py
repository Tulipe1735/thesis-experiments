"""K2 hand rule v2: palm-mesh contacts are booked as hand, the wrist mesh stays non-hand."""
import unittest

try:
    import mujoco
    from harness import hand_support as H
    from experiments.t0_agent_v1.diversity_predicates import snapshot
except ImportError as exc:  # pragma: no cover - environment gate
    mujoco = None
    SKIP_REASON = f'MuJoCo is unavailable: {exc}'

BOX = '-.05 -.05 -.01  .05 -.05 -.01  -.05 .05 -.01  .05 .05 -.01  -.05 -.05 .01  .05 -.05 .01  -.05 .05 .01  .05 .05 .01'
# The wrist body carries the palm mesh and its own wrist mesh, like the G1 *_wrist_yaw_link.
SCENE = f'''<mujoco>
  <asset>
    <mesh name="left_hand_palm_link" vertex="{BOX}"/>
    <mesh name="left_wrist_yaw_link" vertex="{BOX}"/>
  </asset>
  <worldbody>
    <body name="left_wrist_yaw_link">
      <geom type="mesh" mesh="left_hand_palm_link" pos="0 0 .1"/>
      <geom type="mesh" mesh="left_wrist_yaw_link" pos=".3 0 .1"/>
    </body>
    <body name="cup" pos="0 0 .13"><freejoint name="cup_free"/><geom type="box" size=".02 .02 .02" mass=".2"/></body>
    <body name="can" pos=".3 0 .13"><freejoint name="can_free"/><geom type="box" size=".02 .02 .02" mass=".2"/></body>
  </worldbody>
</mujoco>'''
INSTANCE = {'objects': [{'name': 'cup', 'asset': {'kind': 'cup'}}, {'name': 'can', 'asset': {'kind': 'can'}}],
            'facilities': [], 'regions': []}


class PalmRuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if mujoco is None:
            raise unittest.SkipTest(SKIP_REASON)
        cls.model = mujoco.MjModel.from_xml_string(SCENE)
        cls.data = mujoco.MjData(cls.model)
        for _ in range(1000):
            mujoco.mj_step(cls.model, cls.data)
        cls.v1 = snapshot(cls.model, cls.data, INSTANCE)['objects']
        cls.v2 = H.snapshot(cls.model, cls.data, INSTANCE)['objects']

    def test_only_the_palm_mesh_is_found(self):
        self.assertEqual(sorted(H.palm_geoms(self.model).values()), ['left_hand_palm_link'])

    def test_cradled_target_moves_from_wrist_to_palm(self):
        self.assertEqual(list(self.v1['cup']['upward_support_N']), ['left_wrist_yaw_link'])
        self.assertEqual(self.v1['cup']['hand_contact_N'], 0.)
        self.assertEqual(list(self.v2['cup']['upward_support_N']), ['left_hand_palm_link'])
        self.assertGreater(self.v2['cup']['hand_contact_N'], 1.)
        self.assertAlmostEqual(self.v2['cup']['upward_support_N']['left_hand_palm_link'],
                               self.v1['cup']['upward_support_N']['left_wrist_yaw_link'])

    def test_wrist_mesh_support_is_unchanged(self):
        self.assertEqual(self.v2['can'], self.v1['can'])
        self.assertIn('left_wrist_yaw_link', self.v2['can']['upward_support_N'])


if __name__ == '__main__':
    unittest.main()
