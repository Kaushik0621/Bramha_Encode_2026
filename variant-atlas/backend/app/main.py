import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pymongo.errors import PyMongoError
from .config import Settings
from .schemas import (Health, Workspace, Criteria, Analysis, VariantDetail, Neighbors,
    InvestigationRequest, Investigation, InvestigationSummary)
from .repositories import RepositoryError
from .repositories.local import LocalRepository
from .repositories.atlas import AtlasRepository
from .analysis import filter_variants, variant_detail, get_spatial_neighbors
from .workflow import investigate, markdown_export
from .runs import RunManager
from .run_schemas import RunSnapshot, TERMINAL
from .fixtures import FIXTURE_PATH

def create_app(settings: Settings | None = None, repository_override=None):
    config=settings or Settings.from_env()
    @asynccontextmanager
    async def lifespan(app):
        app.state.repository=None
        app.state.storage_error=None
        app.state.runs=None
        try:
            if repository_override is not None: repo=repository_override
            elif config.data_backend=='local': repo=LocalRepository(config.local_data_dir)
            elif config.data_backend=='atlas': repo=AtlasRepository(config.mongodb_uri,config.mongodb_database)
            else: raise RepositoryError('Unsupported DATA_BACKEND. Choose local or atlas.')
            app.state.repository=repo
            repo.workspace()  # Verify seed/readability before reporting healthy.
            app.state.runs=RunManager(repo,config)
            await app.state.runs.recover()
        except RepositoryError as exc:
            app.state.storage_error=str(exc)
        except Exception:
            app.state.storage_error='Configured storage is unavailable or invalid. Check setup and seed the workspace.'
        yield
        if app.state.runs: await app.state.runs.shutdown()
        if app.state.repository: app.state.repository.close()
    app=FastAPI(title='Variant Atlas API',version='0.1.0',lifespan=lifespan)
    app.add_middleware(CORSMiddleware,allow_origins=list(config.cors_origins),allow_methods=['GET','POST'],allow_headers=['Content-Type'])
    @app.exception_handler(RepositoryError)
    async def repository_error(request,exc):
        return JSONResponse(status_code=503,content={'detail':str(exc)})
    @app.exception_handler(PyMongoError)
    async def mongo_error(request,exc):
        return JSONResponse(status_code=503,content={'detail':'Atlas operation failed. No local fallback was used.'})
    @app.exception_handler(OSError)
    async def disk_error(request,exc):
        return JSONResponse(status_code=503,content={'detail':'Local persistence failed. Check directory permissions and disk space.'})
    def repo():
        if app.state.storage_error: raise HTTPException(503,app.state.storage_error)
        return app.state.repository
    def saved(iid):
        inv=repo().get(iid)
        if inv is None: raise HTTPException(404,'Investigation not found.')
        return inv
    @app.get('/api/health',response_model=Health)
    def health(response: Response):
        error=app.state.storage_error
        if not error:
            try: repo().workspace()
            except Exception: error='Configured storage cannot be read. No fallback was used.'
        if error: response.status_code=503
        configured=config.llm_provider=='mock' or (config.llm_provider=='openrouter' and bool(config.openrouter_api_key and config.openrouter_model))
        return Health(status='error' if error else 'ok',storage=config.data_backend,storage_ready=not bool(error),storage_error=error,
            llm_provider=config.llm_provider,llm_model=config.openrouter_model if config.llm_provider=='openrouter' else 'fixture-extractive-v1' if config.llm_provider=='mock' else None,llm_configured=configured)
    @app.get('/api/workspace',response_model=Workspace)
    def workspace(): return repo().workspace()
    @app.post('/api/analyze',response_model=Analysis)
    def analyze(criteria: Criteria): return filter_variants(repo().workspace(),criteria)
    @app.get('/api/variants/{vid}',response_model=VariantDetail)
    def variant(vid: str):
        try: return variant_detail(repo().workspace(),vid)
        except KeyError: raise HTTPException(404,'Variant not found.') from None
    @app.get('/api/variants/{vid}/neighbors',response_model=Neighbors)
    def neighbors(vid: str,radius: float=Query(12,gt=0,le=100,allow_inf_nan=False)):
        try: return get_spatial_neighbors(repo().workspace(),vid,radius)
        except KeyError: raise HTTPException(404,'Variant not found.') from None
    @app.post('/api/investigations',response_model=Investigation | RunSnapshot,status_code=201)
    async def new_investigation(request: InvestigationRequest,response: Response,execution: str=Query('sync',pattern='^(sync|live)$')):
        try:
            if execution=='live':
                repo()
                response.status_code=202
                return await app.state.runs.start(request)
            return await investigate(repo(),config,request)
        except ValueError as exc: raise HTTPException(422,str(exc)) from None
    @app.get('/api/investigations',response_model=list[InvestigationSummary])
    def investigations():
        return [InvestigationSummary(id=i.id,title=i.title,created_at=i.created_at,selected_count=len(i.selected_ids),result_mode=i.result_mode) for i in repo().list()]
    def run_snapshot(iid):
        repo()
        run=app.state.runs.get(iid)
        if run is None: raise HTTPException(404,'Run not found.')
        return run

    @app.get('/api/chamber/fixture',response_model=RunSnapshot)
    def chamber_fixture():
        path=FIXTURE_PATH.parent/'chamber-run.json'
        if not path.exists(): raise HTTPException(503,'Generate the chamber fixture with scripts/chamber_fixture.py.')
        return RunSnapshot.model_validate_json(path.read_text())

    @app.get('/api/chamber/fixture/export')
    def chamber_fixture_export():
        run=chamber_fixture()
        return Response('**Simulated workflow — synthetic data.**\n\n'+markdown_export(run.result,repo().workspace()),media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="simulated-chamber-brief.md"'})

    @app.get('/api/investigations/{iid}',response_model=Investigation | RunSnapshot)
    def investigation(iid: str):
        return run_snapshot(iid) if iid.startswith('run-') else saved(iid)

    @app.post('/api/investigations/{iid}/cancel',response_model=RunSnapshot)
    async def cancel_run(iid: str):
        run_snapshot(iid)
        return await app.state.runs.cancel(iid)

    @app.get('/api/investigations/{iid}/events')
    async def events(iid: str,request: Request,after: int=Query(0,ge=0)):
        run_snapshot(iid)
        last=request.headers.get('last-event-id')
        if last:
            try:
                prefix,seq=last.rsplit(':',1)
                if prefix!=iid: raise ValueError()
                after=max(after,int(seq))
            except ValueError: raise HTTPException(400,'Invalid Last-Event-ID.') from None
        async def stream():
            cursor=after
            while True:
                if await request.is_disconnected(): return
                run=run_snapshot(iid)
                for event in run.events:
                    if event.sequence>cursor:
                        cursor=event.sequence
                        yield f'id: {event.event_id}\nevent: run-event\ndata: {event.model_dump_json()}\n\n'
                if run.status in TERMINAL: return
                signal=app.state.runs.signals.setdefault(iid,asyncio.Event())
                signal.clear()
                # Re-check after clearing: a producer cannot race this synchronous section.
                if len(run.events)>cursor: continue
                try: await asyncio.wait_for(signal.wait(),timeout=10)
                except asyncio.TimeoutError: yield ': heartbeat\n\n'
        return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
    @app.get('/api/investigations/{iid}/export')
    def export(iid: str):
        inv=saved(iid)
        return Response(markdown_export(inv,repo().workspace()),media_type='text/markdown',headers={'Content-Disposition':f'attachment; filename="{inv.id}.md"'})
    return app

app=create_app()
