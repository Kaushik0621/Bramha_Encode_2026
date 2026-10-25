"""Run-scoped brief, numeric provenance and immutable result interpretation."""
import copy
import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
from app.science import ScientificData
from app.repositories.research import ResearchStore
from app.research_schemas import AgentAction
from app.result_analyst import measurement_rows


def fixture(tmp_path,status='completed_with_limitations'):
    settings=Settings(local_data_dir=tmp_path,worker_mode='external',openrouter_api_key='test-key',openrouter_model='test-model')
    science=ScientificData();w=science.workspace();store=ResearchStore(settings);store.seed(w)
    rows=copy.deepcopy([r for r in w['variants'] if r['activity'] is not None and r['abundance'] is not None][:3]);rows[0]['activity']=-2.5;rows[1]['abundance']=None
    rid='research-'+uuid4().hex
    run={'run_id':rid,'workspace_id':'pten-real','status':status,'created_at':'2026-10-25T12:00:00Z','revision':0,'dataset_version':w['dataset_version'],'request':{'question':'Compare the measured PTEN profiles in this selected set.','selected_ids':[r['id'] for r in rows],'criteria':{**{k:w['defaults'][k] for k in ['scenario','activity_cutoff','abundance_cutoff']},'mapping':'all'}},'input_variants':rows,'source_manifest':w['sources'],'artifacts':[{'id':'artifact-test','kind':'assess_comparability','data':{'outcome':'ok','summary':'These assays retain different endpoints and native score scales.'}}],'findings':[{'id':'finding-test','text':'The selected measurements require assay-specific interpretation.','claim_type':'reported_observation','reviewer_status':'pending','evidence_refs':[],'limitations':['No clinical conclusion is established.']}],'events':[],'tasks':[],'budget':{'model_requests':0,'tool_calls':1}}
    store.create(run)
    return settings,run,store.root/(rid+'.json')


def test_brief_uses_frozen_measurements_and_never_invokes_model(tmp_path,monkeypatch):
    settings,run,path=fixture(tmp_path);original=path.read_bytes()
    async def forbidden(*args,**kwargs):raise AssertionError('No model calls on brief load')
    monkeypatch.setattr('app.result_analyst.ActionProvider.generate_action',forbidden)
    with TestClient(create_app(settings)) as c:
        r=c.get('/api/hub/investigations/'+run['run_id']+'/brief');assert r.status_code==200,r.text
        b=r.json();assert len(b['rows'])==3 and b['rows'][0]['activity']==-2.5
        assert b['rows'][1]['abundance'] is None and b['rows'][1]['matches'] is None
        assert b['metrics']['paired']==2 and b['metrics']['selected']==3
        assert b['metrics']['findings']==1 and b['metrics']['sources']>0
        assert b['sources'][0]['url'].startswith('/library/')
        assert any('Historical text coverage is unavailable' not in s['coverage'] for s in b['sources'])
        assert not b['messages'] and path.read_bytes()==original


def test_analyst_is_run_scoped_saves_separately_and_rejects_invented_numbers(tmp_path,monkeypatch):
    settings,run,path=fixture(tmp_path);original=path.read_bytes();invalid=False
    async def answer(self,prompt,**kwargs):
        p=json.loads(prompt);assert p['run']['run_id']==run['run_id']
        evidence=next(e for e in p['evidence'] if e['kind']=='measurement' and '-2.5' in e['quote'])
        return AgentAction(action='invoke_tool',summary='Source-linked interpretation',tool='result_analysis',arguments={'claims':[{'text':'The saved activity is '+('99' if invalid else '-2.5')+'.','quote_id':evidence['id']}],'limitations':['Native assay scale; no clinical classification.'],'next_questions':[]}),{'provider':'fixture','model':'scripted'}
    monkeypatch.setattr('app.result_analyst.ActionProvider.generate_action',answer)
    with TestClient(create_app(settings)) as c:
        url='/api/hub/investigations/'+run['run_id']
        r=c.post(url+'/analyst',json={'question':'Explain the measured evidence.'});assert r.status_code==200,r.text
        assert '-2.5' in r.json()['claims'][0]['quote']
        assert len(c.get(url+'/brief').json()['messages'])==1
        invalid=True
        r=c.post(url+'/analyst',json={'question':'Explain the measured evidence.'});assert r.status_code==422,r.text
        assert 'number could not be verified' in r.json()['detail']
        assert len(c.get(url+'/brief').json()['messages'])==1 and path.read_bytes()==original


def test_failed_run_explains_no_accepted_conclusion_and_empty_history_has_no_fabricated_plot(tmp_path):
    settings,run,path=fixture(tmp_path,status='failed')
    run['input_variants']=[];run['findings']=[];path.write_text(json.dumps(run))
    with TestClient(create_app(settings)) as c:
        b=c.get('/api/hub/investigations/'+run['run_id']+'/brief').json()
        assert b['rows']==[] and b['metrics']['paired']==0
        assert b['limitations'][0].startswith('Run status: failed')
        assert 'No final observations' in b['overview']
        assert c.get('/api/hub/investigations/nonexistent/brief').status_code==404


def test_artifact_rows_are_scoped_and_missing_values_stay_missing():
    run={'request':{'selected_ids':['PTEN:p.C124S'],'criteria':{}},'artifacts':[{'data':{'data':{'rows':[{'id':'PTEN:p.C124S','activity':0,'abundance':None},{'id':'unselected','activity':999,'abundance':999}]}}}]}
    rows=measurement_rows(run)
    assert len(rows)==1 and rows[0]['activity']==0 and rows[0]['abundance'] is None
    assert rows[0]['matches'] is None and rows[0]['origin']=='Saved measurement artifact'
