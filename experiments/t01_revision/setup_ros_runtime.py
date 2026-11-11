"""Download signed ROS packages into a local prefix; never install system packages."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ['ros-jazzy-rclpy', 'ros-jazzy-std-msgs', 'ros-jazzy-std-srvs',
            'ros-jazzy-control-msgs', 'ros-jazzy-controller-manager',
            'ros-jazzy-forward-command-controller', 'ros-jazzy-joint-state-broadcaster',
            'ros-jazzy-ros2controlcli', 'ros-jazzy-hardware-interface', 'cmake']


def setup(folder):
    folder.mkdir(parents=True, exist_ok=False)
    for name in ['state/lists/partial', 'cache/archives/partial', 'log', 'rootfs']:
        (folder / name).mkdir(parents=True, exist_ok=True)
    key = folder / 'ros-archive-keyring.gpg'
    for attempt in range(4):
        try:
            with urllib.request.urlopen('https://raw.githubusercontent.com/ros/rosdistro/master/ros.key', timeout=30) as response:
                key.write_bytes(response.read())
            break
        except OSError:
            if attempt == 3:
                raise
            time.sleep(1)
    sources = folder / 'sources.list'
    sources.write_text(f'deb [arch=amd64 signed-by={key}] http://packages.ros.org/ros2/ubuntu noble main\n')
    options = ['-o', f'Dir::State={folder / "state"}',
               '-o', 'Dir::State::status=/var/lib/dpkg/status',
               '-o', f'Dir::Cache={folder / "cache"}',
               '-o', f'Dir::Log={folder / "log"}',
               '-o', f'Dir::Etc::sourcelist={sources}',
               '-o', 'Dir::Etc::sourceparts=/etc/apt/sources.list.d',
               '-o', 'Debug::NoLocking=true', '-o', 'APT::Sandbox::User=tulipe',
               '-o', 'Acquire::Retries=2']
    subprocess.run(['apt-get', *options, 'update'], check=True)
    subprocess.run(['apt-get', *options, 'install', '--download-only', '--no-install-recommends',
                    '--assume-yes', *PACKAGES], check=True)
    manifest = []
    for package in sorted((folder / 'cache/archives').glob('*.deb')):
        info = subprocess.check_output(['dpkg-deb', '-f', str(package), 'Package', 'Version'], text=True)
        digest = hashlib.sha256(package.read_bytes()).hexdigest()
        manifest.append(dict(file=str(package.relative_to(ROOT)), package_info=info.strip(), sha256=digest))
        subprocess.run(['dpkg-deb', '-x', str(package), str(folder / 'rootfs')], check=True)
    with (folder / 'manifest.json').open('x') as stream:
        json.dump(dict(date='2026-10-29', status='downloaded_and_extracted_not_runtime_verified',
                       rootless=True, system_packages_installed=False, requested=PACKAGES,
                       packages=manifest), stream, indent=2)
    print(json.dumps(dict(prefix=str((folder / 'rootfs/opt/ros/jazzy').relative_to(ROOT)),
                          downloaded_packages=len(manifest))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    setup(args.output.resolve())
