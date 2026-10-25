"""Autonomous task teams and artifact-scoped internal agent-to-agent handoffs."""
import asyncio
from typing import Literal
from pydantic import Field
from ..schemas import Model
from ..research_schemas import Finding
from uuid import uuid4
from .paths import timestamp

class AgentMessage(Model):
    id:str
    from_task_id:str
    to_task_id:str
    kind:Literal['assignment','artifact_handoff','result','blocked']
    summary:str=Field(min_length=1,max_length=1200)
    artifact_refs:list[str]=Field(default_factory=list,max_length=30)
    at:str
    dataset_version:str

def message(engine,rid,sender,recipient,kind,summary,refs=()):
    def save(d):
        tasks={t['id']:t for t in d['tasks']};artifacts={a['id']:a for a in d['artifacts']}
        if sender not in tasks or recipient not in tasks:raise ValueError('Unknown agent in handoff.')
        allowed={a['id'] for a in d['artifacts'] if sender=='coordinator' or a['task_id']==sender or a['id'] in tasks[sender]['input_artifact_ids']}
        if not set(refs)<=allowed:raise ValueError('Handoff exceeds sender artifact scope.')
        if any(artifacts[r].get('dataset_version',d['dataset_version'])!=d['dataset_version'] for r in refs):raise ValueError('Handoff dataset mismatch.')
        envelope=AgentMessage.model_validate({'id':'message-'+uuid4().hex,'from_task_id':sender,'to_task_id':recipient,'kind':kind,'summary':summary,'artifact_refs':list(refs),'at':timestamp(),'dataset_version':d['dataset_version']})
        d.setdefault('agent_messages',[]).append(envelope.model_dump(mode='json'))
        return d
    engine.edit(rid,save);engine.event(rid,'agent.'+kind,sender,summary,inputs=list(refs),outputs=[recipient])

async def dispatch(engine,rid,worker,guard,children,semaphore):
    state=engine.store.get(rid)
    if state.get('network_dispatched'):return
    if state['budget']['max_spawned_tasks']-state['budget']['spawned_tasks']<4:raise RuntimeError('Spawn budget cannot accommodate the required independent team.')
    declared={tool for p in state.get('paths',[]) for tool in p['expected_tools']}
    jobs={
      'identity':[('validate_variant_identity',{}),('resolve_reference_sequence',{})],
      'assay':[('inspect_assay',{'assay_id':'activity'}),('inspect_assay',{'assay_id':'abundance'}),('assess_comparability',{}),('summarize_measurement_coverage',{}),('filter_measurements',{})],
      'structure':[('load_structure_metadata',{}),('align_structure_reference',{}),('map_variant_residues',{})],
    }
    mapped=sorted([v for v in state['input_variants'] if v['mapping']['status']=='mapped'],key=lambda v:v['id'])
    if 'find_spatial_neighbors' in declared and mapped:jobs['structure'].append(('find_spatial_neighbors',{'variant_id':mapped[0]['id'],'radius':state['request'].get('neighbor_radius',10)}))
    if 'calculate_residue_distances' in declared and len(mapped)>1:jobs['structure'].append(('calculate_residue_distances',{'variant_id':mapped[0]['id'],'other_variant_id':mapped[1]['id']}))
    ids={role:'team-'+role+'-'+uuid4().hex[:8] for role in jobs}
    def assign(d):
        d['network_dispatched']=True;d['budget']['spawned_tasks']+=3
        for role,tools in jobs.items():
            path=next((p for p in d.get('paths',[]) if any(name in p['expected_tools'] for name,_ in tools)),None)
            d['tasks'].append({'id':ids[role],'role':role,'question':'Inspect the assigned '+role+' evidence. Computations are already executed; finalize qualitative observations from those artifacts. Do not include numeric quantities, ranges, resolution, version numbers or coordinate positions in prose. Let the result plots and tables display them. If essential, numeric facts require exact numeric_claims with stored paths and unrounded values. Reference the actual artifacts and preserve uncertainty.','allowed_tools':[name for name,_ in tools],'input_artifact_ids':[],'parent_task_id':'coordinator','depth':1,'status':'queued','max_steps':4,'engine':'deterministic identity validator' if role=='identity' else 'independent model reviewer + deterministic tools','path_id':path['id'] if path else None,'depends_on':[] if role=='identity' else [ids['identity']],'tool_plan':[{'tool':name,'arguments':args,'reason':'Required PTEN evidence check' if name not in declared else 'Capability selected in the research lead’s declared plan'} for name,args in tools]})
        return d
    engine.edit(rid,assign)
    for role,tid in ids.items():
        engine.event(rid,'task.queued',tid,'Independent '+role+' team assigned from the lead’s research plan.')
        message(engine,rid,'coordinator',tid,'assignment','The lead delegated scoped '+role+' work with explicit dependencies.')
    async def branch(role):
        tid=ids[role]
        try:
            if role!='identity':
                await children[ids['identity']]
                upstream=engine.store.get(rid)
                if next(t for t in upstream['tasks'] if t['id']==ids['identity'])['status']!='completed':raise ValueError('Identity precondition failed; dependent scientific work is unavailable.')
                refs=[a['id'] for a in upstream['artifacts'] if a['task_id']==ids['identity']]
                message(engine,rid,ids['identity'],tid,'artifact_handoff','Validated identities and reference sequence delivered to the '+role+' specialist.',refs)
                engine.task_status(rid,tid,'queued',input_artifact_ids=refs)
            engine.task_status(rid,tid,'running',started_at=timestamp())
            for name,args in jobs[role]:
                def reserve(d):
                    if d['cancel_requested']:raise asyncio.CancelledError()
                    if d['budget']['tool_calls']>=d['budget']['max_tool_calls']:raise RuntimeError('Tool budget exhausted.')
                    d['budget']['tool_calls']+=1;return d
                engine.edit(rid,reserve);engine.event(rid,'tool.started',tid,name)
                async with semaphore:result=await guard(asyncio.to_thread(engine.registry.execute,name,args,{**engine.store.get(rid),'_allowed_tools':[n for n,_ in jobs[role]]}))
                aid=engine.artifact(rid,tid,name,result.model_dump(mode='json'),parameters=args)
                engine.event(rid,'tool.completed',tid,result.summary,outputs=[aid])
                # Paths describe concurrently executed checks; they do not park one another.
                def checkpoint(d):
                    for p in d.get('paths',[]):
                        if name in p['expected_tools']:
                            p.setdefault('assigned_task_ids',[])
                            if tid not in p['assigned_task_ids']:p['assigned_task_ids'].append(tid)
                            p['evidence_refs']=list(dict.fromkeys(p['evidence_refs']+[aid]))
                            p['status']='exploring';p['history'].append({'at':timestamp(),'status':'exploring','reason':'Assigned specialist executed '+name+'.','evidence_refs':[aid]})
                    return d
                engine.edit(rid,checkpoint)
                if role=='identity' and result.outcome!='ok':raise ValueError('Identity validation did not complete successfully.')
            if role=='structure':
                for operation,needed in [('find_spatial_neighbors',1),('calculate_residue_distances',2)]:
                    if operation in declared and len(mapped)<needed:
                        reason='Skipped because the selection lacks the accepted reference coordinates required for '+operation+'.'
                        aid=engine.artifact(rid,tid,operation,{'tool':operation,'outcome':'missing_data','summary':reason,'data':{'status':'skipped'},'limitations':[reason]})
                        engine.event(rid,'operation.skipped',tid,reason,outputs=[aid])
            if role=='identity':engine.task_status(rid,tid,'completed',finished_at=timestamp());engine.event(rid,'task.completed',tid,'Pinned identities and reference sequence checked.')
            else:await worker(tid)
            saved=engine.store.get(rid);refs=[a['id'] for a in saved['artifacts'] if a['task_id']==tid]
            message(engine,rid,tid,'coordinator','result','The '+role+' specialist delivered its saved outputs.',refs)
        except asyncio.CancelledError:raise
        except Exception as exc:
            engine.task_status(rid,tid,'failed',finished_at=timestamp(),error=type(exc).__name__)
            engine.event(rid,'task.failed',tid,'Independent '+role+' work failed; completed peer outputs remain available.')
    for role in jobs:children[ids[role]]=asyncio.create_task(branch(role))
    await guard(asyncio.gather(*(children[tid] for tid in ids.values())))
    # Cross-team verification consumes actual artifacts after both reviews finish.
    fresh=engine.store.get(rid);vid='team-verifier-'+uuid4().hex[:8]
    engine.edit(rid,lambda d:{**d,'budget':{**d['budget'],'spawned_tasks':d['budget']['spawned_tasks']+1},'tasks':d['tasks']+[{'id':vid,'role':'verifier','question':'Check saved artifact references and preserve unresolved reviews.','allowed_tools':[],'input_artifact_ids':[],'parent_task_id':'coordinator','depth':1,'status':'running','started_at':timestamp(),'engine':'deterministic artifact verifier','depends_on':[ids['assay'],ids['structure']]}]})
    for role in ['assay','structure']:
        refs=[a['id'] for a in fresh['artifacts'] if a['task_id']==ids[role]]
        message(engine,rid,ids[role],vid,'artifact_handoff','Peer '+role+' outputs delivered for mechanical verification.',refs)
    refs=[a['id'] for a in fresh['artifacts'] if a['task_id'] in [ids['assay'],ids['structure']]]
    engine.task_status(rid,vid,'running',input_artifact_ids=refs)
    check=engine.registry.check_references([Finding.model_validate(f) for f in fresh['findings']],fresh,engine.data.workspace())
    aid=engine.artifact(rid,vid,'verification',{'references':check,'scientific_truth_established':False})
    engine.task_status(rid,vid,'completed' if check['passed'] else 'needs_review',finished_at=timestamp())
    message(engine,rid,vid,'coordinator','result','Cross-team reference checks returned to the research lead.',[aid])
    def finish_paths(d):
        for p in d.get('paths',[]):
            used={a['kind'] for a in d['artifacts'] if a['id'] in p['evidence_refs'] and a['data'].get('outcome')=='ok'}
            if set(p['expected_tools'])<=used:
                p['status']='completed';p['outcome']='The declared computations produced successful artifacts. Interpretation still requires scientific review.'
                p['history'].append({'at':timestamp(),'status':'completed','reason':p['outcome'],'evidence_refs':p['evidence_refs']})
        return d
    engine.edit(rid,finish_paths)
