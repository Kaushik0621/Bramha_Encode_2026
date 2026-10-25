import base64,copy,json
from uuid import uuid4
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.portfolio import digest
from app.repositories.research import ResearchStore
from app.science import ScientificData


def test_source_visuals_derive_actual_coverage_and_scope_work_to_exact_version(tmp_path):
    settings=Settings(local_data_dir=tmp_path,worker_mode='external');ResearchStore(settings).seed(ScientificData().workspace())
    with TestClient(create_app(settings)) as c:
        sources=c.get('/api/portfolio/sources').json();source=next(s for s in sources if s['type']=='sequence')
        p=c.post('/api/portfolio/projects',json={'title':'Visual source reference','objective':'Inspect reference sequence, missing measurements and saved output changes.','method':'pten','source_ids':[s['id'] for s in sources if s['method']=='pten']}).json()
        w=c.get('/api/workspaces/pten-real').json();criteria={k:w['defaults'][k] for k in ['scenario','activity_cutoff','abundance_cutoff','mapping']}
        body={'confirmed':True,'question':p['objective'],'selected_ids':['PTEN:p.C124S','PTEN:p.R172H','PTEN:p.Y16T'],'criteria':criteria}
        a=c.post('/api/analysis/projects/'+p['id']+'/run',json=body).json()
        b=c.post('/api/analysis/projects/'+p['id']+'/run',json={**body,'criteria':{**criteria,'activity_cutoff':10},'baseline_run_id':a['run_id']}).json()
        frozen=c.get('/api/research/investigations/'+a['run_id']).content
        old=copy.deepcopy(a);old['run_id']='research-'+uuid4().hex;old['id']=old['run_id'];old['data_mode']='synthetic';old['source_manifest'][0]['release']='version-scope fixture';old_version=digest(old['source_manifest'][0]);c.app.state.research_store.create(old)
        response=c.get('/api/source-visuals/'+source['id']);assert response.status_code==200,response.text
        data=response.json();m=data['molecular'];assert data['default_run_id']==b['run_id']
        assert len(m['positions'])==403 and m['protein']['sequence']==w['protein']['sequence']
        assert m['coverage']=={'outside_structure_coverage':81,'mapped':307,'missing_coordinates':15}
        assert m['positions'][123]['auth_seq_id']==124 and isinstance(m['positions'][123]['auth_seq_id'],int)
        assert m['unresolved_construct_positions']==2 and m['measurements']['loaded_profiles']==131
        assert data['total_exact_runs']==2 and data['other_version_runs']==1
        assert all(r['source_version']==source['version'] for r in data['runs'])
        assert next(v for v in m['variants'] if v['id']=='PTEN:p.R172H')['abundance'] is None
        assert any(check['status']=='not_measured' for check in data['checks'])
        historical=c.get('/api/source-visuals/'+source['id'],params={'version':old_version}).json()
        assert historical['molecular'] is None and historical['total_exact_runs']==1
        assert c.get('/api/source-visuals/'+source['id'],params={'version':'unknown-version'}).status_code==404
        assert c.get('/api/source-visuals/'+source['id'],params={'project':p['id']}).json()['total_exact_runs']==2
        assert c.get('/api/research/investigations/'+a['run_id']).content==frozen


def test_document_source_visuals_use_original_extraction_without_invented_molecule(tmp_path):
    with TestClient(create_app(Settings(local_data_dir=tmp_path,worker_mode='external'))) as c:
        original='原文の研究結果。PTEN evidence requires independent verification.'
        source=c.post('/api/portfolio/sources/import',json={'filename':'source-visual.txt','content_base64':base64.b64encode(original.encode()).decode()}).json()
        d=c.get('/api/source-visuals/'+source['id']).json()
        assert d['molecular'] is None and d['runs']==[] and d['default_run_id'] is None
        assert original in d['document']['chunks'][0]['text'] and d['document']['total_chunks']==1
        assert c.get('/api/source-visuals/unknown-source').status_code==404
