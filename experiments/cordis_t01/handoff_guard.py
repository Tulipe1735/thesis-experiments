"""One bounded visual centering proposal from public RGB-D and proprioception only."""
import math
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

from experiments.t0_agent_v1.runtime import CountedPort,mujoco  # initializes existing sensor/controller imports
from arm_planner import ArmPlanner
from rgbd_cup import point_cloud,PerceptionError

RADIUS=.041
TRIGGER_M=.008
MAX_CORRECTION_M=.040


def circle(points, expected):
    if len(points)<100:
        raise PerceptionError('Insufficient visible held-cup wall points')
    points=points[::max(1,len(points)//1600)]
    rng=np.random.default_rng(7401)
    best=None
    for _ in range(400):
        a,b=points[rng.choice(len(points),2,replace=False)]
        delta=b-a;distance=np.linalg.norm(delta)
        if not .008<distance<2*RADIUS:
            continue
        normal=np.array([-delta[1],delta[0]])/distance
        shift=normal*math.sqrt(RADIUS**2-distance**2/4)
        for center in ((a+b)/2+shift,(a+b)/2-shift):
            if np.linalg.norm(center-expected)>.05:
                continue
            inliers=np.abs(np.linalg.norm(points-center,axis=1)-RADIUS)<.0025
            score=int(inliers.sum())
            if best is None or score>best[0]:best=(score,center)
    if best is None:
        raise PerceptionError('No bounded held-cup circle proposal')
    center=best[1]
    for _ in range(3):
        inliers=np.abs(np.linalg.norm(points-center,axis=1)-RADIUS)<.003
        if inliers.sum()<100:
            raise PerceptionError('Too few held-cup circle inliers')
        center=least_squares(lambda xy:np.linalg.norm(points[inliers]-xy,axis=1)-RADIUS,
                             center,loss='soft_l1',f_scale=.001).x
    error=np.linalg.norm(points[inliers]-center,axis=1)-RADIUS
    rms=float(np.sqrt(np.mean(error**2)))
    fraction=float(np.mean(inliers))
    angles=np.arctan2(points[inliers,1]-center[1],points[inliers,0]-center[0])
    resultant=float(abs(np.mean(np.exp(1j*angles))))
    if rms>.002 or fraction<.55 or resultant>.98:
        raise PerceptionError(f'Held-cup circle confidence rejected: rms={rms:.5f}, fraction={fraction:.3f}, resultant={resultant:.3f}')
    return dict(center_xy_m=center.tolist(),rms_m=rms,inlier_fraction=fraction,
                points=len(points),angular_resultant=resultant)


def robot_self_mask(observation, depth):
    """Predict robot pixels from the public body model and measured joints, never the task model."""
    planner=ArmPlanner()
    with tempfile.TemporaryDirectory() as temporary:
        path=Path(temporary)/'robot.xml'
        mujoco.mj_saveLastXML(str(path),planner.model)
        root=ET.parse(path).getroot()
    transform=np.asarray(observation['T_optical_to_pelvis'])
    rotation=Rotation.from_matrix(transform[:3,:3]@np.diag([1.,-1.,-1.])).as_quat()
    height,width=depth.shape
    visual=root.find('visual')
    if visual is None:visual=ET.SubElement(root,'visual')
    global_view=visual.find('global')
    if global_view is None:global_view=ET.SubElement(visual,'global')
    global_view.set('offwidth',str(width));global_view.set('offheight',str(height))
    fovy=math.degrees(2*math.atan(height/(2*observation['K'][1][1])))
    ET.SubElement(root.find('worldbody'),'camera',name='handoff_head',
        pos=' '.join(map(str,transform[:3,3])),
        quat=' '.join(map(str,rotation[[3,0,1,2]])),fovy=str(fovy))
    model=mujoco.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'))
    data=mujoco.MjData(model)
    data.qpos[:7]=[0.,0.,0.,1.,0.,0.,0.]
    for name,value in observation['body_state']['joints'].items():
        data.qpos[model.jnt_qposadr[model.joint(name).id]]=value['q']
    mujoco.mj_forward(model,data)
    options=mujoco.MjvOption();options.geomgroup[:]=[0,1,1,0,0,0]
    with mujoco.Renderer(model,height=height,width=width) as renderer:
        renderer.update_scene(data,camera='handoff_head',scene_option=options)
        renderer.enable_depth_rendering()
        robot_depth=renderer.render().copy()
    return np.isfinite(depth)&(np.abs(robot_depth-depth)<.004)


def estimate_held_center(observation, nominal_offset):
    # No model, object identity, task instance, evaluator result or private pose is accepted.
    rgb=np.asarray(Image.open(observation['head_rgb_path']).convert('RGB'),dtype=float)
    depth=np.load(observation['depth_path'],allow_pickle=False)
    cloud=point_cloud(depth,observation['K'],observation['T_optical_to_pelvis'])
    palm=observation['body_state']['palms']['left']
    position=np.asarray(palm['position_m'])
    rotation=Rotation.from_quat(palm['quaternion_xyzw']).as_matrix()
    predicted=position+rotation@np.asarray(nominal_offset)
    self_mask=robot_self_mask(observation,depth)
    mask=(np.isfinite(cloud).all(axis=-1)&~self_mask&(rgb.min(axis=-1)>95)&(np.ptp(rgb,axis=-1)<35)
          &(np.linalg.norm(cloud[:,:,:2]-predicted[:2],axis=-1)<.085))
    fits=[]
    for low,high in ((-.045,-.020),(-.020,.005)):
        band=mask&(cloud[:,:,2]>position[2]+low)&(cloud[:,:,2]<position[2]+high)
        fits.append(circle(cloud[band,:2],predicted[:2]))
    disagreement=float(np.linalg.norm(np.asarray(fits[0]['center_xy_m'])-fits[1]['center_xy_m']))
    if disagreement>.005:
        raise PerceptionError('Held-cup height bands disagree')
    center=np.mean([f['center_xy_m'] for f in fits],axis=0)
    return dict(center_xy_m=center.tolist(),band_fits=fits,band_disagreement_m=disagreement,
        observation_id=observation['observation_id'],simulation_seconds=observation['simulation_seconds'],
        source='head_RGBD_known_radius_and_robot_FK_only',object_truth_used=False)


def proposal(observation, nominal_offset, tray):
    estimate=estimate_held_center(observation,nominal_offset)
    short=np.asarray(tray['axis_short'])[:2];short=short/np.linalg.norm(short)
    target=np.asarray(tray['center_floor_pelvis_m'])[:2]
    error=float((np.asarray(estimate['center_xy_m'])-target)@short)
    correction=-error*short
    actionable=TRIGGER_M<abs(error)<=MAX_CORRECTION_M
    return dict(status='CORRECT' if actionable else 'KEEP_NOMINAL',estimate=estimate,
        short_axis_error_m=error,correction_xy_m=correction.tolist(),
        trigger_m=TRIGGER_M,max_correction_m=MAX_CORRECTION_M,confidence_passed=True,
        reason='bounded visible misalignment' if actionable else 'inside trigger or outside bounded correction scope')
