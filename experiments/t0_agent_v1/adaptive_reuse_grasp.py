"""Bounded route and contact-adaptive transfer of the successful grasp methods."""
from copy import deepcopy
import math
from pathlib import Path

import numpy as np

from .reuse_grasp import (PROGRAM, ReuseGrasp, ReusePort, solve_pose,
                          TabletopPlant, independent_verify, ActionFailure)
from .common import relative, write_new, append_event
from arm_planner import ArmPlanner, yaw_rotation
from .reuse_grasp import locate_target, point_cloud

DEFAULTS = dict(pressure_coordination='independent',finger_proximal_scale=1.,load_compensation=False,finger_distal_scale=1.,lift_roll_delta_rad=0.,approach_contact_stop_N=0.,lift_retreat_m=0.,palm_roll_rad=0.,pressure_recovery_s=4.8,palm_pitch_rad=0.,active_wait_hold=False,servo_period_s=.2,thumb_pitch_rad=0.,index_scale=1.,pressure_target_N=1.8,hand_kp=4.,hand_kd=.12,preferred_yaw=.5, offset_delta_m=[0., 0., 0.],
    thumb_scale=1., thumb_distal_scale=1., finger_scale=1., preclose_fraction=0.,
    hand_step_rad=.012, hand_lead_rad=.02, arm_step_rad=.03,
    contact_stop_N=2.5, touch_stop_N=.4, backoff_m=.13, forward_first=True,
    clear_position_m=[-.04, .34, .30], cartesian_step_m=.0125,
    lift_height_m=.12, hold_seconds=1.5, handle_aware=True, auto_sphere_height=True,
    closure_mode='synchronous',approach_mode='palm_backoff',grip_hold=True,grasp_feature='body')
BOUNDS = dict(finger_proximal_scale=(.25,1.),finger_distal_scale=(.5,1.5),lift_roll_delta_rad=(-1.6,1.6),approach_contact_stop_N=(0.,4.),lift_retreat_m=(0.,.06),palm_roll_rad=(-1.7,1.7),pressure_recovery_s=(.04,4.8),palm_pitch_rad=(-.6,.6),servo_period_s=(.02,.2),thumb_pitch_rad=(-.3,.35),index_scale=(.7,1.3),pressure_target_N=(1.5,14.),hand_kp=(.5,8.),hand_kd=(.03,.5),preferred_yaw=(-math.pi,math.pi), thumb_scale=(.35,1.5), finger_scale=(.5,1.4),
    thumb_distal_scale=(.05,2.4),
    preclose_fraction=(0.,.4), hand_step_rad=(.005,.04), hand_lead_rad=(.008,.15),
    arm_step_rad=(.01,.03), contact_stop_N=(2.,18.), touch_stop_N=(.2,1.), backoff_m=(.045,.13),
    cartesian_step_m=(.008,.025), lift_height_m=(.115,.20), hold_seconds=(1.2,2.5))
CATEGORY_KEYS = {'pressure_coordination','finger_proximal_scale','load_compensation','finger_distal_scale','lift_roll_delta_rad','approach_contact_stop_N','lift_retreat_m','palm_roll_rad','lift_height_m','pressure_recovery_s','cartesian_step_m','palm_pitch_rad','active_wait_hold','hold_seconds','servo_period_s','grasp_feature','thumb_pitch_rad','index_scale','pressure_target_N','hand_kp','hand_kd','offset_delta_m','thumb_scale','finger_scale','preclose_fraction',
                 'preferred_yaw','backoff_m','forward_first','clear_position_m','handle_aware','auto_sphere_height',
                 'thumb_distal_scale','closure_mode','approach_mode','grip_hold','contact_stop_N','hand_lead_rad','hand_step_rad'}


def _validate(parameters, partial=False):
    if type(parameters) is not dict or not set(parameters) <= set(DEFAULTS):
        raise ValueError('Unknown adaptive parameters')
    for key, value in parameters.items():
        if key in BOUNDS:
            lo, hi = BOUNDS[key]
            if type(value) not in (int,float) or not math.isfinite(value) or not lo <= value <= hi:
                raise ValueError('Parameter outside safe bounds: '+key)
        elif key in ('forward_first','handle_aware','auto_sphere_height','grip_hold','active_wait_hold','load_compensation'):
            if type(value) is not bool:
                raise ValueError(key+' must be boolean')
        elif key in ('closure_mode','approach_mode','grasp_feature','pressure_coordination'):
            allowed={'pressure_coordination':('independent','coupled'),'closure_mode':('thumb_lead','synchronous'),'approach_mode':('palm_backoff','pelvis_forward','top_down'),'grasp_feature':('body','visible_handle','visible_neck')}[key]
            if value not in allowed:raise ValueError('Unknown mode: '+key)
        else:
            if type(value) is not list or len(value) != 3 or any(type(v) not in (int,float)
                or not math.isfinite(v) for v in value):
                raise ValueError('Three finite values required: '+key)
            limits = [(-.05,.05),(-.09,.05),(-.05,.08)] if key == 'offset_delta_m' else [(-.07,.30),(.15,.42),(.23,.38)]
            if not all(lo <= v <= hi for v, (lo,hi) in zip(value,limits)):
                raise ValueError('Vector outside safe bounds: '+key)


def validate_adaptive_recipe(value):
    if type(value) is not dict or set(value) != {'program','parameters','by_category'} or value['program'] != PROGRAM:
        raise ValueError('Fixed safe stage sequence and parameter mappings required')
    _validate(value['parameters'])
    if type(value['by_category']) is not dict or not set(value['by_category']) <= {'cup','fruit','bottle'}:
        raise ValueError('Only semantic object categories may select overrides')
    for parameters in value['by_category'].values():
        if not set(parameters) <= CATEGORY_KEYS:
            raise ValueError('Forbidden category override')
        _validate(parameters, partial=True)
    result = deepcopy(value)
    result['parameters'] = dict(deepcopy(DEFAULTS), **value['parameters'])
    period=result['parameters']['servo_period_s']
    if abs(period/.002-round(period/.002))>1e-8:raise ValueError('Servo period must align with physics steps')
    for partial in result['by_category'].values():
        period=partial.get('servo_period_s',result['parameters']['servo_period_s'])
        if abs(period/.002-round(period/.002))>1e-8:raise ValueError('Servo period must align with physics steps')
    return result


def parameters_for(recipe, category):
    recipe = validate_adaptive_recipe(recipe)
    return dict(recipe['parameters'], **recipe['by_category'].get(category,{}))


def visible_handle(sensor,estimate,task):
    """Observed cup protrusions only; absent/occluded handles stay unknown."""
    if task['target_category'] != 'cup':
        return dict(visible=False)
    rgb=np.asarray(sensor['rgb'],float)/255.
    cloud=point_cloud(sensor['depth_m'],sensor['K'],sensor['T_optical_to_pelvis'])
    nominal=np.asarray(task['nominal_rgba'][:3])
    if np.ptp(nominal)>.15:
        colour=(rgb[...,0]>1.5*rgb[...,1])&(rgb[...,0]>1.5*rgb[...,2])&(rgb[...,0]>.18)
    else:
        colour=(rgb.min(axis=-1)>.52)&(np.ptp(rgb,axis=-1)<.22)
    center=np.asarray(estimate['cup_bottom_position_m'])
    delta=cloud[...,:2]-center[:2]
    radial=np.linalg.norm(delta,axis=-1)
    mask=(colour&np.isfinite(cloud).all(axis=-1)&(radial>estimate['radius_estimate_m']+.008)
          &(radial<.105)&(cloud[...,2]>center[2]+.012)&(cloud[...,2]<center[2]+.14))
    points=delta[mask]
    if len(points)<8:
        return dict(visible=False,points=int(len(points)))
    direction=np.mean(points,axis=0)
    concentration=float(np.linalg.norm(direction)/np.mean(np.linalg.norm(points,axis=1)))
    if concentration<.75:
        return dict(visible=False,points=len(points),concentration=concentration)
    return dict(visible=True,center_pelvis_m=np.mean(cloud[mask],axis=0).tolist(),
        direction_pelvis_xy=(direction/np.linalg.norm(direction)).tolist(),
        projected_protrusion_xy_m=points[::max(1,len(points)//50)].tolist(),points=len(points),
        heading_rad=float(math.atan2(direction[1],direction[0])),concentration=concentration,
        source='coloured RGB-D points outside the visually fitted cup wall')


def visible_neck(sensor,estimate,task):
    """Find an upper narrow band from the same lawful head RGB-D observation."""
    if task['target_category']!='bottle':return dict(visible=False)
    rgb=np.asarray(sensor['rgb'],float)/255.
    cloud=point_cloud(sensor['depth_m'],sensor['K'],sensor['T_optical_to_pelvis'])
    plane=np.asarray(estimate['table_plane'])
    bottom=np.asarray(estimate['cup_bottom_position_m'])
    height=cloud[...,2]-(cloud[...,:2]@plane[:2]+plane[2])
    radius=np.linalg.norm(cloud[...,:2]-bottom[:2],axis=-1)
    mask=(np.isfinite(cloud).all(axis=-1)&(rgb[...,1]>1.4*rgb[...,0])&
          (rgb[...,1]>1.2*rgb[...,2])&(height>.015)&(height<.25)&(radius<.09))
    if mask.sum()<30:return dict(visible=False,reason='insufficient visible bottle surface')
    top=float(np.percentile(height[mask],98));rows=[]
    for low in np.arange(.02,top,.008):
        selected=mask&(height>=low)&(height<low+.008)
        if selected.sum()>=3:
            rows.append(dict(height_m=float(low+.004),radius_m=float(np.percentile(radius[selected],75)),points=int(selected.sum())))
    candidates=[r for r in rows if .72*top<r['height_m']<.92*top]
    if not candidates:return dict(visible=False,reason='upper band occluded')
    minimum=min(r['radius_m'] for r in candidates)
    if minimum>.85*estimate['radius_estimate_m']:
        return dict(visible=False,reason='no observed narrow upper band')
    neck=min([r for r in candidates if r['radius_m']<minimum+.002],key=lambda r:abs(r['height_m']-.85*top))
    return dict(visible=True,center_pelvis_m=[float(bottom[0]),float(bottom[1]),float(bottom[2]+neck['height_m'])],
        radius_m=neck['radius_m'],height_above_support_m=neck['height_m'],visible_height_m=top,
        observed_profile=rows,source='head_RGBD_narrow_upper_profile',assumption='upright visible bottle axis follows lower cylinder fit')


def prepare_preview(planner, state, parameters):
    data = planner.start(state)
    for position, quaternion in (([-.07,.34,.09],None),
                                  ([-.04,.34,.30],[0.,0.,0.,1.]),
                                  (parameters['clear_position_m'],[0.,0.,0.,1.])):
        if not solve_pose(planner,data,position,quaternion)['reachable']:
            return None
    result = deepcopy(state)
    for joint,q in zip(planner.ids,data.qpos[planner.qids]):
        result['joints'][planner.model.joint(joint).name]['q'] = float(q)
    return result


def grasp_rotation(yaw,parameters):
    pitch=parameters['palm_pitch_rad']
    roll=parameters['palm_roll_rad']
    if pitch==0. and roll==0.:return yaw_rotation(yaw)
    cp,sp=math.cos(pitch),math.sin(pitch);cr,sr=math.cos(roll),math.sin(roll)
    return yaw_rotation(yaw)@np.array([[cp,0.,sp],[0.,1.,0.],[-sp,0.,cp]])@np.array([[1.,0.,0.],[0.,cr,-sr],[0.,sr,cr]])


def grasp_quaternion(yaw,parameters):
    if parameters['palm_pitch_rad']==0. and parameters['palm_roll_rad']==0.:
        return [0.,0.,math.sin(yaw/2),math.cos(yaw/2)]
    import mujoco
    value=np.empty(4);mujoco.mju_mat2Quat(value,grasp_rotation(yaw,parameters).ravel())
    return value[[1,2,3,0]].tolist()


def rolled_lift_goals(start_palm,offset,yaw,parameters):
    """Lift a grasp-relative anchor while turning the hand; no target state queried."""
    start=np.asarray(start_palm,float)
    lever=np.array([offset[0],offset[1],0.])
    anchor=start+grasp_rotation(yaw,parameters)@lever
    remaining=parameters['lift_height_m']-.02
    delta=parameters['lift_roll_delta_rad']
    count=max(1,math.ceil((remaining+abs(delta)*np.linalg.norm(lever))/parameters['cartesian_step_m']),
              math.ceil(abs(delta)/.08))
    goals=[]
    for step in range(1,count+1):
        fraction=step/count
        roll=parameters['palm_roll_rad']+delta*fraction
        pose=dict(parameters,palm_roll_rad=roll)
        center=anchor+np.array([-parameters['lift_retreat_m']*fraction,0.,remaining*fraction])
        palm=center-grasp_rotation(yaw,pose)@lever
        goals.append((f'main_lift_roll_{step:02}',palm,roll))
    return goals


def route_goals(bottom,offset,yaw,parameters):
    palm = np.asarray(bottom)-grasp_rotation(yaw,parameters)@np.asarray(offset)
    if parameters['approach_mode']=='top_down':
        return [('orient_clear',parameters['clear_position_m']),
                ('above_target',palm+[0.,0.,parameters['backoff_m']]),('approach_open',palm),
                ('test_lift',palm+[0.,0.,.02]),('main_lift',palm+[-parameters['lift_retreat_m'],0.,parameters['lift_height_m']])]
    direction=grasp_rotation(yaw,parameters)@[parameters['backoff_m'],0.,0.] if parameters['approach_mode']=='palm_backoff' else np.array([parameters['backoff_m'],0.,0.])
    behind = palm-direction
    high = behind.copy(); high[2] = parameters['clear_position_m'][2]
    goals = [('orient_clear',parameters['clear_position_m'])]
    if parameters['forward_first']:
        goals.append(('forward_clear',[max(.20,float(high[0])),parameters['clear_position_m'][1],float(high[2])]))
    goals += [('behind_high',high),('lower_behind',behind),('approach_open',palm),
              ('test_lift',palm+[0.,0.,.02]),('main_lift',palm+[-parameters['lift_retreat_m'],0.,parameters['lift_height_m']])]
    return goals


def checked_route(planner,state,goals,yaw,parameters):
    import mujoco
    data = planner.start(state)
    rows = []
    for waypoint in goals:
        stage,goal=waypoint[:2]
        pose=dict(parameters,palm_roll_rad=waypoint[2]) if len(waypoint)==3 else parameters
        start = data.site_xpos[planner.site].copy()
        count = 1 if stage == 'orient_clear' else max(1,math.ceil(
            np.linalg.norm(np.asarray(goal)-start)/parameters['cartesian_step_m']))
        for step in range(1,count+1):
            previous = data.qpos[planner.qids].copy()
            position=start+(np.asarray(goal)-start)*step/count
            result=planner.solve(data,position,yaw) if pose['palm_pitch_rad']==0. and pose['palm_roll_rad']==0. and parameters['lift_roll_delta_rad']==0. else solve_pose(planner,data,position,grasp_quaternion(yaw,pose),.001,.025)
            jump = float(max(abs(data.qpos[planner.qids]-previous)))
            row = dict(stage=stage,step=step,max_joint_delta_rad=jump,**result)
            mujoco.mj_collision(planner.model,data)
            self_contacts=[]
            for contact in data.contact:
                bodies=[planner.model.body(int(planner.model.geom_bodyid[g])).name for g in (contact.geom1,contact.geom2)]
                if contact.dist<0. and any(n.startswith('left_') and any(v in n for v in ('shoulder','elbow','wrist','hand')) for n in bodies):
                    self_contacts.append(dict(bodies=bodies,separation_m=float(contact.dist)))
            if self_contacts:
                row['reachable']=False
                row['robot_self_contacts']=self_contacts
                result['reachable']=False
            rows.append(row)
            if not result['reachable'] or stage != 'orient_clear' and jump > .5:
                return dict(reachable=False,failed_at=row,path=rows,environment_collision_checked=False)
    return dict(reachable=True,path=rows,goals=[(g[0],np.asarray(g[1]).tolist(),*g[2:]) for g in goals],
                environment_collision_checked=False)


class AdaptivePort(ReusePort):
    def __init__(self,plant,parameters):
        super().__init__(plant)
        self.parameters = parameters
        self.contact_cap = None
        self.hold_targets = None
        self.grip_tick_mode = False
        self.arm_bias = {}

    def invoke(self,tool,arguments):
        if tool == 'wait':
            if not self.hold_targets or not self.parameters['active_wait_hold']:return super().invoke(tool,arguments)
            count=max(1,math.ceil(arguments['seconds']/self.parameters['servo_period_s']))
            old_mode=self.grip_tick_mode;self.grip_tick_mode=True
            try:
                for _ in range(count):
                    result=self.invoke('set_joints',dict(targets=self.hold_targets,duration=self.parameters['servo_period_s']))
                    if result['status']!='EXECUTED':return result
            finally:self.grip_tick_mode=old_mode
            return result
        from experiments.grow_up_v2.plant import ALLOWED,HAND
        targets = arguments.get('targets')
        if tool == 'move_ee':
            if arguments['side'] != 'left':
                raise ActionFailure('Only left end effector allowed')
            data = self.kinematics.start(self.state())
            precision=(.001,.025) if self.parameters['palm_pitch_rad']!=0. or self.parameters['palm_roll_rad']!=0. or self.parameters['lift_roll_delta_rad']!=0. else (.004,.12)
            plan = solve_pose(self.kinematics,data,arguments['position'],arguments.get('quaternion_xyzw'),*precision)
            if not plan['reachable']:
                return dict(status='POSE_IK_REJECTED',**plan)
            targets = {self.kinematics.model.joint(j).name:float(q)
                for j,q in zip(self.kinematics.ids,data.qpos[self.kinematics.qids])}
            ideal_targets=dict(targets)
            if self.parameters['load_compensation']:
                targets={n:q+self.arm_bias.get(n,0.) for n,q in ideal_targets.items()}
                for n,q in targets.items():
                    if not self.kinematics.model.joint(n).range[0]<=q<=self.kinematics.model.joint(n).range[1]:
                        return dict(status='LOAD_COMPENSATION_RANGE_REJECTED',joint=n)
        elif tool != 'set_joints':
            raise ActionFailure('Unrecognized physical tool')
        if not set(targets) <= ALLOWED:
            raise ActionFailure('Non-left command rejected')
        moving_targets = dict(targets)
        if tool=='move_ee' and self.hold_targets:
            targets=dict(targets,**self.hold_targets)
        first = {n:float(self.plant.targets[self.plant.ai[n]]) for n in targets}
        period=self.parameters['servo_period_s']
        steps = {n:(self.parameters['hand_step_rad'] if n in HAND else self.parameters['arm_step_rad'])*period/.2 for n in targets}
        count = max(1,math.ceil(arguments.get('duration',period)/period),
                    max(math.ceil(abs(q-first[n])/steps[n]) for n,q in moving_targets.items()))
        last = None
        limited = set()
        stalled = 0
        # Keep contact forces small by stopping the loaded joint's advance.
        # The original tactile gate and physical success predicate remain intact.
        iteration_limit=1 if getattr(self,'grip_tick_mode',False) else count+math.ceil(8./period)
        for index in range(1,iteration_limit+1):
            observation = self.plant.observation()
            values = {}
            for name,target in targets.items():
                old = float(self.plant.targets[self.plant.ai[name]])
                measured = observation['joints'][name]['q']
                nominal=first[name]+(target-first[name])*min(1.,index/count)
                if name in HAND and ((getattr(self,'grip_tick_mode',False) and
                                      self.parameters['pressure_coordination']=='independent') or
                                     tool=='move_ee' and self.hold_targets):
                    # Pressure feedback must not inherit another finger's travel fraction.
                    nominal=target
                step = float(np.clip(nominal-old,-steps[name],steps[name]))
                if name in HAND:
                    digit = name.split('left_hand_',1)[1].split('_',1)[0]
                    load = sum(v for joint,v in observation['tactile_joint_load_N'].items()
                               if 'left_hand_'+digit+'_' in joint)
                    toward_close = abs(target) > abs(old)+1e-5
                    threshold=self.contact_cap if self.contact_cap is not None else self.parameters['contact_stop_N']
                    if toward_close and load >= threshold:
                        step = 0.; limited.add(name)
                    proposed = old+step
                    lead = self.parameters['hand_lead_rad']
                    proposed = float(np.clip(proposed,measured-lead,measured+lead))
                    values[name] = float(np.clip(proposed,old-steps[name],old+steps[name]))
                else:
                    values[name] = old+step
            last = self.plant.dispatch(dict(op='set_joints',targets=values,duration=period))
            if last['status'] != 'EXECUTED':
                return last
            remaining = [abs(target-float(self.plant.targets[self.plant.ai[name]]))
                         for name,target in moving_targets.items() if name not in limited]
            if index >= math.ceil(arguments.get('duration',period)/period) and (not remaining or max(remaining) < .001):
                break
            if all(abs(values[n]-observation['joints'][n]['target']) < 1e-5 for n in targets):
                stalled += 1
                if stalled >= 4:
                    break
            else:
                stalled = 0
        if last:
            last['contact_limited_joints'] = sorted(limited)
            if tool == 'move_ee' and last['status'] == 'EXECUTED':
                actual = np.asarray(self.state()['palms']['left']['position_m'])
                error = float(np.linalg.norm(actual-np.asarray(arguments['position'])))
                compensation_ticks=0
                if self.parameters['load_compensation']:
                    old_mode=self.grip_tick_mode;self.grip_tick_mode=True
                    try:
                        for _ in range(math.ceil(2./period)):
                            if error<=.005:break
                            state=self.state();values={}
                            for name,ideal in ideal_targets.items():
                                current=float(self.plant.targets[self.plant.ai[name]])
                                correction=float(np.clip(.6*(ideal-state['joints'][name]['q']),-steps[name],steps[name]))
                                proposed=float(np.clip(current+correction,ideal-.15,ideal+.15))
                                joint=self.kinematics.model.joint(name)
                                if not joint.range[0]<=proposed<=joint.range[1]:
                                    return dict(status='LOAD_COMPENSATION_RANGE_REJECTED',joint=name)
                                values[name]=proposed
                            result=self.invoke('set_joints',dict(targets=values,duration=period))
                            if result['status']!='EXECUTED':return result
                            self.arm_bias={n:float(self.plant.targets[self.plant.ai[n]])-ideal for n,ideal in ideal_targets.items()}
                            if self.hold_targets:
                                result=self.invoke('wait',dict(seconds=period))
                                if result['status']!='EXECUTED':return result
                            last=result;compensation_ticks+=1
                            actual=np.asarray(self.state()['palms']['left']['position_m'])
                            error=float(np.linalg.norm(actual-np.asarray(arguments['position'])))
                    finally:self.grip_tick_mode=old_mode
                last['load_compensation_ticks']=compensation_ticks
                settled=0.
                if not self.parameters['load_compensation'] and (self.parameters['palm_pitch_rad']!=0. or self.parameters['palm_roll_rad']!=0.):
                    while error>.005 and settled<1.:
                        result=self.invoke('wait',dict(seconds=.2))
                        if result['status']!='EXECUTED':return result
                        settled+=.2
                        actual=np.asarray(self.state()['palms']['left']['position_m'])
                        error=float(np.linalg.norm(actual-np.asarray(arguments['position'])))
                last['tracking_settle_seconds']=settled
                last['actual_position_error_m'] = error
                if error > .015:
                    last['status'] = 'ENDPOINT_TRACKING_ERROR'
        return last


class AdaptiveGrasp(ReuseGrasp):
    def __init__(self,port,folder,task,parameters):
        inherited = dict(preferred_yaw=parameters['preferred_yaw'],
            offset_delta_m=parameters['offset_delta_m'],closure='adaptive')
        super().__init__(port,folder,task,inherited)
        self.adaptive = parameters
        self.contact_approach=False
        self.close = np.asarray(self.close,float)
        self.close[:2] *= parameters['thumb_scale']
        self.close[2] *= parameters['thumb_distal_scale']
        self.close[3:] *= parameters['finger_scale']
        self.close[[3,5]] *= parameters['finger_proximal_scale']
        self.close[[4,6]] *= parameters['finger_distal_scale']
        self.close[0]=parameters['thumb_pitch_rad']
        self.close[5:]*=parameters['index_scale']

    def locate(self,pixel_hint=None):
        result=super().locate(pixel_hint)
        result['visible_handle']=visible_handle(self.port.plant.rgbd(),result,self.public_task)
        result['visible_neck']=visible_neck(self.port.plant.rgbd(),result,self.public_task)
        if self.public_task['target_category']=='fruit' and self.adaptive['auto_sphere_height']:
            self.offset[2]=(-result['radius_estimate_m']+self.adaptive['offset_delta_m'][2]+math.sin(self.adaptive['palm_pitch_rad'])*self.offset[0])/math.cos(self.adaptive['palm_pitch_rad'])
        if self.adaptive['palm_roll_rad']!=0. and self.public_task['target_category']=='fruit' and self.adaptive['auto_sphere_height']:
            vertical=-result['radius_estimate_m']+self.adaptive['offset_delta_m'][2]
            row=grasp_rotation(0.,self.adaptive)[2]
            axis=1 if abs(row[1])>abs(row[2]) else 2
            self.offset[axis]=(vertical-sum(row[j]*self.offset[j] for j in range(3) if j!=axis))/row[axis]
        self.grasp_anchor=np.asarray(result['cup_bottom_position_m'],float).copy()
        if self.adaptive['grasp_feature']=='visible_neck':
            neck=result['visible_neck']
            if not neck.get('visible'):raise ActionFailure('Visible neck required for feature grasp')
            self.grasp_anchor=np.asarray(neck['center_pelvis_m'],float)
        if self.adaptive['grasp_feature']=='visible_handle':
            handle=result['visible_handle']
            if not handle.get('visible'):raise ActionFailure('Visible handle required for feature grasp')
            center=np.asarray(handle['center_pelvis_m'])
            self.grasp_anchor[:2]=center[:2]
            self.grasp_anchor[2]=np.asarray(result['table_plane'])@np.r_[center[:2],1.]
            height=max(center[2]-self.grasp_anchor[2],.055)
            self.offset[2]=(-height+self.adaptive['offset_delta_m'][2]+math.sin(self.adaptive['palm_pitch_rad'])*self.offset[0])/math.cos(self.adaptive['palm_pitch_rad'])
        result['grasp_anchor_position_m']=self.grasp_anchor.tolist()
        result['grasp_feature']=self.adaptive['grasp_feature']
        result['grasp_offset_in_palm_m']=self.offset.tolist()
        self.save()
        return result

    def prepare(self):
        if self.phase != 'initial':
            raise ActionFailure('Prepare exactly once')
        self.action('raise_front','move_ee',side='left',position=[-.07,.34,.09],duration=1.5)
        self.action('raise_clear','move_ee',side='left',position=[-.04,.34,.30],
                    quaternion_xyzw=[0.,0.,0.,1.],duration=2.)
        self.action('translate_clear','move_ee',side='left',position=self.adaptive['clear_position_m'],
                    quaternion_xyzw=[0.,0.,0.,1.],duration=2.)
        names = ['left_hand_'+digit+'_'+joint+'_joint' for digit in ('middle','index') for joint in ('0','1')]
        self.action('free_space_finger_preshape','set_joints',
            targets=dict(zip(names,self.close[3:]*self.adaptive['preclose_fraction'])),duration=.6)
        self.phase = 'ready'
        return self.locate()

    def preflight(self):
        if self.estimate is None or self.phase not in ('initial','ready'):
            raise ActionFailure('Locate before adaptive preflight')
        planner = ArmPlanner()
        state = self.port.state()
        if self.phase == 'initial':
            state = prepare_preview(planner,state,self.adaptive)
            if state is None:
                return dict(reachable=False,reason='preparation preview failed')
        trials = []
        yaws=list(dict.fromkeys([self.preferred_yaw,1.5,1.25,1.,.7,.5,.25,0.,-.5,-1.,2.]))
        handle=self.estimate.get('visible_handle',{})
        if self.adaptive['grasp_feature']=='visible_handle':
            angle=handle['heading_rad']
            derived=[(v+math.pi)%(2*math.pi)-math.pi for v in (angle-math.pi/2,angle+math.pi/2,angle+math.pi)]
            yaws=list(dict.fromkeys(derived+yaws))
        elif self.adaptive['handle_aware'] and handle.get('visible'):
            points=np.asarray(handle['projected_protrusion_xy_m'])
            yaws=[yaw for yaw in yaws if self.offset[1]+
                  max(points@np.array([-math.sin(yaw),math.cos(yaw)]))<=-.008]
        for yaw in yaws:
            goals = route_goals(self.grasp_anchor,self.offset,yaw,self.adaptive)
            if self.adaptive['lift_roll_delta_rad']!=0.:
                goals=goals[:-1]+rolled_lift_goals(goals[-2][1],self.offset,yaw,self.adaptive)
            path = checked_route(planner,state,goals,yaw,self.adaptive)
            trials.append(dict(yaw=yaw,reachable=path['reachable'],failed_at=path.get('failed_at')))
            if path['reachable']:
                self.plan = dict(selected_yaw_rad=yaw,selected_offset_m=self.offset.tolist(),path=path)
                break
        else:
            self.plan = None
        from diagnose_grasp import write_json
        write_json(self.folder/'adaptive_preflight.json',dict(trials=trials,plan=self.plan))
        return dict(reachable=self.plan is not None,selected_yaw_rad=self.plan['selected_yaw_rad'] if self.plan else None,
            trials=trials,source='inherited robot-only IK with bounded route parameters',environment_collision_checked=False)

    def stop_on_approach_contact(self):
        threshold=self.adaptive['approach_contact_stop_N']
        if threshold<=0. or self.port.plant.guard:return False
        state=self.port.state();current=np.asarray(state['palms']['left']['position_m'])
        loads=state['approximate_contact_load_N']['left']
        digits={digit:sum(v for name,v in loads.items() if '_'+digit+'_' in name) for digit in ('index','middle')}
        distance=float(np.linalg.norm(current-self.palm))
        if min(digits.values())<threshold or distance>.035:return False
        append_event(self.folder/'contact_approach.jsonl',dict(simulation_seconds=state['simulation_seconds'],
            status='CONTACT_STOP_BEFORE_COMMAND_ENDPOINT',distance_to_original_goal_m=distance,
            actual_palm=current.tolist(),anonymous_digit_load_N=digits))
        self.palm=current.copy();self.contact_approach=True
        return True

    def linear(self,stage,position,duration):
        start = np.asarray(self.port.state()['palms']['left']['position_m'])
        end = np.asarray(position)
        count = max(1,math.ceil(np.linalg.norm(end-start)/self.adaptive['cartesian_step_m']))
        quaternion = grasp_quaternion(self.yaw,self.adaptive)
        for step in range(1,count+1):
            if stage=='approach_open':
                if self.stop_on_approach_contact():return
                try:
                    fresh=locate_target(self.port.plant.rgbd(),self.public_task)
                except Exception as exc:
                    append_event(self.folder/'visual_tracking.jsonl',dict(stage=stage,
                        time=self.port.state()['simulation_seconds'],available=False,reason=str(exc)[:300]))
                else:
                    displacement=float(np.linalg.norm(np.asarray(fresh['cup_bottom_position_m'])-
                                                       self.estimate['cup_bottom_position_m']))
                    append_event(self.folder/'visual_tracking.jsonl',dict(stage=stage,
                        observation=fresh,displacement_m=displacement))
                    if displacement>.015:
                        raise ActionFailure('VISUAL_TARGET_MOVED_DURING_APPROACH: '+str(round(displacement,4)))
            try:
                self.action(f'{stage}_{step:02}','move_ee',side='left',
                    position=(start+(end-start)*step/count).tolist(),quaternion_xyzw=quaternion,duration=duration/count)
            except ActionFailure as exc:
                if stage=='approach_open' and 'ENDPOINT_TRACKING_ERROR' in str(exc) and self.stop_on_approach_contact():
                    return
                raise
            if self.adaptive['grip_hold'] and stage in ('test_lift_2cm','main_lift'):
                self.maintain_grip('pressure_during_'+stage)

    def maintain_grip(self,stage):
        names=['left_hand_'+n+'_joint' for n in ('thumb_0','thumb_1','thumb_2','middle_0','middle_1','index_0','index_1')]
        self.port.grip_tick_mode=True
        try:
            stable=0
            period=self.adaptive['servo_period_s']
            recovery=4.8 if stage=='firm_grip_after_opposing_touch' else self.adaptive['pressure_recovery_s']
            for tick in range(math.ceil(recovery/period)):
                self.action(stage+'_'+str(tick),'set_joints',targets=dict(zip(names,self.close)),duration=period)
                loads=self.port.state()['approximate_contact_load_N']['left']
                thumb=sum(v for n,v in loads.items() if '_thumb_' in n)
                finger=max(sum(v for n,v in loads.items() if '_'+digit+'_' in n) for digit in ('middle','index'))
                stable=stable+1 if min(thumb,finger)>=self.adaptive['pressure_target_N'] else 0
                if stable>=math.ceil(.4/period):break
        finally:
            self.port.grip_tick_mode=False

    def approach(self):
        if self.phase != 'ready' or self.plan is None:
            raise ActionFailure('Two successful preflights required')
        self.yaw = self.plan['selected_yaw_rad']
        self.palm = self.grasp_anchor-grasp_rotation(self.yaw,self.adaptive)@self.offset
        for waypoint in self.plan['path']['goals']:
            stage,goal=waypoint[:2]
            if stage in ('test_lift','main_lift') or stage.startswith('main_lift_roll_'):
                break
            if stage == 'orient_clear':
                self.action(stage,'move_ee',side='left',position=goal,
                    quaternion_xyzw=grasp_quaternion(self.yaw,self.adaptive),duration=1.5)
            else:
                self.linear(stage,goal,2.)
        self.phase = 'approached'
        return dict(status='APPROACHED_CONTACT_STOP' if self.contact_approach else 'APPROACHED',actual_palm=self.port.state()['palms']['left'])

    def close_and_test(self):
        if self.phase != 'approached':
            raise ActionFailure('Approach before closing')
        names = ['left_hand_'+n+'_joint' for n in
                 ('thumb_0','thumb_1','thumb_2','middle_0','middle_1','index_0','index_1')]
        preclose = dict(zip(names[3:],self.close[3:]*self.adaptive['preclose_fraction']))
        self.action('finger_preclose_before_thumb','set_joints',targets=preclose,duration=.6)
        self.port.contact_cap=self.adaptive['touch_stop_N']
        if self.adaptive['closure_mode']=='thumb_lead':
            self.action('bounded_thumb_lead','set_joints',targets=dict(zip(names[:3],self.close[:3])),duration=.7)
        for fraction in (.15,.3,.45,.6,.75,.9,1.):
            targets=dict(zip(names,self.close*fraction)) if self.adaptive['closure_mode']=='synchronous' else dict(zip(names[3:],self.close[3:]*fraction))
            self.action('adaptive_close_'+str(fraction),'set_joints',targets=targets,duration=.4)
            loads = self.port.state()['approximate_contact_load_N']['left']
            thumb = sum(v for n,v in loads.items() if '_thumb_' in n)
            finger = max(sum(v for n,v in loads.items() if '_'+digit+'_' in n) for digit in ('middle','index'))
            threshold=.7*self.adaptive['touch_stop_N']
            if thumb >= threshold and finger >= threshold:
                break
        self.port.plant.head_image(self.folder.parent/'grip_light_touch_head.jpg')
        self.port.contact_cap=None
        if thumb<threshold or finger<threshold:
            raise ActionFailure('TOUCH_ALIGNMENT_FAILED')
        if self.adaptive['grip_hold']:self.port.hold_targets=dict(zip(names,self.close))
        self.maintain_grip('firm_grip_after_opposing_touch')
        self.port.plant.head_image(self.folder.parent/'grip_before_settle_head.jpg')
        self.action('grip_settle','wait',seconds=.6)
        self.port.plant.head_image(self.folder.parent/'grip_after_settle_head.jpg')
        self.tactile_gate('inherited_tactile_grip_gate')
        if self.adaptive['grip_hold']:
            self.port.hold_targets=dict(zip(names,self.close))
        if self.contact_approach:
            self.palm=np.asarray(self.port.state()['palms']['left']['position_m'])
            goals=[('test_lift',self.palm+[0.,0.,.02]),('main_lift',self.palm+[-self.adaptive['lift_retreat_m'],0.,self.adaptive['lift_height_m']])]
            plan=checked_route(ArmPlanner(),self.port.state(),goals,self.yaw,self.adaptive)
            from diagnose_grasp import write_json
            write_json(self.folder/'contact_lift_preflight.json',plan)
            if not plan['reachable']:raise ActionFailure('CONTACT_LIFT_PATH_UNREACHABLE')
        self.linear('test_lift_2cm',self.palm+[0.,0.,.02],1.)
        self.action('test_lift_hold','wait',seconds=.6)
        result = self.tactile_gate('inherited_tactile_test_lift_gate')
        if self.adaptive['lift_roll_delta_rad']!=0.:
            current=self.port.state()
            goals=rolled_lift_goals(current['palms']['left']['position_m'],self.offset,self.yaw,self.adaptive)
            self.rolled_lift_plan=checked_route(ArmPlanner(),current,goals,self.yaw,self.adaptive)
            from diagnose_grasp import write_json
            write_json(self.folder/'post_grasp_roll_preflight.json',self.rolled_lift_plan)
            if not self.rolled_lift_plan['reachable']:
                raise ActionFailure('POST_GRASP_ROLL_LIFT_UNREACHABLE')
        self.phase = 'tested'
        return result

    def lift_and_hold(self):
        if self.phase != 'tested':
            raise ActionFailure('Test lift before full lift')
        if self.adaptive.get('lift_roll_delta_rad',0.)==0.:
            self.linear('main_lift',self.palm+[-self.adaptive['lift_retreat_m'],0.,self.adaptive['lift_height_m']],2.)
        else:
            for stage,position,roll in self.rolled_lift_plan['goals']:
                pose=dict(self.adaptive,palm_roll_rad=roll)
                self.action(stage,'move_ee',side='left',position=position,
                    quaternion_xyzw=grasp_quaternion(self.yaw,pose),duration=.2)
                if self.adaptive['grip_hold']:self.maintain_grip('pressure_during_'+stage)

        # The wait adapter includes bounded hand feedback in this physical duration.
        self.action('hold','wait',seconds=self.adaptive['hold_seconds'])
        result = self.tactile_gate('inherited_tactile_final_gate')
        self.phase = 'complete'
        return dict(status='MOTION_ENDED_AWAITING_INDEPENDENT_VERIFICATION',tactile=result)


def execute_adaptive(scene,case,output,recipe,budget=120.):
    import mujoco
    output = Path(output)
    output.mkdir(parents=True,exist_ok=False)
    model = mujoco.MjModel.from_xml_path(str(scene))
    plant = TabletopPlant(case['instance'],case['case_path'],model,output,budget=budget)
    parameters = parameters_for(recipe,case['task']['target_category'])
    from .tabletop_training_plant import set_left_hand_impedance
    configuration=set_left_hand_impedance(model,parameters['hand_kp'],parameters['hand_kd'])
    for name in configuration['joints']:
        index=plant.ai[name]
        plant.kp[index]=parameters['hand_kp'];plant.kd[index]=parameters['hand_kd']
    write_new(output/'left_hand_impedance.json',configuration)
    plant.head_image(output/'initial_head.jpg')
    port = AdaptivePort(plant,parameters)
    folder = output/'tools'; folder.mkdir()
    controller = AdaptiveGrasp(port,folder,case['task'],parameters)
    error,feedback,calls = None,[],0
    try:
        response = port.invoke('wait',dict(seconds=.6))
        if response['status'] != 'EXECUTED':
            raise ActionFailure('initial settling: '+response['status'])
        for tool in PROGRAM:
            calls += 1
            if tool == 'finish':
                if controller.phase != 'complete':
                    raise ActionFailure('Finish before completed lift/hold')
                result = dict(status='ENDED_AWAITING_INDEPENDENT_VERIFICATION')
            else:
                result = getattr(controller,tool)()
            feedback.append(dict(tool=tool,result=result,phase=controller.phase))
            if tool in ('prepare','approach','close_and_test'):
                plant.head_image(output/(tool+'_head.jpg'))
            if tool == 'preflight' and not result['reachable']:
                raise ActionFailure('ADAPTIVE_APPROACH_PATH_UNREACHABLE')
    except Exception as exc:
        error = dict(type=type(exc).__name__,message=str(exc)[:600])
    stop = plant.observation()
    from experiments.grow_up_v2.plant import ALLOWED
    legal = {key:stop[key] for key in ('simulation_seconds','left_palm','tactile_joint_load_N','guard')}
    legal['joints'] = {n:v for n,v in stop['joints'].items() if n in ALLOWED}
    runtime = plant.save(error,dict(phase=controller.phase),
        dict(execution='validated adaptive declarative engineering recipe'),calls)
    verdict = independent_verify(output,case['instance'],model,initial_valid=True)
    write_new(output/'legal_tool_feedback.json',dict(steps=feedback,stopping_observation=legal))
    return dict(alias=case['alias'],verified_task_success=verdict['verified_task_success'],
        simulation_seconds=runtime['simulation_seconds'],high_level_tool_calls=calls,
        low_level_commands=runtime['low_level_commands'],guard=plant.guard,error=error,
        legal_stop_observation=legal,legal_tool_feedback=feedback,folder=relative(output),
        initial_hash=plant.initial_hash,phase=controller.phase,parameters=parameters)


def episode_job(arguments):
    """Fresh process/render context for each independent training episode."""
    import contextlib
    scene,case,output,recipe,budget = arguments
    output = Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    log = output.parent/(output.name+'_runtime.log')
    with log.open('x',encoding='utf-8') as stream, contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        return execute_adaptive(scene,case,output,recipe,budget)
