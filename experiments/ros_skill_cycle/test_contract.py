"""Regression and evidence gates that prevent invalid skill promotion/success claims."""
import unittest
from .public_check import verdict
from .run import select


class ContractTests(unittest.TestCase):
    def test_no_improvement_cannot_be_promoted(self):
        rows=[dict(arm=a,case_id='a',independent_success=True,low_level_command_calls=1,policy=dict(gain=.5))
              for a in ['nominal','candidate']]
        self.assertIsNone(select(rows)['selected'])

    def test_repair_does_not_hide_regression(self):
        rows=[]
        for arm,values in [('nominal',[False,True]),('candidate',[True,False])]:
            rows += [dict(arm=arm,case_id=str(i),independent_success=value,
                          low_level_command_calls=1,policy=dict(gain=.5)) for i,value in enumerate(values)]
        self.assertIsNone(select(rows)['selected'])
        self.assertEqual(select(rows)['candidates'][0]['regressed'],1)

    def test_candidate_selected_only_after_paired_repair(self):
        rows=[]
        for arm,values in [('nominal',[False,True]),('candidate',[True,True])]:
            rows += [dict(arm=arm,case_id=str(i),independent_success=value,
                          low_level_command_calls=1,policy=dict(gain=.5)) for i,value in enumerate(values)]
        self.assertEqual(select(rows)['selected']['repaired'],1)

    def test_missing_visual_evidence_is_not_success(self):
        self.assertEqual(verdict([dict(error='occluded')])['status'],'UNVERIFIED')

    def test_multiple_frames_without_elapsed_time_are_not_stability(self):
        samples=[dict(simulation_seconds=1.,center_in_tray_xy_m=[0.,0.],instantaneous_pass=True)]*3
        self.assertEqual(verdict(samples)['status'],'FAIL')

    def test_unstable_motion_is_not_success(self):
        samples=[dict(simulation_seconds=i*.5,center_in_tray_xy_m=[i*.01,0.],instantaneous_pass=True)
                 for i in range(3)]
        self.assertEqual(verdict(samples)['status'],'FAIL')

    def test_stable_confident_evidence_can_pass(self):
        samples=[dict(simulation_seconds=i*.5,center_in_tray_xy_m=[i*.0001,0.],instantaneous_pass=True)
                 for i in range(3)]
        self.assertEqual(verdict(samples)['status'],'PASS')


if __name__=='__main__':
    unittest.main()
