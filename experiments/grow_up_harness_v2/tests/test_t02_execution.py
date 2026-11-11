import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'experiments/grow_up_harness_v2/calibration'))
from t02_execution import bind_slot, execute_batch
from harness import artifact as A

class T02ExecutionTests(unittest.TestCase):
    def test_nonexecuted_waypoint_stops_release(self):
        calls=[]
        def execute(command):
            calls.append(command['op'])
            return [{'status':'EXECUTED'},{'status':'ENDPOINT_TRACKING_ERROR'}]
        result=execute_batch([{'op':'move_linear'},{'op':'joints'}],execute,phase='lift',log=lambda x:None)
        self.assertEqual(calls,['move_linear'])
        self.assertEqual(result['response']['status'],'ENDPOINT_TRACKING_ERROR')

    def test_slot_selection_changes_executable_ir_without_touching_source(self):
        record=A.load(ROOT/'experiments/grow_up_harness_v2/artifacts/t02_slot_place.yaml')
        bound=bind_slot(record,'slot_2')
        self.assertIn("_place(params, PLACE_ABOVE_M, 'slot_2')",A.generate_code(bound))
        self.assertIn("_place(params, PLACE_ABOVE_M, 'slot_0')",A.generate_code(record))
        with self.assertRaises(ValueError):bind_slot(record,'missing')

    def test_wait_uses_guard_and_missing_motion_status_is_rejected(self):
        self.assertIsNone(execute_batch([{'op':'wait'}],lambda c:[{'guard':None}],phase='p',log=lambda x:None))
        self.assertIsNotNone(execute_batch([{'op':'wait'}],lambda c:[{'guard':'BUDGET'}],phase='p',log=lambda x:None))
        self.assertIsNotNone(execute_batch([{'op':'move'}],lambda c:[{}],phase='p',log=lambda x:None))

    def test_slot_hold_rejects_transient_success_and_missing_frames(self):
        from t02_execution import stable_slot
        cup={'footprint_margin_m':.005,'tray_floor_support_N':1.8,'hand_contact_N':0.,
             'other_object_contact_N':0.,'support_height_error_m':0.,'cup_tilt_deg':0.,
             'linear_speed_m_s':0.,'angular_speed_rad_s':0.,'pelvis_tilt_deg':0.,
             'pelvis_drift_m':0.,'cup_position_tray_m':[-.09,0.,0.]}
        rows=[{'time':i*.05,'cups':{'task_cup':cup}} for i in range(21)]
        self.assertTrue(stable_slot(rows,'task_cup',[-.09,0.])['stable_slot_success'])
        self.assertFalse(stable_slot(rows[:-1],'task_cup',[-.09,0.])['stable_slot_success'])
        self.assertFalse(stable_slot([r for i,r in enumerate(rows) if i!=10],'task_cup',[-.09,0.])['stable_slot_success'])
        self.assertFalse(stable_slot(rows,'task_cup',[.09,0.])['stable_slot_success'])

    def test_cli_cannot_report_tray_only_success_as_slot_success(self):
        import t02_slot_check
        from unittest.mock import patch
        with patch.object(t02_slot_check,'run',return_value={'single_cup_success':True,'slot_success':False}):
            with patch('builtins.print'):
                self.assertEqual(t02_slot_check.main(['--output','/tmp/t02-unused-test-output']),2)
