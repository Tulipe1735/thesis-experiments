"""Export declared representative trajectory replays and the complete request table."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import io
import json
import math
import multiprocessing
import os
from pathlib import Path
import subprocess

os.environ.setdefault('MUJOCO_GL', 'egl')
os.environ.setdefault('LP_NUM_THREADS', '4')
import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from experiments.t0_agent_v1.common import ROOT, read, relative, sha, write_new

MAIN = ROOT/'experiments/ros_skill_cycle/runs/cycle_20261029_008'
VIEW = ROOT/'experiments/ros_skill_cycle/runs/active_view_20261029_001'
CONFIRM = ROOT/'experiments/ros_skill_cycle/runs/active_view_confirmation_20261029_001'


def render(job):
    episode, video = ROOT/job['episode'], ROOT/job['video']
    ref = read(episode/'model_reference.json')
    if sha(ROOT/ref['path']) != ref['sha256']:
        raise ValueError('Model reference changed')
    verdict = read(episode/'independent_verification.json')
    samples = read(episode/'verified_samples.json')
    events = [json.loads(line) for line in (episode.parent/'memory.jsonl').read_text().splitlines()]
    events = [event for event in events if 'simulation_seconds' in event]
    model = mujoco.MjModel.from_binary_path(str(ROOT/ref['path']))
    data = mujoco.MjData(model)
    options = mujoco.MjvOption()
    options.geomgroup[:] = [0,1,1,0,0,0]
    font = ImageFont.truetype(job['font'], 18)
    small = ImageFont.truetype(job['font'], 15)
    physical = 'PASS' if verdict['verified_success'] else 'FAIL'
    color = '#86efac' if verdict['verified_success'] else '#fca5a5'
    fps = job['fps']
    command = ['ffmpeg','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','1280x456',
        '-r',str(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','veryfast','-crf','22',
        '-threads','2','-pix_fmt','yuv420p','-movflags','frag_keyframe+empty_moov','-f','mp4','pipe:1']
    with np.load(episode/'trajectory.npz',allow_pickle=False) as trace:
        times = trace['time']
        if len(times)!=len(samples):
            raise ValueError('Trajectory/evaluator frame count differs')
        frames = int(math.ceil(float(times[-1])*fps))+1
        with video.open('xb') as target, video.with_suffix('.encoding.log').open('x') as log:
            encoder = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=target,stderr=log)
            try:
                with mujoco.Renderer(model,height=360,width=640,max_geom=4000) as renderer:
                    for frame in range(frames):
                        t = frame/fps
                        i = int(np.clip(np.searchsorted(times,t,side='right')-1,0,len(times)-1))
                        data.qpos[:],data.qvel[:],data.time = trace['qpos'][i],trace['qvel'][i],times[i]
                        mujoco.mj_forward(model,data)
                        canvas = Image.new('RGB',(1280,456),'#101827')
                        for panel,camera in enumerate(('task_observer','g1_head')):
                            renderer.update_scene(data,camera=camera,scene_option=options)
                            canvas.paste(Image.fromarray(renderer.render().copy()),(panel*640,72))
                        draw = ImageDraw.Draw(canvas)
                        draw.text((10,1),f"{job['label']} | 仿真 / 保存轨迹 / 1x 原速",font=font,fill='white')
                        draw.text((10,25),f"最终独立物理验收：{physical} | 最终公开核验：{job['runtime_check']} | {job['case_id']}",font=font,fill=color)
                        draw.text((10,50),'观察者视角（仅回放，不进入技能）',font=small,fill='white')
                        draw.text((650,50),'机器人头部视角',font=small,fill='white')
                        cup = samples[i]['cups']['task_cup']
                        stage = next((e['stage'] for e in reversed(events) if e['simulation_seconds']<=t),'initial')
                        footer = (f"t={t:.2f}s | {stage} | 离线验收：杯底余量 {cup['footprint_margin_m']*1000:.1f}mm，"
                            f"底板支撑 {cup['tray_floor_support_N']:.2f}N，手接触 {cup['hand_contact_N']:.2f}N")
                        draw.text((10,434),footer,font=small,fill='white')
                        if frame==frames-1:
                            canvas.save(video.with_suffix('.final.png'))
                        encoder.stdin.write(canvas.tobytes())
            finally:
                encoder.stdin.close()
                code=encoder.wait()
            if code:
                raise RuntimeError('Encoding failed: '+job['case_id'])
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=width,height,avg_frame_rate,nb_read_frames:format=duration','-of','json',str(video)],text=True))
    actual=probe['streams'][0]
    if int(actual['nb_read_frames'])!=frames or abs(float(probe['format']['duration'])-frames/fps)>.01:
        raise ValueError('Video frame count or duration mismatch')
    result=dict(id=job['id'],label=job['label'],case_id=job['case_id'],episode=job['episode'],video=job['video'],
        independent_success=verdict['verified_success'],runtime_check=job['runtime_check'],frames=frames,
        fps=fps,seconds=frames/fps,dimensions=[1280,456],playback_rate=1,physics_advanced=False,
        trajectory_sha256=sha(episode/'trajectory.npz'),video_sha256=sha(video),video_bytes=video.stat().st_size)
    write_new(video.with_suffix('.json'),result)
    return result


def export(output,workers,fps):
    output.mkdir(parents=True,exist_ok=False)
    declarations=[
        ('S01','已知失败：原流程',MAIN/'jobs/orientation_280201__nominal'),
        ('S02','同初态修复：冻结 1.1 版',CONFIRM/'jobs/orientation_280201__active_view'),
        ('S03','观察修订前：物理成功，公开证据不足',MAIN/'jobs/fresh_480100__gain050'),
        ('S04','观察修订后：开发回归通过',VIEW/'development/jobs/fresh_480100__active_view'),
        ('S05','冻结后新初态：成功复用',VIEW/'frozen_test/jobs/position_840100__active_view'),
        ('S06','保留新初态失败：抓取载荷不足',VIEW/'frozen_test/jobs/joint_840300__active_view'),
        ('S07','外部扰动挑战：证据不足，不返回成功',VIEW/'boundary/jobs/active_boundary_01__active_view')]
    bindings={}
    jobs=[]
    font=subprocess.check_output(['fc-match','-f','%{file}','sans-serif:lang=zh-cn'],text=True).strip()
    for name,label,folder in declarations:
        row=read(folder/'execution/result.json')
        video=output/(name+'_'+row['case_id']+'.mp4')
        jobs.append(dict(id=name,label=label,case_id=row['case_id'],episode=row['episode'],
            video=relative(video),runtime_check=row['runtime_result']['runtime_check'],fps=fps,font=font))
        episode=ROOT/row['episode']
        for path in [folder/'execution/result.json',episode.parent/'memory.jsonl']+[
                episode/n for n in ['trajectory.npz','independent_verification.json','verified_samples.json','model_reference.json']]:
            bindings[relative(path)]=sha(path)
        ref=read(episode/'model_reference.json');bindings[ref['path']]=ref['sha256']
    all_rows=[]
    for suite,phase in [(MAIN,'development'),(MAIN/'frozen_test','frozen_test'),(MAIN/'boundary','boundary'),
                        (VIEW/'development','v1.1_development'),(VIEW/'frozen_test','v1.1_frozen_test'),
                        (VIEW/'boundary','v1.1_boundary'),(CONFIRM,'v1.1_paired_confirmation')]:
        path=suite/('development_results.json' if suite==MAIN else 'results.json')
        value=read(path)
        rows=value.get('rows',value.get('results',[])) if isinstance(value,dict) else value
        bindings[relative(path)]=sha(path)
        all_rows.extend(dict(row,export_phase=phase) for row in rows)
    if len(all_rows)!=59 or sum(r['physical_episodes'] for r in all_rows)!=57:
        raise ValueError('Full request denominator differs from registered execution')
    write_new(output/'export_registration.json',dict(date='2026-10-29',boundary='simulation',
        selection='7 declared representative cases, not statistical samples; full 59-request table retained',
        videos=jobs,source_bindings=bindings,exporter_source=relative(Path(__file__)),
        exporter_sha256=sha(Path(__file__)),physics_advanced=False,model_requests=0))
    stream=io.StringIO(newline='');columns=['phase','case_id','arm','physical_episodes','independent_success',
        'runtime_check','failed_tool','execution_error','simulation_seconds','low_level_commands','evidence']
    writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
    for row in all_rows:
        writer.writerow(dict(phase=row['export_phase'],case_id=row['case_id'],arm=row['arm'],
            physical_episodes=row['physical_episodes'],independent_success=row['independent_success'],
            runtime_check=row['runtime_result']['runtime_check'],failed_tool=row['failed_tool'],
            execution_error=json.dumps(row['execution_error'],ensure_ascii=False),
            simulation_seconds=row['simulation_seconds'],low_level_commands=row['low_level_command_calls'],evidence=row['job']))
    with (output/'all_59_requests.csv').open('x',encoding='utf-8-sig',newline='') as handle:
        handle.write(stream.getvalue())
    records={}
    with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        futures={pool.submit(render,job):job['id'] for job in jobs}
        for future in as_completed(futures):
            result=future.result();records[result['id']]=result
            print(json.dumps(dict(event='video_complete',id=result['id'],done=len(records),total=len(jobs)),ensure_ascii=False),flush=True)
    if not all(sha(ROOT/path)==digest for path,digest in bindings.items()):
        raise ValueError('Source evidence changed during rendering')
    ordered=[records[job['id']] for job in jobs]
    sheet=Image.new('RGB',(1280,228*4),'#101827')
    for i,row in enumerate(ordered):
        with Image.open((ROOT/row['video']).with_suffix('.final.png')) as frame:
            sheet.paste(frame.resize((640,228)),((i%2)*640,(i//2)*228))
    sheet.save(output/'contact_sheet.png')
    write_new(output/'manifest.json',dict(status='completed',boundary='simulation',videos=ordered,
        request_count=59,physical_episodes=57,representative_video_count=7,source_evidence_unchanged=True,
        fps=fps,playback_rate=1,new_physics_steps=0,model_requests=0,
        total_bytes=sum(r['video_bytes'] for r in ordered),total_seconds=sum(r['seconds'] for r in ordered)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--fps',type=int,default=15)
    args=parser.parse_args();export(args.output.resolve(),args.workers,args.fps)
