"""Audit saved verdicts, rank successful holdouts, and render faithful 1x replays."""
import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'experiments/grow_up_harness_v2'
sys.path[:0] = [str(ROOT), str(PACKAGE), str(PACKAGE / 'calibration')]

from mapping_holdout import inventory, read, rel, sha
from harness import grow_loop as L, t02_episode
from experiments.t0_agent_v1.tray_verify import verify, summarize, tray_predicate


def official_first_success(episode, verdict):
    rows = read(episode / 'verified_samples.json')
    names = list(rows[0]['cups'])
    since = previous = None
    for i, row in enumerate(rows):
        passed = (all(tray_predicate(c) for c in row['cups'].values())
                  and row['tray_linear_speed_m_s'] <= .02 and row['tray_angular_speed_rad_s'] <= .2
                  and row['tray_tilt_deg'] <= 5. and row['tray_hand_contact_N'] < .1)
        if not passed:
            since = None
        elif since is None or (previous is not None and row['time'] - previous > .051):
            since = row['time']
        if since is not None and row['time'] - since >= 1.:
            checked = summarize(rows[:i + 1], names, verdict['execution_error'], verdict['protection'], verdict['initial_valid'])
            if checked['verified_success']:
                return row['time']
        previous = row['time']
    return None


def render(output, choice, fps=20):
    import mujoco
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    episode = ROOT / choice['episode_path']
    reference = read(episode / 'model_reference.json')
    model_path = ROOT / reference['path']
    if sha(model_path) != reference['sha256']:
        raise ValueError('render model differs from the recorded model')
    model = mujoco.MjModel.from_binary_path(str(model_path))
    for name in ('task_observer', 'g1_head'):
        model.camera(name)
    data = mujoco.MjData(model)
    options = mujoco.MjvOption()
    options.geomgroup[:] = [0, 1, 1, 0, 0, 0]
    videos = output / 'videos'
    videos.mkdir(exist_ok=True)
    base = videos / (choice['family'] + '_' + choice['arm'])
    video = base.with_suffix('.mp4')
    font_path = '/home/tulipe/.local/share/fonts/NotoSansCJK-Regular.ttc'
    font = ImageFont.truetype(font_path, 20)
    small = ImageFont.truetype(font_path, 17)
    samples = read(episode / 'verified_samples.json')
    command = ['ffmpeg', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '1280x466',
               '-r', str(fps), '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-preset', 'veryfast',
               '-crf', '22', '-threads', '2', '-pix_fmt', 'yuv420p', '-movflags', 'frag_keyframe+empty_moov',
               '-f', 'mp4', 'pipe:1']
    with np.load(episode / 'trajectory.npz', allow_pickle=False) as trace:
        times = trace['time']
        frames = math.ceil(float(times[-1]) * fps) + 1
        if len(times) != len(samples):
            raise ValueError('trajectory and evaluator sample counts differ')
        with video.open('xb') as target, base.with_suffix('.encoding.log').open('x') as log:
            encoder = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=target, stderr=log)
            try:
                with mujoco.Renderer(model, height=360, width=640, max_geom=4000) as renderer:
                    for frame in range(frames):
                        time_s = frame / fps
                        i = int(np.clip(np.searchsorted(times, time_s, side='right') - 1, 0, len(times) - 1))
                        data.qpos[:], data.qvel[:], data.time = trace['qpos'][i], trace['qvel'][i], times[i]
                        mujoco.mj_forward(model, data)
                        canvas = Image.new('RGB', (1280, 466), '#121a25')
                        for panel, camera in enumerate(('task_observer', 'g1_head')):
                            renderer.update_scene(data, camera=camera, scene_option=options)
                            canvas.paste(Image.fromarray(renderer.render().copy()), (panel * 640, 78))
                        draw = ImageDraw.Draw(canvas)
                        score_label = '诊断分数' if choice['family'] == 'T01' else '最小杯底余量(m)'
                        name = 'Skill / 按ID调用同一工件' if choice['arm'] == 'skill' else 'Code / 直接执行同一工件'
                        draw.text((12, 1), f"{choice['family']}  {name}  |  独立验收 PASS", font=font, fill='#98edbd')
                        draw.text((12, 29), f"{choice['task_id']}  |  {score_label}={choice['score']:.6f}  |  首次稳定成功 {choice['first_success_s']:.2f}s", font=small, fill='white')
                        draw.text((12, 54), '仿真保存轨迹 · 1×原速 · 观察者视角仅用于回放', font=small, fill='#d0d7e4')
                        draw.text((652, 54), '机器人头部视角', font=small, fill='#d0d7e4')
                        margin = min(c['footprint_margin_m'] for c in samples[i]['cups'].values())
                        draw.text((12, 441), f"物理时间 {time_s:.2f}s  |  当前最小杯底余量 {margin*1000:.2f}mm  |  候选工件，未晋升", font=small, fill='white')
                        if frame == frames - 1:
                            canvas.save(base.with_suffix('.final.png'))
                        if frame == frames // 2:
                            canvas.save(base.with_suffix('.preview.png'))
                        encoder.stdin.write(canvas.tobytes())
            finally:
                encoder.stdin.close()
                code = encoder.wait()
            if code:
                raise RuntimeError('video encoding failed: ' + str(video))
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                       '-show_entries', 'stream=width,height,avg_frame_rate,nb_read_frames:format=duration',
                       '-of', 'json', str(video)], text=True))
    if int(probe['streams'][0]['nb_read_frames']) != frames or abs(float(probe['format']['duration']) - frames / fps) > .01:
        raise ValueError('encoded video frame count or duration mismatch')
    meta = {'video': rel(video), 'sha256': sha(video), 'trajectory_sha256': sha(episode / 'trajectory.npz'),
            'verdict_sha256': sha(ROOT / choice['verdict_path']), 'selection': choice,
            'fps': fps, 'frames': frames, 'playback_speed': 1., 'probe': probe,
            'renderer_sha256': sha(Path(__file__)),
            'rendering': 'mj_forward only, no physics or model calls; saved qpos/qvel at their original timestamps'}
    L.write_new(base.with_suffix('.json'), meta)
    return {'video': rel(video), 'frames': frames, 'duration_s': frames / fps}


def select(output, family_filter=None):
    import numpy as np
    registration = read(output / 'registration.json')
    if inventory(output / 'exports') != read(output / 'store_frozen.json')['files']:
        raise ValueError('frozen mapping exports changed')
    choices = []
    for family, generated in registration['tasks'].items():
        if family_filter is not None and family != family_filter: continue
        summary = read(output / family / 'summary.json')
        if summary['status'] == 'void': raise ValueError('void batch cannot supply success videos')
        task = generated['tasks'][0]
        manifest = read(output / 'exports' / family / 'manifest.json')
        for arm in ('code', 'skill'):
            folder = output / family / task['task_id'] / arm
            if arm == 'skill': folder = folder / 'execution'
            if not (folder / 'result.json').exists(): continue
            result, verdict = read(folder / 'result.json'), read(folder / 'verdict.json')
            if not result['success']: continue
            if not verdict.get('verified_local_success', verdict.get('verified_success')):
                raise ValueError('result and independent verdict disagree')
            if result['source_sha256'] != manifest['code_sha256']:
                raise ValueError('success did not execute the mapped artifact bytes')
            with np.load(ROOT / task['private']['initial_source'], allow_pickle=False) as a, np.load(folder / 'episode/initial_state.npz', allow_pickle=False) as b:
                if set(a.files) != set(b.files) or not all(np.array_equal(a[k], b[k]) for k in a.files):
                    raise ValueError('video episode differs from registered initial')
            score = result['score'] if family == 'T01' else min(c['footprint_margin_m'] for c in verdict['final']['cups'].values())
            choices.append({'family':family, 'arm':arm, 'task_id':task['task_id'], 'artifact_ref':manifest['artifact_ref'],
                 'skill_execution':'artifact_call', 'episode_path':rel(folder/'episode'), 'verdict_path':rel(folder/'verdict.json'),
                 'score':score, 'first_success_s':official_first_success(folder/'episode',verdict),
                 'simulation_seconds':result['simulation_seconds'], 'source_sha256':result['source_sha256']})
    result = {'selected':choices, 'rule':'all independently successful preselected same-artifact code/skill arms; no best-of sampling',
              'missing_successful_arms':[f+'_'+a for f in registration['tasks'] if family_filter is None or f==family_filter for a in ('code','skill') if not any(c['family']==f and c['arm']==a for c in choices)]}
    L.write_new(output / ('video_selection_' + family_filter + '.json' if family_filter else 'video_selection.json'),result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['select','render'])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--family',choices=['T01','T02'])
    parser.add_argument('--arm',choices=['skill','code'])
    args=parser.parse_args();output=args.output.resolve()
    if args.action=='select': result=select(output,args.family)
    else:
        selected=read(output / ('video_selection_' + args.family + '.json' if args.family else 'video_selection.json'))['selected']
        result=[render(output,c) for c in selected if (args.family is None or c['family']==args.family) and (args.arm is None or c['arm']==args.arm)]
    print(json.dumps(result,ensure_ascii=False,indent=1),flush=True)
if __name__=='__main__':main()
