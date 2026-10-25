import asyncio,json
from pathlib import Path
from types import SimpleNamespace
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.corpus_store import CorpusStore
from app.languages import canonical,catalog
from app.multilingual_research import pubmed_abstracts,JstagePage,translate_public,TranslationRequest,numeric_tokens
from app.research_schemas import AgentAction
from test_observatory import setup,mock_http

XML='''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>20001</PMID><Article><VernacularTitle>原始题目</VernacularTitle></Article><OtherAbstract Type="Publisher" Language="chi"><AbstractText>BRCA1基因检测纳入77例患者，原始研究仍需独立验证。这里保留完整的原始摘要供研究者审阅。</AbstractText></OtherAbstract><OtherAbstract Type="plain-language-summary" Language="chi"><AbstractText>公众说明不应伪装为原始论文摘要。</AbstractText></OtherAbstract></MedlineCitation></PubmedArticle></PubmedArticleSet>'''

def test_native_parser_and_language_catalogue_preserve_original_labels():
    result=pubmed_abstracts(XML.encode())['20001'];assert result['native_title']=='原始题目' and len(result['abstracts'])==1
    assert result['abstracts'][0]['language']=='zh' and '77' in result['abstracts'][0]['text']
    assert canonical('chi')==canonical('Chinese')==canonical('中文')=='zh'
    assert len(catalog())>=70 and len({l['code'] for l in catalog()})==len(catalog())
    assert '77' in numeric_tokens('纳入77例，比例5.3%。')
    assert numeric_tokens('2020年４月至2022年12月')==numeric_tokens('2020-04 to 2022-12')
    assert numeric_tokens('2020年４月至2022年12月')==numeric_tokens('April 2020 to December 2022')
    assert numeric_tokens('This may change in December.')==set()
    assert numeric_tokens('−3.5 and 5.3%')!=numeric_tokens('3.5 and 5.3%')
    parser=JstagePage();parser.feed('<html><meta name="citation_title" content="遺伝子研究"><div id="article-overiew-abstract-wrap"><div class="section-title-18">抄録</div><div class="global-para-14"><p>BRCA2遺伝子について解析した。</p></div></div><div>Not part of abstract</div></html>')
    assert parser.abstract=='BRCA2遺伝子について解析した。' and parser.meta['citation_title']==['遺伝子研究']


def test_language_import_archives_native_text_and_real_library_source(tmp_path,monkeypatch):
    settings,_,_,_,_=setup(tmp_path)
    def handler(req):
        if '/search' in str(req.url):return httpx.Response(200,json={'hitCount':1,'resultList':{'result':[{'id':'20001','source':'MED','title':'BRCA1 genetics fixture','abstractText':'The indexed English abstract describes a genetics study.','language':['chi'],'authorString':'Publisher fixture authors'}]}})
        if 'efetch.fcgi' in str(req.url):return httpx.Response(200,content=XML.encode())
        raise AssertionError(req.url)
    mock_http(monkeypatch,handler)
    with TestClient(create_app(settings)) as client:
        first=client.post('/api/observatory/multilingual/import',json={'languages':['zh'],'per_language':1});assert first.status_code==200,first.text
        job=client.get('/api/observatory/ingestion/'+first.json()['id']).json();assert job['status']=='completed' and job['native_studies']==1
        result=client.get('/api/observatory/studies',params={'language':'chi','native_only':'true'}).json();assert result['total']==1
        study=result['studies'][0];assert study['native_text_languages']==['zh'] and study['library_source_id']
        detail=client.get('/api/observatory/studies/'+study['id']).json();native=[p for p in detail['passages'] if p.get('language')=='zh'];assert native and 'BRCA1' in native[0]['text'];assert all(p['version']==study['version'] for p in detail['passages'])
        paper=client.get('/api/research/papers/'+study['library_paper_id']).json();assert '77' in paper['chunks'][0]['text'] and paper['provenance']['languages']==['zh']
        before=len(list((tmp_path/'papers').glob('*.json')))
        again=client.post('/api/observatory/multilingual/import',json={'languages':['Chinese'],'per_language':1});assert again.status_code==200
        assert len(list((tmp_path/'papers').glob('*.json')))==before
        assert client.get('/api/observatory/studies',params={'q':'原始研究','language':'zh'}).json()['total']==1
        status=client.get('/api/observatory/status').json();assert next(l for l in status['language_catalog'] if l['code']=='zh')['native_text_studies']==1
        assert client.post('/api/observatory/multilingual/import',json={'languages':['not-a-language']}).status_code==422


@pytest.mark.parametrize('invalid',[None,'alignment','numbers','identifier'])
def test_translations_are_aligned_versioned_and_reject_lost_scientific_content(tmp_path,monkeypatch,invalid):
    from app.world_research import split_passages
    settings,store,_,study,_=setup(tmp_path)
    passages=split_passages(study['id'],study['version'],[{'section':'Chinese original','text':'BRCA1基因检测纳入77例患者，原始研究仍需独立验证。'}]);p={**passages[0],'language':'zh'};store.put('passages',p['id'],p)
    class Provider:
        def __init__(self,*a):self.on_attempt=None
        async def close(self):pass
        async def generate_action(self,prompt):
            data=json.loads(prompt);assert data['passages'][0]['text']==p['text'] and data['target_language']=='English' and 'project' not in data
            text='BRCA1 genetic testing included 77 participants; independent validation is still required.'
            if invalid=='numbers':text=text.replace('77','88')
            if invalid=='identifier':text=text.replace('BRCA1','a gene')
            return AgentAction(action='invoke_tool',tool='study_translation',summary='Scripted translation fixture',arguments={'passages':[{'passage_id':'invented' if invalid=='alignment' else p['id'],'text':text}],'limitations':['Fixture translation; semantic accuracy requires review.']}),{'provider':'fixture','model':'scripted'}
    monkeypatch.setattr('app.multilingual_research.ActionProvider',Provider)
    body=TranslationRequest(passage_ids=[p['id']],target_language='en',source_version=study['version'])
    if invalid:
        with pytest.raises(ValueError):asyncio.run(translate_public(store,settings,study['id'],body))
        saved=store.rows('searches');assert saved[0]['status']=='failed' and saved[0]['passages']==[]
    else:
        result=asyncio.run(translate_public(store,settings,study['id'],body));assert result['passages'][0]['original']==p['text'] and result['source_version']==study['version']
    with pytest.raises(ValueError,match='version changed'):asyncio.run(translate_public(store,settings,study['id'],body.model_copy(update={'source_version':'stale'})))


def test_japanese_import_uses_publisher_native_text_not_english_index(tmp_path,monkeypatch):
    settings,_,_,_,_=setup(tmp_path)
    atom='''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/"><entry><article_title><ja>BRCA2遺伝子研究・テスト用原文</ja></article_title><article_link><ja>https://www.jstage.jst.go.jp/article/fixture/1/1/1_1/_article/-char/ja/</ja></article_link><pubyear>2024</pubyear><prism:doi>10.0000/fixture.test</prism:doi></entry></feed>'''
    original='BRCA2遺伝子の検査について報告した。これはテストのための抄録であり、実際の研究結果ではない。'
    html='<html><meta name="citation_author" content="Fixture author"><meta name="citation_author_institution" content="東京・テスト機関"><div id="article-overiew-abstract-wrap"><div class="global-para-14"><p>'+original+'</p></div></div></html>'
    def handler(req):
        if req.url.host=='api.jstage.jst.go.jp':return httpx.Response(200,content=atom.encode())
        if req.url.host=='www.jstage.jst.go.jp':return httpx.Response(200,content=html.encode())
        raise AssertionError(req.url)
    mock_http(monkeypatch,handler)
    with TestClient(create_app(settings)) as client:
        response=client.post('/api/observatory/multilingual/import',json={'languages':['Japanese'],'per_language':1});assert response.status_code==200
        job=client.get('/api/observatory/ingestion/'+response.json()['id']).json();assert job['status']=='completed' and job['native_studies']==1
        rows=client.get('/api/observatory/studies',params={'language':'ja','native_only':True}).json()['studies'];assert len(rows)==1
        study=rows[0];assert study['provider']=='J-STAGE' and study['countries']==['Japan'] and study['library_source_id']
        detail=client.get('/api/observatory/studies/'+study['id']).json();assert detail['passages'][0]['text']==original and detail['passages'][0]['language']=='ja'
        assert detail['study']['available_text_languages']==['ja']
        source=client.get('/api/portfolio/sources/'+study['library_source_id']).json();assert source['url']==study['url'] and 'J-STAGE' in source['licence']


def test_native_indexing_is_scoped_to_imported_public_studies(tmp_path,monkeypatch):
    from app.multilingual_research import MultilingualResearch
    from app.world_research import WorldResearch
    settings,store,_,existing,_=setup(tmp_path)
    settings=__import__('dataclasses').replace(settings,corpus_embeddings='local-multilingual')
    native={**existing,'id':'study-native-embedding-fixture','abstract':'','version':'before-native'}
    service=MultilingualResearch(SimpleNamespace(),settings,store)
    native=service.archive(native,[{'section':'Publisher native fixture','text':'BRCA1基因研究的测试原文，仅供软件验证，并非真实实验的结果。','language':'zh','source_url':'https://example.org/native-fixture'}],b'<fixture/>','xml','https://example.org/native-fixture')
    seen=[]
    def vectors(self,texts):seen.extend(texts);return [[1.0]*384 for _ in texts]
    monkeypatch.setattr('app.world_research.MultilingualEmbeddings.vectors',vectors)
    result=WorldResearch(store,settings).embed_pending(1000,[native['id']]);assert result['embedded']==1 and seen[0].startswith('BRCA1基因')
    indexed=store.get('passages',WorldResearch(store,settings).passages(native['id'])[0]['id']);assert indexed['embedding_model']==settings.corpus_embedding_model
    assert all(p.get('embedding_model') is None for p in WorldResearch(store,settings).passages(existing['id']))
