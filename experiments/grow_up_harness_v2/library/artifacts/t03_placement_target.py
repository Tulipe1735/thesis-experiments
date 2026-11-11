def act(observation, task, state):
    # Local placement-target selection only.
    # Preserve the proven planar offset that avoided the inward shoulder collision.
    dx = 0.01
    dy = 0.10
    # Bounded nominal release clearance above the camera-estimated platter floor.
    # The fruit is already platter-supported during descent; a positive z keeps the
    # unchanged lower controller from overpressing the floor/hand and tripping the
    # 15mm endpoint check, while still allowing normal release above the platter.
    dz = 0.02
    return {"action": {"op": "done"}, "state": {"offset_m": [dx, dy, dz]}}
