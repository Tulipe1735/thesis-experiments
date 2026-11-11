// The native's registered poses are authoritative; relative child colliders stay local.
import RAPIER from './vendor/rapier/rapier.mjs';
export {RAPIER};
export const PHYSICS_DT=1/240;
export const toV=p=>({x:p[0],y:p[2],z:-p[1]});
export const toQ=p=>({x:p?.[1]??0,y:p?.[3]??0,z:-(p?.[2]??0),w:p?.[0]??1});
function mul(a,b){return {w:a.w*b.w-a.x*b.x-a.y*b.y-a.z*b.z,x:a.w*b.x+a.x*b.w+a.y*b.z-a.z*b.y,y:a.w*b.y-a.x*b.z+a.y*b.w+a.z*b.x,z:a.w*b.z+a.x*b.y-a.y*b.x+a.z*b.w};}
function rotate(q,v){const p=mul(mul(q,{w:0,...v}),{w:q.w,x:-q.x,y:-q.y,z:-q.z});return {x:p.x,y:p.y,z:p.z};}
export function colliderDesc(c){
  const d=c.shape==='trimesh'?RAPIER.ColliderDesc.trimesh(new Float32Array(c.vertices.flatMap(p=>[p[0],p[2],-p[1]])),new Uint32Array(c.indices)):
    c.shape==='cylinder'?RAPIER.ColliderDesc.cylinder(c.half_height,c.radius):RAPIER.ColliderDesc.cuboid(c.half[0],c.half[2],c.half[1]);
  const p=toV(c.center);return d.setTranslation(p.x,p.y,p.z).setRotation(toQ(c.rotation)).setFriction(.72).setRestitution(.01);
}
export function createBody(world,r,kind){
  const p=toV(r.position),q=toQ(r.rotation);
  // Bake the reference yaw into the hinge's local collision shapes. The body
  // now starts at identity, so the engine motor's zero really is the closed
  // pose. Rendering must compose body quaternion * reference quaternion.
  const identity={w:1,x:0,y:0,z:0};
  const body=world.createRigidBody(RAPIER.RigidBodyDesc.dynamic().setTranslation(p.x,p.y,p.z).setRotation(kind==='hinge'?identity:q).setCcdEnabled(true).setLinearDamping(kind==='hinge'?1.5:.2).setAngularDamping(kind==='hinge'?1.2:.45));
  r.colliders.forEach(c=>{
    const d=colliderDesc(c).setMass((r.mass_kg??3.1)/r.colliders.length).setFriction(r.friction??.65).setRestitution(r.restitution??.01);
    if(kind==='hinge'){const a=rotate(q,toV(c.center));d.setTranslation(a.x,a.y,a.z).setRotation(mul(q,toQ(c.rotation)));}
    world.createCollider(d,body);
  });
  if(kind!=='hinge')return {body};
  const anchor=world.createRigidBody(RAPIER.RigidBodyDesc.fixed().setTranslation(p.x,p.y,p.z));
  const joint=world.createImpulseJoint(RAPIER.JointData.revolute({x:0,y:0,z:0},{x:0,y:0,z:0},{x:0,y:1,z:0}),anchor,body,true);
  body.setEnabledRotations(false,false,false,true);joint.setLimits(0,0);joint.configureMotorModel(RAPIER.MotorModel.ForceBased);
  return {body,anchor,joint,reference:q};
}
export function driveHinge(h){
  const rel=h.body.rotation();
  h.angle=2*Math.atan2(rel.y,rel.w);while(h.angle>Math.PI)h.angle-=2*Math.PI;while(h.angle<-Math.PI)h.angle+=2*Math.PI;
  const latched=h.target===0&&Math.abs(h.angle)<.006&&Math.abs(h.body.angvel().y)<.03;
  h.body.setEnabledRotations(false,!latched,false,true);
  if(latched)h.joint.setLimits(0,0);else h.joint.setLimits(h.record.limits_deg[0]*Math.PI/180,h.record.limits_deg[1]*Math.PI/180);
  h.joint.configureMotorPosition(h.target,h.record.id.includes('entry')?320:55,h.record.id.includes('entry')?60:12);
}
