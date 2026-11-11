import { Context } from '@deepseek-ai/cordis'
import { spawn } from 'node:child_process'
import { closeSync, mkdirSync, openSync, readFileSync, writeFileSync, existsSync } from 'node:fs'
import { dirname, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { PythonBridge, jsonlRecorder } from './robot-plugin.mjs'
import { capabilityPlugin, alignmentPlugin } from './guard_plugin.mjs'

const directory=dirname(fileURLToPath(import.meta.url))
const root=resolve(directory,'../..')
const args=process.argv.slice(2)
if(args.length!==2||args[0]!=='--suite'||!process.env.G1_PYTHON)throw new Error('Set G1_PYTHON; pass --suite NEW_REGISTERED_SUITE')
const suite=resolve(root,args[1])
if(!suite.startsWith(resolve(directory,'runs')+sep))throw new Error('Suite must be under cordis_t01/runs')
const read=path=>JSON.parse(readFileSync(path,'utf8'))
const write=(path,value)=>writeFileSync(path,JSON.stringify(value,null,2)+'\n',{flag:'wx'})
const registration=read(resolve(suite,'registration.json'))
write(resolve(suite,'launch.json'),{started:new Date().toISOString(),node:process.version,kernel:'4.0.6-alpha.1',schedule:registration.schedule})
mkdirSync(resolve(suite,'episodes'))
const results=[]
for(const job of registration.schedule){
  console.log(JSON.stringify({event:'started',index:results.length+1,total:registration.schedule.length,...job}))
  const output=resolve(suite,'episodes',job.case_id+'__'+job.condition)
  mkdirSync(output)
  const workerArgs=['--suite',suite,'--case-id',job.case_id,'--condition',job.condition]
  if(job.condition==='cordis_guard'){
    const ctx=new Context()
    const bridge=new PythonBridge({python:process.env.G1_PYTHON,root,output,worker:'experiments.cordis_t01.guard_worker',workerArguments:[...workerArgs,'--rpc']})
    const fiber=await ctx.plugin(capabilityPlugin(bridge,jsonlRecorder(resolve(output,'cordis-tools.jsonl'))))
    const guard=await ctx.plugin(alignmentPlugin())
    const invoke=tool=>ctx.serial('robot/tool',{tool})
    try{
      for(const tool of ['inspect_scene','grasp_cup','transfer_to_tray'])await invoke(tool)
      await ctx.serial('robot/placement-checkpoint')
      await invoke('release_in_tray')
      await invoke('verify_task')
    }catch(error){
      write(resolve(output,'driver_failure.json'),{error:error.message})
      try{await invoke('verify_task')}catch(error){console.error(error.message)}
    }finally{await guard.dispose();await fiber.dispose()}
  }else{
    const fd=openSync(resolve(output,'python-worker.log'),'wx')
    try{
      const code=await new Promise((done,reject)=>{
        const child=spawn(process.env.G1_PYTHON,['-B','-m','experiments.cordis_t01.guard_worker','--output',output,...workerArgs],{
          cwd:root,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1',OPENBLAS_NUM_THREADS:'1',MUJOCO_GL:process.env.MUJOCO_GL||'egl'},stdio:['ignore',fd,fd]})
        child.on('error',reject);child.on('close',done)
      })
      if(code!==0)write(resolve(output,'driver_failure.json'),{exit_code:code})
    }finally{closeSync(fd)}
  }
  const path=resolve(output,'result.json')
  const result=existsSync(path)?read(path):{...job,verified_success:false,infrastructure_failure:true}
  results.push(result)
  console.log(JSON.stringify({event:'completed',...result}))
}
const groups=Object.fromEntries(registration.conditions.map(condition=>{
  const rows=results.filter(r=>r.condition===condition)
  return[condition,{instances:rows.length,successes:rows.filter(r=>r.verified_success).length,corrections:rows.reduce((n,r)=>n+(r.corrections||0),0)}]
}))
write(resolve(suite,'results.json'),{date:new Date().toISOString(),status:'completed',boundary:'simulation',phase:registration.phase,groups,results,model_requests:0})
console.log(JSON.stringify({event:'suite_completed',groups}))
if(results.some(r=>r.infrastructure_failure||!r.source_unchanged))process.exitCode=1
