import copy
import unittest
from harness import t03_runtime as T

class T03BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fruit={'cup_bottom_position_m':[.4,.2,.17]}
        self.valid={'action':{'op':'done'},'state':{'routes':[{'yaw_rad':0.,'offset_m':[-.06,0.,0.], 'waypoints':[[.46,.2,.17]]}]}}

    def test_worker_cannot_bypass_route_interface_with_joint_actions(self):
        bad=copy.deepcopy(self.valid);bad['action']={'op':'set_joints','targets':{'waist_pitch_joint':1},'duration':.2}
        with self.assertRaisesRegex(ValueError,'action'):T.validate_reply(bad,self.fruit)

    def test_fabricated_grasp_location_is_rejected(self):
        bad=copy.deepcopy(self.valid);bad['state']['routes'][0]['waypoints'][-1][0]=.3
        with self.assertRaisesRegex(ValueError,'observed fruit'):T.validate_reply(bad,self.fruit)

    def test_legacy_path_only_for_engineering_baseline(self):
        value={'action':{'op':'done'},'state':{'legacy':True}}
        T.validate_reply(value,self.fruit,True)
        with self.assertRaises(ValueError):T.validate_reply(value,self.fruit)

    def test_boundaries_accept_valid_route(self):
        self.assertEqual(T.validate_reply(self.valid,self.fruit),self.valid['state'])

    def test_command_budget_prevents_dispatch(self):
        plant=object.__new__(T.BudgetPlant);plant.command_count=2;plant.caps={'commands':2}
        with self.assertRaisesRegex(RuntimeError,'COMMAND_BUDGET'):plant.dispatch({'op':'wait','duration':.2})
