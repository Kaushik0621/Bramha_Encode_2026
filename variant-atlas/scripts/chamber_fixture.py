"""Generate an explicitly SIMULATED, deterministic event fixture, without API calls."""
import asyncio
import sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.config import Settings
from app.fixtures import load_fixture,FIXTURE_PATH
from app.schemas import InvestigationRequest
from app.runs import RunManager

class MemoryRepository:
    def workspace(self): return load_fixture()
    def save(self,result): self.result=result
    def save_run(self,run): pass

async def main():
    manager=RunManager(MemoryRepository(),Settings(llm_provider='mock'))
    initial=await manager.start(InvestigationRequest(explanation_mode='fixture'))
    await manager.tasks[initial.run_id]
    run=manager.get(initial.run_id)
    old=run.run_id
    run.run_id='run-simulated-fixture'
    run.execution_mode='simulated'
    run.result_id='inv-'+'0'*32
    result_old=run.result.id
    run.result.id=run.result_id
    start=datetime(2026,10,24,10,0,tzinfo=timezone.utc)
    for i,event in enumerate(run.events):
        event.run_id=run.run_id
        event.event_id=f'{run.run_id}:{event.sequence}'
        event.mode='simulated'
        event.timestamp=(start+timedelta(milliseconds=450*i)).isoformat()
        event.output_refs=[run.result_id if x==result_old else x for x in event.output_refs]
    for artifact in run.artifacts:
        artifact.refs=[run.result_id if x==result_old else x for x in artifact.refs]
        if artifact.id=='artifact-brief': artifact.data['investigation_id']=run.result_id
    run.created_at=run.events[0].timestamp
    run.updated_at=run.events[-1].timestamp
    run.result.created_at=run.updated_at
    for step in run.result.steps: step.completed_at=run.updated_at
    (FIXTURE_PATH.parent/'chamber-run.json').write_text(run.model_dump_json(indent=2)+'\n')
    print(f'Wrote simulated chamber fixture: {len(run.events)} recorded events. No external call made.')

asyncio.run(main())
