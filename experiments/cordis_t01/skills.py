"""Split the existing T01 controller at its grasp/place boundary; no new policy."""
import numpy as np

from experiments.t0_agent_v1.common import append_event, write_new
from experiments.t0_agent_v1.skills import ActionFailure
from experiments.t0_agent_v1.tray_tools import TrayCupTools, TrayTaskTools


class T01Skills:
    def __init__(self, port, folder):
        self.port, self.folder = port, folder
        self.stage = 'new'
        self.controller = None
        self.tool_steps = 0

    def require(self, stage):
        if self.stage != stage:
            raise ActionFailure(f'Contract requires {stage}; current stage is {self.stage}')

    def invoke(self, name):
        self.tool_steps += 1
        append_event(self.folder/'skill-steps.jsonl', dict(event='started', operation=name,
                     phase=self.controller.phase, simulation_seconds=self.port.state()['simulation_seconds']))
        result = getattr(self.controller, name)()
        append_event(self.folder/'skill-steps.jsonl', dict(event='completed', operation=name,
                     result=result, phase=self.controller.phase,
                     simulation_seconds=self.port.state()['simulation_seconds']))
        return result

    def inspect_scene(self):
        self.require('new')
        try:
            result = TrayTaskTools(self.port, self.folder, 1).inspect()
            tray = result['tray']
            folder = self.folder/'cup_attempt_01'
            folder.mkdir(exist_ok=False)
            target = np.asarray(tray['center_floor_pelvis_m'])
            self.controller = TrayCupTools(self.port, folder, tray, target, False, False, 0)
            write_new(folder/'visual_target.json', dict(target_pelvis_m=target.tolist(),
                      tray_observation=tray['observation_id'], allocation='one visual cup to tray center',
                      hidden_truth=False))
            self.stage = 'inspected'
            return dict(status='SCENE_BOUND', roles=['target_cup', 'target_tray'],
                        visible_cups=result['visible_uncollected_cups'], tray=tray,
                        ground_truth_used=False)
        except Exception:
            self.stage = 'failed'
            raise

    def grasp_cup(self):
        self.require('inspected')
        try:
            self.invoke('locate')
            self.invoke('prepare')
            plan = self.invoke('preflight')
            while not plan['reachable'] and plan['suggested_waist_pitch_rad'] is not None:
                self.invoke('adjust_reach')
                plan = self.invoke('preflight')
            if not plan['reachable']:
                raise ActionFailure('CUP_APPROACH_UNREACHABLE')
            for name in ('approach', 'close_and_test', 'lift_and_hold'):
                result = self.invoke(name)
            if self.controller.phase != 'complete' or not result['tactile']['passed']:
                raise ActionFailure('GRASP_POSTCONDITION_FAILED')
            self.stage = 'holding'
            return dict(status='HOLDING_EVIDENCE', object_role='target_cup',
                        tactile=result['tactile'], controller_phase=self.controller.phase,
                        evidence_limit='anonymous tactile load; not independent object/task verification')
        except Exception:
            self.stage = 'failed'
            raise
        finally:
            self.controller.save()

    def place_in_tray(self):
        self.require('holding')
        try:
            # Sensor check at the skill boundary; no object identity or hidden pose.
            holding = self.controller.tactile_gate('composition_before_place')
            for name in ('transfer', 'lower', 'release_and_retreat'):
                self.invoke(name)
            if self.controller.phase != 'placed':
                raise ActionFailure('PLACE_POSTCONDITION_FAILED')
            self.stage = 'placed'
            return dict(status='PLACEMENT_MOTION_ENDED_AWAIT_VERIFICATION',
                        target_role='target_tray', holding_precondition=holding['passed'],
                        release_command_executed=True, independent_task_success=False)
        except Exception:
            self.stage = 'failed'
            raise
        finally:
            self.controller.save()
