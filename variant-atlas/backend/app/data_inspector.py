"""Read-only, bounded inspection of the configured research corpus and storage layout."""
import json
import re
import sqlite3
from datetime import datetime,timezone
from pathlib import Path
from fastapi import APIRouter,HTTPException,Query
from pymongo.errors import PyMongoError
from .corpus_store import COLLECTIONS,CorpusUnavailable

DESCRIPTIONS={
 'studies':('Published studies','Bibliographic metadata, abstracts, source URLs, coverage and version identifiers.'),
 'passages':('Source passages & vectors','Original-language text chunks with study/version links and optional multilingual embeddings.'),
 'entities':('Molecular mentions','Literal genes, substitutions and structure identifiers extracted from source passages.'),
 'structures':('Structural references','Acquired PDB/mmCIF references, provenance and checksummed asset pointers.'),
 'relations':('Evidence relationships','Links between publications, passages and structural references.'),
 'measurements':('Measured variants','Imported public PTEN measurements; native assay values and missingness are retained.'),
 'expeditions':('Research expeditions','Saved public-research questions, worker outputs, handoffs and outcomes.'),
 'tasks':('Worker tasks','Individual expedition worker assignments and execution status.'),
 'events':('Execution events','Ordered expedition activity and output references.'),
 'searches':('Search, guidance & translations','Public retrieval history, molecular-focus worker checks and research handoffs, source-linked guidance, follow-up proposals and aligned translations with original source versions.'),
 'ingestion_jobs':('Data ingestion jobs','Progress, coverage and errors from public-data acquisition batches.'),
 'scenarios':('Synthetic planning templates','Explicitly synthetic research questions; these are not evidence or measurements.'),
 'metadata':('Corpus metadata','Recorded index verification, ingestion and approved-backup summaries.'),
 'workspace_snapshots':('Approved workspace backups','Pointers and checksums for the approved historical files. These are snapshots, not live synchronization.'),
 'assets':('Original files · GridFS','Checksummed source files, structures and approved backup bytes; file metadata is inspectable here.'),
}
SEARCH_FIELDS=('id','title','question','text','label','pdb_id','path','gene','study_id','expedition_id','status','version')
HIDDEN=re.compile(r'(api.?key|secret|password|authorization|credential|connection.?string|mongodb.?uri|access.?token)',re.I)

def safe(value,depth=0):
    if depth>8:return '[Nested content omitted]'
    if isinstance(value,dict):
        result={}
        for k,v in list(value.items())[:120]:
            if HIDDEN.search(str(k)):result[str(k)]='[Redacted]'
            elif k in ('embedding','content_base64','raw_bytes'):result[str(k)]={'omitted':True,'length':len(v) if hasattr(v,'__len__') else None}
            else:result[str(k)]=safe(v,depth+1)
        return result
    if isinstance(value,list):return [safe(v,depth+1) for v in value[:30]]+(['[Additional items omitted]'] if len(value)>30 else [])
    if isinstance(value,bytes):return '[Binary content omitted]'
    if isinstance(value,str):
        if re.search(r'(mongodb(?:\+srv)?://|sk-or-v1-|AIza[\w-]{20})',value):return '[Connection credential redacted]'
        return value[:12000]+('… [truncated]' if len(value)>12000 else '')
    if value is None or isinstance(value,(int,float,bool)):return value
    return value.isoformat() if hasattr(value,'isoformat') else str(value)

class DataInspector:
    def __init__(self,app,settings):self.app=app;self.settings=settings;self.store=getattr(app.state,'corpus_store',None)
    def available(self):
        if self.store is None:raise HTTPException(503,'The configured research corpus is unavailable. Local storage remains listed in the overview; no fallback database is used.')
        return self.store
    def inventory(self):
        s=self.settings;root=Path(s.local_data_dir);rows=[]
        for title,path,pattern,scope in [
          ('PTEN investigations','research','research-*.json','Authoritative saved runs, tool artifacts, results and agent messages'),
          ('Blood-group investigations','blood','research-*.json','Authoritative comparative evidence runs'),
          ('Paper archive','papers','*.json','Local paper metadata and original-language reading records'),
        ]:
            directory=root/path;files=list(directory.glob(pattern)) if directory.exists() else []
            rows.append({'title':title,'location':path+'/'+pattern,'documents':len(files),'bytes':sum(p.stat().st_size for p in files),'scope':scope,'mode':'local files'})
        metadata=root/'portfolio'/'metadata.json'
        if s.data_backend=='local':
            try:
                doc=json.loads(metadata.read_text()) if metadata.exists() else {};counts={'projects':len(doc.get('projects',{})),'notes':len(doc.get('notes',{})),'source_versions':len(doc.get('catalogue_versions',{}))}
                rows.append({'title':'Projects & notebook','location':'portfolio/metadata.json','documents':int(metadata.exists()),'bytes':metadata.stat().st_size if metadata.exists() else 0,'scope':'Project links, revisions and attributed notebook entries','mode':'local JSON','counts':counts})
            except (OSError,ValueError):rows.append({'title':'Projects & notebook','location':'portfolio/metadata.json','mode':'local JSON','status':'Could not inspect metadata'})
        archive=root/'research-hub.sqlite3'
        if archive.exists() and s.data_backend=='local':
            try:
                with sqlite3.connect(archive.as_uri()+'?mode=ro',uri=True) as c:counts=dict(c.execute('SELECT kind,count(*) FROM documents GROUP BY kind').fetchall())
                rows.append({'title':'Research & model archive','location':'research-hub.sqlite3','documents':sum(counts.values()),'bytes':archive.stat().st_size,'counts':counts,'scope':'Discovery, assistant records, supplied structures and comparisons','mode':'local SQLite'})
            except sqlite3.Error:rows.append({'title':'Research & model archive','location':'research-hub.sqlite3','mode':'local SQLite','status':'Could not inspect archive'})
        return rows
    def overview(self):
        s=self.settings;root=Path(s.local_data_dir);response={'checked_at':datetime.now(timezone.utc).isoformat(),'database':s.mongodb_database if s.corpus_backend=='atlas' else 'Local corpus','corpus_backend':s.corpus_backend,'project_backend':s.data_backend,'connected':False,'collections':[],'local':self.inventory(),'vector':{'model':s.corpus_embedding_model,'enabled':s.corpus_embeddings=='local-multilingual'},'backup':None,'notice':'This console only reads stored data. Opening it does not ingest, upload, migrate, embed or call a model.','local_root':str(root),'flows':[
          {'title':'Public evidence','steps':['Discover published studies','Save metadata & original files','Extract versioned passages','Link molecular mentions & structures'],'destination':'bramha_studies → bramha_passages / entities / relations / structures; binary files in bramha_assets GridFS' if s.corpus_backend=='atlas' else 'corpus/documents.sqlite3 and corpus/assets'},
          {'title':'Semantic retrieval','steps':['Read acquired passages','Generate embeddings locally','Store vector + model/version','Retrieve relevant original passages'],'destination':'bramha_passages.embedding + Atlas Vector Search' if s.corpus_backend=='atlas' else 'Local passage vectors + cosine retrieval'},
          {'title':'Research execution','steps':['Start reviewed question','Persist workers & events','Save artifacts and findings','Reopen historical result'],'destination':'Public expeditions use the corpus store. Project investigations use DATA_BACKEND='+s.data_backend+'.'},
          {'title':'Approved backups','steps':['Approved manifest','Checksum source bytes','Archive exact file snapshot','Read back and verify'],'destination':'bramha_workspace_snapshots points to GridFS bytes. Later local edits are not automatically synchronized.'},
        ]}
        if not self.store:response['error']='The configured corpus is unavailable; counts are not substituted with local data.';return response
        try:
            stats=self.store.stats();response['connected']=True
            for name in COLLECTIONS:response['collections'].append({'name':name,'physical_name':'bramha_'+name if self.store.db is not None else name,'title':DESCRIPTIONS[name][0],'description':DESCRIPTIONS[name][1],'count':stats['collections'][name]})
            response['collections'].append({'name':'assets','physical_name':'bramha_assets.files / bramha_assets.chunks' if self.store.db is not None else 'corpus/assets','title':DESCRIPTIONS['assets'][0],'description':DESCRIPTIONS['assets'][1],'count':stats['assets']})
            if self.store.db is not None:
                response['vector']['stored_passages']=self.store.collection('passages').count_documents({'embedding':{'$exists':True}})
                sizes=list(self.store.db['bramha_assets.files'].aggregate([{'$group':{'_id':None,'bytes':{'$sum':'$length'}}}]))
                response['asset_bytes']=sizes[0]['bytes'] if sizes else 0
            else:
                with self.store.connect() as c:response['vector']['stored_passages']=c.execute("SELECT count(*) FROM corpus WHERE collection='passages' AND json_type(body,'$.embedding')='array'").fetchone()[0]
            response['vector']['recorded_index_status']=safe(self.store.get('metadata','vector-status'))
            response['backup']=safe(self.store.get('metadata','approved-local-backup'))
            response['jobs']=[safe(d) for d in sorted(self.store.rows('ingestion_jobs',100),key=lambda d:d.get('created_at',''),reverse=True)[:6]]
        except (PyMongoError,CorpusUnavailable,OSError,sqlite3.Error):response['connected']=False;response['error']='The configured corpus could not be read. Retry after checking the connection.'
        return response
    def records(self,name,q,offset,limit,identity=None):
        if name not in DESCRIPTIONS:raise HTTPException(404,'Unknown inspectable collection.')
        store=self.available()
        if store.db is not None:
            collection=store.db['bramha_assets.files'] if name=='assets' else store.collection(name)
            match=({'_id' if name=='assets' else 'id':identity} if identity else {})
            if q:
                fields=('filename','sha256','metadata.path') if name=='assets' else SEARCH_FIELDS
                match['$or']=[{k:{'$regex':re.escape(q),'$options':'i'}} for k in fields]
            projection={'embedding':0} if name!='assets' else None
            total=collection.count_documents(match,maxTimeMS=8000)
            rows=list(collection.find(match,projection).sort('_id',1).skip(offset).limit(limit).max_time_ms(8000))
        elif name=='assets':
            rows=[{'id':p.stem,'key':str(p.relative_to(store.assets.root)),'length':p.stat().st_size} for p in sorted(store.assets.root.glob('*/*')) if p.is_file()]
            rows=[r for r in rows if (not identity or r['id']==identity) and (not q or q.casefold() in r['key'].casefold())];total=len(rows);rows=rows[offset:offset+limit]
        else:
            where='collection=?';args=[name]
            if identity:where+=" AND id=?";args.append(identity)
            if q:
                where+=' AND ('+' OR '.join("instr(lower(CAST(json_extract(body,'$."+k+"') AS TEXT)),lower(?))>0" for k in SEARCH_FIELDS)+')';args.extend([q]*len(SEARCH_FIELDS))
            with store.connect() as c:
                total=c.execute('SELECT count(*) FROM corpus WHERE '+where,args).fetchone()[0]
                rows=[json.loads(r[0]) for r in c.execute('SELECT body FROM corpus WHERE '+where+' ORDER BY id LIMIT ? OFFSET ?',args+[limit,offset]).fetchall()]
        return {'collection':name,'backend':self.settings.corpus_backend,'total':total,'offset':offset,'limit':limit,'records':[safe({**r,'id':str(r.get('id',r.get('_id','')))}) for r in rows],'scope':'Read-only record preview. Binary bytes, vector arrays and credentials are omitted; long fields and lists may be truncated.'}

def router(app,settings):
    r=APIRouter(prefix='/api/data')
    @r.get('/overview')
    def overview():return DataInspector(app,settings).overview()
    @r.get('/collections/{name}')
    def records(name:str,q:str=Query('',max_length=160),offset:int=Query(0,ge=0,le=10000),limit:int=Query(20,ge=1,le=50),id:str|None=Query(None,max_length=500)):
        try:return DataInspector(app,settings).records(name,q,offset,limit,id)
        except (PyMongoError,CorpusUnavailable,OSError,sqlite3.Error):raise HTTPException(503,'Stored records could not be read; no fallback is used.') from None
    return r
