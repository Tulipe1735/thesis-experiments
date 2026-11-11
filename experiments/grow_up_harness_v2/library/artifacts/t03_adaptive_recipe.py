def act(observation, task, state):
    # Consumed 613003: index distal link contacted distractor_2 at grip_settle.
    # Index repair passed settle/test lift; middle distal then hit the can.
    # Add a bounded 4cm backward component to the existing main lift.
    return {
        "action": {"op": "done"},
        "state": {
            "parameters": {
                "offset_delta_m": [0.0, 0.0, -0.014],
                "preclose_fraction": 0.15,
                "palm_pitch_rad": 0.0,
                "hand_lead_rad": 0.06,
                "hand_kp": 6.0,
                "active_wait_hold": True,
                "pressure_target_N": 2.4,
                "index_scale": 0.7,
                "lift_retreat_m": 0.04,
            }
        },
    }
