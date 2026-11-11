"""Process environment for the already extracted native kernel and generated Action."""
import os
import sys
import hashlib
from pathlib import Path
from experiments.t0_agent_v1.common import ROOT
from experiments.t01_revision.build_native import environment

NATIVE = ROOT / 'experiments/t01_revision/native_builds/jazzy_20261029_003'
INTERFACES = ROOT / 'experiments/ros_skill_cycle/interfaces/build_20261029_007'


def action_name(request_id):
    return '/thesis_skill/execute_'+hashlib.sha256(request_id.encode()).hexdigest()[:16]


def configured():
    env = environment(NATIVE)
    env['LD_LIBRARY_PATH'] = str(INTERFACES / 'lib') + ':' + env['LD_LIBRARY_PATH']
    env['PYTHONPATH'] = str(INTERFACES / 'python') + ':' + env['PYTHONPATH']
    env['ROS_LOG_DIR'] = str(ROOT / 'experiments/ros_skill_cycle/ros_logs')
    env['ROS_DOMAIN_ID'] = '152'
    env['THESIS_SKILL_CYCLE_ENV'] = '1'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['OPENBLAS_NUM_THREADS'] = '1'
    env['MUJOCO_GL'] = 'egl'
    return env


def bootstrap(module):
    if os.environ.get('THESIS_SKILL_CYCLE_ENV') != '1':
        os.execve(sys.executable, [sys.executable, '-B', '-m', module, *sys.argv[1:]], configured())
