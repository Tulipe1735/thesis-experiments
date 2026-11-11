"""Small, explicit collision assets; external visuals retain their own provenance."""
from copy import deepcopy
import math
import os
from pathlib import Path
import xml.etree.ElementTree as ET

from .common import ROOT, read, sha

VERSION = 't0-diversity-assets-v2'
VENDOR = ROOT/'experiments/t0_agent_v1/assets/robosuite_bottle_v1'


def asset(identifier, kind, **parameters):
    return dict(id=identifier, kind=kind, origin='local_procedural_proxy',
                source='experiments/t0_agent_v1/diversity_assets.py',
                physical_parameters='engineering approximations, not measured objects',
                robot_grasp_qualified=False, **parameters)


ASSETS = [
    asset('mug_standard_proxy', 'cup', radius_m=.041, height_m=.098, mass_kg=.19,
          footprint_radius_m=.072, handle=True, rgba=[.9, .9, .86, 1]),
    asset('tumbler_slim_proxy', 'cup', radius_m=.032, height_m=.115, mass_kg=.15,
          footprint_radius_m=.033, handle=False, rgba=[.15, .50, .85, 1]),
    asset('mug_wide_proxy', 'cup', radius_m=.044, height_m=.085, mass_kg=.22,
          footprint_radius_m=.075, handle=True, rgba=[.65, .20, .18, 1]),
    asset('orange_80mm_proxy', 'fruit', radii_m=[.04, .04, .04], mass_kg=.19,
          radius_m=.04, height_m=.08, footprint_radius_m=.04, rgba=[1, .36, .015, 1]),
    asset('orange_68mm_proxy', 'fruit', radii_m=[.034, .034, .034], mass_kg=.13,
          radius_m=.034, height_m=.068, footprint_radius_m=.034, rgba=[1, .55, .02, 1]),
    asset('apple_ellipsoid_proxy', 'fruit', radii_m=[.039, .042, .038], mass_kg=.17,
          radius_m=.042, height_m=.076, footprint_radius_m=.042, rgba=[.75, .06, .04, 1]),
    asset('tray_long_proxy', 'tray', half_xy_m=[.26, .095], height_m=.022,
          floor_m=.006, rim_m=.006, mass_kg=.60, rgba=[.08, .24, .60, 1]),
    asset('tray_broad_proxy', 'tray', half_xy_m=[.25, .12], height_m=.024,
          floor_m=.006, rim_m=.007, mass_kg=.70, rgba=[.42, .26, .13, 1]),
    asset('platter_small_proxy', 'platter', half_xy_m=[.17, .10], height_m=.022,
          floor_m=.006, rim_m=.006, mass_kg=.48, rgba=[.08, .48, .36, 1]),
    asset('platter_large_proxy', 'platter', half_xy_m=[.20, .12], height_m=.025,
          floor_m=.007, rim_m=.007, mass_kg=.60, rgba=[.68, .55, .30, 1]),
    asset('sealed_bottle_proxy', 'bottle', radius_m=.032, height_m=.21, mass_kg=.30,
          footprint_radius_m=.032, rgba=[.17, .63, .75, 1]),
    asset('non_target_can_proxy', 'distractor', radius_m=.027, height_m=.09,
          mass_kg=.10, footprint_radius_m=.027, rgba=[.55, .55, .55, 1]),
    asset('cabinet_narrow_proxy', 'cabinet', half_xy_m=[.31, .25], height_m=.40,
          wall_m=.015, rgba=[.50, .30, .16, 1]),
    asset('cabinet_wide_proxy', 'cabinet', half_xy_m=[.38, .27], height_m=.44,
          wall_m=.015, rgba=[.55, .45, .35, 1]),
    asset('shelf_narrow_proxy', 'shelf', half_xy_m=[.34, .24], height_m=.025,
          rgba=[.45, .47, .49, 1]),
    asset('shelf_wide_proxy', 'shelf', half_xy_m=[.40, .27], height_m=.025,
          rgba=[.54, .40, .24, 1]),
]


def catalog():
    rows = deepcopy(ASSETS)
    manifest = VENDOR/'manifest.json'
    if manifest.exists():
        for record in read(manifest)['files']:
            if sha(VENDOR/record['path']) != record['sha256']:
                raise ValueError('Vendored asset changed: '+record['path'])
        rows.append(asset('robosuite_bottle', 'bottle', radius_m=.0254, height_m=.157,
                          footprint_radius_m=.036, mass_kg=.30, rgba=[.24, .65, .80, 1],
                          vendor_manifest=str(manifest.relative_to(ROOT))))
        rows[-1].update(origin='external_native_mjcf',
                        source=str(manifest.relative_to(ROOT)), source_sha256=sha(manifest),
                        physical_parameters='upstream mesh; local mass/friction and placement adapter')
    return {row['id']: row for row in rows}


def values(items):
    return ' '.join(f'{float(v):.12g}' for v in items)


def geom(body, name, shape, size, position=(0, 0, 0), **extra):
    return ET.SubElement(body, 'geom', name=name, type=shape, size=values(size),
                         pos=values(position), friction='.8 .005 .0001',
                         solref='.008 1', solimp='.95 .99 .001', **extra)


def add_body(world, item):
    """All free-object origins are at the bottom, not at the centre of mass."""
    a, name = item['asset'], item['name']
    body = ET.SubElement(world, 'body', name=name, pos=values(item['position_m']),
                         quat=values(item['quaternion_wxyz']))
    ET.SubElement(body, 'freejoint', name=name+'_free')
    height = a['height_m']
    # Explicit positive inertia avoids giving hollow walls unintended density.
    r = a.get('radius_m', max(a.get('half_xy_m', [.1])))
    mass = a['mass_kg']
    inertia = [mass*(3*r*r+height*height)/12]*2+[mass*r*r/2]
    if a['kind'] == 'fruit':
        rx, ry, rz = a['radii_m']
        inertia = [mass*(ry*ry+rz*rz)/5, mass*(rx*rx+rz*rz)/5, mass*(rx*rx+ry*ry)/5]
    ET.SubElement(body, 'inertial', mass=str(mass), pos=values([0, 0, height/2]),
                  diaginertia=values(inertia))
    style = dict(rgba=values(a['rgba']), density='0')
    kind = a['kind']
    if kind == 'cup':
        r, h, wall = a['radius_m'], a['height_m'], .002
        geom(body, name+'_base', 'cylinder', [r, .0025], [0, 0, .0025], **style)
        for i in range(24):
            angle = i*math.tau/24
            geom(body, f'{name}_wall_{i}', 'box', [wall/2, r*math.sin(math.pi/24), h/2],
                 [(r-wall/2)*math.cos(angle), (r-wall/2)*math.sin(angle), h/2],
                 quat=values([math.cos(angle/2), 0, 0, math.sin(angle/2)]), **style)
        if a['handle']:
            for i in range(16):
                points = []
                for j in (i, i+1):
                    angle = j*math.tau/16
                    points.extend([r+.013+.013*math.cos(angle), 0, h*.52+h*.30*math.sin(angle)])
                # fromto sets position and orientation together.
                ET.SubElement(body, 'geom', name=f'{name}_handle_{i}', type='capsule',
                              size='.004', fromto=values(points), friction='.8 .005 .0001', **style)
    elif kind == 'fruit':
        radii = a['radii_m']
        spherical = max(radii)-min(radii) < 1e-12
        geom(body, name+'_fruit', 'sphere' if spherical else 'ellipsoid',
             [radii[0]] if spherical else radii, [0, 0, radii[2]], **style)
    elif kind in ('tray', 'platter'):
        hx, hy = a['half_xy_m']
        t, f = a['rim_m'], a['floor_m']
        geom(body, name+'_floor', 'box', [hx, hy, f/2], [0, 0, f/2], **style)
        for axis, half in enumerate((hx, hy)):
            for sign in (-1, 1):
                size, pos = [hx, hy, height/2], [0., 0., height/2]
                size[axis] = t/2
                pos[axis] = sign*(half-t/2)
                geom(body, f'{name}_rim_{axis}_{sign}', 'box', size, pos, **style)
    elif kind in ('bottle', 'distractor'):
        r = a['radius_m']
        geom(body, name+'_base', 'cylinder', [r, height*.4], [0, 0, height*.4], **style)
        geom(body, name+'_neck', 'cylinder', [r*.45, height*.10], [0, 0, height*.9], **style)
    else:
        raise ValueError(f'Not a free-object asset: {kind}')
    return body


def add_vendor_bottle(root, body, item, output):
    """Import the upstream visual/collision geometry, with a local SI adapter."""
    # The preserved source XML and STL are never patched in place.
    source = VENDOR/'objects/bottle.xml'
    upstream = ET.parse(source).getroot()
    assets = root.find('asset')
    if assets is None:
        assets = ET.SubElement(root, 'asset')
    prefix = item['name']+'_vendor_'
    names = {}
    for element in upstream.findall('./asset/*'):
        element = deepcopy(element)
        if element.get('name'):
            old = element.get('name')
            names[old] = prefix+old
            element.set('name', names[old])
        for node in element.iter():
            if node.get('file'):
                node.set('file', os.path.relpath((source.parent/node.get('file')).resolve(), output))
        assets.append(element)
    for node in assets:
        if node.get('name', '').startswith(prefix):
            for key in ('texture', 'material', 'mesh'):
                if node.get(key) in names:
                    node.set(key, names[node.get(key)])
    object_body = upstream.find(".//body[@name='object']")
    if object_body is None:
        raise ValueError('Upstream bottle object structure changed')
    for node in list(body):
        if node.tag == 'geom':
            body.remove(node)
    # Upstream origin is at the centre; its bottom site defines the SI offset.
    bottom = upstream.find(".//site[@name='bottom_site']")
    offset = -float(bottom.get('pos').split()[2])
    for index, source_geom in enumerate(object_body.findall('geom')):
        node = deepcopy(source_geom)
        node.set('name', prefix+str(index))
        for key in ('mesh', 'material'):
            if node.get(key) in names:
                node.set(key, names[node.get(key)])
        pos = [float(x) for x in node.get('pos', '0 0 0').split()]
        pos[2] += offset
        node.set('pos', values(pos))
        node.set('density', '0')
        node.set('friction', '.8 .005 .0001')
        body.append(node)


def add_facility(world, item):
    a, name = item['asset'], item['name']
    x, y, z = item['position_m']
    hx, hy = a['half_xy_m']
    body = ET.SubElement(world, 'body', name=name, pos=values([x, y, z]))
    style = dict(rgba=values(a['rgba']))
    geom(body, name+'_floor', 'box', [hx, hy, .0125], [0, 0, -.0125], **style)
    if a['kind'] == 'cabinet':
        h, t = a['height_m'], a['wall_m']
        for sign in (-1, 1):
            geom(body, f'{name}_side_{sign}', 'box', [t/2, hy, h/2],
                 [sign*(hx-t/2), 0, h/2], **style)
        geom(body, name+'_back', 'box', [hx, t/2, h/2], [0, hy-t/2, h/2], **style)
        geom(body, name+'_top', 'box', [hx, hy, t/2], [0, 0, h-t/2], **style)
        door = ET.SubElement(body, 'body', name=name+'_door', pos=values([-hx, -hy, 0]))
        ET.SubElement(door, 'joint', name=name+'_hinge', type='hinge', axis='0 0 1',
                      range='-1.5 0', limited='true', damping='2', frictionloss='.1')
        geom(door, name+'_door_panel', 'box', [hx-t-.002, t/2, h/2-t-.002], [hx, 0, h/2],
             mass='2', **style)
    return body
