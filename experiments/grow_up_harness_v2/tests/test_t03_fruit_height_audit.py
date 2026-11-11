import copy,math,unittest
import numpy as np
from harness import t03_fruit_height_audit as H
from experiments.t0_agent_v1 import diversity_predicates as D
class FruitSupportGeometryTests(unittest.TestCase):
 def setUp(self):
  self.instance={'objects':[{'name':'fruit','asset':{'kind':'fruit','radii_m':[.034]*3,'mass_kg':.13}},
   {'name':'plate','asset':{'kind':'platter','half_xy_m':[.20,.12],'rim_m':.006,'floor_m':.006}}],'facilities':[],'regions':[]}
 def frame(self,q):
  center=np.array([0,0,.04]);root=center-D.rotation(q)@np.array([0,0,.034])
  return {'objects':{'fruit':{'position_m':root.tolist(),'quaternion_wxyz':q,'upward_support_N':{'plate_floor':1.3},'hand_contact_N':0.},
   'plate':{'position_m':[0,0,0],'quaternion_wxyz':[1,0,0,0]}}}
 def test_same_supported_sphere_changes_old_verdict_only(self):
  upright=self.frame([1,0,0,0]);tilted=self.frame([math.cos(math.pi/8),math.sin(math.pi/8),0,0])
  self.assertTrue(D.relation(self.instance,upright,'fruit','plate',True))
  self.assertFalse(D.relation(self.instance,tilted,'fruit','plate',True))
  self.assertTrue(H.proposed_relation(self.instance,upright,'fruit','plate',True))
  self.assertTrue(H.proposed_relation(self.instance,tilted,'fruit','plate',True))
 def test_actual_support_and_release_remain_required(self):
  f=self.frame([1,0,0,0]);f['objects']['fruit']['upward_support_N']['plate_floor']=.01
  self.assertFalse(H.proposed_relation(self.instance,f,'fruit','plate',True))
  f=self.frame([1,0,0,0]);f['objects']['fruit']['hand_contact_N']=.2
  self.assertFalse(H.proposed_relation(self.instance,f,'fruit','plate',True))
 def test_complete_footprint_remains_required(self):
  f=self.frame([1,0,0,0]);f['objects']['fruit']['position_m'][0]=.19
  self.assertFalse(H.proposed_relation(self.instance,f,'fruit','plate',True))

 def test_ellipsoid_in_tilted_container_uses_relative_lowest_point(self):
  import mujoco
  instance=copy.deepcopy(self.instance);radii=np.array([.039,.042,.038]);instance['objects'][0]['asset']['radii_m']=radii.tolist()
  q_obj=[math.cos(.41),math.sin(.41),0,0];q_plate=[math.cos(.025),0,math.sin(.025),0]
  ro=D.rotation(q_obj);rp=D.rotation(q_plate);relative=rp.T@ro
  vertical=float(np.linalg.norm(relative[2]*radii))
  root=rp@np.array([0,0,.006+vertical])-ro@np.array([0,0,radii[2]])
  f=self.frame([1,0,0,0]);f['objects']['fruit'].update(position_m=root.tolist(),quaternion_wxyz=q_obj);f['objects']['plate']['quaternion_wxyz']=q_plate
  self.assertAlmostEqual(H.geometry(instance,f,'fruit','plate')['geometric_bottom_height_error_m'],0.,places=12)
  self.assertTrue(H.proposed_relation(instance,f,'fruit','plate',True))
  for delta,expected in [(.0039,True),(.0041,False),(-.0041,False)]:
   shifted=copy.deepcopy(f);shifted['objects']['fruit']['position_m']=(root+rp@np.array([0,0,delta])).tolist()
   self.assertEqual(H.proposed_relation(instance,shifted,'fruit','plate',True),expected)
 def test_noncontainer_target_delegates_to_frozen_predicate(self):
  instance=copy.deepcopy(self.instance);instance['objects']=instance['objects'][:1]
  instance['regions']=[{'name':'region','position_m':[0,0,0],'quaternion_wxyz':[1,0,0,0],'half_xy_m':[.2,.12],'support_body':'world'}]
  f=self.frame([1,0,0,0]);f['objects']['region']=f['objects'].pop('plate');f['objects']['fruit']['upward_support_N']={'world':1.3}
  self.assertEqual(H.proposed_relation(instance,f,'fruit','region',True),D.relation(instance,f,'fruit','region',True))
