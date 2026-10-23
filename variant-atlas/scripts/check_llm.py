"""Check the configured OpenRouter model without printing secrets or provider bodies.

--explain additionally makes one bounded explanation workflow call (at most one repair).
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import httpx
from app.config import Settings
from app.fixtures import load_fixture
from app.analysis import filter_variants
from app.schemas import Criteria, DEFAULT_RESEARCH_QUESTION
from app.llm import explanation_payload, ExplanationError
from app.llm.openrouter import OpenRouterExplainer

async def check(explain: bool):
    settings=Settings.from_env()
    if not settings.openrouter_api_key or not settings.openrouter_model:
        print(json.dumps({'configured':False,'error':'Set the backend key and model in backend/.env.'}))
        return 1
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response=await client.get(settings.openrouter_base_url+'/models',headers={'Authorization':f'Bearer {settings.openrouter_api_key}'})
        if response.status_code!=200:
            print(json.dumps({'configured':True,'catalog_http_status':response.status_code,'model':settings.openrouter_model}))
            return 1
        catalog=response.json().get('data',[])
        model=next((m for m in catalog if m.get('id')==settings.openrouter_model),None)
        print(json.dumps({'configured':True,'model':settings.openrouter_model,'catalog_listed':model is not None}))
        if not model:
            print('Configured model is not listed; no model was substituted and no generation was requested.')
            return 1
        if explain:
            workspace=load_fixture()
            result=filter_variants(workspace,Criteria())
            payload=explanation_payload(workspace,result,result.matching_ids)
            payload.update(research_question=DEFAULT_RESEARCH_QUESTION,candidate_budget=10)
            narrative=await OpenRouterExplainer(settings).explain(payload)
            print(json.dumps({'explanation_status':'validated','model':settings.openrouter_model,
                'selected_count':len(result.matching_ids),'finding_count':len(narrative.findings),
                'hypothesis_count':len(narrative.hypotheses)}))
        return 0
    except ExplanationError as exc:
        print(json.dumps({'explanation_status':'failed','error':str(exc)}))
        return 1
    except (httpx.HTTPError,ValueError,KeyError):
        print(json.dumps({'error':'Model check failed: connection or invalid catalog response. No provider body was logged.'}))
        return 1

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--explain',action='store_true',help='Make a bounded live call using synthetic fixture records.')
    args=parser.parse_args()
    raise SystemExit(asyncio.run(check(args.explain)))
