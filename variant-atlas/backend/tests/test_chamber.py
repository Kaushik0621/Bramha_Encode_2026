import asyncio
import json
import threading
import time
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.llm.mock import MockExplainer
from app.run_schemas import RunSnapshot,TERMINAL
from app.repositories.local import LocalRepository
from app.schemas import InvestigationRequest
from app.runs import RunManager

@pytest.fixture
def settings(tmp_path): return Settings(local_data_dir=tmp_path/'store')

def finish(client,run_id):
    for _ in range(200):
        snapshot=client.get('/api/investigations/'+run_id).json()
        if snapshot['status'] in TERMINAL:return snapshot
        time.sleep(.005)
    raise AssertionError('Run did not reach a terminal state.')

def start(client,**kwargs):
    response=client.post('/api/investigations?execution=live',json={'explanation_mode':'fixture',**kwargs})
    assert response.status_code==202,response.text
    return response.json()

def test_live_events_order_dependencies_persistence_and_sse_reconnect(settings):
    with TestClient(create_app(settings)) as client:
        initial=start(client)
        assert initial['status']=='queued'
        assert initial['result'] is None
        run=finish(client,initial['run_id'])
        assert run['status']=='completed' and run['execution_mode']=='live'
        events=run['events']
        assert [e['sequence'] for e in events]==list(range(1,len(events)+1))
        assert len({e['event_id'] for e in events})==len(events)
        assert events[-1]['type']=='run.completed'
        assert run['storage']=='local' and run['provider']=='mock'
        assert all(w['kind']=='deterministic_tool' for w in run['workers'])
        assay=next(e for e in events if e['worker_id']=='assay-analysis' and e['type']=='tool.completed')
        assert assay['metrics']['matching_variants']==5
        assert assay['metrics']['missing_measurements']==1
        mapping=next(e for e in events if e['worker_id']=='structure-mapping' and e['type']=='tool.completed')
        assert mapping['metrics']=={'mapped':3,'unmapped':2}
        assert any(e['type']=='warning' and e['worker_id']=='structure-mapping' for e in events)
        for handoff in [e for e in events if e['type']=='handoff']:
            assert handoff['sender'] and handoff['recipient'] and handoff['output_refs']
        for worker in run['workers']:
            starts=[e['sequence'] for e in events if e['worker_id']==worker['id'] and e['type'] in ('tool.started','task.started')]
            if not starts:continue
            for dependency in worker['depends_on']:
                ends=[e['sequence'] for e in events if e['worker_id']==dependency and e['type'] in ('tool.completed','task.completed','task.skipped','task.failed')]
                assert ends and min(starts)>max(ends)
        midpoint=events[len(events)//2]
        response=client.get(f'/api/investigations/{run["run_id"]}/events',headers={'Last-Event-ID':midpoint['event_id']})
        streamed=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        assert [e['sequence'] for e in streamed]==list(range(midpoint['sequence']+1,len(events)+1))
        assert 'text/event-stream' in response.headers['content-type']
        assert client.get(f'/api/investigations/{run["run_id"]}/events',headers={'Last-Event-ID':'other-run:3'}).status_code==400
        saved=client.get('/api/investigations/'+run['result_id']).json()
        assert saved['selected_ids']==['demo-v01','demo-v02','demo-v05','demo-v06','demo-v08']
    with TestClient(create_app(settings)) as restarted:
        snapshot=restarted.get('/api/investigations/'+run['run_id']).json()
        assert snapshot==run
        assert restarted.post('/api/investigations/'+run['run_id']+'/cancel').json()['status']=='completed'


def test_failed_model_produces_partial_needs_review_result(settings):
    settings.llm_provider='openrouter'
    settings.openrouter_model='test-model'
    settings.openrouter_api_key=''
    with TestClient(create_app(settings)) as client:
        initial=start(client,explanation_mode='configured')
        run=finish(client,initial['run_id'])
        assert run['status']=='needs_review'
        assert run['result']['result_mode']=='llm_error'
        assert any(w['kind']=='llm_call' for w in run['workers'])
        assert any(e['type']=='task.failed' and e['worker_id']=='brief-synthesis' for e in run['events'])
        assert run['events'][-1]['type']=='run.needs_review'
        assert not any(e['type']=='run.completed' for e in run['events'])


def test_cancel_interrupts_inflight_call_and_persists_authoritative_terminal_state(settings,monkeypatch):
    started=threading.Event();interrupted=threading.Event()
    async def slow(self,payload):
        started.set()
        try:await asyncio.sleep(60)
        finally:interrupted.set()
    monkeypatch.setattr(MockExplainer,'explain',slow)
    with TestClient(create_app(settings)) as client:
        initial=start(client)
        assert started.wait(3)
        response=client.post('/api/investigations/'+initial['run_id']+'/cancel')
        assert response.json()['status']=='cancellation_requested'
        run=finish(client,initial['run_id'])
        assert run['status']=='cancelled' and run['result'] is None
        assert interrupted.wait(1)
        assert run['events'][-1]['type']=='run.cancelled'
        assert any(e['type']=='task.cancelled' and e['worker_id']=='brief-synthesis' for e in run['events'])
        assert client.get('/api/investigations').json()==[]
        assert client.post('/api/investigations/'+initial['run_id']+'/cancel').json()['status']=='cancelled'


def test_domain_failure_and_unknown_run_do_not_fake_success(settings):
    with TestClient(create_app(settings)) as client:
        initial=start(client,selected_ids=['demo-v07'])
        run=finish(client,initial['run_id'])
        assert run['status']=='failed' and run['result'] is None
        assert run['events'][-1]['type']=='run.failed'
        assert 'current matching candidate' in run['error']
        for suffix in ['', '/events','/cancel']:
            response=client.post('/api/investigations/run-unknown'+suffix) if suffix=='/cancel' else client.get('/api/investigations/run-unknown'+suffix)
            assert response.status_code==404


def test_restart_marks_interrupted_local_job_failed(settings):
    repo=LocalRepository(settings.local_data_dir)
    async def queued():
        manager=RunManager(repo,settings)
        run=await manager.start(InvestigationRequest())
        task=manager.tasks[run.run_id]
        task.cancel()
        await asyncio.gather(task,return_exceptions=True)
        # Represent an abrupt process stop before any worker continuation.
        stored=repo.get_run(run.run_id)
        stored.status='running'
        repo.save_run(stored)
        return run.run_id
    run_id=asyncio.run(queued())
    with TestClient(create_app(settings)) as client:
        run=client.get('/api/investigations/'+run_id).json()
        assert run['status']=='failed'
        assert 'backend restart' in run['error']
        assert run['events'][-1]['type']=='run.failed'


def test_recorded_fixture_is_explicit_and_exportable(settings):
    with TestClient(create_app(settings)) as client:
        fixture=client.get('/api/chamber/fixture').json()
        assert fixture['execution_mode']=='simulated'
        assert fixture['provider']=='mock'
        assert all(e['mode']=='simulated' for e in fixture['events'])
        assert fixture['result']['selected_ids']==['demo-v01','demo-v02','demo-v05','demo-v06','demo-v08']
        assert 'Simulated workflow' in client.get('/api/chamber/fixture/export').text
