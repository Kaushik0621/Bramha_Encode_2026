import re
from typing import Protocol
from ..schemas import Narrative, Workspace, Analysis

class ExplanationError(Exception): pass

class ResearchExplainer(Protocol):
    async def explain(self, payload: dict) -> Narrative: ...

def explanation_payload(workspace: Workspace, analysis: Analysis, selected_ids: list[str]) -> dict:
    sources={sid for v in workspace.variants if v.id in selected_ids for sid in v.evidence_ids}
    return dict(selected_ids=selected_ids,criteria=analysis.criteria.model_dump(),
        records=[r.model_dump() for r in analysis.results if r.variant_id in selected_ids],
        evidence=[e.model_dump() for e in workspace.evidence if e.id in sources],
        schema=Narrative.model_json_schema(),
        limitations=['Synthetic measurements and illustrative geometry', 'No clinical or mechanistic conclusions are established'])

def validate_narrative(narrative: Narrative, payload: dict) -> Narrative:
    selected=set(payload['selected_ids'])
    evidence={e['id']: e for e in payload['evidence']}
    # Claims are extractive in this milestone: a finding must quote an actual supplied
    # fictional record. Numeric results are rendered separately from deterministic tools.
    for f in narrative.findings:
        if not set(f.variant_ids)<=selected or not set(f.evidence_ids)<=evidence.keys():
            raise ExplanationError('Explanation contains an unknown or out-of-scope reference.')
        if not any(f.text==evidence[s]['text'] for s in f.evidence_ids):
            raise ExplanationError('Finding is not an exact supported source claim.')
        for vid in f.variant_ids:
            if not any(vid in evidence[s]['variant_ids'] for s in f.evidence_ids):
                raise ExplanationError('Finding source is not linked to its variant.')
    narrative_text=[narrative.summary,*narrative.follow_up_questions,*narrative.limitations,*[h.text for h in narrative.hypotheses]]
    allowed_references=selected | evidence.keys()
    for text in narrative_text:
        for ref in re.findall(r'demo-(?:v\d+|evidence-\d+)',text):
            if ref not in allowed_references: raise ExplanationError('Unknown reference in explanation.')
        # Reject unverified numerical claims entirely outside extractive findings.
        clean=re.sub(r'demo-(?:v\d+|evidence-\d+)', '', text)
        if re.search(r'\d',clean):
            raise ExplanationError('Numerical narrative assertions are not supported; use verified tool results.')
    if not any('synthetic' in x.lower() and 'geometry' in x.lower() for x in narrative.limitations):
        raise ExplanationError('Required synthetic-data and geometry limitation is missing.')
    return narrative
