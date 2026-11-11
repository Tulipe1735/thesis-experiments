import unittest
from harness import t03_placement as P
from harness.t03_placement import numeric_gate
class PlacementGateTests(unittest.TestCase):
 def test_real_tuple_worker_reply_becomes_schema_rejection(self):
  with self.assertRaisesRegex(ValueError,'not a tuple'):
   numeric_gate("def act(observation,task,state):\n return {'op':'done'}, {'offset_m':[0,.1,0]}\n")
 def test_bounded_release_clearance_and_no_downward_target(self):
  def reply(z):return {'action':{'op':'done'},'state':{'offset_m':[.01,.1,z]}}
  P.validate(reply(.02))
  for z in [-.01,.04]:
   with self.assertRaises(ValueError):P.validate(reply(z))
 def test_placement_leaf_cannot_emit_actuator_commands(self):
  with self.assertRaises(ValueError):P.validate({'action':{'op':'set_joints'},'state':{'offset_m':[0,.1,0]}})
