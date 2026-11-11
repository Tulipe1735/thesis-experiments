import math

CHAIN = [
    ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), 'waist_yaw_joint', (0.0, 0.0, 1.0)),
    ((-0.0039635, 0.0, 0.044), (1.0, 0.0, 0.0, 0.0), 'waist_roll_joint', (1.0, 0.0, 0.0)),
    ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), 'waist_pitch_joint', (0.0, 1.0, 0.0)),
    ((0.0039563, 0.10022, 0.24778), (0.9902641396131312, 0.13920101962535997, 1.387220195578278e-05, -9.868681391343435e-05), 'left_shoulder_pitch_joint', (0.0, 1.0, 0.0)),
    ((0.0, 0.038, -0.013831), (0.9902682191424201, -0.13917203079821713, 0.0, 0.0), 'left_shoulder_roll_joint', (1.0, 0.0, 0.0)),
    ((0.0, 0.00624, -0.1032), (1.0, 0.0, 0.0, 0.0), 'left_shoulder_yaw_joint', (0.0, 0.0, 1.0)),
    ((0.015783, 0.0, -0.080518), (1.0, 0.0, 0.0, 0.0), 'left_elbow_joint', (0.0, 1.0, 0.0)),
    ((0.1, 0.00188791, -0.01), (1.0, 0.0, 0.0, 0.0), 'left_wrist_roll_joint', (1.0, 0.0, 0.0)),
    ((0.038, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), 'left_wrist_pitch_joint', (0.0, 1.0, 0.0)),
    ((0.046, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), 'left_wrist_yaw_joint', (0.0, 0.0, 1.0)),
]
PALM = (0.09, 0.0, 0.0)
DEFAULT_Q = {'waist_yaw_joint': 0.25, 'waist_roll_joint': 0.0, 'waist_pitch_joint': -0.15}
IK_JOINTS = ['left_shoulder_pitch_joint', 'left_shoulder_roll_joint', 'left_shoulder_yaw_joint', 'left_elbow_joint']
LIMITS = {'left_shoulder_pitch_joint': (-3.0, 2.6),
          'left_shoulder_roll_joint': (-1.5, 2.2),
          'left_shoulder_yaw_joint': (-2.5, 2.5),
          'left_elbow_joint': (-1.02, 2.05)}
RELEASE = [
    {'left_elbow_joint': -0.54943, 'left_shoulder_pitch_joint': -0.41799, 'left_shoulder_roll_joint': 0.57944, 'left_shoulder_yaw_joint': -0.59743, 'left_wrist_pitch_joint': 0.51067, 'left_wrist_roll_joint': -0.94166, 'left_wrist_yaw_joint': 0.80166},
    {'left_elbow_joint': -0.45821, 'left_shoulder_pitch_joint': -0.16357, 'left_shoulder_roll_joint': 0.50667, 'left_shoulder_yaw_joint': 0.08966, 'left_wrist_pitch_joint': 0.73745, 'left_wrist_roll_joint': -0.63918, 'left_wrist_yaw_joint': 0.24781},
    {'left_elbow_joint': -0.28745, 'left_shoulder_pitch_joint': -0.20823, 'left_shoulder_roll_joint': 0.61531, 'left_shoulder_yaw_joint': 0.42508, 'left_wrist_pitch_joint': 0.67563, 'left_wrist_roll_joint': -0.58815, 'left_wrist_yaw_joint': 0.30033},
]
FINAL = [
    {'left_elbow_joint': -1.00251, 'left_shoulder_pitch_joint': -0.65329, 'left_shoulder_roll_joint': 0.82256, 'left_shoulder_yaw_joint': -0.32922, 'left_wrist_pitch_joint': 0.66098, 'left_wrist_roll_joint': -1.7849, 'left_wrist_yaw_joint': 1.41215},
    {'left_elbow_joint': -0.78058, 'left_shoulder_pitch_joint': -0.23679, 'left_shoulder_roll_joint': 0.75027, 'left_shoulder_yaw_joint': 0.62633, 'left_wrist_pitch_joint': 1.25709, 'left_wrist_roll_joint': -1.56619, 'left_wrist_yaw_joint': 0.72429},
    {'left_elbow_joint': -0.58232, 'left_shoulder_pitch_joint': -0.11612, 'left_shoulder_roll_joint': 0.86993, 'left_shoulder_yaw_joint': 0.95035, 'left_wrist_pitch_joint': 1.17406, 'left_wrist_roll_joint': -1.13041, 'left_wrist_yaw_joint': 0.42144},
]
LIM = 0.028
STEP_S = 0.15
WAIT_S = 0.2
LIFT = 0.10
TOL = 0.008
MAX_STEPS = 24
LAM = 0.05


def _mm(A, B):
    return [[A[i][0] * B[0][j] + A[i][1] * B[1][j] + A[i][2] * B[2][j] for j in range(3)] for i in range(3)]


def _mv(A, v):
    return [A[i][0] * v[0] + A[i][1] * v[1] + A[i][2] * v[2] for i in range(3)]


def _q2m(q):
    w, x, y, z = q
    n = w * w + x * x + y * y + z * z
    s = 2.0 / n
    return [[1.0 - s * (y * y + z * z), s * (x * y - w * z), s * (x * z + w * y)],
            [s * (x * y + w * z), 1.0 - s * (x * x + z * z), s * (y * z - w * x)],
            [s * (x * z - w * y), s * (y * z + w * x), 1.0 - s * (x * x + y * y)]]


def _rot(axis, ang):
    x, y, z = axis
    c = math.cos(ang)
    s = math.sin(ang)
    C = 1.0 - c
    return [[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
            [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
            [z * x * C - y * s, z * y * C + x * s, c + z * z * C]]


def fk_palm(q):
    R = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    p = [0.0, 0.0, 0.0]
    for pos, quat, name, axis in CHAIN:
        d = _mv(R, pos)
        p = [p[0] + d[0], p[1] + d[1], p[2] + d[2]]
        R = _mm(R, _q2m(quat))
        R = _mm(R, _rot(axis, q.get(name, 0.0)))
    d = _mv(R, PALM)
    return [p[0] + d[0], p[1] + d[1], p[2] + d[2]], R


def _jac(q):
    base, _r = fk_palm(q)
    J = [[0.0, 0.0, 0.0, 0.0] for _ in range(3)]
    eps = 1e-4
    for k, name in enumerate(IK_JOINTS):
        q2 = dict(q)
        q2[name] = q.get(name, 0.0) + eps
        p2, _r2 = fk_palm(q2)
        for i in range(3):
            J[i][k] = (p2[i] - base[i]) / eps
    return J


def _solve(A, b):
    n = len(b)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for c in range(n):
        piv = c
        for r in range(c, n):
            if abs(M[r][c]) > abs(M[piv][c]):
                piv = r
        if abs(M[piv][c]) < 1e-12:
            return None
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        for j in range(c, n + 1):
            M[c][j] /= pv
        for r in range(n):
            if r != c:
                f = M[r][c]
                if abs(f) > 0.0:
                    for j in range(c, n + 1):
                        M[r][j] -= f * M[c][j]
    return [M[i][n] for i in range(n)]


def init(profile):
    return {'stage': 0, 'steps': 0, 'w': 0, 'cup': 0}


def act(observation, task, state):
    joints = observation['joints']
    q = {}
    for _pos, _quat, name, _axis in CHAIN:
        if name in joints:
            q[name] = joints[name]['target']
        else:
            q[name] = DEFAULT_Q.get(name, 0.0)

    if state.get('stage', 0) == 0:
        best = 0
        bestd = 1e9
        for i in range(len(RELEASE)):
            d = 0.0
            for name in RELEASE[i]:
                d += abs(q[name] - RELEASE[i][name])
            if d < bestd:
                bestd = d
                best = i
        state['cup'] = best
        p0, _r = fk_palm(q)
        qf = dict(q)
        qf.update(FINAL[best])
        pf, _r2 = fk_palm(qf)
        state['p0'] = [p0[0], p0[1], p0[2]]
        state['pf'] = [pf[0], pf[1], pf[2]]
        state['stage'] = 1
        state['steps'] = 0
        state['w'] = 0

    stage = state['stage']

    if stage in (1, 2, 3):
        p0 = state['p0']
        pf = state['pf']
        if stage == 1:
            tgt = [p0[0], p0[1], p0[2] + LIFT]
        elif stage == 2:
            tgt = [pf[0], pf[1], p0[2] + LIFT]
        else:
            tgt = [pf[0], pf[1], pf[2]]
        cur, _r = fk_palm(q)
        err = [tgt[0] - cur[0], tgt[1] - cur[1], tgt[2] - cur[2]]
        elen = math.sqrt(err[0] * err[0] + err[1] * err[1] + err[2] * err[2])
        state['steps'] += 1
        if elen < TOL or state['steps'] > MAX_STEPS:
            state['stage'] = stage + 1
            state['steps'] = 0
            return {'action': {'op': 'wait', 'duration': 0.1}, 'state': state}
        J = _jac(q)
        A = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        for i in range(3):
            for j in range(3):
                s = 0.0
                for k in range(4):
                    s += J[i][k] * J[j][k]
                A[i][j] = s
            A[i][i] += LAM * LAM
        y = _solve(A, err)
        if y is None:
            state['stage'] = stage + 1
            state['steps'] = 0
            return {'action': {'op': 'wait', 'duration': 0.1}, 'state': state}
        dq = []
        for k in range(4):
            s = 0.0
            for i in range(3):
                s += J[i][k] * y[i]
            dq.append(s)
        mx = 0.0
        for v in dq:
            mx = max(mx, abs(v))
        scale = 1.0
        if mx > LIM:
            scale = LIM / mx
        cart = 0.0
        for i in range(3):
            s = 0.0
            for k in range(4):
                s += J[i][k] * dq[k] * scale
            cart += s * s
        cart = math.sqrt(cart)
        if cart > 0.03:
            scale *= 0.03 / cart
        targets = {}
        for k, name in enumerate(IK_JOINTS):
            lo, hi = LIMITS[name]
            v = q[name] + dq[k] * scale
            v = max(lo, min(hi, v))
            if abs(v - q[name]) > 1e-9:
                targets[name] = v
        if not targets:
            state['stage'] = stage + 1
            state['steps'] = 0
            return {'action': {'op': 'wait', 'duration': 0.1}, 'state': state}
        return {'action': {'op': 'set_joints', 'targets': targets, 'duration': STEP_S}, 'state': state}

    if stage == 4:
        goal = FINAL[state['cup']]
        targets = {}
        done = True
        for name in goal:
            diff = goal[name] - q[name]
            if abs(diff) > 1e-3:
                done = False
                step = max(-LIM, min(LIM, diff))
                targets[name] = q[name] + step
        if done:
            hs = 1.0
            if task is not None and 'hold_s' in task:
                hs = float(task['hold_s'])
            if hs < 1.0:
                hs = 1.0
            state['n'] = int(math.ceil(hs / WAIT_S)) + 2
            state['w'] = 0
            state['stage'] = 5
            return {'action': {'op': 'wait', 'duration': 0.1}, 'state': state}
        return {'action': {'op': 'set_joints', 'targets': targets, 'duration': STEP_S}, 'state': state}

    if stage == 5:
        if state['w'] < state.get('n', 7):
            state['w'] += 1
            return {'action': {'op': 'wait', 'duration': WAIT_S}, 'state': state}
        state['stage'] = 6

    return {'action': {'op': 'done'}, 'state': state}
