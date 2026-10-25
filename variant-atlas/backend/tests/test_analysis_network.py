import asyncio,json
from fastapi.testclient import TestClient
import pytest
from app.config import Settings
from app.science import ScientificData
from app.main import create_app
from app.repositories.research import ResearchStore
from app.research_schemas import ResearchRequest,AgentAction,Finding
from app.orchestration.engine import ResearchEngine
from app.analysis_results import AnalysisResult,validate_bindings
from app.orchestration.agent_network import message


def local(tmp_path):
    s=Settings(local_data_dir=tmp_path,worker_mode='external',openrouter_api_key='fixture',openrouter_model='fixture',max_model_requests=30)
    d=ScientificData();store=ResearchStore(s);store.seed(d.workspace());return s,d,store


def test_real_baseline_single_criterion_followup_and_reconnect(tmp_path):
    s,data,store=local(tmp_path)
    with TestClient(create_app(s)) as c:
        sources=c.get('/api/portfolio/sources').json()
        project=c.post('/api/portfolio/projects',json={'title':'Quantitative reference check','objective':'Compare measured substitutions and reference geometry.','method':'pten','source_ids':[x['id'] for x in sources if x['method']=='pten']}).json()
        ids=['PTEN:p.C124S','PTEN:p.R172H','PTEN:p.Y16T'];criteria=data.workspace()['defaults'];criteria={k:criteria[k] for k in ['scenario','activity_cutoff','abundance_cutoff','mapping']}
        body={'confirmed':True,'question':project['objective'],'selected_ids':ids,'criteria':criteria}
        response=c.post('/api/analysis/projects/'+project['id']+'/run',json=body);assert response.status_code==200,response.text
        first=response.json();assert first['status']=='completed_with_limitations' and first['budget']['model_requests']==0
        assert len(first['analysis_results'])>=10 and len(first['agent_messages'])>=8
        assert all(r['inputs']['dataset_version']==first['dataset_version'] for r in first['analysis_results'])
        for r in first['analysis_results']:validate_bindings(first,AnalysisResult.model_validate(r))
        before=data.preview(__import__('app.research_schemas',fromlist=['ResearchCriteria']).ResearchCriteria.model_validate(criteria),ids)['matching_ids']
        follow={**body,'criteria':{**criteria,'activity_cutoff':10},'baseline_run_id':first['run_id']}
        response=c.post('/api/analysis/projects/'+project['id']+'/run',json=follow);assert response.status_code==200,response.text
        second=response.json();delta=second['baseline_comparison'];assert delta['changed_factors']==['criteria.activity_cutoff']
        from app.research_schemas import ResearchCriteria
        after=data.preview(ResearchCriteria.model_validate(follow['criteria']),ids)['matching_ids']
        assert delta['entered']==sorted(set(after)-set(before));assert delta['left']==sorted(set(before)-set(after));assert delta['unchanged']==sorted(set(before)&set(after))
        assert c.get('/api/research/investigations/'+first['run_id']).json()['request']['criteria']==first['request']['criteria']
        assert c.get('/api/portfolio/investigations/'+second['run_id']).json()['project']['id']==project['id']
        unchanged=c.post('/api/analysis/projects/'+project['id']+'/run',json={**body,'baseline_run_id':first['run_id']}).json();assert not unchanged['baseline_comparison']['entered'] and not unchanged['baseline_comparison']['left']
        bad={**follow,'criteria':{**follow['criteria'],'abundance_cutoff':.1}}
        assert c.post('/api/analysis/projects/'+project['id']+'/run',json=bad).status_code==422
        missing=next(v['id'] for v in data.workspace()['variants'] if v['activity'] is None or v['abundance'] is None)
        partial=c.post('/api/analysis/projects/'+project['id']+'/run',json={**body,'selected_ids':[missing]}).json();assert partial['input_variants'][0]['activity'] is None or partial['input_variants'][0]['abundance'] is None
        assert partial['status']=='completed_with_limitations'


def test_autonomous_network_handoffs_concurrency_and_independent_providers(tmp_path):
    s,data,store=local(tmp_path);instances=[];started=set();ready=asyncio.Event()
    class Provider:
        def __init__(self,*a):instances.append(self)
        async def close(self):pass
        async def generate_action(self,prompt,on_remote=None):
            ctx=json.loads(prompt.split(' Context: ')[-1]);t=ctx['task'];tid=t['id']
            if tid=='coordinator' and not ctx['paths']:
                return AgentAction(action='plan_paths',summary='Plan separate validation, assay and geometry work.',arguments={'paths':[{'id':name,'title':'Inspect '+name+' evidence','question':'Which '+name+' checks support the comparison?','rationale':'Establish the exact computational preconditions.','expected_tools':tools} for name,tools in [('identity',['validate_variant_identity']),('assay',['assess_comparability','filter_measurements']),('structure',['map_variant_residues'])]]}),{'provider':'fixture','model':'offline-network'}
            if tid!='coordinator':
                started.add(t['role'])
                if {'assay','structure'}<=started:ready.set()
                await asyncio.wait_for(ready.wait(),timeout=3)
                assert t['input_artifact_ids'] and all(a['task_id']==tid or a['id'] in t['input_artifact_ids'] for a in ctx['artifacts'])
            refs=[a['id'] for a in ctx['artifacts'] if a['data'].get('outcome')=='ok']
            return AgentAction(action='finalize',summary='Scoped computation outputs are saved with uncertainty.',findings=[Finding(id='scoped-evidence',claim_type='computed_result',text='The declared checks have inspectable outputs; scientific interpretation remains limited.',evidence_refs=refs[:2],limitations=['Mechanical checks do not establish causation.'])]),{'provider':'fixture','model':'offline-network'}
    e=ResearchEngine(store,data,s,Provider)
    req=ResearchRequest(question='Compare measured PTEN profiles and reliable structure evidence.',selected_ids=['PTEN:p.C124S','PTEN:p.R172H'],criteria={k:data.workspace()['defaults'][k] for k in ['scenario','activity_cutoff','abundance_cutoff','mapping']},provider='openrouter',explore_paths=True,autonomous_team=True)
    # Defaults include UI derivation metadata; only typed scientific criteria enter the request.
    r=e.start(req);asyncio.run(e.execute(r['run_id']));saved=store.get(r['run_id'])
    assert saved['status']=='completed_with_limitations',saved.get('error')
    assert len(instances)==3 and saved['budget']['model_requests']==4
    assert saved['budget']['spawned_tasks']==4 and len(saved['agent_messages'])>=10
    assert all(t['status']=='completed' for t in saved['tasks'])
    assert len(saved['findings'])==3 and saved['artifacts'][-1]['kind']=='research_brief'
    assert all(p['status']=='completed' for p in saved['paths'])
    assert any(m['kind']=='artifact_handoff' and m['from_task_id'].startswith('team-identity') and m['to_task_id'].startswith('team-structure') for m in saved['agent_messages'])
    with pytest.raises(ValueError,match='scope'):message(e,r['run_id'],saved['tasks'][1]['id'],'coordinator','artifact_handoff','Invalid handoff',['unknown-artifact'])
    result=AnalysisResult.model_validate(saved['analysis_results'][0]);result.output_artifact_refs=['missing']
    with pytest.raises(ValueError,match='Unknown'):validate_bindings(saved,result)


def test_supplied_models_real_reference_alignment_scope_and_immutability(tmp_path):
    import base64,io
    from app.structure_comparison import SuppliedModels,ModelImport,ModelComparison
    s,data,store=local(tmp_path)
    with TestClient(create_app(s)) as c:
        p=c.post('/api/portfolio/projects',json={'title':'Supplied model comparison','objective':'Compare supplied protein coordinate models with checked correspondences.','method':'pten'}).json()
        source=data.assets.read(data.workspace()['structure_asset']);service=SuppliedModels(c.app,s)
        first=service.import_model(p['id'],ModelImport(filename='reference.cif',content_base64=base64.b64encode(source).decode(),origin='experimental',generation_method='Pinned public PDB reference'))
        second=service.import_model(p['id'],ModelImport(filename='identical-copy.cif',content_base64=base64.b64encode(source).decode(),origin='experimental',generation_method='Same pinned public reference'))
        result=service.compare(p['id'],ModelComparison(reference_id=first['id'],mobile_id=second['id'],reference_chain='A',mobile_chain='A'))
        assert result['rmsd_angstrom']<1e-7 and result['coverage_fraction']==1 and all(r['displacement_angstrom']<1e-7 for r in result['per_residue'])
        # Rigid rotation/translation cannot masquerade as a conformational displacement.
        import numpy as np
        from Bio.PDB import MMCIFIO
        from app.structure_comparison import parsed
        moved,_=parsed(source,'source.cif')
        rotation=np.array([[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]])
        for atom in moved.get_atoms():atom.coord=np.asarray(atom.coord)@rotation+np.array([20.,-30.,12.])
        writer=MMCIFIO();writer.set_structure(moved);text=io.StringIO();writer.save(text)
        rotated=service.import_model(p['id'],ModelImport(filename='rigid-transform.cif',content_base64=base64.b64encode(text.getvalue().encode()).decode()))
        rigid=service.compare(p['id'],ModelComparison(reference_id=first['id'],mobile_id=rotated['id'],reference_chain='A',mobile_chain='A'))
        assert rigid['rmsd_angstrom']<1e-4 and max(r['displacement_angstrom'] for r in rigid['per_residue'])<1e-4
        # Equal residue numbers alone cannot establish compatible protein identity.
        for residue in next(moved.get_models())['A']:
            if 'CA' in residue:residue.resname='ALA'
        writer=MMCIFIO();writer.set_structure(moved);text=io.StringIO();writer.save(text)
        incompatible=service.import_model(p['id'],ModelImport(filename='incompatible-sequence.cif',content_base64=base64.b64encode(text.getvalue().encode()).decode()))
        with pytest.raises(ValueError,match='compatible correspondence'):service.compare(p['id'],ModelComparison(reference_id=first['id'],mobile_id=incompatible['id'],reference_chain='A',mobile_chain='A',allow_identity_difference=True))
        assert service.assets.read(first['asset'])==source
        from app.structure_comparison import parsed
        assert len(list(parsed(service.assets.read(result['aligned_asset']),'aligned.cif')[1].get_atoms()))>0
        with pytest.raises(ValueError,match='chain'):service.compare(p['id'],ModelComparison(reference_id=first['id'],mobile_id=second['id'],reference_chain='missing',mobile_chain='A'))
        assert c.get('/api/analysis/projects/'+p['id']+'/models').json()['mutant_model_generation']['available'] is False
        assert c.post('/api/analysis/projects/'+p['id']+'/models',json={'filename':'bad.pdb','content_base64':base64.b64encode(b'no atoms').decode()}).status_code==422
        another=c.post('/api/portfolio/projects',json={'title':'Other model scope','objective':'A separate project for artifact access checking.','method':'pten'}).json()
        with pytest.raises(ValueError,match='project'):service.get(another['id'],first['id'])


def test_identity_mismatch_blocks_mapping_and_descriptive_selection(tmp_path):
    from app.tools.registry import Registry
    s,data,store=local(tmp_path);w=data.workspace();v=next(v for v in w['variants'] if v['mapping']['status']=='mapped');broken={**v,'ref':'Z'}
    class Altered:
        def workspace(self):return w
        def variant(self,vid):return broken
    request={'selected_ids':[v['id']],'criteria':{k:w['defaults'][k] for k in ['scenario','activity_cutoff','abundance_cutoff','mapping']}}
    for name in ['validate_variant_identity','map_variant_residues','filter_measurements']:
        result=Registry(Altered()).execute(name,{}, {'dataset_version':w['dataset_version'],'request':request})
        assert result.outcome=='incompatible' and result.data['rejected_ids']==[v['id']]
