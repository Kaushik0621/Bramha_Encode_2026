import asyncio
import json
import math
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from app.analysis import filter_variants, get_spatial_neighbors
from app.config import Settings
from app.fixtures import generate_fixture, load_fixture
from app.llm import explanation_payload, validate_narrative, ExplanationError
from app.llm.mock import MockExplainer
from app.llm.openrouter import OpenRouterExplainer
from app.main import create_app
from app.repositories.local import LocalRepository
from app.repositories.atlas import AtlasRepository
from app.repositories import RepositoryError
from app.schemas import Criteria

DEFAULT_IDS=['demo-v01','demo-v02','demo-v05','demo-v06','demo-v08']

@pytest.fixture
def workspace(): return load_fixture()

@pytest.fixture
def settings(tmp_path): return Settings(local_data_dir=tmp_path/'store')

@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client: yield client

def test_fixture_matches_contract_and_generation(workspace):
    assert workspace.model_dump()==generate_fixture().model_dump()
    assert len(workspace.variants)==8
    assert len(workspace.measurements)==16
    assert len(workspace.evidence)==4
    assert len(workspace.structure.points)==109
    assert len(workspace.protein.sequence)==120
    positions={p.position for p in workspace.structure.points}
    for v in workspace.variants:
        assert v.ref==workspace.protein.sequence[v.position-1]
        assert v.ref!=v.alt
        assert (v.position in positions)==(v.mapping_status=='mapped')

def test_expected_selection_and_nulls(workspace):
    result=filter_variants(workspace,Criteria())
    assert result.matching_ids==DEFAULT_IDS
    assert (result.mapped_count,result.unmapped_count)==(3,2)
    assert result.missing_measurement_count==1
    null=next(r for r in result.results if r.variant_id=='demo-v07')
    assert null.activity is None and not null.matches
    assert filter_variants(workspace,Criteria(mapping='mapped')).matching_ids==['demo-v01','demo-v02','demo-v05']
    assert filter_variants(workspace,Criteria(mapping='unmapped')).matching_ids==['demo-v06','demo-v08']
    assert filter_variants(workspace,Criteria(evidence='missing')).matching_ids==[]
    assert filter_variants(workspace,Criteria(abundance_min=0,activity_max=1)).matching_ids==[v.id for v in workspace.variants if v.id!='demo-v07']

def test_neighbors_exact_distance_self_exclusion_and_unavailable(workspace):
    result=get_spatial_neighbors(workspace,'demo-v01',100)
    assert result.status=='available'
    assert len(result.neighbors)==5
    assert 'demo-v01' not in {n.variant_id for n in result.neighbors}
    p={x.position:x for x in workspace.structure.points}
    a,b=p[12],p[28]
    expected=round(math.sqrt((a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2),6)
    assert next(n.distance for n in result.neighbors if n.variant_id=='demo-v02')==expected
    assert get_spatial_neighbors(workspace,'demo-v01',.01).neighbors==[]
    for vid in ['demo-v06','demo-v08']:
        n=get_spatial_neighbors(workspace,vid,12)
        assert n.status=='unavailable' and n.reason and n.neighbors==[]

@pytest.mark.parametrize('payload',[{'abundance_min':-1},{'activity_max':1.1},{'mapping':'other'},{'evidence':'fake'},{'activity_max':'NaN'}])
def test_validation_rejects_bad_filters(client,payload):
    assert client.post('/api/analyze',json=payload).status_code==422

def test_api_contract_and_unknown_ids(client):
    assert client.get('/api/health').json()['llm_provider']=='mock'
    assert client.get('/api/workspace').json()['synthetic']
    assert client.post('/api/analyze',json={}).json()['matching_ids']==DEFAULT_IDS
    assert client.get('/api/variants/demo-v07').json()['measurements'][1]['value'] is None
    assert client.get('/api/variants/no-such-id').status_code==404
    assert client.get('/api/variants/no-such-id/neighbors').status_code==404
    assert client.get('/api/investigations/not-found').status_code==404
    assert client.get('/api/investigations/not-found/export').status_code==404
    assert client.get('/api/variants/demo-v01/neighbors?radius=-1').status_code==422
    assert client.get('/api/variants/demo-v01/neighbors?radius=nan').status_code==422
    assert client.post('/api/investigations',json={'selected_ids':['demo-v07']}).status_code==422

def test_persistence_restart_export_and_modes(settings):
    with TestClient(create_app(settings)) as client:
        response=client.post('/api/investigations',json={'title':'Saved acceptance case'})
        assert response.status_code==201,response.text
        inv=response.json()
        assert inv['selected_ids']==DEFAULT_IDS and inv['result_mode']=='fixture'
        assert inv['provider']=='mock'
        assert [s['name'] for s in inv['steps']]==['Validate input','Filter variants','Check coverage','Collect evidence','Explain supplied evidence','Verify shortlist','Save investigation']
        assert inv['steps'][-1]['name']=='Save investigation'
        iid=inv['id']
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(f'/api/investigations/{iid}').json()==inv
        assert restarted.get('/api/investigations').json()[0]['id']==iid
        exported=restarted.get(f'/api/investigations/{iid}/export')
        assert exported.status_code==200
        assert 'text/markdown' in exported.headers['content-type']
        for fragment in ['Synthetic data','Illustrative geometry','demo-evidence-01','fixture','demo-v08','0.70','0.35']:
            assert fragment in exported.text
        none=restarted.post('/api/investigations',json={'explanation_mode':'none','selected_ids':[]}).json()
        assert none['result_mode']=='deterministic' and none['narrative'] is None
        assert none['selected_ids']==[]

def test_local_atomic_write_and_reseed_retains_investigations(settings):
    with TestClient(create_app(settings)) as client:
        iid=client.post('/api/investigations',json={}).json()['id']
    repo=LocalRepository(settings.local_data_dir)
    repo.seed(load_fixture())
    assert repo.get(iid) is not None
    assert repo.get('../../workspace') is None
    assert len(list(settings.local_data_dir.glob('investigations/*')))==1

@pytest.mark.parametrize('corrupt',['variant','source','number','unsupported','link','limitation'])
def test_invalid_model_references_and_claims_are_rejected(workspace,corrupt):
    payload=explanation_payload(workspace,filter_variants(workspace,Criteria()),DEFAULT_IDS)
    result=asyncio.run(MockExplainer().explain(payload)).model_copy(deep=True)
    if corrupt=='variant': result.findings[0].variant_ids=['demo-v99']
    if corrupt=='source': result.findings[0].evidence_ids=['demo-evidence-99']
    if corrupt=='number': result.summary='The activity is 0.99.'
    if corrupt=='unsupported': result.findings[0].text='The activity is 0.99.'
    if corrupt=='link': result.findings[0].variant_ids=['demo-v08']
    if corrupt=='limitation': result.limitations=['No limitations.']
    with pytest.raises(ExplanationError): validate_narrative(result,payload)

def test_openrouter_error_is_not_fake_success(settings):
    settings.llm_provider='openrouter'
    settings.openrouter_api_key=''
    settings.openrouter_model='test-model'
    with TestClient(create_app(settings)) as client:
        inv=client.post('/api/investigations',json={}).json()
        assert inv['result_mode']=='llm_error'
        assert inv['narrative'] is None
        assert inv['selected_ids']==DEFAULT_IDS
        assert inv['explanation_error']
        explicit=client.post('/api/investigations',json={'explanation_mode':'fixture'}).json()
        assert explicit['result_mode']=='fixture'
        assert explicit['provider']=='mock'

def test_openrouter_validated_success_repair_limit_and_http_errors(workspace,monkeypatch):
    settings=Settings(llm_provider='openrouter',openrouter_api_key='test-secret',openrouter_model='configured-test-model')
    payload=explanation_payload(workspace,filter_variants(workspace,Criteria()),DEFAULT_IDS)
    valid=asyncio.run(MockExplainer().explain(payload)).model_dump_json()
    calls=[]
    responses=[httpx.Response(200,json={'choices':[{'message':{'content':'not json'}}]}),httpx.Response(200,json={'choices':[{'message':{'content':valid}}]})]
    async def post(self,url,**kwargs):
        calls.append(kwargs)
        return responses.pop(0)
    monkeypatch.setattr(httpx.AsyncClient,'post',post)
    result=asyncio.run(OpenRouterExplainer(settings).explain(payload))
    assert result.findings and len(calls)==2
    assert calls[0]['json']['model']=='configured-test-model'
    assert calls[0]['headers']['Authorization']=='Bearer test-secret'
    responses.extend([httpx.Response(429,json={'error':{'message':'never expose provider text'}})])
    with pytest.raises(ExplanationError,match='rate limited'):
        asyncio.run(OpenRouterExplainer(settings).explain(payload))
    responses.extend([httpx.Response(200,json={}),httpx.Response(200,json={})])
    with pytest.raises(ExplanationError,match='invalid or unsupported'):
        asyncio.run(OpenRouterExplainer(settings).explain(payload))
    assert len(calls)==5

def test_openrouter_timeout(workspace,monkeypatch):
    async def post(*args,**kwargs): raise httpx.ReadTimeout('sensitive provider text')
    monkeypatch.setattr(httpx.AsyncClient,'post',post)
    payload=explanation_payload(workspace,filter_variants(workspace,Criteria()),DEFAULT_IDS)
    settings=Settings(openrouter_api_key='test-secret',openrouter_model='test')
    with pytest.raises(ExplanationError,match='timed out') as error:
        asyncio.run(OpenRouterExplainer(settings).explain(payload))
    assert 'sensitive' not in str(error.value)

def test_atlas_missing_config_is_explicit_and_no_local_fallback(tmp_path):
    settings=Settings(data_backend='atlas',mongodb_uri='',local_data_dir=tmp_path/'never-created')
    with TestClient(create_app(settings)) as client:
        health=client.get('/api/health')
        assert health.status_code==503
        assert health.json()['storage']=='atlas'
        assert not health.json()['storage_ready']
        assert client.get('/api/workspace').status_code==503
        assert not settings.local_data_dir.exists()
    with pytest.raises(RepositoryError): AtlasRepository('', 'test')

def test_health_and_exports_never_contain_backend_secrets(settings):
    settings.openrouter_api_key='test-super-secret-key'
    with TestClient(create_app(settings)) as client:
        for path in ['/api/health','/api/workspace','/openapi.json']:
            assert settings.openrouter_api_key not in client.get(path).text
        inv=client.post('/api/investigations',json={}).json()
        assert settings.openrouter_api_key not in json.dumps(inv)
        assert settings.openrouter_api_key not in client.get(f'/api/investigations/{inv["id"]}/export').text

def test_business_decision_brief_preserves_objective_and_capacity(client):
    request={'research_question':'Which supplied profiles warrant a follow-up discussion, and what evidence is missing?',
             'candidate_budget':2,'selected_ids':['demo-v01','demo-v06'],'explanation_mode':'none'}
    response=client.post('/api/investigations',json=request)
    assert response.status_code==201,response.text
    inv=response.json()
    assert inv['research_question']==request['research_question']
    assert inv['candidate_budget']==2
    assert [n['variant_id'] for n in inv['decision_notes']]==request['selected_ids']
    for n in inv['decision_notes']:
        assert n['hypothesis_status']=='unverified'
        assert n['observations'] and all(m['synthetic'] for m in n['observations'])
        assert n['selection_reason'] and n['unresolved_question'] and n['follow_up_approach']
        assert n['alternative_explanation'] and n['evidence_ids']
    missing=inv['decision_notes'][1]
    assert any('Geometry unavailable' in x for x in missing['limitations'])
    text=client.get(f'/api/investigations/{inv["id"]}/export').text
    for fragment in ['Research decision','Candidate capacity: 2','Unresolved question','Alternative explanation','Proposed follow-up approach','demo-v02: Matches the filters but was not included']:
        assert fragment in text


def test_capacity_is_enforced_without_silent_ranking(client):
    before=client.get('/api/investigations').json()
    response=client.post('/api/investigations',json={'candidate_budget':2})
    assert response.status_code==422
    assert 'Curate the shortlist explicitly' in response.json()['detail']
    assert client.get('/api/investigations').json()==before
    for invalid in [0,-1,1.5,True]:
        assert client.post('/api/investigations',json={'candidate_budget':invalid}).status_code==422
    assert client.post('/api/investigations',json={'research_question':'short'}).status_code==422


def test_export_evidence_is_a_saved_snapshot(settings):
    with TestClient(create_app(settings)) as client:
        inv=client.post('/api/investigations',json={'explanation_mode':'none'}).json()
        original=client.get(f'/api/investigations/{inv["id"]}/export').text
    repo=LocalRepository(settings.local_data_dir)
    workspace=repo.workspace()
    workspace.evidence[0].text='Changed source text after this investigation.'
    workspace.variants[0].position=13
    repo.seed(workspace)
    with TestClient(create_app(settings)) as restarted:
        exported=restarted.get(f'/api/investigations/{inv["id"]}/export').text
    assert exported==original
    assert 'Changed source text' not in exported


def test_env_process_overrides_private_dotenv_without_mutating_environment(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','mock')
    monkeypatch.setenv('OPENROUTER_API_KEY','')
    monkeypatch.setenv('BACKEND_HOST','127.0.0.1')
    monkeypatch.setenv('BACKEND_PORT','8123')
    monkeypatch.setenv('FRONTEND_ORIGIN','http://localhost:8500')
    monkeypatch.delenv('CORS_ORIGINS',raising=False)
    settings=Settings.from_env()
    assert settings.llm_provider=='mock' and not settings.openrouter_api_key
    assert settings.backend_host=='127.0.0.1' and settings.backend_port==8123
    assert settings.frontend_origin=='http://localhost:8500'
    assert set(settings.cors_origins)=={'http://localhost:8500','http://127.0.0.1:8500'}
    assert 'openrouter_api_key' not in repr(settings)


def test_new_frontend_origin_allowed_by_cors(client):
    response=client.options('/api/investigations',headers={'Origin':'http://localhost:8500','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'})
    assert response.status_code==200
    assert response.headers['access-control-allow-origin']=='http://localhost:8500'
