"""Explicit engineering tools, not autonomous joint-level skill synthesis."""
import math
import sys
import numpy as np

from .common import ROOT, relative
sys.path.insert(0, str(ROOT / 'grasp_optimization'))
from arm_planner import ArmPlanner, yaw_rotation
from run_direct_grasp import ActionFailure
from vision_grasp_v2 import VisionGraspV2

OPERATIONS = frozenset(('locate', 'prepare', 'preflight', 'adjust_reach', 'approach',
                       'close_and_test', 'lift_and_hold', 'transfer', 'lower',
                       'release_and_retreat', 'observe', 'finish', 'stop', 'run_candidate'))


def validate_action(value):
    if type(value) is not dict or set(value) != {'tool', 'arguments'}:
        raise ValueError('Expected tool/arguments object')
    name, args = value['tool'], value['arguments']
    if name not in OPERATIONS or type(args) is not dict:
        raise ValueError('Unknown tool or invalid arguments')
    if name == 'stop':
        if set(args) != {'reason'} or not isinstance(args['reason'], str) or not 1 <= len(args['reason'].strip()) <= 300:
            raise ValueError('Short stop reason required')
    elif args:
        raise ValueError('This tool takes no model-defined parameters')
    return name, args


def validate_program(program):
    # Declarative programs cannot access files, Python, truth or arbitrary parameters.
    if type(program) is not list or not 1 <= len(program) <= 12:
        raise ValueError('Expected a bounded list of engineering tools')
    for tool in program:
        validate_action(dict(tool=tool, arguments={}))
        if tool in ('stop', 'observe', 'adjust_reach', 'run_candidate'):
            raise ValueError('Nonlinear recovery is delegated to the supervisor')
    if program[-1] != 'finish' or program.count('finish') != 1:
        raise ValueError('Candidate must terminate exactly once at its end')
    return program


class CupTools(VisionGraspV2):
    def __init__(self, port, folder, task, offset):
        super().__init__(port, folder)
        self.task = task
        self.target_offset = np.asarray(offset, dtype=float)
        if self.target_offset.shape != (3,) or not np.isfinite(self.target_offset).all():
            raise ValueError('Invalid public displacement')
        if not -.07 <= self.target_offset[0] <= -.05 or abs(self.target_offset[1]) > .005 or self.target_offset[2] != 0:
            raise ValueError('Displacement outside pilot task envelope')
        self.memory_reference['source'] = relative(self.memory_path)
        # Legacy primitive writes an engineering reference during initialization.
        # Normalize its source path before this new episode is finalized.
        from diagnose_grasp import write_json
        write_json(folder / 'retrieved_engineering_memory.json', self.memory_reference)

    def transfer(self):
        if self.phase != 'complete' or self.task != 'place_cup':
            raise ActionFailure('Hold a lifted cup before transferring')
        self.tactile_gate('before_transfer')
        goal = self.palm + self.target_offset + [0., 0., .125]
        planner = ArmPlanner()
        trial = planner.start(self.port.state())
        # Robot-only kinematic check, explicitly not a collision guarantee.
        for point in (goal, self.palm + self.target_offset + [0., 0., .004]):
            if not planner.solve(trial, point, self.yaw)['reachable']:
                raise ActionFailure('PLACE_PATH_IK_REJECTED')
        self.linear('transfer', goal, 2.)
        self.tactile_gate('after_transfer')
        self.phase = 'transferred'
        return dict(status='TRANSFERRED_NOT_VERIFIED', actual_palm=self.port.state()['palms']['left'])

    def lower(self):
        if self.phase != 'transferred':
            raise ActionFailure('Transfer before lowering')
        self.linear('lower_to_table', self.palm + self.target_offset + [0., 0., .004], 2.5)
        self.phase = 'lowered'
        return dict(status='LOWERED_NOT_VERIFIED')

    def release_and_retreat(self):
        if self.phase != 'lowered':
            raise ActionFailure('Lower before release')
        names = [f'left_hand_{n}_joint' for n in ('thumb_0', 'thumb_1', 'thumb_2',
                                                'middle_0', 'middle_1', 'index_0', 'index_1')]
        self.action('release', 'set_joints', targets=dict.fromkeys(names, 0.), duration=1.5)
        self.action('release_settle', 'wait', seconds=.5)
        current = np.asarray(self.port.state()['palms']['left']['position_m'])
        retreat = current - yaw_rotation(self.yaw) @ [.10, 0., 0.]
        self.linear('retreat', retreat, 2.)
        self.linear('raise_after_release', retreat + [0., 0., .08], 1.5)
        self.action('placement_settle', 'wait', seconds=2.)
        self.phase = 'placed'
        return dict(status='PLACEMENT_MOTION_ENDED_AWAIT_INDEPENDENT_EVALUATION')
