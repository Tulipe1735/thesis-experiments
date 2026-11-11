#!/usr/bin/env python3
"""
Render videos from saved episodes.
Usage:
    python render_episode.py <episode_dir> <output.mp4> [--fps 30] [--camera head]
"""
import argparse
import json
import sys
from pathlib import Path
import numpy as np

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import mujoco
import mediapy


def render_episode(episode_dir: Path, output_path: Path, fps: int = 30, camera: str = 'head'):
    """Render a video from saved trajectory."""
    episode_dir = Path(episode_dir)

    # Load model reference
    model_ref = json.loads((episode_dir / 'model_reference.json').read_text())
    model_path = Path(model_ref['scene_path'])
    if not model_path.exists():
        # Try relative to thesis-experiments root
        model_path = Path(__file__).parent.parent.parent.parent / model_ref['scene_path']

    print(f"Loading model from: {model_path}")
    model = mujoco.MjModel.from_xml_path(str(model_path))
    data = mujoco.MjData(model)

    # Load trajectory
    traj_path = episode_dir / 'trajectory.npz'
    if not traj_path.exists():
        raise FileNotFoundError(f"No trajectory.npz in {episode_dir}")

    traj = np.load(traj_path, allow_pickle=False)
    qpos_seq = traj['qpos']

    print(f"Trajectory: {len(qpos_seq)} frames")

    # Setup renderer
    renderer = mujoco.Renderer(model, height=480, width=640)

    # Find camera ID
    try:
        camera_id = model.camera(camera).id
    except KeyError:
        print(f"Camera '{camera}' not found, using default")
        camera_id = 0

    # Render frames
    frames = []
    for i, qpos in enumerate(qpos_seq):
        if i % 10 == 0:
            print(f"  Rendering frame {i}/{len(qpos_seq)}", end='\r')

        data.qpos[:] = qpos
        mujoco.mj_forward(model, data)

        renderer.update_scene(data, camera=camera_id)
        pixels = renderer.render()
        frames.append(pixels)

    print(f"\nWriting video to {output_path}")
    mediapy.write_video(str(output_path), frames, fps=fps)
    print(f"Done: {len(frames)} frames @ {fps} fps = {len(frames)/fps:.1f}s")


def main():
    parser = argparse.ArgumentParser(description='Render episode video')
    parser.add_argument('episode_dir', type=Path, help='Episode directory with trajectory.npz')
    parser.add_argument('output', type=Path, help='Output video file (.mp4)')
    parser.add_argument('--fps', type=int, default=30, help='Frames per second')
    parser.add_argument('--camera', type=str, default='head', help='Camera name')

    args = parser.parse_args()

    render_episode(args.episode_dir, args.output, fps=args.fps, camera=args.camera)


if __name__ == '__main__':
    main()
