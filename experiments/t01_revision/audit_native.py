"""Audit native migrations against the already saved Python physical executions."""
import argparse
from pathlib import Path
import tempfile

from experiments.t0_agent_v1.common import ROOT, read, relative, sha, write_new
from experiments.t0_agent_v1.tray_verify import verify
from experiments.t0_agent_v1.runtime import mujoco


def audit(outputs, destination):
    destination.mkdir(parents=True, exist_ok=False)
    rows = []
    for output in outputs:
        registration, result = read(output / 'registration.json'), read(output / 'result.json')
        episode = ROOT / result['episode']
        expected = read(ROOT / registration['expected_reference'])
        ref = read(episode / 'model_reference.json')
        model = mujoco.MjModel.from_binary_path(str(ROOT / ref['path']))
        timestep = float(model.opt.timestep)
        with tempfile.TemporaryDirectory(prefix='native-t01-audit-') as temporary:
            verdict = verify(episode, execution_error=result['execution_error'], output=Path(temporary))
        checks = dict(source_input_bindings=all(sha(ROOT / p) == h for p, h in registration['bindings'].items()),
            independent_success=verdict['verified_success'] == result['verified_success'] == expected['verified_success'] == True,
            initial_identity=sha(episode / 'initial_state.npz') == result['initial_sha256'] == expected['initial_sha256'],
            trajectory_identity=sha(episode / 'trajectory.npz') == result['trajectory_sha256'] == expected['trajectory_sha256'],
            verdict_bound=sha(episode / 'independent_verification.json') == result['verdict_sha256'],
            stable_duration=abs(verdict['terminal_simultaneous_stable_s'] - result['terminal_stable_s']) < 1e-9,
            one_control_cycle_per_physics_step=result['kernel']['read_update_write_steps'] == round(result['simulation_seconds'] / timestep),
            actual_actuator_coverage=result['kernel']['actuator_count'] == model.nu,
            no_attach_or_external_force=verdict['equality_constraints'] == 0 and verdict['no_external_forces'],
            public_agent_telemetry_received=read(output / 'agent_kernel.json')['telemetry_received'] > 0,
            no_external_model=result['model_requests'] == 0,
            real_kernel_declared=result['ros2_execution'] and result['kernel']['reference_identity_checked_every_step'])
        rows.append(dict(output=relative(output), case_id=result['case_id'], policy=result['condition'],
            checks=checks, verified_success=result['verified_success'], terminal_stable_s=result['terminal_stable_s'],
            simulation_seconds=result['simulation_seconds'], actuator_count=model.nu,
            physical_control_period_s=timestep, native_cycles=result['kernel']['read_update_write_steps'],
            reference=registration['expected_reference'], trajectory_sha256=result['trajectory_sha256']))
    success = all(all(row['checks'].values()) for row in rows)
    report = dict(date='2026-10-29', boundary='simulation', status='passed' if success else 'failed',
        physical_episodes=len(rows), rows=rows, new_independent_initials=0, model_requests=0,
        interpretation='real control-kernel migration preserved these known physical executions; no performance gain inferred',
        limitations=['Agent Kernel uses local skill calls and real ROS topic telemetry; generic Skill Action transport is pending',
                     'interface-only ROS URDF; existing MuJoCo geometry/limits and original controller protections remain authoritative'])
    write_new(destination / 'audit.json', report)
    print(dict(status=report['status'], physical_episodes=len(rows), checks=sum(len(r['checks']) for r in rows)), flush=True)
    if not success:
        raise ValueError('Native audit mismatch retained')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit([p.resolve() for p in args.runs], args.output.resolve())
