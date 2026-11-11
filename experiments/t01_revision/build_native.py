"""Build a local ros2_control plugin against the signed extracted ROS prefix."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sysconfig

from experiments.t0_agent_v1.common import ROOT, read, relative, sha, write_new

RUNTIME = ROOT / 'experiments/t01_revision/runtime/ros_jazzy_20261029_002'


def environment(prefix):
    filesystem = RUNTIME / 'rootfs'
    ros = filesystem / 'opt/ros/jazzy'
    env = dict(os.environ)
    lib = [prefix / 'lib', ros / 'lib', ros / 'lib/x86_64-linux-gnu',
           filesystem / 'usr/lib/x86_64-linux-gnu', filesystem / 'usr/lib']
    lib.extend(p for p in (ros / 'opt').glob('*/lib') if p.is_dir())
    lib.extend(p for p in (ros / 'opt').glob('*/lib/x86_64-linux-gnu') if p.is_dir())
    env['LD_LIBRARY_PATH'] = ':'.join(map(str, lib)) + ':' + env.get('LD_LIBRARY_PATH', '')
    env['AMENT_PREFIX_PATH'] = ':'.join(map(str, [prefix, ros, *[p for p in (ros / 'opt').glob('*') if p.is_dir()]]))
    env['PYTHONPATH'] = ':'.join(map(str, [ros / 'lib/python3.12/site-packages',
                 Path(sysconfig.get_paths()['purelib']), filesystem / 'usr/lib/python3/dist-packages',
                 Path('/usr/lib/python3/dist-packages')])) + ':' + env.get('PYTHONPATH', '')
    env['ROS_LOG_DIR'] = str(prefix / 'ros_logs')
    env['ROS_DOMAIN_ID'] = '149'
    env['ROS_LOCALHOST_ONLY'] = '1'
    env['RMW_IMPLEMENTATION'] = 'rmw_fastrtps_cpp'
    return env


def build(output):
    if not (RUNTIME / 'manifest.json').exists():
        raise ValueError('Signed ROS runtime extraction is incomplete')
    ros = RUNTIME / 'rootfs/opt/ros/jazzy'
    system = RUNTIME / 'rootfs/usr'
    output.mkdir(parents=True, exist_ok=False)
    for path in ['lib', 'share/thesis_kernel', 'share/ament_index/resource_index/packages',
                 'share/ament_index/resource_index/hardware_interface__pluginlib__plugin',
                 'share/ament_index/resource_index/controller_interface__pluginlib__plugin', 'ros_logs']:
        (output / path).mkdir(parents=True, exist_ok=True)
    package = output / 'share/thesis_kernel'
    (package / 'package.xml').write_text('<package format="3"><name>thesis_kernel</name><version>0.1.0</version>'
        '<description>Simulation lockstep adapter</description><maintainer email="noreply@example.invalid">Thesis</maintainer>'
        '<license>Apache-2.0</license></package>\n')
    (output / 'share/ament_index/resource_index/packages/thesis_kernel').touch()
    for base, name, derived in [('hardware_interface', 'hardware', 'MujocoSystem'),
                                 ('controller_interface', 'controller', 'ReferenceController')]:
        (package / f'{name}_plugins.xml').write_text(f'<library path="thesis_kernel">'
            f'<class name="thesis_kernel/{derived}" type="thesis_kernel::{derived}" '
            f'base_class_type="{base}::{"SystemInterface" if name == "hardware" else "ControllerInterface"}"/>'
            '</library>\n')
        (output / f'share/ament_index/resource_index/{base}__pluginlib__plugin/thesis_kernel').write_text(
            f'share/thesis_kernel/{name}_plugins.xml\n')
    source = Path(__file__).with_name('native_control.cpp')
    shutil.copyfile(source, output / 'native_control.cpp')
    includes = [ros / 'include', system / 'include', system / 'include/eigen3']
    includes.extend(p for p in (ros / 'include').iterdir() if p.is_dir())
    command = ['g++', '-std=c++17', '-O2', '-shared', '-fPIC', '-pthread',
               *['-I' + str(p) for p in includes], str(source),
               '-L' + str(ros / 'lib'), '-L' + str(system / 'lib/x86_64-linux-gnu'),
               '-lcontroller_manager', '-lcontroller_interface', '-lhardware_interface',
               '-lrclcpp', '-lrclcpp_lifecycle', '-lrcl', '-lrcutils', '-lclass_loader',
               '-lrcpputils', '-lrcl_lifecycle', '-ldl',
               '-Wl,-rpath,' + str(ros / 'lib'), '-Wl,-rpath,' + str(system / 'lib/x86_64-linux-gnu'),
               '-o', str(output / 'lib/libthesis_kernel.so')]
    write_new(output / 'build_command.json', dict(command=command, source_sha256=sha(source),
                runtime_manifest_sha256=sha(RUNTIME / 'manifest.json')))
    with (output / 'build.log').open('x') as log:
        subprocess.run(command, env=environment(output), stdout=log, stderr=log, check=True)
    write_new(output / 'build_result.json', dict(status='compiled_not_runtime_verified',
        shared_library_sha256=sha(output / 'lib/libthesis_kernel.so'), source_sha256=sha(source)))
    print(relative(output), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args().output.resolve())
