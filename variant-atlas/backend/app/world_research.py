"""Public study corpus, exact mention extraction, structural backtracking and ingestion."""
import asyncio
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree as ET
import httpx
import numpy as np
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from pymongo.operations import SearchIndexModel
from .research_hub import now,words,ranked_chunks,EUROPE
from .languages import canonical

GENES=('PTEN','TP53','KRAS','NRAS','HRAS','EGFR','BRCA1','BRCA2','BRAF','PIK3CA','AKT1','APC','MLH1','ERBB2','RB1','ATM','ATR','PALB2','CHEK2','CDKN2A','CDH1','VHL','NF1','NF2','IDH1','IDH2','NOTCH1','MYC','TERT','BCL2','ALK','RET','ROS1','MET','KIT','JAK2','STAT3','CTNNB1','SMAD4','TET2','DNMT3A','NPM1','FLT3','ABO','RHD','HBB','INS','CFTR','HTT','APOE','DMD','MYH7','F8')
COUNTRIES={
 'China':{'aliases':['China','Chinese Academy','P.R. China'],'lat':35,'lon':104},'United States':{'aliases':['United States','USA','U.S.A.'],'lat':39,'lon':-98},'United Kingdom':{'aliases':['United Kingdom','UK','England','Scotland','Wales'],'lat':55,'lon':-3},'Russia':{'aliases':['Russia','Russian Federation','Российская Федерация','Россия'],'lat':60,'lon':100},'Japan':{'aliases':['Japan'],'lat':36,'lon':138},'Germany':{'aliases':['Germany','Deutschland'],'lat':51,'lon':10},'France':{'aliases':['France'],'lat':47,'lon':2},'India':{'aliases':['India'],'lat':22,'lon':79},'South Korea':{'aliases':['Republic of Korea','South Korea'],'lat':36,'lon':128},'Canada':{'aliases':['Canada'],'lat':56,'lon':-106},'Australia':{'aliases':['Australia'],'lat':-25,'lon':134},'Brazil':{'aliases':['Brazil','Brasil'],'lat':-14,'lon':-51},'Italy':{'aliases':['Italy','Italia'],'lat':42,'lon':12},'Spain':{'aliases':['Spain','España'],'lat':40,'lon':-4},'Netherlands':{'aliases':['Netherlands'],'lat':52,'lon':5},'Sweden':{'aliases':['Sweden'],'lat':62,'lon':15},'Switzerland':{'aliases':['Switzerland'],'lat':47,'lon':8},'Singapore':{'aliases':['Singapore'],'lat':1,'lon':104},'South Africa':{'aliases':['South Africa'],'lat':-30,'lon':25},'Israel':{'aliases':['Israel'],'lat':31,'lon':35},'Taiwan':{'aliases':['Taiwan'],'lat':24,'lon':121},'Finland':{'aliases':['Finland'],'lat':64,'lon':26},'Denmark':{'aliases':['Denmark'],'lat':56,'lon':10},'Norway':{'aliases':['Norway'],'lat':61,'lon':8},'Turkey':{'aliases':['Turkey','Türkiye'],'lat':39,'lon':35},'Iran':{'aliases':['Iran'],'lat':32,'lon':54},'Poland':{'aliases':['Poland'],'lat':52,'lon':19},'Belgium':{'aliases':['Belgium'],'lat':51,'lon':4},'Austria':{'aliases':['Austria'],'lat':48,'lon':14},'Mexico':{'aliases':['Mexico'],'lat':23,'lon':-102},'New Zealand':{'aliases':['New Zealand'],'lat':-41,'lon':174},'Saudi Arabia':{'aliases':['Saudi Arabia'],'lat':24,'lon':45},'Egypt':{'aliases':['Egypt'],'lat':27,'lon':30}}
TOPICS=['PTEN protein function','TP53 cancer mutations','KRAS cancer structure','BRCA1 DNA repair','EGFR targeted cancer','BRAF melanoma mutation','protein variant functional assays','ABO malaria rosetting','CFTR protein mutation','HBB sickle cell structure','DNA repair cancer genetics','single cell tumour immunity']
VECTOR_INDEX='bramha_passages_multilingual_v1'

def identity(prefix,text):return prefix+'-'+hashlib.sha256(text.encode()).hexdigest()[:24]
def text_of(node):return re.sub(r'\s+',' ',' '.join(node.itertext())).strip() if node is not None else ''
def plain(text):
    try:return text_of(ET.fromstring('<root>'+text+'</root>'))
    except ET.ParseError:return re.sub('<[^>]*>',' ',text)
def countries_of(affiliations):
    joined=' '.join(affiliations)
    return [name for name,c in COUNTRIES.items() if any(re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',joined,re.I) for alias in c['aliases'])]
def genes_of(text):
    result=[gene for gene in GENES if re.search(r'(?<![A-Za-z0-9_])'+gene+r'(?![A-Za-z0-9_])',text,re.I)]
    if re.search(r'\bp53\b',text,re.I) and 'TP53' not in result:result.append('TP53')
    return result

def article_row(raw,topic):
    affiliations=[]
    for author in raw.get('authorList',{}).get('author',[]):
        affiliations.extend(a['affiliation'] for a in author.get('authorAffiliationDetailsList',{}).get('authorAffiliation',[]) if a.get('affiliation'))
    title=raw.get('title','Untitled publication');abstract=plain(raw.get('abstractText',''))
    original=raw.get('source','MED')+':'+str(raw['id']);sid=identity('study',original)
    return {'id':sid,'external_key':original,'external_id':str(raw['id']),'provider':'Europe PMC','title':title,'authors':raw.get('authorString','Not supplied'),'doi':raw.get('doi'),'pmcid':raw.get('pmcid'),'year':raw.get('pubYear'),'languages':raw.get('language') if isinstance(raw.get('language'),list) else [raw.get('language','Not supplied')],'affiliations':list(dict.fromkeys(affiliations))[:20],'countries':countries_of(affiliations),'country_basis':'Publication affiliation text; not author nationality or participant location','genes':genes_of(title+' '+abstract),'abstract':abstract,'topics':[topic],'open_access':raw.get('isOpenAccess')=='Y','licence':raw.get('license') or 'Inspect original source for rights','url':'https://europepmc.org/article/'+raw.get('source','MED')+'/'+str(raw['id']),'coverage':'indexed abstract' if abstract else 'bibliographic metadata only','synthetic':False,'retrieved_at':now(),'publication_type':raw.get('pubTypeList',{}).get('pubType',[]),'cited_by_count':raw.get('citedByCount'),'version':hashlib.sha256((title+'\n'+abstract).encode()).hexdigest()}

def split_passages(study_id,version,sections):
    rows=[]
    for section in sections:
        text=section['text'];start=0
        while start<len(text):
            end=min(len(text),start+650)
            if end<len(text):
                boundary=text.rfind(' ',start+400,end)
                if boundary>start:end=boundary
            content=text[start:end].strip()
            if len(content)>20:
                pid=identity('passage',study_id+'@'+version+':'+str(len(rows)))
                rows.append({'id':pid,'study_id':study_id,'version':version,'section':section['section'],'text':content,'offset':start,'synthetic':False,'embedding_model':None})
            start=end
    return rows

def extract_mentions(passages):
    rows=[];seen=set()
    patterns=[('protein_variant',r'\bp\.(?:[A-Z][a-z]{2}|[A-Z])\d{1,5}(?:[A-Z][a-z]{2}|[A-Z*])\b'),('dna_variant',r'\bc\.\d+(?:[+-]\d+)?[ACGT]>[ACGT]\b'),('pdb_mention',r'(?i:\bPDB(?:\s+(?:ID|code|accession))?\s*[:=#(]?\s*)([1-9][A-Za-z0-9]{3})\b'),('uniprot_accession',r'\b(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9])\b'),('sequence_candidate',r'(?<![A-Z])[ACDEFGHIKLMNPQRSTVWY]{24,}(?![A-Z])')]
    for p in passages:
        for kind,pattern in patterns:
            for match in re.finditer(pattern,p['text']):
                value=match.group(1) if kind=='pdb_mention' else match.group()
                key=(kind,value,p['id'])
                if key in seen:continue
                seen.add(key);start=max(0,match.start()-100);end=min(len(p['text']),match.end()+120)
                rows.append({'id':identity('entity',':'.join(key)),'study_id':p['study_id'],'version':p['version'],'type':kind,'label':value,'passage_id':p['id'],'quote':p['text'][start:end],'status':'literal mention; biological identity and chain mapping require validation','synthetic':False})
        for gene in genes_of(p['text']):
            key=('gene',gene,p['id'])
            if key in seen:continue
            seen.add(key);rows.append({'id':identity('entity',':'.join(key)),'study_id':p['study_id'],'version':p['version'],'type':'gene','label':gene,'passage_id':p['id'],'quote':p['text'],'status':'name match; not evidence of a measured mutation','synthetic':False})
    return rows

class MultilingualEmbeddings:
    _model=None;_lock=None
    def __init__(self,settings):self.settings=settings
    def vectors(self,texts):
        if self.settings.corpus_embeddings!='local-multilingual':raise ValueError('Local multilingual embeddings are disabled.')
        import threading
        if MultilingualEmbeddings._lock is None:MultilingualEmbeddings._lock=threading.Lock()
        with MultilingualEmbeddings._lock:
            if MultilingualEmbeddings._model is None:
                from fastembed import TextEmbedding
                MultilingualEmbeddings._model=TextEmbedding(model_name=self.settings.corpus_embedding_model,cache_dir=str(self.settings.local_data_dir/'models'),threads=2)
            return [v.astype(float).tolist() for v in MultilingualEmbeddings._model.embed(texts,batch_size=32)]

class WorldResearch:
    def __init__(self,store,settings):self.store=store;self.settings=settings
    async def discover(self,query,limit=50,cursor='*'):
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.get(EUROPE+'/search',params={'query':query,'format':'json','resultType':'core','pageSize':min(limit,100),'cursorMark':cursor});r.raise_for_status();data=r.json()
        rows=[];new_passages=[]
        for raw in data.get('resultList',{}).get('result',[]):
            row=article_row(raw,query);old=self.store.get('studies',row['id'])
            if old:
                row={**old,'topics':list(dict.fromkeys(old.get('topics',[])+[query]))}
            rows.append(row)
            if not old:
                new_passages.extend(split_passages(row['id'],row['version'],[{'section':'abstract','text':row['abstract']}])[:20])
        self.store.put_many('studies',rows);self.store.put_many('passages',new_passages)
        return {'studies':rows,'hit_count':data.get('hitCount',0),'next_cursor':data.get('nextCursorMark'),'query':query,'provider':'Europe PMC'}
    async def acquire(self,sid):
        study=self.store.get('studies',sid)
        if not study:raise KeyError(sid)
        if study.get('text_asset'):return study
        sections=[{'section':'abstract','text':study['abstract']}];error=None;raw=None
        if study.get('open_access') and re.fullmatch(r'PMC\d+',study.get('pmcid') or ''):
            try:
                async with httpx.AsyncClient(timeout=30) as c:
                    async with c.stream('GET',EUROPE+'/'+study['pmcid']+'/fullTextXML') as r:
                        r.raise_for_status();pieces=[];size=0
                        async for b in r.aiter_bytes():
                            size+=len(b)
                            if size>4_000_000:raise ValueError('Open text exceeds the acquisition byte ceiling.')
                            pieces.append(b)
                raw=b''.join(pieces);root=ET.fromstring(raw);body=root.find('.//body')
                if body is not None:
                    for sec in body.findall('.//sec'):
                        title=text_of(sec.find('title')) or 'Body section'
                        paragraphs=[text_of(p) for p in sec.findall('p')]
                        if paragraphs:sections.append({'section':title,'text':'\n'.join(paragraphs)})
                    if len(sections)==1:
                        paragraphs=[text_of(p) for p in body.findall('.//p')]
                        if paragraphs:sections.append({'section':'body','text':'\n'.join(paragraphs)})
                if len(sections)>1:study['coverage']='open-access body text'
                licence=text_of(root.find('.//license'))
                if licence:study['licence']=licence[:1500]
            except (httpx.HTTPError,ET.ParseError,ValueError) as exc:error=type(exc).__name__
        extracted='\n\n'.join(s['section']+'\n'+s['text'] for s in sections)
        # The original XML and extraction are independently content-addressed.
        study['text_asset']=self.store.put_asset(extracted.encode(),'txt',{'study_id':sid,'coverage':study['coverage']})
        if raw:study['original_asset']=self.store.put_asset(raw,'xml',{'study_id':sid,'source_url':study['url']})
        version=hashlib.sha256(extracted.encode()).hexdigest();study.update(version=version,extraction_error=error,acquired_at=now(),sections=[{'section':s['section'],'characters':len(s['text'])} for s in sections],genes=list(dict.fromkeys(study.get('genes',[])+genes_of(extracted))))
        passages=split_passages(sid,version,sections)
        self.store.put_many('passages',passages)
        entities=extract_mentions(passages)
        self.store.put_many('entities',entities)
        study['passage_count']=len(passages);study['entity_count']=len(entities)
        return self.store.put('studies',sid,study)
    def passages(self,sid,limit=500):
        study=self.store.get('studies',sid)
        if not study:raise KeyError(sid)
        if self.store.db is not None:return list(self.store.collection('passages').find({'study_id':sid,'version':study['version']},{'_id':0,'embedding':0}).limit(limit))
        return [p for p in self.store.rows('passages',100000) if p['study_id']==sid and p['version']==study['version']][:limit]
    async def structures(self,sid,limit=2,refresh=False):
        study=self.store.get('studies',sid)
        if not study:raise KeyError(sid)
        existing=[s for s in self.store.rows('structures') if sid in s.get('study_ids',[])]
        if existing and not refresh:
            relations={r['structure_id']:r for r in self.store.rows('relations',20000) if r['study_id']==sid}
            return sorted([{**s,**{k:v for k,v in relations.get(s['id'],{}).items() if k in ('relationship','citation_matches','pdb_mentioned')}} for s in existing],key=lambda r:(not r.get('citation_matches'),r.get('relationship','').startswith('related')))[:limit]
        entities=[e for e in self.store.rows('entities',20000) if e['study_id']==sid and e['version']==study['version']]
        mentions=list(dict.fromkeys(e['label'].upper() for e in entities if e['type']=='pdb_mention'))[:4]
        async with httpx.AsyncClient(timeout=25) as c:
            ids=[]
            if not ids:
                citation_query={'attribute':'citation.pdbx_database_id_DOI','operator':'exact_match','value':study['doi']} if study.get('doi') else {'attribute':'citation.title','operator':'contains_phrase','value':plain(study['title'])}
                query={'query':{'type':'terminal','service':'text','parameters':citation_query},'return_type':'entry','request_options':{'paginate':{'start':0,'rows':limit}}}
                response=await c.post('https://search.rcsb.org/rcsbsearch/v2/query',json=query)
                if response.status_code==200:ids=[r['identifier'] for r in response.json().get('result_set',[])]
            if not ids:ids=list(mentions)
            related=False
            if not ids and study.get('genes'):
                query={'query':{'type':'terminal','service':'text','parameters':{'attribute':'rcsb_entity_source_organism.rcsb_gene_name.value','operator':'exact_match','value':study['genes'][0]}},'return_type':'entry','request_options':{'paginate':{'start':0,'rows':limit}}}
                response=await c.post('https://search.rcsb.org/rcsbsearch/v2/query',json=query)
                if response.status_code==200:ids=[r['identifier'] for r in response.json().get('result_set',[])];related=True
            acquired=[]
            for pdb in ids[:limit]:
                if not re.fullmatch(r'[1-9][A-Za-z0-9]{3}',pdb):continue
                try:
                    meta=await c.get('https://data.rcsb.org/rest/v1/core/entry/'+pdb);meta.raise_for_status();entry=meta.json()
                    primary=entry.get('rcsb_primary_citation',{});citation_matches=(str(primary.get('pdbx_database_id_PubMed'))==study['external_id'] or bool(study.get('doi') and str(primary.get('pdbx_database_id_DOI','')).casefold()==study['doi'].casefold()))
                    existing_asset=self.store.get('structures','pdb-'+pdb)
                    if existing_asset:
                        row={**existing_asset,'study_ids':list(dict.fromkeys(existing_asset.get('study_ids',[])+[sid]))}
                    else:
                        async with c.stream('GET','https://files.rcsb.org/download/'+pdb+'.cif') as r:
                            r.raise_for_status();pieces=[];size=0
                            async for b in r.aiter_bytes():
                                size+=len(b)
                                if size>8_000_000:raise ValueError('Structure exceeds the current visualization byte limit.')
                                pieces.append(b)
                        data=b''.join(pieces);cif=MMCIF2Dict(io.StringIO(data.decode()));atom_count=len(cif.get('_atom_site.id',[]))
                        if not 1<=atom_count<=150000:raise ValueError('Structure atom count is outside viewer limits.')
                        row={'id':'pdb-'+pdb,'pdb_id':pdb,'title':entry.get('struct',{}).get('title',pdb),'method':[m['method'] for m in entry.get('exptl',[])],'resolution':entry.get('rcsb_entry_info',{}).get('resolution_combined'),'atom_count':atom_count,'asset':self.store.put_asset(data,'cif',{'pdb_id':pdb,'provider':'RCSB PDB'}),'study_ids':[sid],'primary_citation':primary,'source_url':'https://www.rcsb.org/structure/'+pdb,'synthetic':False,'acquired_at':now()}
                    self.store.put('structures',row['id'],row)
                    relation={'study_id':sid,'structure_id':row['id'],'relationship':'publication-linked structure' if citation_matches else 'structure mentioned in source text' if pdb in mentions else 'related gene reference; not a structure generated by this study','citation_matches':citation_matches,'pdb_mentioned':pdb in mentions,'synthetic':False,'verified_at':now()}
                    self.store.put('relations',identity('relation',sid+':'+row['id']),relation)
                    acquired.append({**row,'relationship':relation['relationship'],'citation_matches':citation_matches})
                except (httpx.HTTPError,ValueError,KeyError):continue
        return acquired
    def embed_pending(self,limit=3000,study_ids=None):
        if self.settings.corpus_embeddings!='local-multilingual':return {'embedded':0,'reason':'Local embeddings disabled.'}
        if self.store.db is not None:
            query={'embedding_model':{'$ne':self.settings.corpus_embedding_model},'synthetic':False}
            if study_ids is not None:query['study_id']={'$in':study_ids}
            pending=list(self.store.collection('passages').find(query,{'_id':0}).limit(limit))
        else:pending=[p for p in self.store.rows('passages',100000) if p.get('embedding_model')!=self.settings.corpus_embedding_model and (study_ids is None or p['study_id'] in study_ids)][:limit]
        versions={s['id']:s['version'] for s in self.store.rows('studies',10000) if not s.get('synthetic')}
        pending=[p for p in pending if p['version']==versions.get(p['study_id'])]
        n=0
        for start in range(0,len(pending),32):
            batch=pending[start:start+32];vectors=MultilingualEmbeddings(self.settings).vectors([p['text'] for p in batch])
            embedded_batch=[]
            for p,vector in zip(batch,vectors):
                if len(vector)!=384 or not all(np.isfinite(vector)):raise ValueError('Embedding dimensions or finite-value validation failed.')
                embedded_batch.append({**p,'embedding':vector,'embedding_model':self.settings.corpus_embedding_model,'embedding_dimension':384});n+=1
            self.store.put_many('passages',embedded_batch)
        return {'embedded':n,'dimension':384,'model':self.settings.corpus_embedding_model,'execution':'Local pretrained model; no external text transmission or new training.'}
    def vector_indexes(self):
        if self.store.db is None:return {'ready':False,'reason':'Local corpus; Atlas vector index unavailable.'}
        c=self.store.collection('passages');existing=list(c.list_search_indexes())
        if not any(i['name']==VECTOR_INDEX for i in existing):
            c.create_search_index(SearchIndexModel(name=VECTOR_INDEX,type='vectorSearch',definition={'fields':[{'type':'vector','path':'embedding','numDimensions':384,'similarity':'cosine'},{'type':'filter','path':'synthetic'},{'type':'filter','path':'embedding_model'}]}))
            existing=list(c.list_search_indexes())
        index=next((i for i in existing if i['name']==VECTOR_INDEX),{})
        status={'ready':index.get('queryable') is True,'name':VECTOR_INDEX,'status':index.get('status','building'),'model':self.settings.corpus_embedding_model,'dimension':384}
        self.store.put('metadata','vector-status',status)
        return status
    def search(self,query='',country='',gene='',language='',mode='lexical',limit=30,native_only=False):
        studies=[s for s in self.store.rows('studies',10000) if not s.get('synthetic') and (not country or country in s.get('countries',[])) and (not gene or gene.upper() in s.get('genes',[])) and (not language or canonical(language) in [canonical(l) for l in s.get('languages',[])]) and (not native_only or (bool(s.get('native_text_languages')) and (not language or canonical(language) in s.get('native_text_languages',[]))))]
        allowed={s['id']:s for s in studies};method='Local lexical ranking over stored publication metadata';scores={};error=None
        if query.strip() and mode=='semantic':
            if self.settings.corpus_embeddings!='local-multilingual':error='Semantic embeddings are disabled; this response uses explicit lexical retrieval.'
            else:
                vector=MultilingualEmbeddings(self.settings).vectors([query])[0]
                if self.store.db is not None:
                    try:
                        results=list(self.store.collection('passages').aggregate([{'$vectorSearch':{'index':VECTOR_INDEX,'path':'embedding','queryVector':vector,'numCandidates':250,'limit':60,'filter':{'synthetic':False,'embedding_model':self.settings.corpus_embedding_model}}},{'$project':{'study_id':1,'version':1,'score':{'$meta':'vectorSearchScore'}}}],maxTimeMS=15000))
                        for p in results:
                            if p['study_id'] in allowed and p['version']==allowed[p['study_id']]['version']:scores[p['study_id']]=max(scores.get(p['study_id'],0),p['score'])
                        method='Atlas Vector Search · local multilingual embeddings'
                    except Exception:error='The Atlas vector index is not queryable yet; this response uses explicit lexical retrieval.'
                else:
                    for p in self.store.rows('passages',100000):
                        if p.get('embedding_model')!=self.settings.corpus_embedding_model or p['study_id'] not in allowed or p['version']!=allowed[p['study_id']]['version']:continue
                        raw=self.store.get('passages',p['id']);v=np.asarray(raw['embedding']);score=float(np.dot(vector,v)/(np.linalg.norm(vector)*np.linalg.norm(v) or 1))
                        scores[p['study_id']]=max(scores.get(p['study_id'],-1),score)
                    method='Local cosine similarity · multilingual embeddings'
        if query.strip() and (mode!='semantic' or error):
            docs=[{'id':s['id'],'title':s['title'],'text':s.get('abstract','')+' '+s.get('native_title','')+' '+' '.join(a['text'] for a in s.get('native_abstracts',[]))+' '+' '.join(s.get('genes',[]))+' '+' '.join(s.get('affiliations',[]))} for s in studies]
            scores={r['id']:r['retrieval_score'] for r in ranked_chunks(docs,query,len(docs))}
            # CJK text has no whitespace word boundaries. Preserve literal substring search
            # alongside lexical ranking, without labelling it semantic retrieval.
            for doc in docs:
                if query.strip().casefold() in (doc['title']+' '+doc['text']).casefold():scores[doc['id']]=scores.get(doc['id'],0)+1
        if query.strip():studies=[s for s in studies if s['id'] in scores];studies.sort(key=lambda s:scores[s['id']],reverse=True)
        else:studies.sort(key=lambda s:(s.get('year') or '',s.get('retrieved_at','')),reverse=True)
        return {'studies':[{**s,'retrieval_score':scores.get(s['id'])} for s in studies[:limit]],'total':len(studies),'method':method,'notice':error,'scope':'Public research corpus; synthetic templates excluded; relevance is not scientific support.'}
    def detail(self,sid):
        study=self.store.get('studies',sid)
        if not study:raise KeyError(sid)
        passages=self.passages(sid);entities=[e for e in self.store.rows('entities',50000) if e['study_id']==sid and e['version']==study['version']]
        relations=[r for r in self.store.rows('relations',10000) if r.get('study_id')==sid]
        structures=[]
        for r in relations:
            s=self.store.get('structures',r['structure_id'])
            if s:structures.append({**s,'relationship':r['relationship'],'citation_matches':r['citation_matches']})
        structures.sort(key=lambda r:(not r.get('citation_matches'),r.get('relationship','').startswith('related')))
        sections={'rationale':[],'methods':[],'outcomes':[],'limitations':[]}
        for p in passages:
            title=p['section'].casefold()
            kind='methods' if re.search('method|material|experiment',title) else 'outcomes' if re.search('result|finding',title) else 'limitations' if re.search('discussion|limitation|conclusion',title) else 'rationale'
            if len(sections[kind])<3:sections[kind].append(p)
        related=self.search(' '.join(study.get('genes',[])[:3]) or study['title'],limit=8)['studies']
        return {'study':study,'passages':passages,'entities':entities[:80],'structures':structures,'sections':sections,'related':[s for s in related if s['id']!=sid][:5],'reconstruction_scope':'Source-linked reconstruction of reported work, not an independent experimental reproduction. A reference model is not a predicted mutant fold.'}
    def seed_scenarios(self,count=240):
        contexts=['cancer cells','DNA repair','protein function','immune signalling','structural context','assay limitations']
        for i in range(count):
            gene=GENES[i%len(GENES)];context=contexts[(i//len(GENES))%len(contexts)]
            sid=identity('scenario',gene+':'+context)
            self.store.put('scenarios',sid,{'title':gene+' · '+context,'question':'What published evidence supports a role for '+gene+' in '+context+', and which experimental or structural limits remain?','genes':[gene],'context':context,'synthetic':True,'kind':'synthetic planning template','paths':['Inspect published methods','Compare reported findings','Locate referenced structures','Check limitations and conflicting evidence'],'scope':'A generated research question, not a real publication, measurement or supported mechanism.'})
        return self.store.count('scenarios')
    async def ingest(self,job_id):
        job=self.store.get('ingestion_jobs',job_id)
        if not job or job.get('status')=='completed':return
        def update(**kw):
            return self.store.mutate('ingestion_jobs',job_id,lambda d:{**d,**kw,'updated_at':now()})
        update(status='running')
        try:
            done=job.get('completed_topics',[])
            for topic in job['topics']:
                if self.store.get('ingestion_jobs',job_id).get('cancel_requested'):update(status='cancelled');return
                if topic in done:continue
                result=await self.discover(topic,job.get('per_topic',40))
                done.append(topic);update(completed_topics=done,studies=self.store.count('studies'),last_action='Indexed public studies for '+topic)
            corpus_studies=self.store.rows('studies',10000)
            acquired_ids=list(job.get('acquired_study_ids',[]))
            remaining=max(0,job.get('full_text_limit',48)-len(acquired_ids))
            candidates=[s for s in corpus_studies if s.get('open_access') and not s.get('text_asset')][:remaining]
            sem=asyncio.Semaphore(3)
            async def acquire(study):
                async with sem:
                    if self.store.get('ingestion_jobs',job_id).get('cancel_requested'):return
                    try:
                        await self.acquire(study['id']);acquired_ids.append(study['id'])
                    except (httpx.HTTPError,ValueError) as e:update(last_error=type(e).__name__)
                    update(acquired_study_ids=acquired_ids,full_texts=len(acquired_ids),last_action='Archived source text and extracted exact mentions')
            await asyncio.gather(*(acquire(s) for s in candidates))
            if self.store.get('ingestion_jobs',job_id).get('cancel_requested'):update(status='cancelled');return
            self.seed_scenarios(job.get('scenario_count',240))
            if job.get('embed',True):
                update(last_action='Generating local multilingual passage embeddings')
                embedded=await asyncio.to_thread(self.embed_pending,job.get('embedding_limit',3000));update(embedding_result=embedded)
                if self.store.db is not None:
                    try:update(vector_index=self.vector_indexes())
                    except Exception as e:update(vector_index={'ready':False,'reason':type(e).__name__})
            update(status='completed',last_action='Public research batch archived; synthetic templates remain separately labeled',counts=self.store.stats()['collections'])
        except Exception as exc:update(status='failed',error=type(exc).__name__+'; the checkpoint and already imported records are retained.')
