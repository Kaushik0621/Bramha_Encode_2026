"""Explicit, reproducible PTEN computations and version-checked follow-up comparisons."""
import asyncio
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter,HTTPException
from pydantic import Field
from .schemas import Model
from .research_schemas import ResearchCriteria
from .portfolio import Portfolio,now
from .orchestration.engine import ResearchEngine
from .orchestration.agent_network import message

class AnalysisStart(Model):
    confirmed:Literal[True]
    selected_ids:list[str]=Field(min_length=1,max_length=200)
    criteria:ResearchCriteria
    question:str=Field(min_length=10,max_length=1800)
    baseline_run_id:str|None=Field(default=None,pattern=r'^research-[a-f0-9]{32}$')
    allow_multiple_factors:bool=False
    radius:float=Field(default=10,gt=0,le=100,allow_inf_nan=False)

class AnalysisExecution:
    def __init__(self,app,settings):
        self.app=app;self.settings=settings;self.data=app.state.science;self.store=app.state.research_store;self.portfolio=Portfolio(app,settings)
        if self.data is None or self.store is None:raise HTTPException(503,'The pinned PTEN dataset is unavailable; restore it before analysis.')
    def plan(self,pid):
        project=self.portfolio.project(pid)
        if project['method']!='pten':raise ValueError('This quantitative mission requires the supported PTEN measurement dataset.')
        w=self.data.workspace()
        return {'question':project['objective'],'dataset_version':w['dataset_version'],'required':['Validate identities','Inspect both assay endpoints','Check assay comparability','Measure missingness','Apply declared criteria','Map reference residues'],'conditional':['Reference-space neighbors when accepted coordinates are available'],'outputs':['Sequence identities','Coverage matrix','Assay comparison','Threshold scatterplot','Mapping and spatial result','Saved input/output differences'],'execution':'Deterministic data validation and descriptive analysis; no model inference, simulation or training.','assays':w['assays'],'defaults':w['defaults'],'source_manifest':w['sources']}
    async def execute(self,pid,body):
        self.plan(pid);w=self.data.workspace();ids=body.selected_ids
        if len(set(ids))!=len(ids):raise ValueError('Duplicate substitution identities are not permitted.')
        variants=[self.data.variant(v) for v in ids]
        for v in variants:
            if w['protein']['sequence'][v['position']-1]!=v['ref']:raise ValueError('Reference identity mismatch; affected analysis is blocked.')
        baseline=None;changed=[]
        if body.baseline_run_id:
            baseline=self.store.get(body.baseline_run_id)
            if not baseline or self.portfolio.project_for(baseline)!=pid:raise ValueError('Baseline must be a saved investigation in this project.')
            if baseline['dataset_version']!=w['dataset_version']:raise ValueError('Baseline dataset differs; a numerical delta is unavailable.')
            if baseline.get('source_manifest')!=w['sources']:raise ValueError('Baseline source versions differ; compare them side by side instead.')
            if baseline['request'].get('neighbor_radius',10)!=body.radius:changed.append('neighbor_radius')
            if set(baseline['request']['selected_ids'])!=set(ids):changed.append('selection')
            for k,v in body.criteria.model_dump().items():
                if baseline['request']['criteria'].get(k)!=v:changed.append('criteria.'+k)
            if len(changed)>1 and not body.allow_multiple_factors:raise ValueError('The first follow-up changes one declared factor. Enable multiple-factor comparison explicitly for more changes.')
        rid='research-'+uuid4().hex;at=now();request={'project_id':pid,'question':body.question,'selected_ids':ids,'criteria':body.criteria.model_dump(),'capacity':len(ids),'max_seconds':120,'provider':'none','explore_paths':False,'neighbor_radius':body.radius}
        tasks=[{'id':'coordinator','role':'research lead','status':'running','engine':'deterministic analysis controller','parent_task_id':None,'input_artifact_ids':[],'allowed_tools':[],'question':body.question,'depth':0,'started_at':at}]
        run={'run_id':rid,'revision':0,'workspace_id':w['id'],'dataset_version':w['dataset_version'],'mapping_version':w['dataset_version'],'data_mode':'real','execution_mode':'live','playback_mode':'live','storage_mode':self.settings.data_backend,'provider':'none','model':'No LLM used','run_type':'Data validation and descriptive analysis','status':'running','created_at':at,'request':request,'tasks':tasks,'events':[],'artifacts':[],'analysis_results':[],'agent_messages':[],'findings':[],'reviews':[],'hypotheses':[],'paths':[],'cancel_requested':False,'source_manifest':w['sources'],'source_versions':w['sources'],'assay_dictionary':w['assays'],'input_variants':variants,'budget':{'model_requests':0,'tool_calls':0,'spawned_tasks':3,'max_tool_calls':40,'max_spawned_tasks':12,'max_model_requests':0,'usage':[],'cost_usd':0,'cost_status':'No model inference requested'}}
        self.store.create(run);self.portfolio.attach(pid,rid);engine=ResearchEngine(self.store,self.data,self.settings)
        roles={'identity':[('validate_variant_identity',{}),('resolve_reference_sequence',{})],'assay':[('inspect_assay',{'assay_id':'activity'}),('inspect_assay',{'assay_id':'abundance'}),('assess_comparability',{}),('summarize_measurement_coverage',{}),('filter_measurements',{})],'structure':[('load_structure_metadata',{}),('align_structure_reference',{}),('map_variant_residues',{})]}
        mapped=sorted([v for v in variants if v['mapping']['status']=='mapped'],key=lambda v:v['id'])
        if mapped:roles['structure'].append(('find_spatial_neighbors',{'variant_id':mapped[0]['id'],'radius':body.radius}))
        if len(mapped)>1:roles['structure'].append(('calculate_residue_distances',{'variant_id':mapped[0]['id'],'other_variant_id':mapped[1]['id']}))
        for role,jobs in roles.items():
            engine.edit(rid,lambda d,role=role,jobs=jobs:{**d,'tasks':d['tasks']+[{'id':'analysis-'+role,'role':role,'status':'queued','engine':'Python scientific tools; no model','parent_task_id':'coordinator','input_artifact_ids':[],'allowed_tools':[n for n,_ in jobs],'question':'Compute the declared '+role+' checks.','depth':1,'depends_on':[] if role=='identity' else ['analysis-identity']}]})
            message(engine,rid,'coordinator','analysis-'+role,'assignment','Assigned explicit '+role+' calculations over the frozen input selection.')
        async def compute(role):
            tid='analysis-'+role;engine.task_status(rid,tid,'running',started_at=now())
            for name,args in roles[role]:
                engine.event(rid,'tool.started',tid,name)
                result=await asyncio.to_thread(engine.registry.execute,name,args,{**self.store.get(rid),'_allowed_tools':[n for n,_ in roles[role]]})
                aid=engine.artifact(rid,tid,name,result.model_dump(mode='json'),parameters=args)
                engine.edit(rid,lambda d:{**d,'budget':{**d['budget'],'tool_calls':d['budget']['tool_calls']+1}})
                engine.event(rid,'tool.completed',tid,result.summary,outputs=[aid])
                if role=='identity' and result.outcome!='ok':raise ValueError('Identity precondition failed.')
            engine.task_status(rid,tid,'completed',finished_at=now());engine.event(rid,'task.completed',tid,'Declared '+role+' calculations saved.')
            message(engine,rid,tid,'coordinator','result','Saved '+role+' results returned to the controller.',[a['id'] for a in self.store.get(rid)['artifacts'] if a['task_id']==tid])
        try:
            await compute('identity');identity_refs=[a['id'] for a in self.store.get(rid)['artifacts'] if a['task_id']=='analysis-identity']
            for role in ['assay','structure']:
                message(engine,rid,'analysis-identity','analysis-'+role,'artifact_handoff','Pinned identities delivered as a prerequisite for '+role+' work.',identity_refs)
                engine.task_status(rid,'analysis-'+role,'queued',input_artifact_ids=identity_refs)
            await asyncio.gather(compute('assay'),compute('structure'))
            for operation,needed in [('find_spatial_neighbors',1),('calculate_residue_distances',2)]:
                if len(mapped)<needed:
                    reason='Not executed: this selection lacks '+str(needed)+' accepted reference-coordinate position(s). Missing coordinates are not interpolated.'
                    aid=engine.artifact(rid,'analysis-structure',operation,{'tool':operation,'outcome':'missing_data','summary':reason,'data':{'status':'skipped'},'limitations':[reason]})
                    engine.event(rid,'operation.skipped','analysis-structure',reason,outputs=[aid])
            fresh=self.store.get(rid);matching=next(a['data']['data']['matching_ids'] for a in fresh['artifacts'] if a['kind']=='filter_measurements');delta=None
            if baseline:
                before=next((a['data'].get('data',{}).get('matching_ids') for a in baseline['artifacts'] if a['kind']=='filter_measurements'),None)
                if before is None:raise ValueError('Baseline has no computed eligibility set to compare.')
                delta={'baseline_run_id':baseline['run_id'],'changed_factors':changed,'entered':sorted(set(matching)-set(before)),'left':sorted(set(before)-set(matching)),'unchanged':sorted(set(before)&set(matching)),'baseline_matching_ids':before,'current_matching_ids':matching,'interpretation':'Analytical selection difference; this does not demonstrate biological causation.'}
                delta['input_changes']=[]
                for field in changed:
                    if field=='selection':before_value=sorted(baseline['request']['selected_ids']);after_value=sorted(ids)
                    elif field=='neighbor_radius':before_value=baseline['request'].get('neighbor_radius',10);after_value=body.radius
                    else:before_value=baseline['request']['criteria'][field.split('.',1)[1]];after_value=body.criteria.model_dump()[field.split('.',1)[1]]
                    delta['input_changes'].append({'field':field,'before':before_value,'after':after_value})
                for result in fresh['analysis_results']:
                    prior=next((r for r in baseline.get('analysis_results',[]) if r['operation']==result['operation'] and r['inputs']['parameters']==result['inputs']['parameters']),None)
                    if prior:result['baseline_result_id']=prior['id'];result['change']={'type':'criterion' if any(c.startswith('criteria.') for c in changed) else 'selection' if 'selection' in changed else 'analysis_result' if 'neighbor_radius' in changed else 'none','reason':'Comparison against the declared baseline.','before_refs':prior['output_artifact_refs'],'after_refs':result['output_artifact_refs']}
            verification=engine.artifact(rid,'coordinator','verification',{'source_version_matches':True,'input_identity_matches':True,'criteria_recomputed':True,'scientific_truth_established':False})
            for result in fresh['analysis_results']:result['verification_refs']=[verification]
            engine.edit(rid,lambda d:{**d,'analysis_results':fresh['analysis_results'],'baseline_comparison':delta,'findings':[{'id':'finding-'+uuid4().hex,'claim_type':'computed_result','text':'Declared assay criteria and accepted reference mappings were evaluated. Exact candidate identities, missing values and geometric checks are retained in the operation results.','variant_ids':ids,'evidence_refs':[a['id'] for a in d['artifacts'] if a['kind']=='filter_measurements'],'limitations':['Descriptive computation does not establish a disease classification, mutation mechanism or new fold.'],'reviewer_status':'pending'}]})
            engine.task_status(rid,'coordinator','completed',finished_at=now());engine.event(rid,'run.completed_with_limitations','coordinator','Declared quantitative mission completed; original data and all calculated outputs are saved.',outputs=[verification],status='completed_with_limitations')
        except Exception as exc:
            engine.edit(rid,lambda d:{**d,'error':type(exc).__name__+': '+str(exc)[:200]});engine.event(rid,'run.failed','coordinator','A declared computation failed. Partial results remain inspectable.',status='failed')
            raise
        return self.store.get(rid)

def router(app,settings):
    r=APIRouter(prefix='/api/analysis')
    @r.get('/projects/{pid}/plan')
    def plan(pid:str):
        try:return AnalysisExecution(app,settings).plan(pid)
        except (KeyError,ValueError) as exc:raise HTTPException(422,str(exc)) from exc
    @r.post('/projects/{pid}/run')
    async def run(pid:str,body:AnalysisStart):
        try:return await AnalysisExecution(app,settings).execute(pid,body)
        except (KeyError,ValueError) as exc:raise HTTPException(422,str(exc)) from exc
    return r
