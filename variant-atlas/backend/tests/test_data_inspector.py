import json
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings


def test_read_only_collection_browser_pagination_search_redaction_and_inventory(tmp_path):
    settings=Settings(local_data_dir=tmp_path,worker_mode='external')
    with TestClient(create_app(settings)) as client:
        store=client.app.state.corpus_store
        for n in range(24):store.put('studies',f'study-{n:02}',{'title':'蛋白质 PTEN '+str(n),'version':'source-v1','synthetic':False})
        store.put('metadata','private-config-fixture',{'api_key':'fixture-hidden','nested':{'password':'secret','uri':'mongodb+srv://user:password@private.example'},'embedding':[1.,2.], 'long_text':'x'*13000})
        asset=store.put_asset(b'public original bytes','txt')
        before={n:store.count(n) for n in ['studies','metadata','searches']}
        response=client.get('/api/data/overview');assert response.status_code==200,response.text
        overview=response.json();assert overview['connected'] and overview['corpus_backend']=='local'
        assert next(c['count'] for c in overview['collections'] if c['name']=='studies')==24
        assert any(r['title']=='Projects & notebook' for r in overview['local'])
        assert 'mongodb_uri' not in overview and 'password' not in response.text
        first=client.get('/api/data/collections/studies?limit=20&q=PTEN').json();second=client.get('/api/data/collections/studies?offset=20&q=PTEN').json()
        assert first['total']==24 and len(first['records'])==20 and len(second['records'])==4
        assert not {r['id'] for r in first['records']} & {r['id'] for r in second['records']}
        assert client.get('/api/data/collections/studies',params={'q':'蛋白质'}).json()['total']==24
        assert client.get('/api/data/collections/studies',params={'q':'.*'}).json()['total']==0
        assert client.get('/api/data/collections/studies?id=study-04').json()['records'][0]['title']=='蛋白质 PTEN 4'
        doc=client.get('/api/data/collections/metadata?id=private-config-fixture').json()['records'][0]
        assert doc['api_key']=='[Redacted]' and doc['nested']['password']=='[Redacted]'
        assert doc['nested']['uri']=='[Connection credential redacted]' and doc['embedding']=={'omitted':True,'length':2}
        assert len(doc['long_text'])<13100
        files=client.get('/api/data/collections/assets').json();assert files['records'][0]['length']==21
        assert store.read_asset(asset)==b'public original bytes'
        assert client.get('/api/data/collections/not-a-collection').status_code==404
        assert client.get('/api/data/collections/studies?limit=999').status_code==422
        assert client.get('/api/data/collections/studies?offset=-1').status_code==422
        assert client.post('/api/data/collections/studies',json={}).status_code==405
        assert {n:store.count(n) for n in before}==before


def test_corpus_outage_keeps_local_inventory_visible(tmp_path):
    with TestClient(create_app(Settings(local_data_dir=tmp_path,worker_mode='external'))) as client:
        client.app.state.corpus_store=None
        data=client.get('/api/data/overview').json()
        assert not data['connected'] and data['collections']==[] and data['local']
        assert client.get('/api/data/collections/studies').status_code==503
