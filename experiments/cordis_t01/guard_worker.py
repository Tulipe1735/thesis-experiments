"""Shared physical backend for plain Python and Cordis; only dispatch differs."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import traceback
from .variation_worker import Session as BaseSession
from .guard_skills import GuardSkills
from experiments.t0_agent_v1.common import relative,sha,write_new,append_event
from experiments.t0_agent_v1.tray_verify import verify


class Session(BaseSession):
    def __init__(self,*args,condition):
        self.condition=condition
        super().__init__(*args)

    def initialize(self):
        super().initialize()
        self.skills=GuardSkills(self.port,self.folder)

    def finalize(self):
        if self.result is not None:return self.result
        if self.robot is None:raise ValueError('No physical episode initialized')
        if not self.closed:
            self.robot.finish();self.closed=True
        error=self.error or (None if self.skills.stage=='placed' else 'COMPOSITION_NOT_FINISHED')
        verdict=verify(self.folder,execution_error=error)
        self.result=dict(case_id=self.case['id'],condition=self.condition,boundary='simulation',
            verified_success=verdict['verified_success'],initial_valid=verdict['initial_valid'],
            terminal_stable_s=verdict['terminal_simultaneous_stable_s'],stage=self.skills.stage,
            failed_tool=self.failed_tool,execution_error=error,episode=relative(self.folder),
            simulation_seconds=float(self.robot.data.time),physical_episodes=1,
            high_level_tool_calls=self.calls+1,cordis_tool_calls=self.calls+1 if self.condition=='cordis_guard' else 0,
            low_level_command_calls=self.port.command_calls,alignment_checks=self.skills.alignment_checks,
            corrections=self.skills.corrections,source_unchanged=self.unchanged(),model_requests=0,
            initial_sha256=sha(self.folder/'initial_state.npz'),trajectory_sha256=sha(self.folder/'trajectory.npz'),
            verdict_sha256=sha(self.folder/'independent_verification.json'),wall_seconds=time.monotonic()-self.started)
        write_new(self.output/'result.json',self.result)
        return self.result


def run_plain(session):
    try:
        for tool in ('inspect_scene','grasp_cup','transfer_to_tray'):session.call(tool,{})
        if session.condition=='plain_guard':
            result=session.call('inspect_alignment',{})
            if result['status']=='CORRECT':session.call('correct_alignment',{})
        session.call('release_in_tray',{})
    except Exception:
        traceback.print_exc(file=sys.stderr)
    return session.call('verify_task',{})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--suite',type=Path,required=True)
    parser.add_argument('--case-id',required=True)
    parser.add_argument('--condition',choices=['plain_baseline','plain_guard','cordis_guard'],required=True)
    parser.add_argument('--rpc',action='store_true')
    args=parser.parse_args()
    if not args.rpc:
        session=Session(args.output,args.suite,args.case_id,condition=args.condition)
        print(json.dumps(run_plain(session),ensure_ascii=False));return
    protocol=os.fdopen(os.dup(sys.stdout.fileno()),'w',encoding='utf-8',buffering=1)
    os.dup2(sys.stderr.fileno(),sys.stdout.fileno())
    session=None
    try:
        for line in sys.stdin:
            request=json.loads(line)
            try:
                if session is None:session=Session(args.output,args.suite,args.case_id,condition=args.condition)
                result=session.call(request['tool'],request.get('arguments',{}))
                response=dict(id=request['id'],ok=True,result=result)
            except Exception as error:
                traceback.print_exc(file=sys.stderr)
                response=dict(id=request['id'],ok=False,error=dict(type=type(error).__name__,message=str(error)))
            protocol.write(json.dumps(response,ensure_ascii=False,allow_nan=False)+'\n')
    finally:
        if session and session.robot and session.result is None:session.finalize()


if __name__=='__main__':main()
