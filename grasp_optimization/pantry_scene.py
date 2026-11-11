"""Build a native-pantry MuJoCo episode with the official G1 and physical cup."""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import mujoco
import numpy as np

from experiment_log import ROOT

NATIVE = ROOT / 'scenes/pantry/mujoco_native_v01'
VERSION = 'native-pantry-runtime-0.2.1'


def numbers(values):
    return ' '.join(f'{float(value):.9g}' for value in values)


def build_scene(seed=1000):
    metadata = json.loads((NATIVE / 'native_export.json').read_text(encoding='utf-8'))
    candidates = ROOT / 'scenes/pantry/p01_zones_v01/candidates'
    candidate = json.loads((candidates / f'P01_native_v01_practice_{seed}.json').read_text(encoding='utf-8'))
    config = json.loads((candidates.parent / 'zone_config.json').read_text(encoding='utf-8'))
    review = json.loads((candidates.parent / 'human_review.json').read_text(encoding='utf-8'))
    if not review.get('human_zone_review') or review['config_sha256'] != config['config_sha256']:
        raise ValueError('The zone review does not match this layout version')
    if metadata['source_sha256'] != config['source_scene_sha256']:
        raise ValueError('The native room export and approved source scene differ')
    profile = json.loads((ROOT / 'assets/robot_profile.json').read_text(encoding='utf-8'))['profile']
    tree = ET.parse(ROOT / 'assets/g1/upstream_model.xml')
    xml = tree.getroot()
    xml.set('model', 'Native_Pantry_G1_P01')
    xml.find('compiler').set('meshdir', '')
    xml.find('compiler').set('inertiafromgeom', 'auto')
    asset, world = xml.find('asset'), xml.find('worldbody')
    # Remove the upstream demo floor/lights; only the native pantry supplies the environment.
    for duplicate in xml.findall('worldbody')[1:]:
        xml.remove(duplicate)
    for duplicate in xml.findall('asset')[1:]:
        xml.remove(duplicate)
    for mesh in asset.findall('mesh'):
        mesh.set('file', os.path.relpath(ROOT / 'assets/g1/meshes' / mesh.get('file'), NATIVE))
    ET.SubElement(xml, 'option', timestep='.002', integrator='implicitfast', gravity='0 0 -9.81',
                  cone='elliptic', iterations='80', noslip_iterations='3')
    ET.SubElement(xml, 'size', memory='128M')
    for material in metadata['materials']:
        ET.SubElement(asset, 'material', name=material['id'], rgba=numbers(material['rgba']),
                      roughness=str(material['roughness']), metallic=str(material['metallic']), specular='.15')
    cup_meshes = []
    for group in metadata['mesh_groups']:
        ET.SubElement(asset, 'mesh', name=group['id'], file=group['file'], inertia='shell', maxhullvert='16')
        geom = ET.Element('geom', name=group['id'] + '_visual', type='mesh', mesh=group['id'],
                          material=group['material_id'], contype='0', conaffinity='0', density='0', group='2')
        if group['dynamic_cup']:
            cup_meshes.append(geom)
        else:
            world.append(geom)
    collider_map = {}
    stance = candidate['robot_stance']
    stance_xy = stance['pelvis_table_xy_m']
    floor_height = 0.
    for index, collider in enumerate(metadata['static_colliders']):
        name = f'room_contact_{index:03}'
        ET.SubElement(world, 'geom', name=name, type='box', pos=numbers(collider['center']),
                      size=numbers(collider['half']), contype='2', conaffinity='5', group='3',
                      rgba='.4 .3 .2 .1', friction='.9 .005 .0001', solref='.008 1')
        collider_map[name] = collider['source_name']
        top = collider['center'][2] + collider['half'][2]
        if -.1 < top < .15 and all(abs(stance_xy[i] - collider['center'][i]) < collider['half'][i] for i in range(2)):
            floor_height = max(floor_height, top)
    # Physical hollow-cup approximation: thin ring walls, bottom, and elliptical handle capsules.
    x, y = candidate['cup_table_xy_m']
    table_z = config['T_table_top_to_hk'][2][3] - config['floor_hkpd_m']
    yaw = candidate['yaw_in_table_rad']
    cup = ET.SubElement(world, 'body', name='task_cup', pos=numbers([x, y, table_z+.0005]),
                        quat=numbers([math.cos(yaw/2), 0, 0, math.sin(yaw/2)]))
    ET.SubElement(cup, 'freejoint', name='task_cup_free')
    ET.SubElement(cup, 'inertial', pos='0 0 .046', mass='.19', diaginertia='.00025 .00025 .00029')
    for mesh in cup_meshes:
        cup.append(mesh)

    def contact(**kwargs):
        return ET.SubElement(cup, 'geom', contype='4', conaffinity='3', group='3',
                             friction='1 .01 .0001', solref='.008 1', rgba='.9 .9 .9 .1', **kwargs)

    contact(name='cup_bottom', type='cylinder', size='.041 .0025', pos='0 0 .0025')
    for i in range(24):
        a = i * math.tau/24
        contact(name=f'cup_wall_{i:02}', type='box', pos=numbers([.0395*math.cos(a), .0395*math.sin(a), .049]),
                size=numbers([.0015, .041*math.sin(math.pi/24), .049]), quat=numbers([math.cos(a/2), 0, 0, math.sin(a/2)]))
    handle_points = [[.0522+.0138*math.cos(a), 0, .052+.033*math.sin(a)] for a in np.linspace(0, math.tau, 17)]
    for i, (a, b) in enumerate(zip(handle_points, handle_points[1:])):
        contact(name=f'cup_handle_{i:02}', type='capsule', size='.005', fromto=numbers(a+b))
    pelvis = xml.find(".//body[@name='pelvis']")
    yaw = stance['pelvis_yaw_in_table_rad']
    pelvis.set('pos', numbers([*stance_xy, .793+floor_height]))
    pelvis.set('quat', numbers([math.cos(yaw/2), 0, 0, math.sin(yaw/2)]))
    for geom in pelvis.iter('geom'):
        if geom.get('contype') != '0':
            geom.set('contype', '1')
            geom.set('conaffinity', '7')
            geom.set('friction', '1 .01 .0001')
            geom.set('solref', '.008 1')
    for side in ('left', 'right'):
        wrist = xml.find(f".//body[@name='{side}_wrist_yaw_link']")
        ET.SubElement(wrist, 'site', name=side+'_palm', pos='.09 0 0', size='.004', group='4')
    mount = np.asarray(profile['head_camera']['mount_transform'])
    # Task camera calibration v2: same torso mount position, look left/up and widen the workspace view.
    yaw_offset=.25
    pitch_up=.25
    rz=np.array([[math.cos(yaw_offset),-math.sin(yaw_offset),0],
                 [math.sin(yaw_offset),math.cos(yaw_offset),0],[0,0,1.]])
    ry=np.array([[math.cos(pitch_up),0,-math.sin(pitch_up)],[0,1.,0],
                 [math.sin(pitch_up),0,math.cos(pitch_up)]])
    camera_axes = np.array([[0., 0., -1.], [-1., 0., 0.], [0., 1., 0.]])
    quat = np.empty(4)
    mujoco.mju_mat2Quat(quat, (rz@ry@mount[:3, :3] @ camera_axes).flatten())
    torso = xml.find(".//body[@name='torso_link']")
    ET.SubElement(torso, 'camera', name='g1_head', pos=numbers(mount[:3, 3]), quat=numbers(quat), fovy='58')
    for camera in metadata['original_cameras']:
        ET.SubElement(world, 'camera', name=camera['name'], pos=numbers(camera['position']),
                      quat=numbers(camera['quaternion_wxyz']), fovy=str(camera['fovy_deg']))
    observer_position=np.array([1.30,.35,1.65])
    observer_target=np.array([.10,.47,1.06])
    z=observer_position-observer_target
    z/=np.linalg.norm(z)
    x=np.cross(np.array([0.,0.,1.]),z);x/=np.linalg.norm(x)
    y=np.cross(z,x)
    mujoco.mju_mat2Quat(quat,np.column_stack((x,y,z)).ravel())
    ET.SubElement(world,'camera',name='task_observer',pos=numbers(observer_position),quat=numbers(quat),fovy='56')
    # Room lights approximate the native fixtures rather than placing a camera above the room.
    for index, position in enumerate(((0, 0, 2.8), (3, -1, 2.8), (5, -1, 2.8))):
        ET.SubElement(world, 'light', name=f'pantry_light_{index}', pos=numbers(position),
                      dir='0 0 -1', diffuse='.6 .6 .6', ambient='.15 .15 .15', castshadow='false')
    visual = xml.find('visual')
    visual.find('headlight').set('ambient', '.35 .35 .35')
    visual.find('global').set('offwidth', '1280')
    visual.find('global').set('offheight', '720')
    ET.SubElement(visual, 'map', znear='.01', zfar='50')
    statistic = xml.find('statistic')
    statistic.set('center', '0 0 1')
    statistic.set('extent', '8')
    path = NATIVE / f'P01_seed_{seed}.xml'
    ET.indent(xml)
    path.write_text(ET.tostring(xml, encoding='unicode')+'\n', encoding='utf-8')
    context = dict(runtime_version=VERSION, candidate=candidate, native_source=metadata['source_blend'],
                   native_source_sha256=metadata['source_sha256'], native_geometry_objects=len(metadata['geometry_records']),
                   T_sim_to_hk=metadata['T_sim_to_hk'], collider_source_map=collider_map,
                   table_height_m=table_z, floor_at_robot_m=floor_height,
                   approved_zone_config_sha256=config['config_sha256'], human_zone_review=True,
                   head_camera=dict(version='pantry_head_wide_v2',parent='torso_link',fovy_deg=58,
                                    yaw_left_offset_rad=yaw_offset,pitch_up_offset_rad=pitch_up,
                                    factory_calibration=False),
                   spectator_camera=dict(name='task_observer',purpose='human_only_robot_hands_and_table_view',
                                         position_sim_m=observer_position.tolist(),look_at_sim_m=observer_target.tolist(),
                                         fovy_deg=56,used_by_agent=False,used_by_vla=False),
                   visual_limitations=metadata['visual_limitations'],
                   cup_collision='24 thin wall boxes, bottom cylinder, 16 handle capsules; engineering mass/inertia')
    return path, context
