"""Fixture verification, not evidence of live translation quality."""
import asyncio
import base64
import copy
import json
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
from app.science import ScientificData
from app.repositories.research import ResearchStore
from app.papers import PaperLibrary, PaperUpload, PaperRead, PaperTranslate
from app.research_schemas import AgentAction
from app.paper_review import PaperReviewEngine, PaperReviewRequest

TEXTS = ['Результаты исследования предварительные и требуют независимой проверки.', 'この研究結果は予備的であり、独立した検証が必要です。', '这项研究的结果是初步的，需要进行独立验证，不能直接用于临床判断。']

def settings_at(path):
    return Settings(local_data_dir=path, worker_mode='external', openrouter_api_key='fixture-key', openrouter_model='fixture-model')

def upload(library, text=TEXTS[0]):
    return library.upload(PaperUpload(filename='研究.txt', content_base64=base64.b64encode(text.encode('utf-8')).decode()))

async def fixture_action(self, prompt, **kwargs):
    payload = json.loads(prompt)
    if 'passages' in payload:
        return AgentAction(action='invoke_tool', summary='Fixture translation', tool='paper_translation', arguments={'passages': [{'chunk_id': c['id'], 'text': 'Fixture translation; independent verification is required.'} for c in payload['passages']], 'limitations': ['Scripted fixture, not verified live translation.']}), {'provider': 'fixture', 'model': 'fixture-model'}
    return AgentAction(action='invoke_tool', summary='Fixture reading', tool='paper_reading', arguments={'summary': 'The selected passages call for validation.', 'claims': [{'text': 'The source reports preliminary results.', 'chunk_id': c['id'], 'quote': c['text'][:30]} for c in payload['chunks']], 'limitations': ['Selected passages only; scientific review is required.']}), {'provider': 'fixture', 'model': 'fixture-model'}

@pytest.mark.parametrize('text', TEXTS)
def test_utf8_aligned_translation_and_selected_reading(tmp_path, monkeypatch, text):
    monkeypatch.setattr('app.papers.ActionProvider.generate_action', fixture_action)
    library = PaperLibrary(settings_at(tmp_path)); paper = upload(library, text)
    original = (library.root / (paper['id'] + '.original')).read_bytes()
    translated = asyncio.run(library.translate(paper['id'], PaperTranslate(chunk_ids=['p1-c1'], language='English')))
    reading = asyncio.run(library.read(paper['id'], PaperRead(chunk_ids=['p1-c1'])))
    assert translated['source_version'] == paper['sha256']
    assert translated['covered_chunk_ids'] == ['p1-c1']
    assert translated['translation']['passages'][0]['chunk_id'] == 'p1-c1'
    assert reading['reading']['claims'][0]['quote'] in text
    assert library.get(paper['id'])['chunks'][0]['text'] == text
    assert (library.root / (paper['id'] + '.original')).read_bytes() == original == text.encode()
    assert translated['provider']['model'] == 'fixture-model'

def test_translation_alignment_failure_retains_failure_without_coverage(tmp_path, monkeypatch):
    async def invalid(self, prompt, **kwargs):
        action, usage = await fixture_action(self, prompt)
        action.arguments['passages'][0]['chunk_id'] = 'invented'
        return action, usage
    monkeypatch.setattr('app.papers.ActionProvider.generate_action', invalid)
    library = PaperLibrary(settings_at(tmp_path)); paper = upload(library)
    with pytest.raises(ValueError, match='alignment'):
        asyncio.run(library.translate(paper['id'], PaperTranslate(chunk_ids=['p1-c1'])))
    saved = json.loads(next(library.root.glob('*-translation-*.json')).read_text())
    assert saved['status'] == 'failed' and saved['covered_chunk_ids'] == []
    assert saved['translation']['passages'] == []
    with pytest.raises(ValueError, match='not in'):
        asyncio.run(library.read(paper['id'], PaperRead(chunk_ids=['invented'])))

def test_registry_visit_and_navigation_are_model_free(tmp_path, monkeypatch):
    calls=[]
    async def forbidden(*args, **kwargs):
        calls.append(True); raise AssertionError('No model call during navigation')
    monkeypatch.setattr('app.papers.ActionProvider.generate_action', forbidden)
    settings=settings_at(tmp_path); ResearchStore(settings).seed(ScientificData().workspace())
    with TestClient(create_app(settings)) as c:
        data=c.get('/api/portfolio/bootstrap').json()
        assert len(data['areas']) == 10
        assert {a['method'] for a in data['areas']} == {'pten','blood','papers'}
        project=c.post('/api/portfolio/projects',json={'title':'Paper-led work','objective':'Review the limitations of this paper.', 'method':'papers','area':'cancer'}).json()
        assert project['method_info']['title'] == 'Bounded paper review'
        v=c.post('/api/portfolio/projects/'+project['id']+'/visit',json={'tab':'evidence'}).json()
        again=c.post('/api/portfolio/projects/'+project['id']+'/visit',json={'tab':'evidence'}).json()
        assert again['revision'] == v['revision'] and again['last_context']['tab'] == 'evidence'
        assert not calls

def test_frozen_paper_run_followup_lineage_and_unlink(tmp_path, monkeypatch):
    monkeypatch.setattr('app.papers.ActionProvider.generate_action', fixture_action)
    settings=settings_at(tmp_path); ResearchStore(settings).seed(ScientificData().workspace())
    with TestClient(create_app(settings)) as c:
        source=c.post('/api/portfolio/sources/import',json={'filename':'研究.txt','content_base64':base64.b64encode(TEXTS[2].encode()).decode()}).json()
        project=c.post('/api/portfolio/projects',json={'title':'Paper research','objective':'Review the reported limitations and applicability.', 'method':'papers','source_ids':[source['id']]}).json()
        path='/api/portfolio/projects/'+project['id']
        body={'confirmed':True,'paper':{'question':project['objective'],'source_id':source['id'],'source_version':source['version'],'chunk_ids':['p1-c1'],'language':'English'}}
        assert c.post(path+'/investigations',json=body).status_code==409
        assert c.post(path+'/sources',json={'source_id':source['id'],'action':'include'}).status_code==200
        response=c.post(path+'/investigations',json=body); assert response.status_code==200,response.text
        rid=response.json()['run_id']; detail=c.get('/api/portfolio/investigations/'+rid).json()
        assert detail['method']=='papers' and detail['run']['status']=='completed_with_limitations'
        assert detail['run']['reading']['covered_chunk_ids']==['p1-c1']
        visited=c.post(path+'/visit',json={'tab':'results','run_id':rid})
        assert visited.status_code==200 and visited.json()['last_context']['run_id']==rid
        other=c.post('/api/portfolio/projects',json={'title':'Separate research','objective':'Review a separate paper question.','method':'papers'}).json()
        assert c.post('/api/portfolio/projects/'+other['id']+'/visit',json={'tab':'results','run_id':rid}).status_code==409
        original_path=tmp_path/'research'/(rid+'.json'); original_bytes=original_path.read_bytes()
        follow=c.post(path+'/investigations/'+rid+'/continue',json={'question':'Which missing evidence limits the reported observation?','reason':'Clarify the applicability gap.'}).json()
        assert follow['baseline_inputs']['question']==project['objective'] and follow['parent_run_id']==rid
        assert c.post(path+'/continuations/'+follow['id'],json={'expected_revision':99,'inputs':follow['inputs']}).status_code==409
        newer_body=copy.deepcopy(body); newer_body['paper']['question']=follow['inputs']['question']; newer_body['continuation_id']=follow['id']
        newer=c.post(path+'/investigations',json=newer_body); assert newer.status_code==200,newer.text
        child=c.get('/api/portfolio/investigations/'+newer.json()['run_id']).json()
        assert child['lineage']['parent_run_id']==rid
        assert original_path.read_bytes()==original_bytes
        assert c.post(path+'/investigations',json=newer_body).status_code==409
        assert c.post(path+'/sources',json={'source_id':source['id'],'action':'unlink'}).status_code==200
        assert c.get('/api/portfolio/sources/'+source['id']).status_code==200
        assert c.get('/api/portfolio/investigations/'+rid).json()['run']['paper_sources'][0]['chunks'][0]['text']==TEXTS[2]

def test_provider_failure_cancellation_and_interrupted_recovery(tmp_path, monkeypatch):
    settings=settings_at(tmp_path); engine=PaperReviewEngine(ResearchStore(settings),settings)
    paper=upload(PaperLibrary(settings)); source={'origin_id':paper['id']}
    body=PaperReviewRequest(question='Explain the limits of this observation.',source_id='source-fixture',source_version=paper['sha256'],chunk_ids=['p1-c1'])
    async def fail(*args,**kwargs):
        raise RuntimeError('sensitive provider text must not be persisted')
    monkeypatch.setattr('app.papers.ActionProvider.generate_action',fail)
    first=engine.start('project-fixture',source,body); asyncio.run(engine.execute(first['run_id']))
    saved=engine.store.get(first['run_id'])
    assert saved['status']=='failed' and not saved['findings'] and 'sensitive' not in saved['error']
    cancelled=engine.start('project-fixture',source,body); engine.cancel(cancelled['run_id']); asyncio.run(engine.execute(cancelled['run_id']))
    assert engine.store.get(cancelled['run_id'])['budget']['model_requests']==0
    stopped=engine.start('project-fixture',source,body); engine.recover()
    assert engine.store.get(stopped['run_id'])['status']=='interrupted'

def test_contextual_assistance_uses_active_project_and_pinned_metadata_without_paid_calls(tmp_path, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError('Selection must not invoke a model')
    monkeypatch.setattr('app.papers.ActionProvider.generate_action', forbidden)
    settings=settings_at(tmp_path); data=ScientificData(); workspace=data.workspace(); ResearchStore(settings).seed(workspace)
    with TestClient(create_app(settings)) as c:
        sources=c.get('/api/portfolio/sources').json()
        project=c.post('/api/portfolio/projects',json={'title':'Scoped assistant','objective':'Compare PTEN measurements without inferring a mutant fold.','method':'pten','source_ids':[s['id'] for s in sources if s['method']=='pten']}).json()
        body={'dataset_version':workspace['dataset_version'],'anchor_id':'PTEN:p.C124S','selected_ids':['PTEN:p.C124S'],'criteria':{k:workspace['defaults'][k] for k in ['scenario','activity_cutoff','abundance_cutoff']},'project_id':project['id'],'question':'Explain this selected observation.','use_model':False}
        response=c.post('/api/research/context',json=body)
        assert response.status_code==200,response.text
        context=response.json()['session_context']
        assert context['objective']==project['objective']
        assert context['active_question']==body['question']
        assert {s['id']:s['version'] for s in context['sources']} == {sid:l['version'] for sid,l in project['sources'].items()}
        assert 'metadata only' in context['coverage']
        paper=c.post('/api/portfolio/projects',json={'title':'Paper only','objective':'Review a paper before interpreting the observations.','method':'papers'}).json()
        body['project_id']=paper['id']
        assert c.post('/api/research/context',json=body).status_code==409
