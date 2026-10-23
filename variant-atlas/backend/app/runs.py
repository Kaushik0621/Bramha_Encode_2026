"""Single-process development jobs; persisted events are independent of SSE viewers."""
import asyncio
from uuid import uuid4
from .run_schemas import Artifact, RunEvent, RunSnapshot, Worker, TERMINAL
from .workflow import investigate, now

WORKERS = [
    ('coordinator','Coordinator',[], 'Controls the bounded workflow and saves the review brief.'),
    ('data-retrieval','Data retrieval',[], 'Loads the configured repository; never substitutes another store.'),
    ('assay-analysis','Assay analysis',['data-retrieval'], 'Applies explicit criteria, retaining missing measurement states.'),
    ('structure-mapping','Structure mapping',['assay-analysis'], 'Checks coordinate coverage and calculates Euclidean neighbours.'),
    ('evidence-review','Evidence review',['assay-analysis','structure-mapping'], 'Collects source records and their variant references.'),
    ('brief-synthesis','Brief synthesis',['evidence-review'], 'Optional single model call or explicitly configured fixture explanation.'),
    ('verification','Verification',['brief-synthesis'], 'Checks deterministic identifiers, outputs and accepted source references.')]

class RunManager:
    def __init__(self, repository, settings):
        self.repository=repository
        self.settings=settings
        self.cache={}
        self.tasks={}
        self.signals={}

    def get(self, run_id):
        if run_id not in self.cache:
            run=self.repository.get_run(run_id)
            if run is None: return None
            self.cache[run_id]=run
        return self.cache[run_id]

    async def emit(self, run, type, worker_id, summary, status=None, **kwargs):
        worker=next(w for w in run.workers if w.id==worker_id)
        event=RunEvent(event_id=f'{run.run_id}:{len(run.events)+1}',run_id=run.run_id,
            sequence=len(run.events)+1,timestamp=now(),type=type,worker_id=worker_id,
            worker_kind=worker.kind,task_id=worker_id,status=status or run.status,summary=summary,
            mode=run.execution_mode,**kwargs)
        run.events.append(event)
        run.updated_at=event.timestamp
        # Atomic local snapshot contains both sequence and events. This synchronous,
        # bounded repository write cannot be interrupted by another asyncio task.
        self.repository.save_run(run)
        self.signals.setdefault(run.run_id,asyncio.Event()).set()
        await asyncio.sleep(0)
        return event

    async def start(self, request):
        provider='none' if request.explanation_mode=='none' else 'mock' if request.explanation_mode=='fixture' else self.settings.llm_provider
        model='fixture-extractive-v1' if provider=='mock' else self.settings.openrouter_model if provider=='openrouter' else None
        run=RunSnapshot(run_id='run-'+uuid4().hex,status='queued',created_at=now(),updated_at=now(),request=request,
            storage=self.settings.data_backend,provider=provider,model=model,
            workers=[Worker(id=i,name=n,kind='llm_call' if i=='brief-synthesis' and provider=='openrouter' else 'deterministic_tool',depends_on=d,description=text) for i,n,d,text in WORKERS])
        self.cache[run.run_id]=run
        await self.emit(run,'run.created','coordinator','Investigation accepted. Waiting for the local development worker.','queued')
        for w in run.workers:
            await self.emit(run,'task.queued',w.id,'Waiting for declared inputs.','queued')
        # Return a frozen queued snapshot before the task begins running.
        initial=run.model_copy(deep=True)
        self.tasks[run.run_id]=asyncio.create_task(self.execute(run),name=run.run_id)
        return initial

    async def execute(self, run):
        active=None
        async def observe(worker,status,summary,**kw):
            nonlocal active
            refs=kw.get('input_refs',[])
            if status=='running':
                active=worker
                descriptor=next(w for w in run.workers if w.id==worker)
                for dep in descriptor.depends_on:
                    artifacts=[a for a in run.artifacts if a.worker_id==dep]
                    if artifacts:
                        await self.emit(run,'handoff',dep,f'{next(w.name for w in run.workers if w.id==dep)} → {descriptor.name}',
                            'completed',sender=dep,recipient=worker,output_refs=[a.id for a in artifacts],input_refs=[r for a in artifacts for r in a.refs])
            if kw.get('dataset_version'): run.dataset_version=kw['dataset_version']
            artifact=kw.get('artifact')
            output=[]
            if artifact:
                a=Artifact(worker_id=worker,**artifact)
                run.artifacts.append(a)
                output=[a.id]
                await self.emit(run,'artifact.created',worker,a.summary,status if status!='output' else 'running',output_refs=output,input_refs=a.refs)
            event_type='warning' if status=='warning' else 'artifact.ready' if status=='output' else ('task.' if worker=='brief-synthesis' else 'tool.')+('started' if status=='running' else status)
            await self.emit(run,event_type,worker,summary,status if status!='warning' else 'needs_review',input_refs=refs,output_refs=output,metrics=kw.get('metrics',{}))
            if status in ('completed','skipped','failed'): active=None
        try:
            run.status='running'
            await self.emit(run,'run.started','coordinator','Starting investigation with the original question, shortlist and declared criteria.','running')
            await self.emit(run,'task.started','coordinator','Coordinating deterministic tools and the configured optional explanation.','running')
            run.artifacts.append(Artifact(id='artifact-context',name='Declared research context',worker_id='coordinator',summary='Original objective, criteria and candidate capacity.',data=run.request.model_dump(mode='json')))
            await self.emit(run,'artifact.created','coordinator','Research context recorded.','running',output_refs=['artifact-context'])
            await self.emit(run,'handoff','coordinator','Declared research context → data retrieval.','running',sender='coordinator',recipient='data-retrieval',output_refs=['artifact-context'])
            result=await investigate(self.repository,self.settings,run.request,observer=observe)
            run.result=result
            run.result_id=result.id
            run.status='needs_review' if result.result_mode=='llm_error' else 'completed'
            await self.emit(run,'task.completed','coordinator','Partial deterministic brief ready; explanation needs review.' if run.status=='needs_review' else 'Review brief ready. Researcher review remains required.','completed',output_refs=['artifact-brief'])
            await self.emit(run,'run.needs_review' if run.status=='needs_review' else 'run.completed','coordinator',
                'Saved a partial result with the explanation error visible.' if run.status=='needs_review' else 'Investigation completed; saved output and provenance are available.',run.status,output_refs=[result.id,'artifact-brief'])
        except asyncio.CancelledError:
            run.status='cancelled'
            run.error='Execution cancelled. Any in-flight client request was interrupted; the remote provider may still process or bill an already submitted request. No returned model output will be used.'
            if active:
                await self.emit(run,'task.cancelled',active,'Active task interrupted; its output is not accepted.','cancelled')
            for w in run.workers:
                states=[e.status for e in run.events if e.worker_id==w.id and (e.type.startswith('task.') or e.type.startswith('tool.'))]
                if not states or states[-1] in ('queued','running'):
                    await self.emit(run,'task.cancelled',w.id,'Cancelled before completion.','cancelled')
            await self.emit(run,'run.cancelled','coordinator',run.error,'cancelled')
        except Exception as exc:
            run.status='failed'
            run.error=str(exc) if isinstance(exc,ValueError) else 'Execution failed. Check the configured repository and service availability; no storage or model fallback was used.'
            if active: await self.emit(run,'task.failed',active,run.error,'failed')
            await self.emit(run,'run.failed','coordinator',run.error,'failed')

    async def cancel(self, run_id):
        run=self.get(run_id)
        if run is None: return None
        if run.status in TERMINAL: return run.model_copy(deep=True)
        if any(a.id=='artifact-brief' for a in run.artifacts):
            await self.emit(run,'warning','coordinator','The brief was already committed before cancellation arrived; the saved result is being finalized.','needs_review')
            return run.model_copy(deep=True)
        run.status='cancellation_requested'
        await self.emit(run,'run.cancellation_requested','coordinator','Cancellation requested. Awaiting confirmation from the local worker.','cancellation_requested')
        response=run.model_copy(deep=True)
        if run.status in TERMINAL or any(a.id=='artifact-brief' for a in run.artifacts):
            return response
        task=self.tasks.get(run_id)
        if task and not task.done(): task.cancel()
        else:
            run.status='cancelled'
            await self.emit(run,'run.cancelled','coordinator','No active worker remained; cancellation confirmed.','cancelled')
        return response

    async def recover(self):
        for run in self.repository.list_runs():
            self.cache[run.run_id]=run
            if run.status not in TERMINAL:
                run.status='failed'
                run.error='The local worker was interrupted by a backend restart. Recorded events remain available; start a new investigation explicitly.'
                for w in run.workers:
                    latest=[e for e in run.events if e.worker_id==w.id and e.type in ('task.started','tool.started','task.completed','tool.completed','task.failed','tool.failed','task.cancelled','tool.cancelled','task.skipped','tool.skipped')]
                    if latest and latest[-1].status=='running':
                        await self.emit(run,'task.failed',w.id,run.error,'failed')
                await self.emit(run,'run.failed','coordinator',run.error,'failed')

    async def shutdown(self):
        pending=[t for t in self.tasks.values() if not t.done()]
        for task in pending: task.cancel()
        await asyncio.gather(*pending,return_exceptions=True)
