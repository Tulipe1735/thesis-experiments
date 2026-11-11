"""T02 task generation: single cup to tray slot.

Each task:
- private: joint configuration for positive control (joint interpolation path)
- public: cup_position_m, tray_position_m, slot_index, cup_quaternion_xyzw
"""
import hashlib
import json
import numpy as np
from pathlib import Path


def generate(seed: int, count: int, slot_target: str = "slot_0") -> list[dict]:
    """Generate T02 slot placement tasks.

    Args:
        seed: Random seed for task generation
        count: Number of tasks to generate
        slot_target: Target slot (slot_0, slot_1, slot_2)

    Returns:
        List of tasks, each with:
        - task_id: T02_<seed>_<index>
        - seed: actual seed used
        - private: {joint_configuration: dict}
        - public: {cup_position_m, cup_quaternion_xyzw, tray_position_m, slot_index}
    """
    rng = np.random.RandomState(seed)

    # Slot index mapping
    slot_map = {"slot_0": 0, "slot_1": 1, "slot_2": 2}
    slot_index = slot_map.get(slot_target, 0)

    tasks = []

    for i in range(count):
        task_seed = seed + i
        task_rng = np.random.RandomState(task_seed)

        # Sample cup position (simplified, needs actual initial state sampling)
        # Typical T02 cup range: x ∈ [-0.05, 0.05], y ∈ [0.30, 0.40], z ∈ [0.80, 0.85]
        cup_position = [
            task_rng.uniform(-0.05, 0.05),
            task_rng.uniform(0.30, 0.40),
            task_rng.uniform(0.80, 0.85)
        ]

        # Cup orientation (upright, slight variation)
        cup_quaternion_xyzw = [
            task_rng.uniform(-0.05, 0.05),  # small x tilt
            task_rng.uniform(-0.05, 0.05),  # small y tilt
            0.0,
            task_rng.uniform(0.99, 1.0)
        ]
        # Normalize
        norm = np.linalg.norm(cup_quaternion_xyzw)
        cup_quaternion_xyzw = [c / norm for c in cup_quaternion_xyzw]

        # Tray position (fixed for now, should load from scene)
        tray_position = [0.0, 0.55, 0.76]  # Approximate from 2401

        # Private: joint configuration (placeholder, needs actual sampling)
        joint_configuration = {
            "waist_yaw_joint": task_rng.uniform(-0.3, 0.3),
            "waist_pitch_joint": -0.15,
            "left_shoulder_pitch_joint": task_rng.uniform(0.2, 0.5),
            "left_shoulder_roll_joint": task_rng.uniform(0.3, 0.6),
            "left_elbow_joint": task_rng.uniform(0.8, 1.2),
        }

        task = {
            "task_id": f"T02_{task_seed:04d}",
            "seed": task_seed,
            "private": {
                "joint_configuration": joint_configuration,
                "note": "Generated; actual T02 needs real initial state sampling"
            },
            "public": {
                "cup_position_m": cup_position,
                "cup_quaternion_xyzw": cup_quaternion_xyzw,
                "tray_position_m": tray_position,
                "slot_index": slot_index,
                "slot_target": slot_target
            }
        }

        tasks.append(task)

    return tasks


def load_real_initial_state(seed: int) -> dict:
    """Load real T02 initial state from saved .npz (if exists).

    For 2400-2402, load from experiments/t0_agent_v1/tray_20261025_*/episodes/*/initial_state.npz
    For new seeds, generate via proper MuJoCo sampling.
    """
    # Placeholder: actual implementation needs to:
    # 1. Check if seed corresponds to existing episode
    # 2. Load initial_state.npz and extract qpos, qvel, cup/tray bodies
    # 3. Return as task-compatible dict

    known_initials = {
        2400: "experiments/t0_agent_v1/tray_20261025_001/episodes/2400_T02_scripted/initial_state.npz",
        2401: "experiments/t0_agent_v1/tray_20261025_001/episodes/2401_T02_scripted/initial_state.npz",
        2402: "experiments/t0_agent_v1/tray_20261025_001/episodes/2402_T02_scripted/initial_state.npz"
    }

    if seed in known_initials:
        # Load from disk
        # data = np.load(known_initials[seed])
        # return extract_public_params(data)
        pass

    # Generate new
    return None
