"""Resumable public corpus ingestion. Private backups use the separately approved manifest tool."""
import argparse,asyncio,json,sys
from dataclasses import replace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.config import Settings
from app.corpus_store import CorpusStore
from app.world_research import WorldResearch,TOPICS,now
from app.science import ScientificData
from pymongo import UpdateOne
import duckdb
p=argparse.ArgumentParser();p.add_argument('--studies-per-topic',type=int,default=40);p.add_argument('--full-texts',type=int,default=48);p.add_argument('--embedding-limit',type=int,default=3000);p.add_argument('--skip-embeddings',action='store_true');p.add_argument('--reference-studies',type=int,default=8);p.add_argument('--output',type=Path)
a=p.parse_args();s=replace(Settings.from_env(),corpus_backend='atlas',corpus_embeddings='disabled' if a.skip_embeddings else 'local-multilingual');store=CorpusStore(s)
try:
    science=ScientificData(s.asset_root);w=science.workspace();path=science.assets.resolve(w['parquet']['key'])
    with duckdb.connect() as c:
        cursor=c.execute('select * from read_parquet(?)',[str(path)]);columns=[d[0] for d in cursor.description]
        rows=[dict(zip(columns,r)) for r in cursor.fetchall()]
    for start in range(0,len(rows),500):
        docs=[]
        for row in rows[start:start+500]:
            for k in ['activity','abundance','activity_se','abundance_se']:
                v=row.get(k)
                if isinstance(v,float) and not __import__('math').isfinite(v):row[k]=None
            docs.append(UpdateOne({'id':row['id']},{'$setOnInsert':{**row,'dataset_version':w['dataset_version'],'source':'Pinned PTEN MaveDB snapshot','synthetic':False}},upsert=True))
        store.collection('measurements').bulk_write(docs,ordered=False)
    print('Archived real PTEN measurement records:',len(rows),flush=True)
    job_id='ingestion-public-initial-v1';job=store.get('ingestion_jobs',job_id)
    if not job:store.put('ingestion_jobs',job_id,{'status':'queued','revision':0,'created_at':now(),'topics':TOPICS,'per_topic':min(100,a.studies_per_topic),'full_text_limit':a.full_texts,'scenario_count':240,'embed':not a.skip_embeddings,'embedding_limit':a.embedding_limit,'completed_topics':[]})
    world=WorldResearch(store,s);asyncio.run(world.ingest(job_id))
    async def reference_publications():
        import httpx
        results=[]
        async with httpx.AsyncClient(timeout=30) as client:
            for pdb in ['1D5R','4HHB','1TUP','1M17','1BNA','2ITY','3OG7','5P21'][:max(0,min(8,a.reference_studies))]:
                try:
                    response=await client.get('https://data.rcsb.org/rest/v1/core/entry/'+pdb);response.raise_for_status()
                    pmid=response.json().get('rcsb_primary_citation',{}).get('pdbx_database_id_PubMed')
                    if not pmid:continue
                    found=await world.discover('EXT_ID:'+str(pmid)+' AND SRC:MED',1)
                    if not found['studies']:continue
                    study=found['studies'][0];await world.acquire(study['id']);models=await world.structures(study['id'],2)
                    results.append({'study_id':study['id'],'structures':[{'id':m['id'],'relationship':m['relationship']} for m in models]})
                except Exception as exc:results.append({'reference':pdb,'error':type(exc).__name__})
        return results
    references=asyncio.run(reference_publications())
    report={'reference_publications':references,'job':store.get('ingestion_jobs',job_id),'stats':store.stats()}
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str))
    print(json.dumps({'status':report['job']['status'],'counts':report['stats']['collections'],'vector_index':report['job'].get('vector_index'),'error':report['job'].get('error')},indent=2),flush=True)
finally:store.close()
