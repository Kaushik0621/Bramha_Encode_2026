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
from .research_schemas import ResearchRequest
from .fixtures import FIXTURE_PATH

def create_app(settings: Settings | None = None, repository_override=None):
    config=settings or Settings.from_env()
    if config.app_profile!='local':raise ValueError('Only the localhost single-user profile is implemented. Public deployment requires authentication and workspace isolation.')
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
        app.state.research_error=None
        app.state.research_store=None
        app.state.science=None
        app.state.research_engine=None
        try:
            from .science import ScientificData
            from .repositories.research import ResearchStore
            from .orchestration.engine import ResearchEngine
            data=ScientificData(config.asset_root)
            store=ResearchStore(config)
            store.workspace()
            data.store=store
            data.workspace()
            if config.data_backend=='atlas' and config.embedding_provider!='disabled':
                from .retrieval.hybrid import HybridRetrieval
                data.retrieval=HybridRetrieval(store,config)
            app.state.science=data;app.state.research_store=store
            app.state.research_engine=ResearchEngine(store,data,config)
            if config.worker_mode=='embedded':await app.state.research_engine.launch()
        except Exception as exc:
            app.state.research_error=str(exc) if isinstance(exc,(RepositoryError,FileNotFoundError,ValueError)) else 'Real-data setup failed; acquire and seed audited data.'
        app.state.blood_engine=None
        app.state.blood_store=None
        app.state.blood_error=None
        try:
            from .blood.engine import BloodEngine
            from .repositories.research import ResearchStore
            app.state.blood_store=ResearchStore(config,workspace_id='blood-group')
            app.state.blood_engine=BloodEngine(app.state.blood_store,config)
            if config.worker_mode=='embedded':await app.state.blood_engine.launch()
        except Exception as exc:
            app.state.blood_error=str(exc)
        yield
        if app.state.blood_engine:await app.state.blood_engine.shutdown()
        if app.state.blood_store:app.state.blood_store.close()
        if app.state.research_engine:await app.state.research_engine.shutdown()
        if app.state.research_store:app.state.research_store.close()
        if app.state.runs: await app.state.runs.shutdown()
        if app.state.repository: app.state.repository.close()
    app=FastAPI(title='Bramha Atlas API',version='0.1.0',lifespan=lifespan)
    @app.middleware('http')
    async def local_only(request,call_next):
        if request.client and request.client.host not in ('127.0.0.1','::1','testclient'):
            return JSONResponse(status_code=403,content={'detail':'This single-user profile accepts loopback clients only.'})
        return await call_next(request)
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
        error=app.state.research_error if config.data_mode=='real' else app.state.storage_error
        if not error:
            try:
                if config.data_mode=='real':app.state.research_store.workspace()
                else:repo().workspace()
            except Exception: error='Configured storage cannot be read. No fallback was used.'
        if error: response.status_code=503
        configured=config.llm_provider=='mock' or (config.llm_provider=='openrouter' and bool(config.openrouter_api_key and config.openrouter_model)) or (config.llm_provider in ('google','gemini') and bool(config.google_api_key))
        return Health(status='error' if error else 'ok',storage=config.data_backend,storage_ready=not bool(error),storage_error=error,
            llm_provider=config.llm_provider,llm_model=config.openrouter_model if config.llm_provider=='openrouter' else 'fixture-extractive-v1' if config.llm_provider=='mock' else config.argon_model if config.llm_provider in ('google','gemini') else None,llm_configured=configured)
    @app.get('/api/workspace',response_model=Workspace)
    def workspace(): return repo().workspace()
    @app.post('/api/analyze',response_model=Analysis)
    def analyze(criteria: Criteria): return filter_variants(repo().workspace(),criteria)
    @app.get('/api/variants/{vid}',response_model=VariantDetail | dict)
    def variant(vid: str):
        if vid.startswith('PTEN:'):return research_endpoint('/api/research/variants/{vid}','GET')(vid)
        try: return variant_detail(repo().workspace(),vid)
        except KeyError: raise HTTPException(404,'Variant not found.') from None
    @app.get('/api/variants/{vid}/neighbors',response_model=Neighbors | dict)
    def neighbors(vid: str,radius: float=Query(12,gt=0,le=100,allow_inf_nan=False)):
        if vid.startswith('PTEN:'):return research_endpoint('/api/research/variants/{vid}/neighbors','GET')(vid,radius)
        try: return get_spatial_neighbors(repo().workspace(),vid,radius)
        except KeyError: raise HTTPException(404,'Variant not found.') from None
    @app.post('/api/investigations',response_model=Investigation | RunSnapshot | dict,status_code=201)
    async def new_investigation(request: ResearchRequest | InvestigationRequest,response: Response,execution: str=Query('sync',pattern='^(sync|live)$')):
        if isinstance(request,ResearchRequest):
            response.status_code=202
            return research_endpoint('/api/research/investigations','POST')(request)
        try:
            if execution=='live':
                repo()
                response.status_code=202
                return await app.state.runs.start(request)
            return await investigate(repo(),config,request)
        except ValueError as exc: raise HTTPException(422,str(exc)) from None
    @app.get('/api/investigations',response_model=list[InvestigationSummary] | list[dict])
    def investigations(workspace_id: str='fixture'):
        if workspace_id=='pten-real':return research_endpoint('/api/research/investigations','GET')()
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

    @app.get('/api/investigations/{iid}',response_model=Investigation | RunSnapshot | dict)
    def investigation(iid: str):
        if iid.startswith('research-'):return research_endpoint('/api/research/investigations/{rid}','GET')(iid)
        return run_snapshot(iid) if iid.startswith('run-') else saved(iid)

    @app.post('/api/investigations/{iid}/cancel',response_model=RunSnapshot | dict)
    async def cancel_run(iid: str):
        if iid.startswith('research-'):return research_endpoint('/api/research/investigations/{rid}/cancel','POST')(iid)
        run_snapshot(iid)
        return await app.state.runs.cancel(iid)

    @app.get('/api/investigations/{iid}/events')
    async def events(iid: str,request: Request,after: int=Query(0,ge=0)):
        if iid.startswith('research-'):return await research_endpoint('/api/research/investigations/{rid}/events','GET')(iid,request,after)
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
        if iid.startswith('research-'):return research_endpoint('/api/research/investigations/{rid}/export','GET')(iid)
        inv=saved(iid)
        return Response(markdown_export(inv,repo().workspace()),media_type='text/markdown',headers={'Content-Disposition':f'attachment; filename="{inv.id}.md"'})
    from .research_api import router
    research_router=router(app,config)
    app.include_router(research_router)
    from .blood.api import router as blood_router
    app.include_router(blood_router(app))
    from .portfolio import router as portfolio_router
    app.include_router(portfolio_router(app,config))
    def research_endpoint(path,method):
        return next(route.endpoint for route in research_router.routes if route.path==path and method in getattr(route,'methods',set()))
    return app

app=create_app()
