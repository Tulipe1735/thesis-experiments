"""Render any actual saved T03 episode without changing its failure/success identity."""
import argparse,math,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'experiments/grow_up_harness_v2')]
from harness import tp01
from experiments.t0_agent_v1.tabletop_training_plant import configure_robot,set_left_hand_impedance
from experiments.t0_agent_v1.common import read,write_new,sha,relative
import mujoco,numpy as np
from PIL import Image


def render(episode,scene,output,fps=20):
 if output.exists():raise FileExistsError(output)
 verdict=read(episode/'verdict.json')
 output.parent.mkdir(parents=True,exist_ok=True)
 model=mujoco.MjModel.from_xml_path(str(scene));configure_robot(model);cfg=read(episode/'left_hand_impedance.json');set_left_hand_impedance(model,cfg['kp'],cfg['kd']);data=mujoco.MjData(model)
 with np.load(episode/'integration_states.npz') as trace:times=trace['time'].copy();states=trace['integration_state'].copy()
 duration=float(times[-1]-times[0]);count=math.ceil(duration*fps);width,height=960,540
 options=mujoco.MjvOption();options.geomgroup[:]=[0,1,1,0,0,0]
 renderer=mujoco.Renderer(model,height=height,width=width,max_geom=5000)
 log=output.with_suffix('.ffmpeg.log')
 with log.open('xb') as err:
  process=subprocess.Popen(['ffmpeg','-n','-loglevel','warning','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}','-r',str(fps),'-i','-',
   '-an','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],stdin=subprocess.PIPE,stderr=err)
  try:
   for index in range(count):
    time=times[0]+index/fps;i=min(len(times)-1,int(np.searchsorted(times,time,side='right')-1))
    if index==count-1:i=len(times)-1
    mujoco.mj_setState(model,data,states[i],mujoco.mjtState.mjSTATE_INTEGRATION);mujoco.mj_forward(model,data)
    renderer.update_scene(data,camera='g1_head',scene_option=options);rgb=renderer.render()
    if index in (0,count-1):
     suffix='_first.png' if index==0 else '_last.png'
     with output.with_name(output.stem+suffix).open('xb') as f:Image.fromarray(rgb).save(f,format='PNG')
    process.stdin.write(rgb.tobytes())
    if index%250==0:print('render',index,'/',count,flush=True)
  finally:
   process.stdin.close();code=process.wait();renderer.close()
 if code:raise RuntimeError('ffmpeg failed: '+str(code))
 write_new(output.with_suffix('.json'),{'source_episode':relative(episode),'scene':relative(scene),'scene_sha256':sha(scene),
  'trajectory_sha256':sha(episode/'integration_states.npz'),'verdict_sha256':sha(episode/'verdict.json'),'video_sha256':sha(output),
  'fps':fps,'frames':count,'simulation_duration_s':duration,'video_duration_s':count/fps,'speed':1.,
  'sampling':'20Hz saved-state replay, terminal state in final frame; duration quantization <1 frame','physics_steps':0,'camera':'g1_head','scope':'actual whole episode; verdict success/failure preserved',
  'evaluator_version':verdict['evaluator_version'],'verified_task_success':verdict['verified_task_success']})
 print('video',output.resolve(),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--episode',type=Path,required=True);p.add_argument('--scene',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();render(a.episode,a.scene,a.output)
