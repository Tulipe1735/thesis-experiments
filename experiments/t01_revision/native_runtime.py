"""Typed Python binding and a non-physical ros2_control lifecycle/resource probe."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys

import numpy as np

from experiments.t0_agent_v1.common import ROOT, relative, sha, write_new
from experiments.t01_revision.build_native import environment


def bootstrap(prefix, module):
    if os.environ.get('THESIS_ROS_PREFIX') != str(prefix):
        env = environment(prefix)
        env['THESIS_ROS_PREFIX'] = str(prefix)
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env['OPENBLAS_NUM_THREADS'] = '1'
        os.execve(sys.executable, [sys.executable, '-B', '-m', module, *sys.argv[1:]], env)


class NativeControl:
    def __init__(self, prefix, names, timestep):
        self.names = list(names)
        self.steps = 0
        self.path = prefix / 'lib/libthesis_kernel.so'
        self.lib = ctypes.CDLL(str(self.path), mode=ctypes.RTLD_GLOBAL)
        self.lib.thesis_error.restype = ctypes.c_char_p
        self.lib.thesis_create.argtypes = [ctypes.c_char_p, ctypes.c_double]
        pointer = ctypes.POINTER(ctypes.c_double)
        self.lib.thesis_step.argtypes = [pointer, pointer, pointer, pointer, ctypes.c_int]
        self.lib.thesis_updates.restype = ctypes.c_uint64
        self.lib.thesis_writes.restype = ctypes.c_uint64
        self.lib.thesis_destroy.restype = None
        code = self.lib.thesis_create('\n'.join(self.names).encode(), timestep)
        if code:
            message = self.lib.thesis_error().decode()
            self.lib.thesis_destroy()
            raise RuntimeError(message)

    def _check(self, code):
        if code:
            raise RuntimeError(self.lib.thesis_error().decode())

    def step(self, positions, velocities, desired):
        arrays = [np.ascontiguousarray(x, dtype=np.float64) for x in [positions, velocities, desired]]
        if any(x.shape != (len(self.names),) for x in arrays):
            raise ValueError('Actuator state shape mismatch')
        accepted = np.zeros(len(self.names), dtype=np.float64)
        pointer = ctypes.POINTER(ctypes.c_double)
        self._check(self.lib.thesis_step(*[x.ctypes.data_as(pointer) for x in arrays],
                    accepted.ctypes.data_as(pointer), len(self.names)))
        if not np.array_equal(accepted, arrays[2]):
            raise RuntimeError('Managed controller changed a reference')
        self.steps += 1
        return accepted

    def conflict_probe(self):
        self._check(self.lib.thesis_conflict_probe())

    def summary(self):
        return dict(runtime='real ros2_control ControllerManager', read_update_write_steps=self.steps,
                    controller_updates=int(self.lib.thesis_updates()), hardware_writes=int(self.lib.thesis_writes()),
                    actuator_count=len(self.names), reference_identity_checked_every_step=True,
                    shared_library_sha256=sha(self.path), model_weight_updates=0,
                    command_limit_policy='original MuJoCo/robot guards retained; CM extra command clamping disabled')

    def close(self):
        self.lib.thesis_destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prefix, output = args.build.resolve(), args.output.resolve()
    bootstrap(prefix, 'experiments.t01_revision.native_runtime')
    output.mkdir(parents=True, exist_ok=False)
    control = None
    try:
        control = NativeControl(prefix, ['probe_joint_1', 'probe_joint_2'], .002)
        for x in [0., .1, -.1]:
            control.step([x, -x], [0., 0.], [.25 + x, -.25 - x])
        control.conflict_probe()
        before = control.steps
        try:
            control.step([float('nan'), 0.], [0., 0.], [0., 0.])
            raise AssertionError('Non-finite input accepted')
        except RuntimeError as error:
            if 'Non-finite' not in str(error):
                raise
        assert control.steps == before
        control.step([0., 0.], [0., 0.], [.4, -.4])
        result = dict(status='passed', physics_steps=0, boundary='non_physical_interface_probe',
                      resource_conflict_rejected=True, non_finite_rejected_before_physics=True,
                      evidence=control.summary())
        write_new(output / 'result.json', result)
        print(json.dumps(result), flush=True)
    except Exception as error:
        write_new(output / 'failure.json', dict(status='failed', error=str(error), physics_steps=0))
        raise
    finally:
        if control is not None:
            control.close()


if __name__ == '__main__':
    main()
