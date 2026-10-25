"""User-selected biological scope: curated starters plus public ontology/protein search.

Recommendations are possible research objects, never inferred patient biology.
"""
import asyncio
import hashlib
import re
from urllib.parse import quote
import httpx
from fastapi import APIRouter,HTTPException
from pydantic import Field
from .schemas import Model
from .research_hub import ResearchHub,now,words

CATALOGUE=[]
def add(kind,label,tags,description,symbol=None):
    identity='bio-'+hashlib.sha256((kind+':'+label).encode()).hexdigest()[:20]
    source=('https://www.uniprot.org/uniprotkb?query='+quote('gene_exact:'+symbol+' AND organism_id:9606')) if symbol else 'https://www.ebi.ac.uk/ols4/search?q='+quote(label)
    CATALOGUE.append({'id':identity,'category':kind,'label':label,'symbol':symbol,'description':description,'tags':tags,'source_url':source,'source_type':'Curated starting point; inspect linked reference','visual_kind':'gene' if symbol else kind,'organism':'Human context; confirm source organism'})
for label in ['Heart','Muscle','Bone','Lung','Breast','Colon','Pancreas','Brain','Liver','Skin','Prostate','Blood','Kidney','Ovary']:
    add('organ',label,['cancer','tumor','tumour','mutation',label.lower()],'An anatomical context you may choose for literature discovery. A broad cancer title does not establish this organ as the study target.')
for label,tags in [('Cardiomyocyte',['heart','cardiac','cardiovascular']),('Skeletal muscle cell',['muscle','dystrophy']),('Pancreatic beta cell',['pancreas','diabetes','insulin']),('Epithelial cell',['cancer','tumor','carcinoma','epithelial','lung','breast','colon']),('T cell',['immune','immunity','cancer','t cell']),('Fibroblast',['stromal','fibrosis','cancer']),('Hepatocyte',['liver','hepatocyte']),('Neuron',['brain','neural','neuroscience']),('Blood cell',['blood','abo','rhd','malaria']),('Stem cell',['stem','development','cancer']),('Tumour cell population',['cancer','tumor','tumour','mutation'])]:
    add('cell',label,tags,'A cell context for comparing published observations. The preview is schematic; no cell sample or microscopy measurement is loaded.')
for symbol,name,tags in [('PTEN','PTEN',['pten','cancer','mutation','phosphatase']),('TP53','TP53 / p53',['tp53','p53','cancer','mutation','dna']),('KRAS','KRAS',['kras','cancer','mutation','lung','pancreas']),('EGFR','EGFR',['egfr','cancer','lung','receptor']),('BRCA1','BRCA1',['brca1','cancer','breast','dna','repair']),('BRCA2','BRCA2',['brca2','cancer','breast','dna','repair']),('BRAF','BRAF',['braf','cancer','skin','mutation']),('PIK3CA','PIK3CA',['pik3ca','cancer','mutation']),('AKT1','AKT1',['akt1','pten','cancer','pathway']),('APC','APC',['apc','colon','cancer']),('MLH1','MLH1',['mlh1','dna','repair','colon']),('ERBB2','ERBB2 / HER2',['erbb2','her2','breast','cancer']),('INS','INS / insulin',['ins','insulin','diabetes','pancreas']),('CFTR','CFTR',['cftr','cystic','fibrosis','lung']),('HBB','HBB / beta-globin',['hbb','hemoglobin','haemoglobin','sickle','blood','thalassemia']),('HTT','HTT',['htt','huntington','brain']),('APOE','APOE',['apoe','alzheimer','brain','lipid']),('DMD','DMD / dystrophin',['dmd','dystrophin','dystrophy','muscle']),('MYH7','MYH7',['myh7','heart','cardiac','cardiomyopathy'])]:
    add('gene',name,tags,'Candidate gene/protein target. Confirm the organism, exact variant and experimental evidence before interpreting its role.',symbol)
for label,tags in [('DNA double helix',['dna','mutation','genetic','genome','cancer','variant','gene']),('Chromatin / nucleosome',['chromatin','epigenetic','regulation','cancer']),('RNA transcript',['rna','expression','transcript','mutation']),('Protein structure',['protein','structure','mutation','cancer'])]:
    add('genetic',label,tags,'A molecular scale for organizing the question. This context object does not supply a measured sequence, genome or predicted structure.')

class PoolSearch(Model):
    query:str=Field(min_length=2,max_length=150)
    category:str=Field(default='gene',pattern=r'^(gene|organ|cell|structure)$')
class SelectObject(Model):
    object_id:str=Field(min_length=5,max_length=160)
    active:bool=True

def selected(h,pid):
    return [d['object'] for d in h.archive.list('scope') if d['project_id']==pid and d.get('active')]

def router(app,settings):
    r=APIRouter(prefix='/api/hub')
    def hub():return ResearchHub(app,settings)
    @r.get('/projects/{pid}/objects')
    def pool(pid:str,query:str='',category:str='all'):
        h=hub();p=h.portfolio.project(pid);title=p['title']+' '+p['objective'];terms=set(words(title));terms|={t[:-1] for t in terms if t.endswith('s')};q=query.strip().casefold()
        rows=[]
        for obj in CATALOGUE:
            if category!='all' and obj['category']!=category:continue
            if q and q not in (obj['label']+' '+' '.join(obj['tags'])).casefold():continue
            overlap=terms&set(obj['tags']);row=dict(obj,relevance=len(overlap),reason='Matches title terms: '+', '.join(sorted(overlap)) if overlap else 'Available in the research object pool; add only if relevant to your question.')
            rows.append(row)
        rows.sort(key=lambda row:(-row['relevance'],row['label']))
        return {'objects':rows,'selected':selected(h,pid),'title_terms':sorted(terms),'recommendation_method':'Transparent title-keyword matching, not a biological inference','scope_note':'Suggestions are possible research directions. No organ, cell type, genotype or disease mechanism has been inferred from this title.'}
    @r.post('/objects/search')
    async def search(body:PoolSearch):
        h=hub();results=[]
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                if body.category=='gene':
                    symbol=re.sub(r'[^A-Za-z0-9_-]',' ',body.query).strip()
                    if not symbol:raise HTTPException(422,'Enter a gene symbol or protein name.')
                    response=await client.get('https://rest.uniprot.org/uniprotkb/search',params={'query':'(organism_id:9606) AND ('+symbol+')','format':'json','size':8,'fields':'accession,gene_names,protein_name,organism_name,length'});response.raise_for_status()
                    for raw in response.json().get('results',[]):
                        accession=raw['primaryAccession'];gene=raw.get('genes',[{}])[0].get('geneName',{}).get('value',accession)
                        name=raw.get('proteinDescription',{}).get('recommendedName',{}).get('fullName',{}).get('value',gene)
                        results.append({'id':'uniprot-'+accession,'category':'gene','label':gene+' · '+name,'symbol':gene,'description':'Public UniProt protein reference · '+str(raw.get('sequence',{}).get('length','?'))+' amino acids. Verify experimental applicability.','source_url':'https://www.uniprot.org/uniprotkb/'+accession,'source_type':'Live UniProt record','accession':accession,'organism':raw.get('organism',{}).get('scientificName'),'visual_kind':'gene','tags':[gene]})
                elif body.category in ('organ','cell'):
                    ontology='uberon' if body.category=='organ' else 'cl'
                    response=await client.get('https://www.ebi.ac.uk/ols4/api/search',params={'q':body.query,'ontology':ontology,'type':'class','rows':8});response.raise_for_status()
                    for raw in response.json().get('response',{}).get('docs',[]):
                        identity='ontology-'+hashlib.sha256(raw['iri'].encode()).hexdigest()[:24]
                        results.append({'id':identity,'category':body.category,'label':raw.get('label',raw['iri']),'description':(raw.get('description') or ['Ontology term; review its definition before selecting.'])[0][:1200],'source_url':'https://www.ebi.ac.uk/ols4/ontologies/'+ontology+'/classes?iri='+quote(raw['iri'],safe=''),'source_type':'Live '+ontology.upper()+' ontology record','accession':raw.get('obo_id'),'visual_kind':body.category,'tags':[]})
                else:
                    query={'query':{'type':'group','logical_operator':'and','nodes':[{'type':'terminal','service':'full_text','parameters':{'value':body.query}},{'type':'terminal','service':'text','parameters':{'attribute':'rcsb_entity_source_organism.taxonomy_lineage.id','operator':'exact_match','value':'9606'}}]},'return_type':'entry','request_options':{'paginate':{'start':0,'rows':8}}}
                    response=await client.post('https://search.rcsb.org/rcsbsearch/v2/query',json=query)
                    if response.status_code==204:return {'objects':[],'provider':'RCSB PDB','query':body.query}
                    response.raise_for_status()
                    ids=[x['identifier'] for x in response.json().get('result_set',[])]
                    semaphore=asyncio.Semaphore(4)
                    async def describe(pdb):
                        if not re.fullmatch(r'[0-9][A-Za-z0-9]{3}',pdb):return None
                        async with semaphore:
                            meta=await client.get('https://data.rcsb.org/rest/v1/core/entry/'+pdb);meta.raise_for_status();data=meta.json()
                        return {'id':'pdb-'+pdb,'category':'structure','label':pdb+' · '+data.get('struct',{}).get('title',pdb),'pdb_id':pdb,'description':'Public structural model · '+', '.join(e.get('method','') for e in data.get('exptl',[]))+'. Includes a human-source entity; inspect other chains and constructs.','source_url':'https://www.rcsb.org/structure/'+pdb,'source_type':'Live RCSB PDB record','visual_kind':'structure','tags':[]}
                    results.extend(obj for obj in await asyncio.gather(*(describe(pdb) for pdb in ids)) if obj)

        except httpx.HTTPError as exc:raise HTTPException(502,'The public reference catalogue is unavailable. The local starting-point pool and saved objects are still available.') from exc
        for obj in results:h.archive.put('pool-object',obj['id'],{**obj,'retrieved_at':now()})
        return {'objects':results,'provider':{'gene':'UniProt','organ':'EMBL-EBI OLS / UBERON','cell':'EMBL-EBI OLS / Cell Ontology','structure':'RCSB PDB'}[body.category],'query':body.query}
    @r.post('/projects/{pid}/objects')
    def select(pid:str,body:SelectObject):
        h=hub();h.portfolio.raw_project(pid)
        obj=next((d for d in CATALOGUE if d['id']==body.object_id),None) or h.archive.get(body.object_id)
        if not obj or obj.get('category') not in ('organ','cell','gene','genetic','structure'):raise HTTPException(422,'Choose a known catalogue or public reference object.')
        identity='scope-'+hashlib.sha256((pid+':'+obj['id']).encode()).hexdigest()[:32]
        h.archive.put('scope',identity,{'project_id':pid,'object':obj,'active':body.active,'updated_at':now()})
        return {'selected':selected(h,pid)}
    return r
