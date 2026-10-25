"""Offline contract checks for discovery, scope, cited retrieval and real geometry math."""
import asyncio
import base64
import io
import json
from types import SimpleNamespace
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from app.main import create_app
from app.config import Settings
from app.science import ScientificData
from app.repositories.research import ResearchStore
from app.research_hub import HubArchive, ResearchHub, ranked_chunks
from app.structure_lab import align_template, atom_rows
from app.papers import PaperLibrary, PaperUpload
from app.paper_review import PaperReviewEngine, PaperReviewRequest
from app.research_schemas import AgentAction


def setup(tmp_path):
    settings=Settings(local_data_dir=tmp_path,worker_mode='external',openrouter_api_key='fixture',openrouter_model='fixture-model',max_run_seconds=600)
    ResearchStore(settings).seed(ScientificData().workspace())
    return settings,create_app(settings)


def transport(monkeypatch, handler):
    actual=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:actual(**{**kw,'transport':httpx.MockTransport(handler)}))


def project(c, method='papers', title='Mutation of cancer cells'):
    response=c.post('/api/portfolio/projects',json={'title':title,'objective':title+' research question','method':method,'area':'cancer'})
    assert response.status_code==200,response.text
    return response.json()['id']


def test_document_archive_unicode_persistence_and_bm25_scope(tmp_path):
    settings,_=setup(tmp_path);a=HubArchive(settings)
    a.put('thread',"x' OR 1=1 --",{'messages':['日本語の研究']})
    assert HubArchive(settings).get("x' OR 1=1 --")['messages']==['日本語の研究']
    assert a.get('missing') is None
    assert len(a.list('thread'))==1 and not a.list('other')
    docs=[{'title':'Cancer mutation','text':'PTEN activity assay'}, {'title':'Unrelated','text':'Weather observations'}]
    result=ranked_chunks(docs,'PTEN mutation')
    assert len(result)==1 and result[0]['title']=='Cancer mutation'
    assert not ranked_chunks(docs,'nonexistentword')


def test_scope_matches_title_without_automatically_selecting_biology(tmp_path):
    settings,app=setup(tmp_path)
    with TestClient(app) as c:
        pid=project(c);other=project(c,title='Separate question')
        path=f'/api/hub/projects/{pid}/objects'
        response=c.get(path);assert response.status_code==200,response.text
        data=response.json();assert data['selected']==[]
        assert {o['category'] for o in data['objects']}=={'organ','cell','gene','genetic'}
        assert 'not a biological inference' in data['recommendation_method']
        kras=next(o for o in data['objects'] if o.get('symbol')=='KRAS')
        assert kras['relevance']>0
        assert c.post(path,json={'object_id':kras['id']}).json()['selected'][0]['symbol']=='KRAS'
        assert c.get(f'/api/hub/projects/{other}/objects').json()['selected']==[]
        assert c.get(path).json()['selected'][0]['id']==kras['id']
        assert c.post(path,json={'object_id':'imaginary-protein'}).status_code==422
        assert c.post(path,json={'object_id':kras['id'],'active':False}).json()['selected']==[]


def test_discovery_import_preserves_provenance_and_unlocks_readable_evidence(tmp_path,monkeypatch):
    settings,app=setup(tmp_path);requests=[]
    def handler(request):
        requests.append(str(request.url))
        assert request.url.host=='www.ebi.ac.uk'
        return httpx.Response(200,json={'hitCount':1,'resultList':{'result':[{'id':'12345','source':'MED','title':'PTEN mutation experiment','authorString':'Example et al.','pubYear':'2025','abstractText':'<p>Measured PTEN activity was reduced in this study. Independent replication is required.</p>','isOpenAccess':'N','authorList':{'author':[{'authorAffiliationDetailsList':{'authorAffiliation':[{'affiliation':'Example Research Laboratory'}]}}]}}]}})
    transport(monkeypatch,handler)
    with TestClient(app) as c:
        pid=project(c)
        found=c.post('/api/hub/discover',json={'question':'Mutation of cancer cells','project_id':pid})
        assert found.status_code==200,found.text
        assert found.json()['model_called'] is False
        candidate=found.json()['results'][0]
        response=c.post('/api/hub/evidence',json={'candidate_id':candidate['id'],'project_id':pid})
        assert response.status_code==200,response.text
        row=response.json();sid=row['source']['id']
        assert row['included'] and row['coverage']=='abstract'
        source=c.get('/api/portfolio/sources/'+sid).json()
        assert source['preparation']=='ready'
        assert source['details']['provenance']['institutions']==['Example Research Laboratory']
        assert source['details']['provenance']['coverage']=='abstract'
        assert c.get(f'/api/hub/projects/{pid}/guide').json()['ready_to_review']
        assert c.get('/api/hub/archive').json()['institutions']==['Example Research Laboratory']
        # Import never accepts an arbitrary URL, and did not fetch non-open full text.
        assert c.post('/api/hub/evidence',json={'candidate_id':'https://attacker.invalid'}).status_code==422
        assert len(requests)==1


def test_public_gene_ontology_and_structure_catalogues_are_saved_and_selectable(tmp_path,monkeypatch):
    settings,app=setup(tmp_path)
    def handler(r):
        if r.url.host=='rest.uniprot.org':return httpx.Response(200,json={'results':[{'primaryAccession':'P04637','genes':[{'geneName':{'value':'TP53'}}],'proteinDescription':{'recommendedName':{'fullName':{'value':'Cellular tumor antigen p53'}}},'organism':{'scientificName':'Homo sapiens'},'sequence':{'length':393}}]})
        if r.url.host=='www.ebi.ac.uk':return httpx.Response(200,json={'response':{'docs':[{'iri':'http://purl.obolibrary.org/obo/UBERON_0002048','label':'lung','obo_id':'UBERON:0002048','description':['Respiratory organ.']}]}})
        if r.url.host=='search.rcsb.org':return httpx.Response(200,json={'result_set':[{'identifier':'1TUP'}]})
        if r.url.host=='data.rcsb.org':return httpx.Response(200,json={'struct':{'title':'P53 DNA complex'},'exptl':[{'method':'X-RAY DIFFRACTION'}]})
        raise AssertionError(str(r.url))
    transport(monkeypatch,handler)
    with TestClient(app) as c:
        pid=project(c)
        for kind,q,identity in [('gene','TP53','P04637'),('organ','lung','UBERON:0002048'),('structure','TP53','1TUP')]:
            response=c.post('/api/hub/objects/search',json={'query':q,'category':kind});assert response.status_code==200,response.text
            obj=response.json()['objects'][0]
            assert identity in json.dumps(obj)
            assert c.post(f'/api/hub/projects/{pid}/objects',json={'object_id':obj['id']}).status_code==200
        assert len(c.get(f'/api/hub/projects/{pid}/objects').json()['selected'])==3


def test_cited_guide_is_project_scoped_rejects_unverifiable_quotes_and_saves_history(tmp_path,monkeypatch):
    settings,app=setup(tmp_path);invalid=False;use_quote_id=False
    async def answer(self,prompt,**kwargs):
        payload=json.loads(prompt)
        assert payload['project']['objective'].startswith('Mutation')
        assert all('unrelated source' not in p['text'] for p in payload['passages'])
        p=payload['passages'][0]
        claim={'text':'The saved study reports a PTEN measurement.','citation_id':p['citation_id'],'quote':'invented quote' if invalid else p['text'][:50]}
        if use_quote_id:claim={'text':'The saved study reports a PTEN measurement.','quote_id':payload['quote_options'][0]['quote_id']}
        return AgentAction(action='invoke_tool',summary='Grounded fixture',tool='research_answer',arguments={'claims':[claim],'limitations':['Reported study, not a new experiment.'],'next_questions':[]}),{'provider':'fixture','model':'scripted'}
    monkeypatch.setattr('app.research_hub.ActionProvider.generate_action',answer)
    with TestClient(app) as c:
        pid=project(c);other=project(c,title='Unrelated question')
        for target,text in [(pid,'PTEN mutation activity was measured. Independent validation is required.'),(other,'PTEN unrelated source should be excluded from project retrieval.')]:
            source=c.post('/api/portfolio/sources/import',json={'filename':'study.txt','content_base64':base64.b64encode(text.encode()).decode()}).json()
            c.post(f'/api/portfolio/projects/{target}/sources',json={'source_id':source['id']})
        body={'question':'What PTEN activity is reported?','project_id':pid}
        response=c.post('/api/hub/assistant',json=body);assert response.status_code==200,response.text
        assert response.json()['citations'] and response.json()['retrieval']['count']==1
        assert len(c.get('/api/hub/assistant/history',params={'project_id':pid}).json()['messages'])==1
        invalid=True
        assert c.post('/api/hub/assistant',json=body).status_code==422
        assert len(c.get('/api/hub/assistant/history',params={'project_id':pid}).json()['messages'])==1
        use_quote_id=True
        exact=c.post('/api/hub/assistant',json=body)
        assert exact.status_code==200,exact.text
        assert exact.json()['claims'][0]['quote'] in 'PTEN mutation activity was measured. Independent validation is required.'


def test_kabsch_fit_has_no_reflection_and_geometry_preserves_reference(tmp_path,monkeypatch):
    settings,app=setup(tmp_path)
    template=np.array([[0.,0,0],[1.,0,0],[0,1.,0]])
    expected=np.array([[0.,1,0],[-1.,0,0],[0,0,1.]])
    ref=template@expected+[4.,2.,3.]
    rotation,center,origin,rmsd=align_template(template,ref)
    assert rmsd<1e-10 and np.linalg.det(rotation)==pytest.approx(1)
    assert np.allclose((template-center)@rotation+origin,ref)
    science=ScientificData();w=science.workspace();variant=science.variant('PTEN:p.C124S')
    atoms=atom_rows(MMCIF2Dict(io.StringIO(science.assets.read(w['structure_asset']).decode())))
    local=[a for a in atoms if a['label']==variant['mapping']['label_seq_id']]
    # Controlled template lets the test assert exact retained coordinates, not a guessed fold.
    rows=[a for a in local if a['name'] in ('N','CA','C','O','CB')]
    cif='data_SER\nloop_\n_chem_comp_atom.atom_id\n_chem_comp_atom.type_symbol\n'+''.join('_chem_comp_atom.pdbx_model_Cartn_'+axis+'_ideal\n' for axis in 'xyz')
    cif+='\n'.join(a['name']+' '+a['element']+' '+' '.join(str(x+3) for x in a['xyz']) for a in rows)+'\n'
    transport(monkeypatch,lambda r:httpx.Response(200,text=cif))
    with TestClient(app) as c:
        pid=project(c,method='pten')
        response=c.post(f'/api/hub/projects/{pid}/geometry',json={'reference_variant_id':'PTEN:p.C124S','target_amino_acid':'S'})
        assert response.status_code==200,response.text
        proposal=response.json();assert proposal['status']=='unrelaxed geometry proposal'
        assert proposal['known_measurements']['variant_id']=='PTEN:p.C124S'
        assert proposal['backbone_fit_rmsd_angstrom']<1e-5
        assert set(proposal['possible_dna_codons'])=={'TCT','TCC','TCA','TCG','AGT','AGC'}
        baseline=c.get('/api/hub/assets/'+proposal['id']+'/reference').text.splitlines()
        edited=c.get('/api/hub/assets/'+proposal['id']+'/proposal').text.splitlines()
        parse=lambda lines:{(int(l[22:26]),l[12:16].strip()):l[30:54] for l in lines if l.startswith('ATOM')}
        a,b=parse(baseline),parse(edited);seq=local[0]['seq']
        assert all(b[k]==xyz for k,xyz in a.items() if k[0]!=seq or k[1] in ('N','CA','C','O'))
        assert len(c.get(f'/api/hub/projects/{pid}/experiments').json()['geometries'])==1
        assert c.post(f'/api/hub/projects/{pid}/geometry',json={'reference_variant_id':'PTEN:p.C124S','target_amino_acid':'C'}).status_code==422
        other=project(c)
        assert c.post(f'/api/hub/projects/{other}/geometry',json={'reference_variant_id':'PTEN:p.C124S','target_amino_acid':'S'}).status_code==422


def test_parallel_review_records_actual_reviewers_and_quote_coverage(tmp_path,monkeypatch):
    settings,app=setup(tmp_path)
    async def answer(self,prompt,**kwargs):
        p=json.loads(prompt);await asyncio.sleep(.01)
        return AgentAction(action='invoke_tool',summary='Reading fixture',tool='paper_reading',arguments={'summary':'Source observation.','claims':[{'text':'Independent validation is required.','chunk_id':x['id'],'quote':x['text'][:35]} for x in p['chunks']],'limitations':['Fixture only.']}),{'provider':'fixture','model':'scripted'}
    monkeypatch.setattr('app.papers.ActionProvider.generate_action',answer)
    library=PaperLibrary(settings)
    papers=[library.upload(PaperUpload(filename=f'study-{i}.txt',content_base64=base64.b64encode(('PTEN mutation study '+str(i)+': independent validation is required.').encode()).decode())) for i in range(2)]
    engine=PaperReviewEngine(ResearchStore(settings),settings)
    body=PaperReviewRequest(question='Compare the reported limitations.',source_id='first',source_version=papers[0]['sha256'],chunk_ids=['p1-c1'],depth='standard',max_seconds=300)
    run=engine.start('project-fixture',{'origin_id':papers[0]['id']},body,additional_sources=[{'origin_id':papers[1]['id']}])
    asyncio.run(engine.execute(run['run_id']))
    saved=engine.store.get(run['run_id'])
    assert saved['status']=='completed_with_limitations'
    assert saved['comparison_summary']['studies']==2 and saved['comparison_summary']['reviewers']==2
    assert saved['budget']['model_requests']==2 and saved['budget']['tool_calls']==3
    assert all(t['status']=='completed' for t in saved['tasks'])
    assert len(saved['source_coverage'])==2 and all(s['covered_chunk_ids']==['p1-c1'] for s in saved['source_coverage'])


def test_archive_simultaneous_startup_reads_and_writes(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    settings,_=setup(tmp_path)
    def write(i):
        archive=HubArchive(settings)
        archive.put('concurrent','row-'+str(i),{'value':i})
        assert archive.get('row-'+str(i))['value']==i
    with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(write,range(40)))
    assert len(HubArchive(settings).list('concurrent'))==40
