import fs from 'node:fs';
import {RAPIER,PHYSICS_DT,toV,colliderDesc,createBody,driveHinge} from './physics_registered.mjs';
const root=new URL('./',import.meta.url),m=JSON.parse(fs.readFileSync(new URL('registered_scene_manifest.json',root),'utf8'));
await RAPIER.init();const checks=[];
function check(name,ok,details){checks.push({name,passed:!!ok,details});console.log(name,!!ok);}
function setup(){
  const w=new RAPIER.World({x:0,y:-9.81,z:0});w.timestep=PHYSICS_DT;w.integrationParameters.numSolverIterations=10;
  m.static_colliders.forEach(c=>w.createCollider(colliderDesc(c)));
  const hinges=m.joints.map(r=>({...createBody(w,r,'hinge'),record:r,target:0,angle:0}));
  const props=m.props.map(r=>({...createBody(w,r,'prop'),record:r}));
  const micro=()=>{hinges.forEach(driveHinge);w.step();};const tick=s=>{for(let i=0;i<Math.ceil(s/PHYSICS_DT);i++)micro();};
  return {w,hinges,props,micro,tick};
}
{
  const s=setup();s.tick(5);
  const states=s.props.map(p=>{const v=p.body.translation(),a=toV(p.record.position),vel=p.body.linvel();return {id:p.record.id,drift:Math.hypot(v.x-a.x,v.z-a.z),drop:a.y-v.y,speed:Math.hypot(vel.x,vel.y,vel.z)};});
  check('Registered cups and bottles retain supports',states.every(p=>p.drift<.014&&p.drop<.03&&p.drop>-.008&&p.speed<.012),states);
  for(const h of s.hinges){h.target=h.record.open_angle_deg*Math.PI/180;h.body.wakeUp();}s.tick(6);
  const open=s.hinges.map(h=>({id:h.record.id,angle:h.angle*180/Math.PI,target:h.record.open_angle_deg}));
  check('All registered hinge references open correctly after yaw and height change',open.every(p=>Math.abs(p.angle-p.target)<2.0),open);
  for(const h of s.hinges){h.target=0;h.body.wakeUp();}s.tick(6);
  check('Registered doors close without residual global yaw',s.hinges.every(h=>Math.abs(h.angle)<.015),s.hinges.map(h=>({id:h.record.id,angle:h.angle})));
  s.w.free();
}
function journey(start,targets,doors=[]){
  const s=setup();s.tick(2);
  for(const id of doors){const d=s.hinges.find(h=>h.record.id===id);d.target=d.record.open_angle_deg*Math.PI/180;d.body.wakeUp();}s.tick(4);
  const p=toV(start),body=s.w.createRigidBody(RAPIER.RigidBodyDesc.kinematicPositionBased().setTranslation(p.x,p.y+.835,p.z));
  const cap=s.w.createCollider(RAPIER.ColliderDesc.capsule(.60,.22),body),cc=s.w.createCharacterController(.012);
  cc.setSlideEnabled(true);cc.enableAutostep(.21,.10,false);cc.enableSnapToGround(.18);cc.setApplyImpulsesToDynamicBodies(true);cc.setCharacterMass(70);
  const legs=[];
  for(const target of targets){const a=toV(target);for(let i=0;i<Math.round(30/PHYSICS_DT);i++){
    const q=body.translation(),dx=a.x-q.x,dz=a.z-q.z,dist=Math.hypot(dx,dz);if(dist<.035)break;
    const step=Math.min(dist,1.15*PHYSICS_DT);cc.computeColliderMovement(cap,{x:dx/dist*step,y:-.3*PHYSICS_DT,z:dz/dist*step});
    const v=cc.computedMovement();body.setNextKinematicTranslation({x:q.x+v.x,y:q.y+v.y,z:q.z+v.z});s.micro();
  }const v={...body.translation()};legs.push({target,actual:[v.x,-v.z,v.y-.835],plan_error:Math.hypot(v.x-a.x,v.z-a.z),height_error:Math.abs(v.y-.835-a.y)});}
  s.w.free();return legs;
}
const approach=journey([84.65,-38.5,9.86],[[84.65,-42.8,9.85],[65.8,-44.1,9.85],[61.1,-44.1,9.85],[61.1,-42.4,9.85],[59.4,-42.1,9.85]]);
check('Actual preserved HK44 bridge connects to the new 1F arrival and stair',approach.every(x=>x.plan_error<.06&&x.height_error<.035),approach);
const stair=journey([59.4,-42.1,9.85],[[59.4,-46.60,12.0166667],[59.4,-51.5,14.1833333],[59.4,-56.4,16.35],[62,-56.4,16.35],[62,-57.3,16.35]]);
check('Three real stair flights, two rest landings and the 2F lobby connect',stair.every(x=>x.plan_error<.06&&x.height_error<.035),stair);
const pantryToRooms=journey([58.5,-63.35,16.35],[[57.6,-63.35,16.35],[56.0,-63.35,16.35],[53.4,-67.2,16.35],[49.4,-71.0,16.35],[44.25,-75.35,16.35]],['DH_2F_pantry_secondary_entry']);
check('Secondary pantry entry and corridor physically connect to existing rooms',pantryToRooms.every(x=>x.plan_error<.06&&x.height_error<.035),pantryToRooms);
const closed=journey([56,-63.35,16.35],[[58.1,-63.35,16.35]]);
check('Closed pantry secondary door blocks passage',closed[0].actual[0]<56.85,closed);
const opened=journey([56,-63.35,16.35],[[58.1,-63.35,16.35]],['DH_2F_pantry_secondary_entry']);
check('Open secondary door permits passage',opened[0].plan_error<.06&&opened[0].height_error<.035,opened);
const mainId='DH_2F_pantry_entry';
const mainPath=journey([62,-57.3,16.35],[[65.6,-57.3,16.35],[65.6,-61.85,16.35],[63.2,-61.85,16.35]],[mainId]);
check('Common lobby and original pantry main door connect',mainPath.every(x=>x.plan_error<.06&&x.height_error<.035),mainPath);
fs.writeFileSync(new URL('registered_physics_verification.json',root),JSON.stringify({revision:m.revision,checks,passed:checks.every(c=>c.passed),scope:'Geometry-aligned Rapier natural use checks; no robot policy or full-city physics claim'},null,2));
if(checks.some(c=>!c.passed))process.exitCode=1;
