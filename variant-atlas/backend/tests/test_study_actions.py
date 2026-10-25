"""Source-bounded proposals, genuine independent branches, and private-data isolation."""
import asyncio
import json
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.research_schemas import AgentAction
from app.study_actions import ProposalRequest,propose
from test_observatory import setup


def provider(monkeypatch, invalid=None):
    class Provider:
        def __init__(self,*args): self.on_attempt=None
        async def close(self): pass
        async def generate_action(self,prompt):
            p=json.loads(prompt)
            assert 'project' not in p
            assert p['task'].startswith('You are the follow-up research adviser')
            citation='invented' if invalid=='citation' else p['passages'][0]['id']
            rationale='The source reports 987654 observations.' if invalid=='number' else 'The source describes PTEN evidence that warrants a source-level comparison.'
            return AgentAction(action='invoke_tool',tool='study_proposals',summary='Scripted proposal contract',arguments={'proposals':[{'title':'Compare PTEN evidence coverage','question':'Which PTEN claims are supported by the original methods and results?','rationale':rationale,'passage_ids':[citation],'examination':'methods audit','required_evidence':['Original methods passages and assay definitions'],'expected_outputs':['Source-linked comparison with missing evidence labelled'],'limitations':['A computational review does not reproduce the experiment.']}]}),{'provider':'fixture','model':'scripted'}
    monkeypatch.setattr('app.study_actions.ActionProvider',Provider)


def test_proposals_are_checked_and_keep_exact_current_evidence(tmp_path,monkeypatch):
    settings,store,_,study,passages=setup(tmp_path);provider(monkeypatch)
    result=asyncio.run(propose(store,settings,study['id'],ProposalRequest(passage_ids=[passages[1]['id']],chapter='limitations',language='中文')))
    assert result['source_version']==study['version']
    assert result['selected_passage_ids']==[passages[1]['id']]
    assert result['proposals'][0]['evidence'][0]['quote']==passages[1]['text']
    assert store.get('searches',result['id'])==result
    assert store.count('expeditions')==0
    with pytest.raises(ValueError,match='current study version'):
        asyncio.run(propose(store,settings,study['id'],ProposalRequest(passage_ids=['foreign-passage'])))
    assert store.count('searches')==1


@pytest.mark.parametrize('invalid',['citation','number'])
def test_proposals_reject_untraceable_claims(tmp_path,monkeypatch,invalid):
    settings,store,_,study,_=setup(tmp_path);provider(monkeypatch,invalid)
    with pytest.raises(ValueError,match='verification'):
        asyncio.run(propose(store,settings,study['id'],ProposalRequest()))
    assert store.count('searches')==0


def test_branches_are_independent_idempotent_project_linked_and_versioned(tmp_path,monkeypatch):
    settings,store,_,study,_=setup(tmp_path);provider(monkeypatch)
    report=asyncio.run(propose(store,settings,study['id'],ProposalRequest()))
    # This test runs the real tools-only worker engine, with remote geometry bounded to no matches.
    async def no_structures(*a,**k):return []
    monkeypatch.setattr('app.world_research.WorldResearch.structures',no_structures)
    body={'report_id':report['id'],'proposal_id':report['proposals'][0]['id'],'mode':'tools-only','max_seconds':120,'request_id':'branch-first-123'}
    with TestClient(create_app(settings)) as client:
        response=client.post('/api/observatory/studies/'+study['id']+'/branches',json=body)
        assert response.status_code==200,response.text
        first=response.json();project=client.get('/api/portfolio/projects/'+first['project_id']).json()
        assert first['provenance']['source_id'] in project['sources']
        assert not project['sources'][first['provenance']['source_id']]['included']
        again=client.post('/api/observatory/studies/'+study['id']+'/branches',json=body).json()
        assert again['expedition_id']==first['expedition_id'] and again['project_id']==first['project_id']
        second=client.post('/api/observatory/studies/'+study['id']+'/branches',json={**body,'request_id':'branch-second-123','project_id':first['project_id']}).json()
        assert second['project_id']==first['project_id'] and second['expedition_id']!=first['expedition_id']
        # Wait on durable worker completion rather than assuming the POST response means work is done.
        import time
        for _ in range(100):
            missions=[client.get('/api/observatory/expeditions/'+b['expedition_id']).json() for b in [first,second]]
            if all(m['status']=='completed_with_limitations' for m in missions):break
            time.sleep(.01)
        assert all(m['status']=='completed_with_limitations' for m in missions),missions
        assert all(len(m['tasks'])==6 and m['budget']['tool_calls']>0 and m['budget']['model_requests']==0 for m in missions)
        assert all(m['branch_provenance']['source_version']==study['version'] for m in missions)
        assert client.get('/api/observatory/studies/'+study['id']+'/proposals').json()['report']['id']==report['id']
        assert len(client.get('/api/observatory/studies/'+study['id']+'/proposals').json()['branches'])==2
        conflict=client.post('/api/observatory/studies/'+study['id']+'/branches',json={**body,'max_seconds':300})
        assert conflict.status_code==422
        store.put('studies',study['id'],{**study,'version':'new-version'})
        stale=client.post('/api/observatory/studies/'+study['id']+'/branches',json={**body,'request_id':'stale-branch-123'})
        assert stale.status_code==422 and 'source version changed' in stale.text
        assert client.get('/api/observatory/studies/'+study['id']+'/proposals').json()['report'] is None


def test_guide_prioritizes_selection_and_retains_coverage(tmp_path,monkeypatch):
    from app.corpus_guide import answer_public_question,CorpusQuestion
    settings,store,_,study,passages=setup(tmp_path)
    class Provider:
        def __init__(self,*a):pass
        async def close(self):pass
        async def generate_action(self,prompt):
            data=json.loads(prompt)
            assert data['passages'][0]['id']==passages[1]['id']
            assert 'methods' in data['available_sections'] and data['coverage'][study['id']]==study['coverage']
            return AgentAction(action='invoke_tool',tool='corpus_answer',summary='Scripted source check',arguments={'claims':[{'text':'The reported evidence requires review.','quote_id':passages[1]['id']}],'limitations':['No laboratory reproduction.']}),{'provider':'fixture','model':'scripted'}
    monkeypatch.setattr('app.corpus_guide.ActionProvider',Provider)
    row=asyncio.run(answer_public_question(store,settings,CorpusQuestion(study_id=study['id'],question='Explain the selected evidence',chapter='methods',passage_ids=[passages[1]['id']])))
    assert row['source_version']==study['version']
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/observatory/studies/'+study['id']+'/answers').json()['answers'][0]['id']==row['id']
        assert client.post('/api/observatory/ask',json={'study_id':study['id'],'question':'Explain the study','passage_ids':['wrong-study-passage']}).status_code==422

@pytest.mark.parametrize('focused',[True,False])
def test_verified_results_survive_synthesis_timeout_and_focused_branch_omits_optional_models(tmp_path,focused):
    from app.expeditions import ExpeditionEngine,ExpeditionStart
    settings,store,_,study,passages=setup(tmp_path);settings.max_run_seconds=.4
    engine=ExpeditionEngine(store,settings);calls=[]
    async def structures(*a,**k):return []
    engine.world=SimpleNamespace(search=lambda *a,**k:{'studies':[study]},acquire=lambda sid:asyncio.sleep(0,result=study),passages=lambda sid:passages,detail=lambda sid:{'entities':[]},structures=structures)
    async def model(rid,tid,tool,payload):
        calls.append(tool)
        if tool=='plan_expedition':return {'directions':[{'title':'Inspect public source '+str(i),'why':'Review the archived evidence.','capability':'read_source_passages'} for i in range(3)],'queries':['PTEN methods']}
        if tool=='source_report':return {'claims':[{'text':'PTEN evidence warrants review.','quote_id':passages[0]['id']}],'limitations':['Published evidence only.']}
        if tool=='revise_research_path':return {'action':'finish','reason':'The supplied evidence is sufficient for a source-level checkpoint.'}
        if tool=='research_synthesis':await asyncio.sleep(10)
        raise AssertionError(tool)
    engine.model=model
    async def go():
        result=engine.start(ExpeditionStart(question='Examine the public PTEN methods evidence',max_seconds=120 if focused else 300,study_ids=[study['id']],study_limit=1,mode='agentic'),branch_provenance={'study_id':study['id'],'source_version':study['version']} if focused else None)
        if not focused:engine.edit(result['id'],lambda d:{**d,'max_seconds':.4})
        await asyncio.gather(*list(engine.pending));return store.get('expeditions',result['id'])
    result=asyncio.run(go())
    assert result['claims'] and all(c['source_version']==study['version'] for c in result['claims'])
    assert any(e['type']=='evidence.checkpoint' for e in result['events'])
    if focused:
        assert result['status']=='completed_with_limitations'
        assert 'research_synthesis' not in calls and 'revise_research_path' not in calls
    else:
        assert result['status']=='interrupted' and result['result_stage']=='evidence_checked'
        assert next(t for t in result['tasks'] if t['id']=='synthesis')['status']=='interrupted'
