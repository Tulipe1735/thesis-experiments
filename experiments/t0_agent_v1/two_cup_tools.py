"""Select distinct cups from RGB-D; adapt the prior engineering composition."""
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

from .common import append_event
from .skills import CupTools
from rgbd_cup import PerceptionError, from_observation, point_cloud
from run_direct_grasp import ActionFailure


def cup_hints(observation):
    rgb = np.asarray(Image.open(observation['head_rgb_path']).convert('RGB'), dtype=float)
    depth = np.load(observation['depth_path'], allow_pickle=False)
    cloud = point_cloud(depth, observation['K'], observation['T_optical_to_pelvis'])
    workspace = (np.isfinite(cloud).all(axis=-1) & (cloud[:, :, 0] > .1)
                 & (cloud[:, :, 0] < .75) & (cloud[:, :, 1] > -.12) & (cloud[:, :, 1] < .7))
    hist, edges = np.histogram(cloud[:, :, 2][workspace], bins=np.arange(-.1, .51, .002))
    if hist.max() < 400:
        raise PerceptionError('No visible table for multi-cup selection')
    mode = edges[int(hist.argmax())]+.001
    points = cloud[workspace & (np.abs(cloud[:, :, 2]-mode) < .004)][::4]
    plane = np.linalg.lstsq(np.c_[points[:, :2], np.ones(len(points))], points[:, 2], rcond=None)[0]
    height = cloud[:, :, 2] - (cloud[:, :, :2] @ plane[:2] + plane[2])
    mask = workspace & (rgb.min(axis=-1) > 95) & (np.ptp(rgb, axis=-1) < 35) & (height > .012) & (height < .115)
    labels, count = ndimage.label(mask)
    hints = []
    for label in range(1, count+1):
        v, u = np.where(labels == label)
        if len(v) >= 150:
            hints.append([float(np.median(u)), float(np.median(v))])
    return hints


def detect_cups(observation):
    candidates = []
    for hint in cup_hints(observation):
        try:
            item = from_observation(observation, pixel_hint=hint)
        except PerceptionError:
            continue
        if not any(np.linalg.norm(np.array(item['cup_bottom_position_m'])-
                                  np.array(old['cup_bottom_position_m'])) < .03 for old in candidates):
            candidates.append(item)
    candidates.sort(key=lambda item: item['cup_bottom_position_m'][1], reverse=True)
    if len(candidates) != 2:
        raise PerceptionError(f'Expected two separately visible fitted cups, found {len(candidates)}')
    if candidates[0]['cup_bottom_position_m'][1] - candidates[1]['cup_bottom_position_m'][1] < .10:
        raise PerceptionError('Ambiguous left/right cup identity')
    return dict(left=candidates[0], right=candidates[1])


class SelectedCupTools(CupTools):
    def __init__(self, port, folder, offset, selection, subsequent=False):
        super().__init__(port, folder, 'place_cup', offset)
        self.selection, self.subsequent = selection, subsequent

    def locate(self, pixel_hint=None):
        if self.phase not in ('initial', 'ready'):
            raise ActionFailure('Cannot relocalize during manipulation')
        observation = self.port.observe()
        found = detect_cups(observation)
        result = dict(found[self.selection], selection=self.selection,
                      selection_rule='descending observed pelvis y; both distinct visual candidates required')
        self.estimate = result
        self.estimates.append(result)
        self.save()
        if self.initial_visual_cup is None:
            self.initial_visual_cup = np.array(result['cup_bottom_position_m'])
        return result

    def prepare(self):
        if not self.subsequent:
            return super().prepare()
        if self.phase != 'initial':
            raise ActionFailure('Prepare is only allowed once per cup')
        # The previous grasp already released and raised the hand. Keep it high
        # while returning; the old initial low waypoint can hit the placed cup.
        current = np.asarray(self.port.state()['palms']['left']['position_m'])
        self.action('second_raise_vertical', 'move_ee', side='left',
                    position=[float(current[0]), float(current[1]), .30], duration=1.5)
        self.action('second_return_clear', 'move_ee', side='left', position=[-.04, .34, .30],
                    quaternion_xyzw=[0., 0., 0., 1.], duration=2.)
        self.phase = 'ready'
        return self.locate()


class TwoCupTools:
    def __init__(self, port, folder, offset, program):
        self.port, self.folder, self.offset = port, Path(folder), offset
        self.program = program
        self.completed = []
        self.tool_steps = 0

    def inspect(self):
        return dict(candidates=detect_cups(self.port.observe()),
                    motion_completed=list(self.completed), independent_verification_pending=True)

    def place(self, selection):
        if selection not in ('left', 'right') or selection in self.completed:
            raise ActionFailure('Select a distinct not-yet-placed cup')
        folder = self.folder / ('cup_' + selection)
        folder.mkdir(exist_ok=False)
        controller = SelectedCupTools(self.port, folder, self.offset, selection, bool(self.completed))
        try:
            for operation in self.program:
                if operation == 'finish':
                    if controller.phase != 'placed':
                        raise ActionFailure('Incomplete single-cup composition')
                    break
                result = getattr(controller, operation)()
                self.tool_steps += 1
                append_event(self.folder / 'candidate_execution.jsonl', dict(selection=selection,
                             tool=operation, result=result, phase_after=controller.phase))
                if operation == 'preflight' and not result['reachable']:
                    raise ActionFailure('TWO_CUP_PATH_UNREACHABLE')
            if controller.phase != 'placed':
                raise ActionFailure('Composition did not place the selected cup')
            self.completed.append(selection)
            return dict(status='SELECTED_CUP_MOTION_COMPLETED_NOT_VERIFIED', selection=selection,
                        completed=list(self.completed), tools_executed=self.tool_steps)
        finally:
            controller.save()

    def finish(self):
        if set(self.completed) != {'left', 'right'}:
            raise ActionFailure('Both distinct cups must complete before finish')
        return dict(status='ENDED_FOR_TWO_CUP_INDEPENDENT_VERIFICATION')
