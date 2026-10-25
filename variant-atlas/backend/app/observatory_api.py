import asyncio
from uuid import uuid4
from fastapi import APIRouter,HTTPException,BackgroundTasks,Query
from fastapi.responses import Response,StreamingResponse
from pydantic import Field
from .schemas import Model
from .world_research import WorldResearch,TOPICS,COUNTRIES
from .research_hub import now
from .languages import canonical,catalog,NLM_CODES
from .multilingual_research import MultilingualResearch,LanguageImport,TranslationRequest,translate_public
from .expeditions import ExpeditionStart,STOPPED
from .corpus_guide import CorpusQuestion,answer_public_question
from .study_actions import ProposalRequest,BranchRequest,propose,branch,saved_study_records

class PublicSearch(Model):
    query:str=Field(min_length=3,max_length=500)
    limit:int=Field(default=30,ge=1,le=100)
class StudyAttachment(Model):
    project_id:str|None=None
class CorpusBatch(Model):
    topics:list[str]=Field(default_factory=lambda:TOPICS,min_length=1,max_length=20)
    per_topic:int=Field(default=40,ge=1,le=100)
    full_text_limit:int=Field(default=24,ge=0,le=120)
    embedding_limit:int=Field(default=1500,ge=0,le=5000)
    embed:bool=True


def router(app,settings):
    r=APIRouter(prefix='/api/observatory')
    def store():
        if not getattr(app.state,'corpus_store',None):raise HTTPException(503,getattr(app.state,'corpus_error',None) or 'The research corpus is unavailable.')
        return app.state.corpus_store
    def world():return WorldResearch(store(),settings)
    @r.get('/status')
    def status():
        s=store();stats=s.stats();studies=s.rows('studies',10000);countries={};languages=set()
        for row in studies:
            if row.get('synthetic'):continue
            for name in row.get('countries',[]):countries[name]=countries.get(name,0)+1
            languages.update(row.get('languages',[]))
        language_counts={}
        for row in studies:
            if row.get('synthetic'):continue
            for code in {canonical(l) for l in row.get('languages',[])}:
                counts=language_counts.setdefault(code,{'publications':0,'native_text_studies':0});counts['publications']+=1;counts['native_text_studies']+=int(code in row.get('native_text_languages',[]))
        multilingual=[{**lang,**language_counts.get(lang['code'],{'publications':0,'native_text_studies':0})} for lang in catalog()]
        jobs=s.rows('ingestion_jobs',50);vector=s.get('metadata','vector-status') or {'ready':False,'status':'Not verified'}
        return {**stats,'language_catalog':multilingual,'native_text_studies':sum(bool(s.get('native_text_languages')) for s in studies if not s.get('synthetic')),'country_counts':[{'name':k,'count':n,**{x:COUNTRIES[k][x] for x in ['lat','lon']}} for k,n in sorted(countries.items(),key=lambda x:-x[1]) if k in COUNTRIES],'languages':sorted(languages),'full_text_studies':sum(x.get('coverage')=='open-access body text' for x in studies),'studies_with_abstracts':sum(bool(x.get('abstract')) for x in studies),'embedding_model':settings.corpus_embedding_model,'embeddings_enabled':settings.corpus_embeddings=='local-multilingual','vector_index':vector,'jobs':sorted(jobs,key=lambda j:j.get('created_at',''),reverse=True)[:5],'private_backup_status':s.get('metadata','approved-local-backup') or {'verified_backups':0,'scope':'No approved backup has been completed.'}}
    @r.get('/studies')
    def studies(q:str='',country:str='',gene:str='',language:str='',mode:str='lexical',limit:int=30,native_only:bool=False):
        if mode not in ('lexical','semantic'):raise HTTPException(422,'Choose lexical or semantic retrieval.')
        return world().search(q[:500],country[:100],gene[:40],language[:80],mode,max(1,min(limit,100)),native_only=native_only)
    @r.post('/discover')
    async def discover(body:PublicSearch):
        try:return await world().discover(body.query,body.limit)
        except Exception as exc:raise HTTPException(502,'Public literature discovery failed ('+type(exc).__name__+'). Stored research remains searchable.') from exc
    @r.get('/studies/{sid}')
    def detail(sid:str):
        try:return world().detail(sid)
        except KeyError as exc:raise HTTPException(404,'Study not found in the public corpus.') from exc
    @r.post('/studies/{sid}/reconstruct')
    async def reconstruct(sid:str):
        w=world()
        try:
            await w.acquire(sid);await w.structures(sid,refresh=True);return w.detail(sid)
        except KeyError as exc:raise HTTPException(404,'Study not found in the public corpus.') from exc
        except Exception as exc:raise HTTPException(502,'Source reconstruction failed ('+type(exc).__name__+'). Acquired records remain saved.') from exc
    @r.post('/studies/{sid}/attach')
    async def attach(sid:str,body:StudyAttachment):
        from .portfolio import Portfolio,ProjectCreate,SourceLink,source_id
        from .papers import PaperLibrary,PaperUpload
        import base64
        service=Portfolio(app,settings)
        try:
            if body.project_id:service.raw_project(body.project_id)
            study=await world().acquire(sid)
            text=store().read_asset(study['text_asset']).decode() if study.get('text_asset') else study.get('abstract','')
            if not text.strip():raise ValueError('No readable public source text is available for this study.')
            raw=(study['title']+'\n'+study['url']+'\nCoverage: '+study['coverage']+'\n\n'+text).encode()
            library=PaperLibrary(settings)
            paper=library.upload(PaperUpload(filename=(study['title'][:140].replace('/','-')+'.txt'),content_base64=base64.b64encode(raw).decode()))
            paper['provenance']={'provider':'Europe PMC public corpus','study_id':sid,'source_url':study['url'],'source_version':study['version'],'coverage':study['coverage'],'licence':study['licence']}
            library.write(library.root/(paper['id']+'.json'),paper)
            source=source_id('paper',paper['id']);service.migrate()
            project=service.raw_project(body.project_id) if body.project_id else service.create(ProjectCreate(title=study['title'][:140],objective='Review the methods, molecular evidence and outcomes of: '+study['title'][:1500],method='papers',source_ids=[source]))
            service.link(project['id'],SourceLink(source_id=source,action='link'))
            return {'project_id':project['id'],'source_id':source,'scope':'Source linked for review; scientific inclusion remains an explicit project decision.'}
        except KeyError as exc:raise HTTPException(404,'Study or project not found.') from exc
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    @r.get('/structures/{structure_id}/asset')
    def structure_asset(structure_id:str):
        s=store();row=s.get('structures',structure_id)
        if not row:raise HTTPException(404,'Archived structural reference not found.')
        return Response(s.read_asset(row['asset']),media_type='text/plain',headers={'Cache-Control':'public,max-age=31536000,immutable'})
    @r.get('/studies/{sid}/text')
    def study_text(sid:str):
        s=store();row=s.get('studies',sid)
        if not row or not row.get('text_asset'):raise HTTPException(404,'Full extraction has not been acquired.')
        return Response(s.read_asset(row['text_asset']),media_type='text/plain; charset=utf-8')
    @r.post('/ask')
    async def ask(body:CorpusQuestion):
        try:return await answer_public_question(store(),settings,body)
        except KeyError as exc:raise HTTPException(404,'Published study not found.') from exc
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        except Exception as exc:raise HTTPException(502,'Public evidence guide failed ('+type(exc).__name__+'). No unsupported answer was saved.') from exc
    @r.get('/studies/{sid}/proposals')
    def saved_proposals(sid:str):
        study=store().get('studies',sid)
        if not study or study.get('synthetic'):raise HTTPException(404,'Published study not found.')
        rows=saved_study_records(store(),sid,'study_proposals',study['version'],1)
        branches=saved_study_records(store(),sid,'study_branch')
        return {'report':max(rows,key=lambda r:r['at']) if rows else None,'branches':branches[:30]}
    @r.post('/studies/{sid}/proposals')
    async def proposals(sid:str,body:ProposalRequest):
        try:return await propose(store(),settings,sid,body)
        except KeyError as exc:raise HTTPException(404,'Published study not found.') from exc
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        except Exception as exc:raise HTTPException(502,'The follow-up adviser could not produce checked proposals ('+type(exc).__name__+'). No proposal was accepted.') from exc
    @r.post('/studies/{sid}/branches')
    async def study_branch(sid:str,body:BranchRequest):
        try:return await branch(app,settings,store(),sid,body)
        except KeyError as exc:raise HTTPException(404,'Published study, proposal or project not found.') from exc
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    @r.get('/studies/{sid}/answers')
    def saved_answers(sid:str):
        study=store().get('studies',sid)
        if not study or study.get('synthetic'):raise HTTPException(404,'Published study not found.')
        rows=saved_study_records(store(),sid,version=study['version'],limit=10)
        return {'answers':sorted(rows,key=lambda r:r['at'],reverse=True)[:10]}
    @r.get('/languages')
    def languages():return {'languages':catalog(),'scope':'Selectable translation targets; not a claim that every language has been evaluated with the configured model.'}
    @r.post('/multilingual/import')
    async def import_languages(body:LanguageImport,background:BackgroundTasks):
        body.languages=list(dict.fromkeys(canonical(l) for l in body.languages))
        if any(l not in NLM_CODES for l in body.languages):raise HTTPException(422,'Choose a supported public discovery language: '+', '.join(NLM_CODES))
        jid='multilingual-'+uuid4().hex
        doc=store().put('ingestion_jobs',jid,{'kind':'multilingual_import','revision':0,'status':'queued','created_at':now(),**body.model_dump(),'topics':body.languages,'completed_topics':[],'results':[],'last_action':'Queued public publisher abstracts; no model call requested.'})
        background.add_task(MultilingualResearch(app,settings,store()).ingest,jid,body)
        return doc
    @r.get('/studies/{sid}/translations')
    def translations(sid:str):
        row=store().get('studies',sid)
        if not row or row.get('synthetic'):raise HTTPException(404,'Published study not found.')
        return {'translations':saved_study_records(store(),sid,'study_translation',row['version'],30)}
    @r.post('/studies/{sid}/translate')
    async def translate(sid:str,body:TranslationRequest):
        try:return await translate_public(store(),settings,sid,body)
        except KeyError as exc:raise HTTPException(404,'Published study not found.') from exc
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        except Exception as exc:raise HTTPException(502,'Translation failed ('+type(exc).__name__+'). Original source text is preserved; no unchecked translation was accepted.') from exc
    @r.get('/scenarios')
    def scenarios(q:str=''):
        rows=store().rows('scenarios',1000)
        return {'scenarios':[s for s in rows if q.casefold() in (s['title']+' '+s['question']).casefold()][:100],'synthetic':True,'scope':'Planning templates, not published findings or experimental measurements.'}
    @r.post('/ingestion')
    async def ingest(body:CorpusBatch,background:BackgroundTasks):
        s=store();rid='ingestion-'+uuid4().hex
        s.put('ingestion_jobs',rid,{'id':rid,'revision':0,'status':'queued','created_at':now(),'completed_topics':[],**body.model_dump(),'full_texts':0,'scenario_count':240})
        background.add_task(WorldResearch(s,settings).ingest,rid)
        return s.get('ingestion_jobs',rid)
    @r.get('/ingestion/{rid}')
    def ingestion(rid:str):
        doc=store().get('ingestion_jobs',rid)
        if not doc:raise HTTPException(404,'Ingestion job not found.')
        return doc
    @r.post('/vector/verify')
    def vector():
        w=world()
        try:
            status=w.vector_indexes();w.store.put('metadata','vector-status',status);return status
        except Exception as exc:raise HTTPException(503,'Atlas vector index provisioning or verification failed ('+type(exc).__name__+').') from exc
    @r.get('/expeditions')
    def missions(project_id:str|None=None,q:str=Query(default='',max_length=500),unassigned:bool=False,offset:int=Query(default=0,ge=0),limit:int=Query(default=50,ge=1,le=100)):
        return store().expedition_page(project_id,q,unassigned,offset,limit)
    @r.post('/expeditions')
    async def start(body:ExpeditionStart):
        store()
        if body.project_id:
            from .portfolio import Portfolio
            try:Portfolio(app,settings).raw_project(body.project_id)
            except KeyError as exc:raise HTTPException(404,'Research project not found.') from exc
        for sid in body.study_ids:
            row=store().get('studies',sid)
            if not row or row.get('synthetic'):raise HTTPException(422,'Choose an existing published study from the public corpus.')
        if body.mode=='agentic' and not(settings.google_api_key or settings.openrouter_api_key):raise HTTPException(422,'Configure Argon/OpenRouter for agentic execution, or choose tools-only exploration.')
        return app.state.expedition_engine.start(body)
    @r.get('/expeditions/{rid}')
    def mission(rid:str):
        d=store().get('expeditions',rid)
        if not d:raise HTTPException(404,'Expedition not found.')
        return d
    @r.post('/expeditions/{rid}/cancel')
    def cancel(rid:str):
        s=store();d=s.get('expeditions',rid)
        if not d:raise HTTPException(404,'Expedition not found.')
        if d['status'] in STOPPED:return d
        app.state.expedition_engine.cancel(rid)
        return s.get('expeditions',rid)
    @r.get('/expeditions/{rid}/events')
    async def events(rid:str,after:int=0):
        s=store()
        if not s.get('expeditions',rid):raise HTTPException(404,'Expedition not found.')
        async def stream():
            cursor=after
            while True:
                d=s.get('expeditions',rid)
                for event in d['events']:
                    if event['sequence']>cursor:
                        cursor=event['sequence'];yield 'event: expedition\ndata: '+__import__('json').dumps(event)+'\n\n'
                if d['status'] in STOPPED:break
                await asyncio.sleep(.7)
        return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache'})
    return r
