"""Public corpus and expedition contracts; no live services or private records."""
import asyncio
import base64
import json
from pathlib import Path
from types import SimpleNamespace
import httpx
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.corpus_store import CorpusStore
from app.world_research import WorldResearch,article_row,split_passages,extract_mentions
from app.expeditions import ExpeditionEngine,ExpeditionStart,STOPPED
from app.research_schemas import AgentAction
from app.main import create_app


def setup(tmp_path):
    settings=Settings(local_data_dir=tmp_path,worker_mode='external',openrouter_api_key='scripted',openrouter_model='scripted',max_run_seconds=600)
    store=CorpusStore(settings);world=WorldResearch(store,settings)
    study=article_row({'source':'MED','id':'10001','title':'PTEN function in cancer cells','doi':'10.example/public','pubYear':'2024','abstractText':'PTEN p.R172H and c.123A>G were examined with a protein assay. PDB ID: 1D5R provides structural context. These published observations require further validation.','authorString':'Example Authors','language':['eng'],'authorList':{'author':[{'authorAffiliationDetailsList':{'authorAffiliation':[{'affiliation':'Example University, China'}]}}]}},'PTEN')
    store.put('studies',study['id'],study)
    passages=split_passages(study['id'],study['version'],[{'section':'methods','text':study['abstract']},{'section':'results','text':'PTEN assay measurements were reported with uncertainty. The source does not establish a clinical result or a mutant protein fold.'}]);store.put_many('passages',passages);store.put_many('entities',extract_mentions(passages))
    return settings,store,world,study,passages


def mock_http(monkeypatch,handler):
    actual=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:actual(**{**kw,'transport':httpx.MockTransport(handler)}))


def test_local_corpus_is_durable_atomic_and_unicode(tmp_path):
    s=Settings(local_data_dir=tmp_path);a=CorpusStore(s)
    a.put('metadata','counter',{'revision':0,'count':0,'text':'蛋白质の研究'})
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:a.mutate('metadata','counter',lambda d:{**d,'count':d['count']+1}),range(40)))
    assert CorpusStore(s).get('metadata','counter')['count']==40
    assert a.get('metadata','counter')['text']=='蛋白质の研究'
    asset=a.put_asset(b'public original bytes','txt');assert a.read_asset(asset)==b'public original bytes'
    with pytest.raises(ValueError):a.put('unapproved-collection','x',{})


def test_entity_extraction_coverage_country_and_synthetic_exclusion(tmp_path):
    _,store,world,study,passages=setup(tmp_path)
    assert study['countries']==['China'] and study['country_basis'].startswith('Publication affiliation')
    mentions=extract_mentions(passages)
    assert {'p.R172H','c.123A>G','1D5R','PTEN'}<={m['label'] for m in mentions}
    assert all(m['quote'] in next(p['text'] for p in passages if p['id']==m['passage_id']) for m in mentions)
    world.seed_scenarios(100);world.seed_scenarios(100);assert store.count('scenarios')==100
    assert all(s['synthetic'] for s in store.rows('scenarios'))
    assert len(world.search('PTEN')['studies'])==1
    store.put('studies','fabricated',{**study,'id':'fabricated','synthetic':True})
    assert [d['id'] for d in world.search('PTEN')['studies']]==[study['id']]
    assert not world.search('PTEN',country='Japan')['studies']


def test_duplicate_discovery_preserves_original_version_and_coverage(tmp_path,monkeypatch):
    _,store,world,study,_=setup(tmp_path);store.put('studies',study['id'],{**study,'coverage':'open-access body text','version':'pinned','text_asset':{'sha256':'fixture'}})
    mock_http(monkeypatch,lambda req:httpx.Response(200,json={'hitCount':1,'resultList':{'result':[{'id':'10001','source':'MED','title':'Changed remote title','abstractText':'A changed remote abstract.'}]}}))
    asyncio.run(world.discover('another query',1));saved=store.get('studies',study['id'])
    assert saved['version']=='pinned' and saved['coverage']=='open-access body text' and 'another query' in saved['topics']


def test_full_text_archive_reuses_assets_and_keeps_current_version(tmp_path,monkeypatch):
    _,store,world,study,_=setup(tmp_path)
    store.put('studies',study['id'],{**study,'open_access':True,'pmcid':'PMC10001'})
    xml=b'<article><front><article-meta><permissions><license>CC BY</license></permissions></article-meta></front><body><sec><title>Methods</title><p>PTEN protein activity was measured in the reported assay using p.R172H as a source example.</p></sec><sec><title>Results</title><p>The observed result includes uncertainty and requires further experimental validation.</p></sec></body></article>'
    calls=[]
    def handler(req):calls.append(str(req.url));return httpx.Response(200,content=xml)
    mock_http(monkeypatch,handler)
    acquired=asyncio.run(world.acquire(study['id']));again=asyncio.run(world.acquire(study['id']))
    assert len(calls)==1 and acquired['version']==again['version']!=study['version']
    assert acquired['coverage']=='open-access body text' and store.read_asset(acquired['original_asset'])==xml
    assert all(p['version']==acquired['version'] for p in world.passages(study['id']))
    assert world.detail(study['id'])['sections']['methods']


def test_structures_use_documented_doi_search_and_verify_primary_citation(tmp_path,monkeypatch):
    _,store,world,study,_=setup(tmp_path);requests=[]
    def handler(req):
        requests.append(req)
        if 'search.rcsb.org' in str(req.url):
            query=json.loads(req.content);assert query['query']['parameters']['attribute']=='citation.pdbx_database_id_DOI'
            return httpx.Response(200,json={'result_set':[{'identifier':'1D5R'}]})
        if 'data.rcsb.org' in str(req.url):return httpx.Response(200,json={'struct':{'title':'Experimental reference'},'exptl':[{'method':'X-RAY DIFFRACTION'}],'rcsb_primary_citation':{'pdbx_database_id_DOI':study['doi']},'rcsb_entry_info':{'resolution_combined':[2.1]}})
        return httpx.Response(200,text='data_test\nloop_\n_atom_site.id\n1\n2\n')
    mock_http(monkeypatch,handler)
    rows=asyncio.run(world.structures(study['id'],1));assert rows[0]['citation_matches'] and rows[0]['relationship']=='publication-linked structure' and rows[0]['atom_count']==2
    again=asyncio.run(world.structures(study['id'],1));assert len(requests)==3 and again[0]['relationship']=='publication-linked structure'
    assert world.detail(study['id'])['structures'][0]['citation_matches']
    assert not any('predicted' in d for d in rows[0])


def test_related_structure_is_never_mislabeled_publication_link(tmp_path,monkeypatch):
    _,_,world,study,_=setup(tmp_path)
    def handler(req):
        if 'search.rcsb.org' in str(req.url):return httpx.Response(200,json={'result_set':[]})
        if 'data.rcsb.org' in str(req.url):return httpx.Response(200,json={'struct':{'title':'Reference from another study'},'rcsb_primary_citation':{'pdbx_database_id_DOI':'10.example/other'}})
        return httpx.Response(200,text='data_test\nloop_\n_atom_site.id\n1\n')
    mock_http(monkeypatch,handler)
    rows=asyncio.run(world.structures(study['id'],1));assert not rows[0]['citation_matches'] and rows[0]['relationship']=='structure mentioned in source text'


def test_embeddings_exclude_stale_versions_and_nonfinite_values(tmp_path,monkeypatch):
    settings,store,_,study,passages=setup(tmp_path);settings.corpus_embeddings='local-multilingual';world=WorldResearch(store,settings)
    store.put('passages','stale',{**passages[0],'id':'stale','version':'old'})
    monkeypatch.setattr('app.world_research.MultilingualEmbeddings.vectors',lambda self,texts:[[1.0]+[0.0]*383 for t in texts])
    assert world.embed_pending(100)['embedded']==2 and store.get('passages','stale')['embedding_model'] is None
    result=world.search('PTEN',mode='semantic');assert result['studies'][0]['id']==study['id']
    store.put('passages',passages[0]['id'],passages[0]);monkeypatch.setattr('app.world_research.MultilingualEmbeddings.vectors',lambda self,texts:[[float('nan')]*384 for t in texts])
    with pytest.raises(ValueError,match='finite'):world.embed_pending(100)


def stub_world(engine,study,passages,markers):
    async def acquire(sid):return study
    async def structures(sid,limit=2,refresh=False):
        markers.add('structure');await asyncio.sleep(.03);assert {'methods','outcomes'}<=markers
        return []
    engine.world=SimpleNamespace(search=lambda *a,**k:{'studies':[study]},acquire=acquire,passages=lambda sid:passages,detail=lambda sid:{'entities':[]},structures=structures)


def scripted_provider(monkeypatch,markers,bad=False,revision='finish'):
    class Provider:
        def __init__(self,*a):self.before_fallback=None;self.on_attempt=None
        async def close(self):pass
        async def generate_action(self,prompt):
            data=json.loads(prompt)
            if 'supported_capabilities' in data:
                tool='plan_expedition';args={'directions':[{'title':c.replace('_',' '),'why':'Check the original public evidence and its scope.','capability':c} for c in ['search_public_studies','trace_structures','verify_source_quotes','read_source_passages','synthesize_evidence']],'queries':['PTEN function']}
            elif 'focus' in data:
                markers.add('methods' if 'Methods reviewer' in data['task'] else 'outcomes');await asyncio.sleep(.03);assert {'structure','methods','outcomes'}<=markers
                tool='source_report';args={'claims':[{'text':'PTEN source observations require further validation.'+(' Unsupported number 9999.' if bad else ''),'quote_id':data['passages'][0]['id']}],'limitations':['Original public passages require scientific interpretation.']}
            elif 'acquired_studies' in data:
                tool='revise_research_path';args={'action':revision,'reason':'Compare additional original passages before accepting the scoped evidence summary.','study_id':data['acquired_studies'][0]['id']}
            else:
                tool='research_synthesis';args={'claims':[{'text':'PTEN observations require validation.','quote_id':data['observations'][0]['id']}],'limitations':['No experimental reproduction was performed.']}
            return AgentAction(action='invoke_tool',summary='Scripted offline test output',tool=tool,arguments=args),{'provider':'fixture','model':'scripted','cost_usd':None}
    monkeypatch.setattr('app.expeditions.ActionProvider',Provider)


def test_actual_concurrent_workers_adaptive_followup_and_durable_quote_checks(tmp_path,monkeypatch):
    settings,store,_,study,passages=setup(tmp_path);engine=ExpeditionEngine(store,settings);markers=set();stub_world(engine,study,passages,markers);scripted_provider(monkeypatch,markers,revision='inspect_more_passages')
    async def go():
        run=engine.start(ExpeditionStart(question='What does PTEN source evidence show?',study_ids=[study['id']],study_limit=1));await asyncio.gather(*list(engine.pending));return store.get('expeditions',run['id'])
    run=asyncio.run(go());assert run['status']=='completed_with_limitations',run
    assert len(run['claims'])==1 and run['claims'][0]['quote']==store.get('passages',run['claims'][0]['passage_id'])['text']
    assert run['budget']['model_requests']==5
    assert {t['id'] for t in run['tasks']}=={'lead','evidence','structure','methods','outcomes','lead-review','followup','verifier','synthesis'}
    assert next(t for t in run['tasks'] if t['id']=='followup')['passage_ids']
    assert any(e['type']=='path.revised' for e in run['events'])
    assert [e['sequence'] for e in run['events']]==list(range(1,len(run['events'])+1))
    assert store.count('events')==len(run['events']) and store.count('tasks')==len(run['tasks'])
    assert not any(p['status']=='exploring' for p in run['directions'])


def test_unsupported_numeric_claims_fail_workers_without_becoming_findings(tmp_path,monkeypatch):
    settings,store,_,study,passages=setup(tmp_path);engine=ExpeditionEngine(store,settings);markers=set();stub_world(engine,study,passages,markers);scripted_provider(monkeypatch,markers,bad=True)
    async def go():
        r=engine.start(ExpeditionStart(question='What does PTEN source evidence show?',study_limit=1));await asyncio.gather(*list(engine.pending));return store.get('expeditions',r['id'])
    run=asyncio.run(go());assert not run['claims'] and all(t['status']=='failed' for t in run['tasks'] if t['id'] in ('methods','outcomes'))
    assert run['status']=='completed_with_limitations' and run['limitations']


def test_tools_only_never_constructs_a_provider(tmp_path,monkeypatch):
    settings,store,_,study,passages=setup(tmp_path);engine=ExpeditionEngine(store,settings)
    async def structures(*a,**k):return []
    engine.world=SimpleNamespace(search=lambda *a,**k:{'studies':[study]},acquire=lambda sid:asyncio.sleep(0,result=study),passages=lambda sid:passages,detail=lambda sid:{'entities':[]},structures=structures)
    monkeypatch.setattr('app.expeditions.ActionProvider',lambda *a:pytest.fail('Tools-only must not call a model'))
    async def go():
        r=engine.start(ExpeditionStart(question='What does PTEN source evidence show?',study_limit=1,mode='tools-only'));await asyncio.gather(*list(engine.pending));return store.get('expeditions',r['id'])
    run=asyncio.run(go());assert run['status']=='completed_with_limitations' and run['budget']['model_requests']==0
    assert run['claims'] and all(c['claim_type'].startswith('literal source extract') for c in run['claims'])


def test_cancellation_and_recovery_preserve_history(tmp_path):
    settings,store,_,study,passages=setup(tmp_path);engine=ExpeditionEngine(store,settings)
    async def wait(sid):await asyncio.sleep(30)
    engine.world=SimpleNamespace(search=lambda *a,**k:{'studies':[study]},acquire=wait)
    async def go():
        r=engine.start(ExpeditionStart(question='Inspect PTEN public study evidence',mode='tools-only',study_limit=1))
        await asyncio.sleep(.01);engine.edit(r['id'],lambda d:{**d,'cancel_requested':True});await engine.close();return store.get('expeditions',r['id'])
    run=asyncio.run(go());assert run['status']=='cancelled' and all(t['status']!='running' for t in run['tasks'])
    store.put('expeditions','interrupted',{**run,'id':'interrupted','status':'running','revision':0});asyncio.run(engine.recover())
    assert store.get('expeditions','interrupted')['status']=='interrupted'


def test_model_budget_is_reserved_before_an_attempt(tmp_path):
    settings,store,_,_,_=setup(tmp_path);settings.max_model_requests=1;engine=ExpeditionEngine(store,settings)
    store.put('expeditions','budget',{'id':'budget','revision':0,'status':'running','budget':{'model_requests':0,'max_model_requests':1}})
    engine.reserve('budget')
    with pytest.raises(ValueError,match='budget exhausted'):engine.reserve('budget')
    assert store.get('expeditions','budget')['budget']['model_requests']==1


def test_public_study_attaches_to_project_with_provenance_and_no_model(tmp_path):
    settings,store,_,study,_=setup(tmp_path)
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/observatory/status').json()['backend']=='local'
        response=client.post('/api/observatory/studies/'+study['id']+'/attach',json={});assert response.status_code==200,response.text
        result=response.json();project=client.get('/api/portfolio/projects/'+result['project_id']).json();assert result['source_id'] in project['sources']
        assert not project['sources'][result['source_id']]['included']
        assert client.get('/api/observatory/studies/missing').status_code==404
        assert client.post('/api/observatory/expeditions',json={'question':'Public PTEN research question','study_ids':['missing'],'mode':'tools-only'}).status_code==422
        paper=list((tmp_path/'papers').glob('*.json'))[0];assert json.loads(paper.read_text())['provenance']['source_version']==store.get('studies',study['id'])['version']


def test_public_rag_rejects_unprovided_citations_and_saves_only_checked_answers(tmp_path,monkeypatch):
    from app.corpus_guide import CorpusQuestion,answer_public_question
    settings,store,_,study,passages=setup(tmp_path);invalid=[False]
    class Provider:
        def __init__(self,*a):self.on_attempt=None
        async def close(self):pass
        async def generate_action(self,prompt):
            data=json.loads(prompt)
            assert 'project' not in data and all(p['study_id']==study['id'] for p in data['passages'])
            return AgentAction(action='invoke_tool',summary='Scripted public RAG answer',tool='corpus_answer',arguments={'claims':[{'text':'PTEN requires further validation.','quote_id':'invented' if invalid[0] else data['passages'][0]['id']}],'limitations':['Source-linked interpretation only.']}),{'provider':'fixture','model':'scripted'}
    monkeypatch.setattr('app.corpus_guide.ActionProvider',Provider)
    body=CorpusQuestion(question='What does PTEN evidence support?',study_id=study['id'],language='中文')
    result=asyncio.run(answer_public_question(store,settings,body));assert result['claims'][0]['quote']==store.get('passages',result['claims'][0]['passage_id'])['text']
    assert store.count('searches')==1
    invalid[0]=True
    with pytest.raises(ValueError,match='verification'):asyncio.run(answer_public_question(store,settings,body))
    assert store.count('searches')==1


def test_each_ingestion_batch_acquires_its_own_bounded_open_texts(tmp_path,monkeypatch):
    _,store,world,study,_=setup(tmp_path)
    store.put('studies',study['id'],{**study,'text_asset':{'sha256':'existing'},'open_access':True})
    second={**study,'id':'new-public-study','open_access':True};store.put('studies',second['id'],second);calls=[]
    async def discover(*a,**k):return {'studies':[]}
    async def acquire(sid):calls.append(sid);return store.put('studies',sid,{**second,'text_asset':{'sha256':'acquired'}})
    monkeypatch.setattr(world,'discover',discover);monkeypatch.setattr(world,'acquire',acquire)
    store.put('ingestion_jobs','batch',{'status':'queued','revision':0,'topics':['PTEN'],'completed_topics':[],'full_text_limit':1,'scenario_count':0,'embed':False})
    asyncio.run(world.ingest('batch'));asyncio.run(world.ingest('batch'))
    assert calls==['new-public-study']
    assert store.get('ingestion_jobs','batch')['acquired_study_ids']==['new-public-study']
    assert store.get('ingestion_jobs','batch')['status']=='completed'


@pytest.mark.parametrize('stop',['cancel','timeout'])
def test_inflight_cancellation_and_deadline_stop_the_actual_task(tmp_path,stop):
    settings,store,_,study,_=setup(tmp_path);settings.max_run_seconds=600
    engine=ExpeditionEngine(store,settings)
    async def wait(sid):await asyncio.sleep(30)
    engine.world=SimpleNamespace(search=lambda *a,**k:{'studies':[study]},acquire=wait)
    async def go():
        r=engine.start(ExpeditionStart(question='Inspect original public PTEN evidence',mode='tools-only',study_limit=1))
        if stop=='timeout':
            # Force a short explicit deadline without sleeping for the API minimum.
            engine.edit(r['id'],lambda d:{**d,'max_seconds':.02})
        await asyncio.sleep(.01)
        if stop=='cancel':engine.cancel(r['id'])
        await asyncio.gather(*list(engine.pending));return store.get('expeditions',r['id'])
    result=asyncio.run(go());assert result['status']==('cancelled' if stop=='cancel' else 'interrupted')
    assert not any(t['status']=='running' for t in result['tasks'])
    assert any(e['type']==('cancel.requested' if stop=='cancel' else 'budget.reached') for e in result['events'])


@pytest.mark.parametrize('deadline',[None,30,3600,14400])
def test_expedition_deadline_is_optional_and_independent_of_short_engine_cap(tmp_path,monkeypatch,deadline):
    from pydantic import ValidationError
    settings,store,_,_,_=setup(tmp_path);settings.max_run_seconds=10
    engine=ExpeditionEngine(store,settings);seen=[]
    actual_wait=asyncio.wait_for
    async def capture(coro,timeout):
        seen.append(timeout)
        return await actual_wait(coro,timeout=1)
    async def work(rid):
        engine.edit(rid,lambda d:{**d,'status':'completed_with_limitations'})
    monkeypatch.setattr(asyncio,'wait_for',capture);monkeypatch.setattr(engine,'work',work)
    async def go():
        body=ExpeditionStart(question='Inspect original public PTEN evidence',max_seconds=deadline,mode='tools-only')
        run=engine.start(body);await asyncio.gather(*list(engine.pending));return run
    run=asyncio.run(go())
    assert seen==[deadline]
    assert store.get('expeditions',run['id'])['max_seconds']==deadline
    assert store.get('expeditions',run['id'])['budget']['max_model_requests']<=12
    assert ExpeditionStart(question='Inspect public source evidence').max_seconds is None
    with pytest.raises(ValidationError):ExpeditionStart(question='Inspect public source evidence',max_seconds=0)
    with pytest.raises(ValidationError):ExpeditionStart(question='Inspect public source evidence',max_seconds=86401)


def test_saved_expedition_history_finds_older_project_records_before_paging(tmp_path):
    settings,store,_,_,_=setup(tmp_path)
    for i in range(65):
        store.put('expeditions','history-'+str(i),{'question':'PTEN 癌研究 '+str(i),'status':'completed_with_limitations','created_at':f'2026-10-{1+i//24:02}T{i%24:02}:00:00Z','project_id':'project-target' if i<4 else None})
    with TestClient(create_app(settings)) as client:
        first=client.get('/api/observatory/expeditions').json()
        assert first['total']==65 and len(first['expeditions'])==50 and first['next_offset']==50
        second=client.get('/api/observatory/expeditions?offset=50').json()
        assert len(second['expeditions'])==15 and second['next_offset'] is None
        assert not {d['id'] for d in first['expeditions']} & {d['id'] for d in second['expeditions']}
        project=client.get('/api/observatory/expeditions?project_id=project-target&q=癌研究').json()
        assert project['total']==4 and len(project['expeditions'])==4
        assert client.get('/api/observatory/expeditions?unassigned=true').json()['total']==61
        assert client.get('/api/observatory/expeditions?q=%5B').json()['total']==0
        assert client.get('/api/observatory/expeditions?offset=-1').status_code==422
