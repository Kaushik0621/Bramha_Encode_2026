"""Public research export, privacy boundaries and explicit snapshot sharing."""
import io
import json
import zipfile
import hashlib
from fastapi.testclient import TestClient
from app.main import create_app
from app.science import ScientificData
from app.expedition_reports import projection_svg
from test_observatory import setup


def record(store,study,passages):
    data=ScientificData();workspace=data.workspace();raw=data.assets.read(workspace['structure_asset']);asset=store.put_asset(raw,'cif')
    structure={'id':'report-reference','pdb_id':'1D5R','title':'Experimental PTEN reference','asset':asset,'relationship':'related reference','source_url':'https://www.rcsb.org/structure/1D5R','method':['X-RAY DIFFRACTION']}
    store.put('structures',structure['id'],structure)
    result={'id':'report-run','created_at':'2026-10-25T09:00:00Z','updated_at':'2026-10-25T09:00:30Z','status':'completed_with_limitations','question':'PTEN cancer evidence <script>alert(1)</script>','summary':'Only reported evidence was compared.','mode':'tools-only','study_ids':[study['id']],'claims':[{'id':'claim-report','text':'PTEN source observation <img src=x onerror=alert(1)>','quote':passages[0]['text'],'study_id':study['id'],'passage_id':passages[0]['id'],'source_version':study['version'],'claim_type':'literal source extract','reviewer_status':'unreviewed'}],'structures':[structure],'tasks':[{'id':'reviewer','role':'Public reviewer','engine':'deterministic extraction','status':'completed','summary':'Retained original public source text.'}],'events':[],'directions':[],'limitations':['No biological experiment was run.'],'budget':{'model_requests':0,'max_model_requests':12,'tool_calls':2,'raw_provider_response':'PRIVATE_PROVIDER_MARKER'},'project_notes':'PRIVATE_NOTE_MARKER','prompts':'PRIVATE_PROMPT_MARKER'}
    store.put('expeditions',result['id'],result);return result,raw


def test_downloads_retain_citations_actual_coordinate_files_and_escape_html(tmp_path):
    settings,store,_,study,passages=setup(tmp_path);run,raw=record(store,study,passages)
    with TestClient(create_app(settings)) as client:
        report=client.get('/api/observatory/expeditions/report-run/report');assert report.status_code==200
        data=report.json();assert data['claims'][0]['quote']==passages[0]['text']
        serialized=json.dumps(data);assert all(secret not in serialized for secret in ['PRIVATE_PROVIDER_MARKER','PRIVATE_NOTE_MARKER','PRIVATE_PROMPT_MARKER'])
        assert data['figures'] and 'no mutation effect computed' in data['figures'][0]['svg']
        html=client.get('/api/observatory/expeditions/report-run/export/html');assert html.status_code==200
        assert '<script>alert(1)</script>' not in html.text and '&lt;script&gt;' in html.text
        assert '<img src=x onerror=alert(1)>' not in html.text
        assert 'Print / Save PDF' in html.text and 'Recorded research output counts' in html.text
        md=client.get('/api/observatory/expeditions/report-run/export/md');assert 'attachment;' in md.headers['content-disposition'];assert '## References' in md.text and '## Limitations' in md.text
        zipped=client.get('/api/observatory/expeditions/report-run/export/zip');assert zipped.status_code==200
        with zipfile.ZipFile(io.BytesIO(zipped.content)) as z:
            assert z.read('structures/1D5R.cif')==raw
            manifest=json.loads(z.read('manifest.json'));assert manifest['structures'][0]['sha256']==hashlib.sha256(raw).hexdigest()
            assert 'research-report.html' in z.namelist() and 'figures/execution-counts.svg' in z.namelist()
            assert 'figures/1D5R-reference-projection.svg' in z.namelist()
        projected=client.get('/api/observatory/structures/report-reference/projection.svg');assert projected.status_code==200 and 'First-model Cα' in projected.text
        assert client.get('/api/observatory/expeditions/report-run/export/unsupported').status_code==422


def test_sharing_is_opt_in_frozen_revocable_and_does_not_send_messages(tmp_path):
    settings,store,_,study,passages=setup(tmp_path);record(store,study,passages)
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/observatory/expeditions/report-run/sharing').json()['shares']==[]
        assert client.get('/api/observatory/shared/not-created').status_code==404
        assert client.post('/api/observatory/expeditions/report-run/share',json={'consent':False}).status_code==422
        shared=client.post('/api/observatory/expeditions/report-run/share',json={'consent':True});assert shared.status_code==200
        token=shared.json()['token'];assert len(token)>=32
        link='/api/observatory/shared/'+token;snapshot=client.get(link);assert snapshot.status_code==200
        assert 'no-store' in snapshot.headers['cache-control'] and 'noindex' in snapshot.headers['x-robots-tag']
        store.mutate('expeditions','report-run',lambda r:{**r,'question':'CHANGED_LATER'})
        assert 'CHANGED_LATER' not in client.get(link).text
        assert len(client.get('/api/observatory/expeditions/report-run/sharing').json()['shares'])==1
        assert client.post('/api/observatory/expeditions/wrong/share/'+token+'/revoke',json={}).status_code==404
        assert client.post('/api/observatory/expeditions/report-run/share/'+token+'/revoke',json={}).status_code==200
        assert client.get(link).status_code==404


def test_reports_preserve_failed_status_and_reject_an_unfinished_run(tmp_path):
    settings,store,_,study,passages=setup(tmp_path);run,_=record(store,study,passages)
    with TestClient(create_app(settings)) as client:
        store.put('expeditions',run['id'],{**run,'status':'failed','claims':[],'structures':[],'error':'A worker failed.'})
        report=client.get('/api/observatory/expeditions/report-run/report').json();assert report['status']=='failed' and report['claims']==[]
        assert 'No source-checked observations were retained' in client.get('/api/observatory/expeditions/report-run/export/md').text
        store.put('expeditions',run['id'],{**run,'status':'running'})
        assert client.get('/api/observatory/expeditions/report-run/report').status_code==409
        assert client.post('/api/observatory/expeditions/report-run/share',json={'consent':True}).status_code==409
