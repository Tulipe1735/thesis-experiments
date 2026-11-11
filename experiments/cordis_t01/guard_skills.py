"""Original skills plus an optional public-observation checkpoint before lowering."""
import numpy as np
from .skills import T01Skills,ActionFailure
from .handoff_guard import proposal,PerceptionError
from experiments.t0_agent_v1.common import write_new
from experiments.t0_agent_v1.tray_collision import CupObstaclePlanner


class GuardSkills(T01Skills):
    def __init__(self,*args):
        super().__init__(*args)
        self.alignment=None
        self.alignment_checks=0
        self.corrections=0

    def transfer_to_tray(self):
        self.require('holding')
        try:
            self.controller.tactile_gate('composition_before_place')
            result=self.invoke('transfer')
            self.stage='above_tray'
            return result
        except Exception:
            self.stage='failed';raise
        finally:self.controller.save()

    def inspect_alignment(self):
        self.require('above_tray')
        if self.alignment_checks or self.corrections:
            raise ActionFailure('Alignment checkpoint is allowed only once per placement')
        self.alignment_checks+=1
        observation=self.port.observe()
        try:
            result=proposal(observation,self.controller.offset,self.controller.tray)
        except PerceptionError as error:
            result=dict(status='KEEP_NOMINAL',confidence_passed=False,reason=str(error),
                        simulation_seconds=observation['simulation_seconds'],object_truth_used=False)
        result['observation_id']=observation['observation_id']
        result['simulation_seconds']=observation['simulation_seconds']
        if result['status']=='CORRECT':
            palm=self.controller.place_palm.copy()
            palm[:2]+=np.asarray(result['correction_xy_m'])
            trials=[];selected=None
            for height in (.12,.09,.06):
                goals=[('visual_centering',palm+[0.,0.,height]),('lower',palm+[0.,0.,.004])]
                path=CupObstaclePlanner([]).checked_path(self.port.state(),goals,self.controller.yaw)
                trials.append(dict(clearance_height_m=height,path=path))
                if path['reachable']:
                    selected=height;break
            result['preflight_trials']=trials
            if selected is None:
                result.update(status='KEEP_NOMINAL',reason='bounded centering path rejected; original path retained')
            else:
                result.update(proposed_place_palm_m=palm.tolist(),clearance_height_m=selected)
        self.alignment=result
        write_new(self.folder/'alignment_check.json',result)
        return result

    def correct_alignment(self):
        self.require('above_tray')
        if not self.alignment or self.alignment['status']!='CORRECT' or self.corrections:
            raise ActionFailure('A fresh bounded alignment proposal is required')
        if self.port.state()['simulation_seconds']!=self.alignment['simulation_seconds']:
            raise ActionFailure('Alignment proposal is stale')
        self.corrections+=1
        try:
            self.controller.place_palm=np.asarray(self.alignment['proposed_place_palm_m'])
            goal=self.controller.place_palm+[0.,0.,self.alignment['clearance_height_m']]
            self.controller.linear('visual_centering',goal,1.5)
            holding=self.controller.tactile_gate('after_visual_centering')
            return dict(status='BOUNDED_CENTERING_EXECUTED',correction_xy_m=self.alignment['correction_xy_m'],
                        holding_evidence=holding['passed'],independent_task_success=False)
        except Exception:
            self.stage='failed';raise
        finally:self.controller.save()

    def release_in_tray(self):
        self.require('above_tray')
        try:
            for name in ('lower','release_and_retreat'):self.invoke(name)
            if self.controller.phase!='placed':raise ActionFailure('PLACE_POSTCONDITION_FAILED')
            self.stage='placed'
            return dict(status='PLACEMENT_MOTION_ENDED_AWAIT_VERIFICATION',independent_task_success=False)
        except Exception:
            self.stage='failed';raise
        finally:self.controller.save()
