"""Deterministic physical grasp diagnostics; no network, model calls, or cup binding."""
import argparse
import json
import os
from pathlib import Path

os.environ.setdefault('MUJOCO_GL', 'egl')
import mujoco
import numpy as np

from pantry_robot import PantryRobot

ROOT = Path(__file__).resolve().parent
PREVIOUS = Path(json.loads((ROOT / 'source_provenance.json').read_text())['source_root'])


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def contacts(model, data, context):
    rows = []
    for index in range(data.ncon):
        contact = data.contact[index]
        geoms = [int(contact.geom1), int(contact.geom2)]
        bodies = [model.body(int(model.geom_bodyid[g])).name or 'world' for g in geoms]
        if not any('_hand_' in b or b == 'task_cup' for b in bodies):
            continue
        force = np.empty(6)
        mujoco.mj_contactForce(model, data, index, force)
        if force[0] < (.001 if 'task_cup' in bodies else .05):
            continue
        names = [model.geom(g).name or f'geom_{g}' for g in geoms]
        rows.append(dict(bodies=bodies, geoms=names,
                         sources=[context['collider_source_map'].get(n, n) for n in names],
                         normal_force_N=float(force[0]), penetration_m=max(0., -float(contact.dist)),
                         position_sim_m=contact.pos.tolist(), normal=contact.frame[:3].tolist()))
    return rows


def snapshot(robot, stage):
    m, d = robot.model, robot.data
    base = d.xmat[robot.pelvis_id].reshape(3, 3)
    cup = d.xpos[robot.cup_id]
    palm = m.site('left_palm').id
    hand_rotation = d.site_xmat[palm].reshape(3, 3)
    return dict(stage=stage, time=float(d.time), cup_position_sim_m=cup.tolist(),
                cup_position_pelvis_m=(base.T @ (cup-d.xpos[robot.pelvis_id])).tolist(),
                cup_position_palm_m=(hand_rotation.T @ (cup-d.site_xpos[palm])).tolist(),
                cup_tilt_deg=float(np.degrees(np.arccos(np.clip(d.xmat[robot.cup_id, 8], -1, 1)))),
                lift_m=float(cup[2]-robot.cup_initial_z),
                palms={side: robot.fk(side) for side in ('left', 'right')},
                contacts=contacts(m, d, robot.context), guard=robot.guard)


class DiagnosticRobot(PantryRobot):
    def __init__(self, folder, seed=1000, budget=180.):
        self.diagnostics = []
        self.stage = 'initial'
        super().__init__(folder, seed, budget)

    def _step(self):
        count = len(self.trace)
        super()._step()
        if len(self.trace) != count:
            self.diagnostics.append(snapshot(self, self.stage))

    def checkpoint(self, stage, images=False):
        row = snapshot(self, stage)
        self.diagnostics.append(row)
        loads = {}
        for c in row['contacts']:
            if any('_hand_' in b for b in c['bodies']):
                key = ' / '.join(c['bodies']) + ' : ' + ' / '.join(c['sources'])
                loads[key] = round(loads.get(key, 0.) + c['normal_force_N'], 3)
        print(json.dumps(dict(stage=stage, time=round(row['time'], 3),
                              cup_palm=np.round(row['cup_position_palm_m'], 4).tolist(),
                              lift=round(row['lift_m'], 4), tilt=round(row['cup_tilt_deg'], 2),
                              hand_contacts=loads), ensure_ascii=False), flush=True)
        if images:
            self.observe()
        return row

    def finish(self):
        result = super().finish()
        write_json(self.folder / 'contact_trace.json', self.diagnostics)
        return result


def inspect_previous():
    results = {}
    for name in json.loads((ROOT / 'source_provenance.json').read_text())['reference_episodes']:
        folder = PREVIOUS / 'episodes' / name
        model = mujoco.MjModel.from_binary_path(str(folder / 'model.mjb'))
        data = mujoco.MjData(model)
        saved = np.load(folder / 'final_state.npz')
        mujoco.mj_setState(model, data, saved['mujoco_integration_state'], mujoco.mjtState.mjSTATE_INTEGRATION)
        mujoco.mj_forward(model, data)
        context = json.loads((folder / 'runtime_context.json').read_text())
        rows = contacts(model, data, context)
        results[name] = dict(time=float(data.time), contacts=rows,
                             force_note='Recomputed from saved integration state, not a new physical step')
        print(name, json.dumps(rows, ensure_ascii=False), flush=True)
    (ROOT / 'reports').mkdir(exist_ok=True)
    write_json(ROOT / 'reports/previous_contacts.json', results)


def baseline(folder):
    folder.mkdir(parents=True, exist_ok=False)
    robot = DiagnosticRobot(folder, budget=120.)
    write_json(folder / 'run_config.json', dict(seed=1000, branch='direct-frozen-baseline',
               model_requests=0, camera_version=robot.context['head_camera']['version'],
               execution_mode='replay_old_action_arguments_with_current_runtime', formal_task_snapshot=False))
    robot.advance(1., 'episode_initial_settling')
    robot.checkpoint('settled', images=True)
    decisions = json.loads((PREVIOUS / 'episodes/pantry_agent_20261023_214553_515599/decisions.json').read_text())
    try:
        for decision in decisions:
            robot.stage = f"round_{decision['round']}_fixed_wait"
            robot.advance(decision['model_wait_wall_seconds'], 'fixed_reference_wait')
            for tool in decision['plan']['actions']:
                if tool['tool'] not in ('move_ee', 'set_joints', 'wait'):
                    continue
                robot.stage = f"round_{decision['round']}_{tool['tool']}"
                output = getattr(robot, tool['tool'])(**tool['arguments'])
                print(robot.stage, json.dumps(output), flush=True)
                robot.checkpoint(robot.stage, images=True)
    finally:
        result = robot.finish()
    print('BASELINE_RESULT', json.dumps(result), flush=True)
    return result['independent_success']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['previous', 'baseline'])
    parser.add_argument('--output', type=Path, default=ROOT / 'episodes/baseline_001')
    args = parser.parse_args()
    if args.mode == 'previous':
        inspect_previous()
    else:
        raise SystemExit(0 if baseline(args.output) else 1)
