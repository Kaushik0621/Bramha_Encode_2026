import asyncio,json
from dataclasses import replace
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
from app.repositories.research import ResearchStore
from app.science import ScientificData
from app.molecular_guidance import MolecularGuidance,FocusRequest
from app.research_schemas import AgentAction

def setup(tmp_path,**kwargs):
    s=Settings(local_data_dir=tmp_path,worker_mode='external',**kwargs);ResearchStore(s).seed(ScientificData().workspace());return s

def reference(c):return next(s for s in c.get('/api/portfolio/sources').json() if s['type']=='sequence')
def request(s,**kw):return {'source_id':s['id'],'source_version':s['version'],'position':124,'variant_id':'PTEN:p.C124S','use_model':False,**kw}

def test_focus_checks_are_real_cached_and_preserve_missingness(tmp_path):
    with TestClient(create_app(setup(tmp_path))) as c:
        source=reference(c);body=request(source);response=c.post('/api/molecular-guidance',json=body);assert response.status_code==200,response.text
        row=c.get('/api/molecular-guidance/'+response.json()['id']).json();assert row['status']=='completed_with_limitations'
        assert [t['status'] for t in row['tasks']]==['completed']*3+['skipped']
        w=c.get('/api/workspaces/pten-real').json();expected=[v for v in w['variants'] if v['position']==124];assert row['measurements']['rows'][0]['activity']==expected[0]['activity']
        assert row['geometry']['mapping']['status']=='mapped' and row['geometry']['neighbors']
        assert all(n['distance_angstrom']<=8 for n in row['geometry']['neighbors'])
        events=row['events'];last_start=max(i for i,e in enumerate(events) if e['task']!='lead' and e['status']=='running');assert last_start<min(i for i,e in enumerate(events) if e['task']!='lead' and e['status']=='completed')
        again=c.post('/api/molecular-guidance',json=body);assert again.json()['id']==row['id'] and again.json()['events']==row['events']
        assert c.post('/api/molecular-guidance',json=request(source,position=172,variant_id='PTEN:p.C124S')).status_code==422
        assert c.post('/api/molecular-guidance',json=request(source,source_version='missing')).status_code==404
        gap=c.post('/api/molecular-guidance',json=request(source,position=1,variant_id=None)).json();gap=c.get('/api/molecular-guidance/'+gap['id']).json();assert not any(a['kind']=='geometry_proposal' for a in gap['actions'])
        missing=c.post('/api/molecular-guidance',json=request(source,position=172,variant_id='PTEN:p.R172H')).json();missing=c.get('/api/molecular-guidance/'+missing['id']).json();assert next(v for v in missing['measurements']['rows'] if v['id']=='PTEN:p.R172H')['abundance'] is None

@pytest.mark.parametrize('bad',[False,True])
def test_model_guidance_is_public_bounded_and_checks_suggestions(tmp_path,monkeypatch,bad):
    settings=setup(tmp_path,openrouter_api_key='fixture')
    class Provider:
        def __init__(self,*a):self.on_attempt=None
        async def close(self):pass
        async def generate_action(self,prompt):
            p=json.loads(prompt);assert 'private' not in prompt and 'saved investigations' not in prompt
            assert p['tool_outputs']['measurements']['rows'] and 'runs' not in p['context']
            selected='not-a-supported-action' if bad else p['available_actions'][0]['id']
            return AgentAction(action='invoke_tool',tool='molecular_focus_guidance',summary='Fixture explanation',arguments={'explanation':'The reference coordinate is separate from the loaded assay observations.','suggestions':[{'action_id':selected,'explanation':'Inspect the independent original measurements.','question':'What do the original assay observations actually support?'}],'limitations':['Offline fixture; no biological experiment.']}),{'provider':'fixture','model':'scripted'}
    monkeypatch.setattr('app.molecular_guidance.ActionProvider',Provider)
    with TestClient(create_app(settings)) as c:
        s=reference(c);r=c.post('/api/molecular-guidance',json=request(s,use_model=True)).json();r=c.get('/api/molecular-guidance/'+r['id']).json()
        assert r['model_status']==('failed' if bad else 'completed')
        assert len(r['actions'])>1 and all(a['id']!='not-a-supported-action' for a in r['actions'])
        if not bad:assert r['provider']['provider']=='fixture'


def test_guidance_handoff_preserves_context_is_idempotent_and_runs_no_experiment(tmp_path):
    with TestClient(create_app(setup(tmp_path))) as c:
        s=reference(c);r=c.post('/api/molecular-guidance',json=request(s)).json();base='/api/molecular-guidance/'+r['id']+'/continue'
        assert c.post(base,json={'action_id':'geometry','target_amino_acid':'C'}).status_code==422
        a=c.post(base,json={'action_id':'geometry','target_amino_acid':'A'});assert a.status_code==200,a.text
        row=a.json();assert 'view=experiments' in row['path'] and 'target=A' in row['path'] and 'residue=PTEN%3Ap.C124S' in row['path']
        assert c.post(base,json={'action_id':'geometry','target_amino_acid':'A'}).json()['project_id']==row['project_id']
        project=c.get('/api/portfolio/projects/'+row['project_id']).json();assert project['sources'] and project['method']=='pten' and not project['run_ids']
        assert c.get('/api/hub/projects/'+row['project_id']+'/experiments').json()['geometries']==[]
        assert c.post(base,json={'action_id':'invented'}).status_code==422
